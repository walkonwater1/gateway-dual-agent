"""
Agent Runtime — 启动入口。

对应设计文档 main.py + apps/robot_app.py。

用法:
    python main.py               # 交互模式（自由文本）
    python main.py --demo        # 演示模式（菜单选择）

架构:
    用户输入
      → Gateway (路由中枢 + 治理)
        → InputAdapter (多模态归一化)
        → TraceLogger (链路追踪)
        → SessionRouter (会话隔离)
        → PriorityManager (优先级)
        → SafetyGate (安全过滤)
        → Router (YAML 规则匹配)
        → ConflictResolver (冲突检测)
        → RuntimeRouter (分发/二次路由)
          → Interaction Runtime (意图理解 → MQTT 指令)
          → Motion Runtime     (动作 / 移动 / 急停)
          → Navigation Runtime (导航 / 建图 / 定位)
            → Agent  (决策：IntentAgent 调 LLM 做意图→MQTT映射)
              → Skill (执行 → MQTT → Bridge → 机器人)

各层职责:
    Gateway:  接收、标准化、路由、治理、安全、Trace
    Runtime:  编排所属 Agent
    Agent:    决策（调 LLM 做意图→MQTT映射）
    Skill:    执行（发 MQTT 指令）
    🤖 对话：机器人本地 SDK 内腾讯云端大模型处理（Agent 层不重复实现）
"""

import logging
import os
import sys

import yaml

# ---------------------------------------------------------------------------
# 依赖
# ---------------------------------------------------------------------------
from openai import OpenAI

from capabilities.mqtt_client import RobotMqttClient

# Skills
from skills.motion_skill import MotionSkill
from skills.navigation_skill import NavigationSkill
from skills.interaction_skill import InteractionSkill

# Agents
from agents.intent_agent import IntentAgent
from agents.motion_agent import MotionAgent
from agents.navigation_agent import NavigationAgent

# Runtimes
from runtimes.motion_runtime import MotionRuntime
from runtimes.interaction_runtime import InteractionRuntime
from runtimes.navigation_runtime import NavigationRuntime

# Gateway & modules
from gateway.gateway import Gateway
from gateway.route_policy import RoutePolicy
from gateway.input_adapter import InputAdapter
from gateway.trace_logger import TraceLogger
from gateway.session_router import SessionRouter
from gateway.priority_manager import PriorityManager
from gateway.safety_gate import SafetyGate
from gateway.event_bus import EventBus
from gateway.conflict_resolver import ConflictResolver
from gateway.result_aggregator import ResultAggregator

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def load_config():
    path = os.path.join(BASE_DIR, "config.local.yaml")
    if not os.path.exists(path):
        path = os.path.join(BASE_DIR, "config.example.yaml")
    with open(path, "r") as f:
        return yaml.safe_load(f)


def load_yaml(path: str) -> dict:
    """加载 YAML 文件，不存在则返回空 dict。"""
    full_path = os.path.join(BASE_DIR, path)
    if not os.path.exists(full_path):
        return {}
    with open(full_path, "r") as f:
        return yaml.safe_load(f) or {}


# ---------------------------------------------------------------------------
# 组装（依赖注入）
# ---------------------------------------------------------------------------
def build_app(cfg: dict):
    """手动组装整个应用 — 相当于轻量 DI 容器。"""

    # --- 能力层 ---
    mqtt = RobotMqttClient(cfg["mqtt"]["host"], cfg["mqtt"]["port"])

    # --- LLM ---
    llm_cfg = cfg["llm"]
    llm = OpenAI(base_url=llm_cfg["base_url"], api_key=llm_cfg["api_key"])
    model = llm_cfg.get("model", "qwen2.5:0.5b")

    # --- Skills ---
    motion_skill = MotionSkill(mqtt)
    nav_skill = NavigationSkill(mqtt)
    interaction_skill = InteractionSkill(mqtt)

    # --- Agents ---
    intent_agent = IntentAgent(llm, model, temperature=0.1)
    motion_agent = MotionAgent(motion_skill)
    nav_agent = NavigationAgent(nav_skill)

    # --- Runtimes ---
    interaction_rt = InteractionRuntime(intent_agent, interaction_skill)
    motion_rt = MotionRuntime(motion_agent)
    navigation_rt = NavigationRuntime(nav_agent)

    # --- Gateway 配置 ---
    gw_cfg = cfg.get("gateway", {})
    routes_yaml = gw_cfg.get("routes_yaml", "config/routes.yaml")
    modules_cfg = gw_cfg.get("modules", {})

    # --- 加载路由策略 ---
    route_policy = RoutePolicy()
    route_path = os.path.join(BASE_DIR, routes_yaml)
    if os.path.exists(route_path):
        route_policy.load(route_path)
    else:
        logging.getLogger("main").warning(
            f"路由配置文件不存在: {route_path}，使用默认路由"
        )

    # --- Gateway 模块（按配置开关） ---
    trace_logger = TraceLogger()

    session_router = None
    if modules_cfg.get("session_router", True):
        session_router = SessionRouter()

    priority_manager = None
    if modules_cfg.get("priority_manager", True):
        priority_manager = PriorityManager()

    safety_gate = None
    if modules_cfg.get("safety_gate", True):
        safety_gate = SafetyGate()

    conflict_resolver = None
    if modules_cfg.get("conflict_resolver", False):
        conflict_resolver = ConflictResolver(
            priority_manager=priority_manager,
        )

    event_bus = EventBus(enabled=modules_cfg.get("event_bus", False))
    result_aggregator = ResultAggregator(
        enabled=modules_cfg.get("result_aggregator", False),
    )

    # --- Gateway ---
    gateway = Gateway(
        interaction_runtime=interaction_rt,
        motion_runtime=motion_rt,
        navigation_runtime=navigation_rt,
        route_policy=route_policy,
        input_adapter=InputAdapter(),
        trace_logger=trace_logger,
        session_router=session_router,
        priority_manager=priority_manager,
        safety_gate=safety_gate,
        conflict_resolver=conflict_resolver,
        event_bus=event_bus,
        result_aggregator=result_aggregator,
    )

    return gateway, mqtt


# ============================================================================
# 演示菜单
# ============================================================================

# 每个菜单项: (显示名, 发送文本, 说明)
DEMO_MENU = [
    # --- 动作 ---
    ("🎯 动作 cqm1",       "cqm1",    "执行预设动作1"),
    ("🎯 动作 cqm2",       "cqm2",    "执行预设动作2"),
    ("🎯 动作 cqm3",       "cqm3",    "执行预设动作3"),
    # --- 移动 ---
    ("🚶 前进",            "前进",     "lx=0.5 向前移动"),
    ("🚶 后退",            "后退",     "lx=-0.3 向后移动"),
    ("🚶 左转",            "左转",     "az=0.5 左转"),
    ("🚶 右转",            "右转",     "az=-0.5 右转"),
    # --- 运动模式 ---
    ("🧍 站立",            "站立",     "切换到 Stand_JOF 模式"),
    ("🧎 趴下",            "趴下",     "切换到 Still 模式"),
    ("🆙 起身",            "起身",     "切换到 Getup 模式"),
    # --- 急停 ---
    ("🛑 急停",            "停",       "紧急停止"),
    ("🟢 解除急停",        "解除急停",  "退出急停状态"),
    # --- 音频 ---
    ("🔊 随机播放音频",    "随机播放",  "随机选一首播放"),
    ("🔊 四川话音频",      "四川话",    "播放 sch1"),
    ("🔊 普通话音频",      "普通话",    "播放 pth1"),
    # --- 交互 ---
    ("😊 换个表情",        "换个表情",  "随机切换情绪"),
    ("🎤 开语音唤醒",      "开语音唤醒", "开启语音交互"),
    ("🎤 关语音唤醒",      "关语音唤醒", "关闭语音交互"),
    # --- 设置 ---
    ("🔉 音量 80",         "音量80",    "设置音量为80"),
    ("💡 氛围灯",          "氛围灯",    "设置氛围灯"),
    # --- 导航 ---
    ("🗺️  导航: 去充电站", "带我去充电站", "导航任务下发"),
]


def run_demo_mode(gateway: Gateway):
    """演示模式：菜单选择 + 显示完整调用链路。"""

    print("\n" + "=" * 60)
    print("  🤖 Agent Runtime — 演示模式")
    print("=" * 60)
    print("  说明: 输入菜单编号 (1/2/3...)，或直接打字进入自由模式")
    print("  输入 'menu' 返回菜单 | 'q' 退出")
    print("=" * 60)

    while True:
        # 打印菜单
        print()
        col_width = 28
        for i, (label, _, desc) in enumerate(DEMO_MENU):
            num = f"{i+1:2d}"
            item = f"{num}. {label}"
            # 中文占 2 字符宽，粗略补偿
            visual_len = len(item) + sum(1 for c in item if '一' <= c <= '鿿')
            pad = max(2, col_width - visual_len % col_width)
            end = "\n" if (i + 1) % 2 == 0 else ""
            print(f"  {item}{' ' * pad}{desc:20s}", end=end)
        if len(DEMO_MENU) % 2 != 0:
            print()

        # 用户选择
        print()
        choice = input("  🎮 请选择 (1-{} / 打字 / q): ".format(len(DEMO_MENU))).strip()

        if not choice:
            continue
        if choice.lower() in ("q", "quit", "exit"):
            print("\n  再见！👋")
            break
        if choice.lower() == "menu":
            continue

        # 尝试解析为菜单编号
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(DEMO_MENU):
                label, text, desc = DEMO_MENU[idx]
                print(f"\n  ══════════════════════════════════════")
                print(f"  已选: {label}")
                print(f"  文本: 「{text}」→ Gateway.handle_text()")
                print(f"  ══════════════════════════════════════\n")
            else:
                print(f"  编号超出范围 (1-{len(DEMO_MENU)})")
                continue
        except ValueError:
            # 不是数字，作为自由文本处理
            text = choice
            print(f"\n  ── 自由文本: 「{text}」──\n")

        # 执行 — 统一通过 Gateway 入口
        result = gateway.handle_text(text)
        if result.reply:
            print(f"  🤖 回复: {result.reply}")
        if result.error:
            print(f"  ⚠️  错误: {result.error}")
        if result.intent and result.intent not in ("chat", "unknown", "safety_blocked"):
            print(f"  📋 意图: {result.intent} | 数据: {result.data}")
        if result.trace_id:
            print(f"  🔍 trace: {result.trace_id[:8]}")


def run_interactive_mode(gateway: Gateway):
    """交互模式：自由文本输入。"""

    print("\n" + "=" * 60)
    print("  🤖 Agent Runtime — 交互模式")
    print("=" * 60)
    print("  直接输入指令或对话: cqm1 | 前进 | 急停 | 四川话 | 换个表情 | 你好 ...")
    print("  输入 /menu 进入菜单模式 | /trace 查看最近链路 | /q 退出")
    print("=" * 60 + "\n")

    while True:
        text = input("你: ").strip()
        if not text:
            continue
        if text.lower() in ("/q", "/quit", "/exit"):
            print("再见！👋")
            break
        if text.lower() == "/menu":
            return "menu"  # 切换到菜单模式
        if text.lower() == "/trace":
            traces = gateway.trace_logger.get_recent_traces(5)
            if not traces:
                print("(暂无 Trace 记录)")
            for t in traces:
                print(f"  🔍 {t['trace_id'][:8]}: 「{t['input']}」"
                      f" → {len(t['events'])} events, {t.get('total_duration_ms', '?')}ms")
            print()
            continue

        result = gateway.handle_text(text)
        if result.reply:
            print(f"🤖: {result.reply}")
        if result.error:
            print(f"  ✗ {result.error}")
        print()


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------
def main():
    cfg = load_config()

    # 日志
    logging.basicConfig(
        level=cfg.get("log_level", "INFO"),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    logger = logging.getLogger("main")

    logger.info("正在启动 Agent Runtime...")
    gateway, mqtt = build_app(cfg)

    # 连接 MQTT
    if not mqtt.connect():
        logger.error("MQTT 连接失败，请检查机器人是否在线 (config.local.yaml → mqtt.host)")
        print("\n✗ MQTT 连接失败！请确认:")
        print(f"  机器人 IP: {cfg['mqtt']['host']}:{cfg['mqtt']['port']}")
        print(f"  mosquitto 是否在运行？Bridge 是否在运行？\n")
        sys.exit(1)

    mqtt_cfg = cfg["mqtt"]
    llm_cfg = cfg["llm"]

    print("\n" + "=" * 60)
    print("  🤖 Agent Runtime 已就绪")
    print("=" * 60)
    print(f"  MQTT  → {mqtt_cfg['host']}:{mqtt_cfg['port']}")
    print(f"  LLM   → {llm_cfg['model']} @ {llm_cfg['base_url']}")
    print(f"  Routes → {gateway._router._policy.pattern_count} 条路由规则")
    print("=" * 60)

    # 判断模式
    demo_mode = "--demo" in sys.argv

    try:
        if demo_mode:
            run_demo_mode(gateway)
        else:
            # 默认交互模式，支持 /menu 切换到菜单
            while True:
                result = run_interactive_mode(gateway)
                if result != "menu":
                    break
                # 切换到菜单模式
                run_demo_mode(gateway)
                break  # 菜单退出后结束
    except KeyboardInterrupt:
        print("\n中断退出")
    finally:
        mqtt.disconnect()


if __name__ == "__main__":
    main()
