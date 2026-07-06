"""
Agent Runtime — 启动入口。

对应设计文档 main.py + apps/robot_app.py。

用法:
    python main.py               # 交互模式（自由文本）
    python main.py --demo        # 演示模式（菜单选择）

架构:
    用户输入
      → Gateway (路由中枢)
        → Router (关键词 / LLM 路由)
          → Interaction Runtime (对话 / 意图理解)
          → Motion Runtime     (动作 / 移动 / 急停)
          → Navigation Runtime (导航 / 建图 / 定位)
            → Agent  (决策)
              → Skill (执行 → MQTT → Bridge → 机器人)

各层职责:
    Gateway:  接收、标准化、路由、二次分发
    Runtime:  编排所属 Agent
    Agent:    决策（调 LLM、选动作）
    Skill:    执行（发 MQTT 指令）
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
from skills.dialogue_skill import DialogueSkill
from skills.navigation_skill import NavigationSkill
from skills.interaction_skill import InteractionSkill

# Agents
from agents.intent_agent import IntentAgent
from agents.motion_agent import MotionAgent
from agents.dialogue_agent import DialogueAgent
from agents.navigation_agent import NavigationAgent

# Runtimes
from runtimes.motion_runtime import MotionRuntime
from runtimes.interaction_runtime import InteractionRuntime
from runtimes.navigation_runtime import NavigationRuntime

# Gateway
from gateway.gateway import Gateway

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
    dialogue_skill = DialogueSkill(llm, model)
    nav_skill = NavigationSkill(mqtt)
    interaction_skill = InteractionSkill(mqtt)

    # --- Agents ---
    intent_agent = IntentAgent(llm, model, temperature=0.1)
    motion_agent = MotionAgent(motion_skill)
    dialogue_agent = DialogueAgent(dialogue_skill)
    nav_agent = NavigationAgent(nav_skill)

    # --- Runtimes ---
    interaction_rt = InteractionRuntime(intent_agent, dialogue_agent, interaction_skill)
    motion_rt = MotionRuntime(motion_agent)
    navigation_rt = NavigationRuntime(nav_agent)

    # --- Gateway ---
    gateway = Gateway(interaction_rt, motion_rt, navigation_rt)

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
    # --- 对话 ---
    ("💬 对话: 你好",      "你好",      "LLM 对话测试"),
    ("💬 对话: 你是谁",    "你是谁",    "LLM 对话测试"),
    # --- 导航 ---
    ("🗺️  导航: 去充电站", "带我去充电站", "导航任务下发"),
]


def run_demo_mode(gateway: Gateway):
    """演示模式：菜单选择 + 显示完整调用链路。"""

    print("\n" + "=" * 60)
    print("  🤖 爱啾 Agent Runtime — 演示模式")
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
            pad = col_width - len(item) % col_width
            # 中文占 2 字符宽，粗略补偿
            visual_len = len(item) + sum(1 for c in item if '一' <= c <= '鿿' or '　' <= c <= '〿' or '＀' <= c <= '￯')
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
        if result.intent and result.intent not in ("chat", "unknown"):
            print(f"  📋 意图: {result.intent} | 数据: {result.data}")


def run_interactive_mode(gateway: Gateway):
    """交互模式：自由文本输入。"""

    print("\n" + "=" * 60)
    print("  🤖 爱啾 Agent Runtime — 交互模式")
    print("=" * 60)
    print("  直接输入指令或对话: cqm1 | 前进 | 急停 | 四川话 | 换个表情 | 你好 ...")
    print("  输入 /menu 进入菜单模式 | /q 退出")
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
    print("  🤖 爱啾 Agent Runtime 已就绪")
    print("=" * 60)
    print(f"  MQTT  → {mqtt_cfg['host']}:{mqtt_cfg['port']}")
    print(f"  LLM   → {llm_cfg['model']} @ {llm_cfg['base_url']}")
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
