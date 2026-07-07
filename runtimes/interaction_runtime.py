"""
交互 Runtime — 意图理解、音频、情绪、语音交互。

当 Router 关键词直接命中 interaction 类动作时，直接用 InteractionSkill 执行。
否则走 IntentAgent(LLM) → 判断意图。

注意：纯对话（chat）由机器人本地语音系统处理，Agent 层不重复实现。
"""
import logging

from shared.message import RuntimeMessage, RuntimeResult
from agents.intent_agent import IntentAgent
from skills.interaction_skill import InteractionSkill

logger = logging.getLogger(__name__)


class InteractionRuntime:
    """交互 Runtime。

    两条路径:
      1. 直接执行: Router 已识别出具体动作 (play_audio/switch_emotion/voice_wakeup)
         → 直接用 InteractionSkill 执行
      2. LLM 理解: Router 无法判断 → IntentAgent→LLM 识别意图
         → interaction → InteractionSkill
         → motion/navigation → 返回给 Gateway 做二次路由
         → chat → 提示走机器人本地语音通道
    """

    def __init__(self, intent_agent: IntentAgent,
                 interaction_skill: InteractionSkill):
        self._intent_agent = intent_agent
        self._skill = interaction_skill

    def handle(self, message: RuntimeMessage) -> RuntimeResult:
        # 路径 1: Router 已预填了 action（关键词命中）
        direct_action = message.context.get("action", "")
        direct_params = message.context.get("params", {})

        if direct_action in ("play_audio", "switch_emotion", "voice_wakeup",
                              "volume", "led"):
            logger.info(f"InteractionRuntime: 直接执行 {direct_action}")
            return self._skill.execute("interaction", {
                "action": direct_action,
                **direct_params,
            })

        # 路径 2: LLM 理解
        result = self._intent_agent.handle(message)
        intent = result.intent
        data = result.data
        action = data.get("action", "")
        params = data.get("params", {})

        logger.info(f"InteractionRuntime: LLM 理解 → intent={intent} action={action}")

        if intent == "chat" or intent == "unknown":
            # 纯对话由机器人本地语音系统处理，Agent 层不参与
            return RuntimeResult(
                intent="chat",
                reply="对话功能由机器人本地语音系统处理",
            )
        elif intent == "interaction":
            return self._skill.execute("interaction", {
                "action": action,
                **params,
            })
        elif intent in ("motion", "navigation"):
            # 返回给 Gateway 做二次路由
            return RuntimeResult(intent=intent, data=data)
        else:
            return RuntimeResult(
                intent="unknown",
                reply="无法理解该指令，请尝试关键词命令。对话请使用机器人本地语音交互。",
            )
