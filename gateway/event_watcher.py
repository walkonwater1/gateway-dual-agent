"""
EventWatcher — MQTT 日志轮询 + 模式检测 + 事件生成。

对应设计: Gateway 的「喂日志」输入源 —— 机器人每秒上报状态到 MQTT，
EventWatcher 解析这些状态消息，按规则检测模式（低电量、过热、心跳丢失），
生成结构化事件喂给 Gateway.handle_event()。

架构:
    MQTT info/often → RobotMqttClient._on_message()
                        → EventWatcher.on_mqtt_message()
                          → 解析 JSON + 更新状态 + 规则匹配
                            → Gateway.handle_event(event_dict)
                              → RuntimeRouter → Runtime → Agent → Skill → MQTT

用法:
    watcher = EventWatcher(gateway, "config/event_rules.yaml")
    mqtt.on_status(watcher.on_mqtt_message)   # 注册 MQTT 回调
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

import yaml

from capabilities.mqtt_client import LOCO_MODE_NAMES

logger = logging.getLogger(__name__)


# ============================================================================
# MQTT 状态指令 ID
# ============================================================================

CMD_BATTERY_STATUS = 4002
CMD_LOCO_MODE_STATUS = 4004
CMD_HOST_STATUS = 4006
CMD_MOTOR_STATUS = 4007
CMD_DRIVER_STATUS = 4008
CMD_HEARTBEAT = 8000


class EventWatcher:
    """MQTT 状态监听 + 规则引擎。

    - 解析 info/often 的机器人状态消息
    - 维护内部状态快照（电池/电机温度/CPU/运动模式）
    - 按 config/event_rules.yaml 规则检测模式
    - 触发规则时生成事件，通过 Gateway.handle_event() 分发

    线程安全：on_mqtt_message 由 paho 网络线程回调，内部状态操作加锁。
    """

    def __init__(self, gateway, rules_path: str | None = None):
        """
        Args:
            gateway: Gateway 实例（需有 handle_event 方法）
            rules_path: event_rules.yaml 路径，为 None 则不加载规则
        """
        self._gateway = gateway
        self._rules: list[dict] = []
        self._state: dict[str, Any] = {}       # 当前状态快照
        self._last_trigger: dict[str, float] = {}  # {rule_name: timestamp}
        self._event_count: int = 0

        if rules_path:
            self.load_rules(rules_path)

    # ------------------------------------------------------------------
    # 规则加载
    # ------------------------------------------------------------------

    def load_rules(self, rules_path: str):
        """加载 event_rules.yaml。"""
        if not os.path.exists(rules_path):
            logger.warning(f"EventWatcher: 规则文件不存在: {rules_path}")
            return

        with open(rules_path, "r") as f:
            data = yaml.safe_load(f) or {}

        self._rules = data.get("rules", [])
        enabled = sum(1 for r in self._rules if r.get("enabled", True))
        logger.info(f"EventWatcher: 加载 {len(self._rules)} 条规则 ({enabled} 启用)")

    # ------------------------------------------------------------------
    # MQTT 回调入口（由 paho 网络线程调用）
    # ------------------------------------------------------------------

    def on_mqtt_message(self, topic: str, payload: bytes):
        """MQTT 消息回调 — 解析 + 更新状态 + 检查规则。

        Args:
            topic: MQTT 主题（info/often, eir/basic_heartbeat_callback）
            payload: 原始 JSON bytes
        """
        try:
            msg = json.loads(payload)
        except json.JSONDecodeError:
            logger.debug(f"EventWatcher: 无法解析消息 {payload[:100]}")
            return

        command = msg.get("command")
        command_data = msg.get("commandData")

        if command is None:
            return

        # Step 1: 更新内部状态
        self._update_state(topic, command, command_data)

        # Step 2: 检查所有规则
        for rule in self._rules:
            if not rule.get("enabled", True):
                continue
            self._check_rule(rule, topic, command, command_data)

    # ------------------------------------------------------------------
    # 状态更新
    # ------------------------------------------------------------------

    def _update_state(self, topic: str, command: int, command_data):
        """解析 commandData 并更新内部状态。"""
        if topic == "info/often":
            if command == CMD_BATTERY_STATUS and isinstance(command_data, list):
                if len(command_data) >= 2:
                    self._state["battery"] = float(command_data[1])
            elif command == CMD_HOST_STATUS and isinstance(command_data, list):
                if len(command_data) >= 2:
                    self._state["cpu_temp"] = float(command_data[0])
                    self._state["cpu_usage"] = float(command_data[1])
            elif command == CMD_MOTOR_STATUS and isinstance(command_data, list):
                self._state["motor_temps"] = [float(t) for t in command_data]
            elif command == CMD_DRIVER_STATUS and isinstance(command_data, list):
                self._state["driver_temps"] = [float(t) for t in command_data]
            elif command == CMD_LOCO_MODE_STATUS:
                self._state["loco_mode"] = int(command_data)
                self._state["loco_mode_name"] = LOCO_MODE_NAMES.get(
                    int(command_data), f"unknown({command_data})"
                )
        elif topic == "eir/basic_heartbeat_callback":
            self._state["last_heartbeat"] = time.time()

    # ------------------------------------------------------------------
    # 规则检查
    # ------------------------------------------------------------------

    def _check_rule(self, rule: dict, topic: str, command: int, command_data):
        """检查单条规则是否触发。"""
        trigger = rule.get("trigger", {})
        condition = rule.get("condition", {})
        action = rule.get("action", {})

        # 1. 匹配 topic 和 command
        if trigger.get("topic") != topic:
            return
        if trigger.get("command") != command:
            return

        # 2. 提取字段值
        value = self._extract_field(command_data, trigger.get("field", "value"))
        if value is None:
            return

        # 3. 比较条件
        operator = condition.get("operator", "lt")
        threshold = condition.get("value", 0)
        if not self._compare(value, operator, threshold):
            return

        # 4. 去抖检查
        rule_name = rule["name"]
        now = time.time()
        debounce = rule.get("debounce", 60)
        if rule_name in self._last_trigger:
            if now - self._last_trigger[rule_name] < debounce:
                return

        # 5. 触发
        self._last_trigger[rule_name] = now
        self._event_count += 1
        self._fire(rule, value)

    def _extract_field(self, command_data, field: str) -> float | None:
        """从 commandData 中提取字段值。

        支持:
          - "value"  → commandData 本身（int/float）
          - "soc"    → commandData[1]（电池百分比）
          - "max"    → max(commandData)
          - "min"    → min(commandData)
          - "index:N" → commandData[N]
        """
        if field == "value":
            if isinstance(command_data, (int, float)):
                return float(command_data)
            return None

        if field == "soc":
            if isinstance(command_data, list) and len(command_data) >= 2:
                return float(command_data[1])
            return None

        if field == "max":
            if isinstance(command_data, list) and command_data:
                return max(float(v) for v in command_data)
            return None

        if field == "min":
            if isinstance(command_data, list) and command_data:
                return min(float(v) for v in command_data)
            return None

        if field.startswith("index:"):
            try:
                idx = int(field.split(":")[1])
                if isinstance(command_data, list) and len(command_data) > idx:
                    return float(command_data[idx])
            except (ValueError, IndexError):
                pass
            return None

        logger.warning(f"EventWatcher: 未知 field 类型: {field}")
        return None

    @staticmethod
    def _compare(value: float, operator: str, threshold: float) -> bool:
        """比较操作。"""
        if operator == "lt":
            return value < threshold
        if operator == "gt":
            return value > threshold
        if operator == "eq":
            return value == threshold
        if operator == "ne":
            return value != threshold
        if operator == "le":
            return value <= threshold
        if operator == "ge":
            return value >= threshold
        logger.warning(f"EventWatcher: 未知 operator: {operator}")
        return False

    # ------------------------------------------------------------------
    # 触发动作
    # ------------------------------------------------------------------

    def _fire(self, rule: dict, matched_value: float):
        """规则触发，生成事件并喂给 Gateway。"""
        action = rule.get("action", {})
        target = action.get("target", "interaction")
        context = action.get("context", {})
        priority = action.get("priority", "high")

        event = {
            "type": rule["name"],
            "description": rule.get("description", ""),
            "matched_value": matched_value,
            "target": target,
            "intent": target,          # Gateway 用 intent 判断路由
            "action": context.get("action", ""),
            "params": context.get("params", {}),
            "priority": priority,
            "source": "event_watcher",
        }

        logger.info(
            f"EventWatcher: 触发规则「{rule['name']}」"
            f" (value={matched_value}) → {target}"
            f" / {context.get('action', '?')}"
            f" [事件 #{self._event_count}]"
        )

        try:
            result = self._gateway.handle_event(event, session_id="system")
            logger.info(
                f"EventWatcher: Gateway 返回 intent={result.intent}"
                f" reply={result.reply[:80] if result.reply else '(无)'}"
            )
        except Exception as e:
            logger.error(f"EventWatcher: Gateway.handle_event 异常: {e}")

    # ------------------------------------------------------------------
    # 查询接口
    # ------------------------------------------------------------------

    @property
    def state(self) -> dict:
        """返回当前机器人状态快照。"""
        return dict(self._state)

    @property
    def rule_count(self) -> int:
        return len(self._rules)

    @property
    def event_count(self) -> int:
        return self._event_count

    @property
    def enabled_rule_count(self) -> int:
        return sum(1 for r in self._rules if r.get("enabled", True))

    def get_state_summary(self) -> str:
        """人类可读的状态摘要。"""
        parts = []
        if "battery" in self._state:
            parts.append(f"电池: {self._state['battery']:.0f}%")
        if "cpu_temp" in self._state:
            parts.append(f"CPU: {self._state['cpu_temp']:.0f}°C")
        if "motor_temps" in self._state:
            temps = self._state["motor_temps"]
            parts.append(f"电机: {min(temps):.0f}~{max(temps):.0f}°C")
        if "loco_mode_name" in self._state:
            parts.append(f"模式: {self._state['loco_mode_name']}")
        return " | ".join(parts) if parts else "(无状态数据)"
