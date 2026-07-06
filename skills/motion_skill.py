"""
运动技能 — 基于机器人实际能力。

真实动作名: cqm1, cqm2, cqm3
运动模式: still(1), ready(2), getup(3), stand(10), ppowalk(20), ampwalk(21), qpwalk(22)
步态: normal(1), ramp(2), obstacle(3), stair(4), stair_ramp(5), stair_45(6)
"""

import logging

from capabilities.mqtt_client import RobotMqttClient, LOCO_MODE_NAMES
from shared.base import BaseSkill
from shared.message import RuntimeResult

logger = logging.getLogger(__name__)

# 可用动作
VALID_MOTIONS = ["cqm1", "cqm2", "cqm3"]


class MotionSkill(BaseSkill):
    """封装机器人已实现的运动 MQTT 指令。"""

    def __init__(self, mqtt: RobotMqttClient):
        self._mqtt = mqtt

    def execute(self, intent: str, params: dict) -> RuntimeResult:
        action = params.get("action", "")

        if action == "motion":
            return self._do_motion(params)
        elif action == "move":
            return self._do_move(params)
        elif action == "stop":
            return self._do_estop(enable=True)
        elif action == "release_estop":
            return self._do_estop(enable=False)
        elif action == "loco_mode":
            return self._do_loco_mode(params)
        elif action == "gait":
            return self._do_gait(params)
        elif action == "body_height":
            return self._do_body_height(params)
        elif action == "orientation":
            return self._do_orientation(params)
        elif action == "oas":
            return self._do_oas(params)
        elif action == "uwb":
            return self._do_uwb(params)
        else:
            return RuntimeResult(success=False, error=f"未知 action={action}")

    # ------------------------------------------------------------------
    # 动作 (1006): cqm1, cqm2, cqm3
    # ------------------------------------------------------------------
    def _do_motion(self, params: dict) -> RuntimeResult:
        name = params.get("name", "cqm1")
        if name not in VALID_MOTIONS:
            return RuntimeResult(
                success=False,
                error=f"不支持的动作: {name}，可用: {', '.join(VALID_MOTIONS)}"
            )
        uuid = self._mqtt.send_motion(name)
        logger.info(f"MotionSkill: 动作 {name}")
        return RuntimeResult(success=True, intent="motion",
                             data={"uuid": uuid}, reply=f"执行动作: {name}")

    # ------------------------------------------------------------------
    # 移动 (3001): [lx, ly, az, swing_height, gait_period]
    # ------------------------------------------------------------------
    def _do_move(self, params: dict) -> RuntimeResult:
        lx = params.get("lx", 0.0)
        ly = params.get("ly", 0.0)
        az = params.get("az", 0.0)
        uuid = self._mqtt.send_move(lx, ly, az)
        logger.info(f"MotionSkill: 移动 lx={lx} ly={ly} az={az}")
        direction = "前" if lx > 0 else ("后" if lx < 0 else "")
        direction += "左转" if az > 0 else ("右转" if az < 0 else "")
        return RuntimeResult(success=True, intent="move",
                             data={"uuid": uuid}, reply=f"移动中 ({direction or '停止'})")

    # ------------------------------------------------------------------
    # 急停 (9000): commandData="1"/"0"
    # ------------------------------------------------------------------
    def _do_estop(self, enable: bool) -> RuntimeResult:
        uuid = self._mqtt.send_estop(enable)
        if enable:
            logger.info(f"MotionSkill: 急停")
            return RuntimeResult(success=True, intent="stop",
                                 data={"uuid": uuid}, reply="已急停！")
        else:
            logger.info(f"MotionSkill: 解除急停")
            return RuntimeResult(success=True, intent="release_estop",
                                 data={"uuid": uuid}, reply="急停已解除")

    # ------------------------------------------------------------------
    # 运动模式 (1001)
    # ------------------------------------------------------------------
    def _do_loco_mode(self, params: dict) -> RuntimeResult:
        mode = params.get("mode", "ready")
        uuid = self._mqtt.send_loco_mode(mode)
        name = mode if isinstance(mode, str) else LOCO_MODE_NAMES.get(mode, str(mode))
        return RuntimeResult(success=True, intent="loco_mode",
                             data={"uuid": uuid}, reply=f"运动模式: {name}")

    # ------------------------------------------------------------------
    # 步态 (1002)
    # ------------------------------------------------------------------
    def _do_gait(self, params: dict) -> RuntimeResult:
        gait = params.get("mode", "normal")
        uuid = self._mqtt.send_gait(gait)
        name = gait if isinstance(gait, str) else str(gait)
        return RuntimeResult(success=True, intent="gait",
                             data={"uuid": uuid}, reply=f"步态: {name}")

    # ------------------------------------------------------------------
    # 身高 (1003)
    # ------------------------------------------------------------------
    def _do_body_height(self, params: dict) -> RuntimeResult:
        height = params.get("height", 0.5)
        uuid = self._mqtt.send_body_height(height)
        return RuntimeResult(success=True, intent="body_height",
                             data={"uuid": uuid}, reply=f"身高: {height}")

    # ------------------------------------------------------------------
    # 姿态 (1008)
    # ------------------------------------------------------------------
    def _do_orientation(self, params: dict) -> RuntimeResult:
        roll = params.get("roll", 0.0)
        pitch = params.get("pitch", 0.0)
        uuid = self._mqtt.send_body_orientation(roll, pitch)
        return RuntimeResult(success=True, intent="orientation",
                             data={"uuid": uuid}, reply=f"姿态 roll={roll} pitch={pitch}")

    # ------------------------------------------------------------------
    # 避障 (1004)
    # ------------------------------------------------------------------
    def _do_oas(self, params: dict) -> RuntimeResult:
        enable = params.get("enable", True)
        uuid = self._mqtt.send_oas(enable)
        return RuntimeResult(success=True, intent="oas",
                             data={"uuid": uuid},
                             reply="避障已开启" if enable else "停障模式")

    # ------------------------------------------------------------------
    # UWB (1005)
    # ------------------------------------------------------------------
    def _do_uwb(self, params: dict) -> RuntimeResult:
        enable = params.get("enable", True)
        uuid = self._mqtt.send_uwb(enable)
        return RuntimeResult(success=True, intent="uwb",
                             data={"uuid": uuid},
                             reply="UWB 跟随已开启" if enable else "UWB 跟随已关闭")
