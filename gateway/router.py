"""
路由策略 — 关键词匹配 → 选 Runtime。

真实能力来源: Bridge API 协议文档 v0.3。

路由优先级:
  1. 关键词命中 → Motion / Navigation，预填 action+params
  2. 未命中 → Interaction Runtime，由 IntentAgent(LLM) 判断
"""

import logging

from shared.message import RuntimeMessage

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 关键词 → (目标Runtime, action, params)
# ---------------------------------------------------------------------------
DIRECT_ROUTES = [
    # ====== 解除急停（优先） ======
    ("解除急停", ("motion", "release_estop", {})),
    ("退出急停", ("motion", "release_estop", {})),
    ("取消急停", ("motion", "release_estop", {})),

    # ====== 急停 ======
    ("急停",   ("motion", "stop", {})),
    ("停",     ("motion", "stop", {})),
    ("停下",   ("motion", "stop", {})),
    ("站住",   ("motion", "stop", {})),
    ("别动",   ("motion", "stop", {})),

    # ====== 动作 (cqm1/cqm2/cqm3) ======
    ("动作1",  ("motion", "motion", {"name": "cqm1"})),
    ("动作2",  ("motion", "motion", {"name": "cqm2"})),
    ("动作3",  ("motion", "motion", {"name": "cqm3"})),
    ("cqm1",   ("motion", "motion", {"name": "cqm1"})),
    ("cqm2",   ("motion", "motion", {"name": "cqm2"})),
    ("cqm3",   ("motion", "motion", {"name": "cqm3"})),
    ("做动作", ("motion", "motion", {"name": "cqm1"})),

    # ====== 移动 ======
    ("前进",   ("motion", "move", {"lx": 0.5})),
    ("往前走", ("motion", "move", {"lx": 0.5})),
    ("后退",   ("motion", "move", {"lx": -0.3})),
    ("往后走", ("motion", "move", {"lx": -0.3})),
    ("左转",   ("motion", "move", {"az": 0.5})),
    ("向左转", ("motion", "move", {"az": 0.5})),
    ("右转",   ("motion", "move", {"az": -0.5})),
    ("向右转", ("motion", "move", {"az": -0.5})),
    ("走",     ("motion", "move", {"lx": 0.3})),

    # ====== 运动模式 ======
    ("站立",   ("motion", "loco_mode", {"mode": "stand"})),
    ("趴下",   ("motion", "loco_mode", {"mode": "still"})),
    ("起身",   ("motion", "loco_mode", {"mode": "getup"})),
    ("小跑",   ("motion", "loco_mode", {"mode": "ppowalk"})),

    # ====== 避障 ======
    ("开避障", ("motion", "oas", {"enable": True})),
    ("关避障", ("motion", "oas", {"enable": False})),

    # ====== 音频（通过 Interaction Runtime 的 InteractionSkill） ======
    ("随机播",    ("interaction", "play_audio", {})),
    ("播放音频",  ("interaction", "play_audio", {})),
    ("播sch1",    ("interaction", "play_audio", {"name": "sch1"})),
    ("播sch2",    ("interaction", "play_audio", {"name": "sch2"})),
    ("播pth1",    ("interaction", "play_audio", {"name": "pth1"})),
    ("四川话",    ("interaction", "play_audio", {"name": "sch1"})),
    ("普通话",    ("interaction", "play_audio", {"name": "pth1"})),

    # ====== 情绪 ======
    ("换个表情",  ("interaction", "switch_emotion", {})),
    ("切换情绪",  ("interaction", "switch_emotion", {})),
    ("换个心情",  ("interaction", "switch_emotion", {})),

    # ====== 语音交互 ======
    ("开语音唤醒",   ("interaction", "voice_wakeup", {"enable": True})),
    ("关语音唤醒",   ("interaction", "voice_wakeup", {"enable": False})),
    ("打开语音交互", ("interaction", "voice_wakeup", {"enable": True})),
    ("关闭语音交互", ("interaction", "voice_wakeup", {"enable": False})),

    # ====== 设置 ======
    ("音量",       ("interaction", "volume", {})),
    ("设置音量",   ("interaction", "volume", {})),
    ("氛围灯",     ("interaction", "led", {})),
    ("灯光",       ("interaction", "led", {})),

    # ====== 导航 ======
    ("导航",   ("navigation", "navigate", {})),
    ("带我去", ("navigation", "navigate", {})),
    ("前往",   ("navigation", "navigate", {})),
    ("去",     ("navigation", "navigate", {})),
]


class Router:
    """Router：输入文本 → 目标 Runtime + context。

    最大匹配原则：长关键词优先（"解除急停" > "急停" > "停"）。
    """

    def route(self, message: RuntimeMessage) -> str:
        text = message.text

        # 找最长匹配
        best_match = None
        best_len = 0
        for keyword, (runtime, action, params) in DIRECT_ROUTES:
            if keyword in text and len(keyword) > best_len:
                best_match = (keyword, runtime, action, params)
                best_len = len(keyword)

        if best_match:
            keyword, runtime, action, params = best_match
            message.context["action"] = action
            message.context["params"] = params
            logger.info(f"Router: 「{text}」→ {runtime} "
                        f"(关键词:「{keyword}」 action={action})")
            return runtime

        logger.info(f"Router: 「{text}」→ interaction (LLM 理解)")
        return "interaction"
