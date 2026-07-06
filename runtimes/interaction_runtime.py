"""
交互 Runtime — 对话、意图理解、音频、情绪、语音交互。

当 Router 关键词直接命中 interaction 类动作时，直接用 InteractionSkill 执行。
否则走 IntentAgent(LLM) → 判断意图。
"""

import logging

from shared.message import RuntimeMessage, RuntimeResult
from agents.dialogue_agent import DialogueAgent
from agents.intent_agent import IntentAgent
from skills.interaction_skill import InteractionSkill

logger = logging.getLogger(__name__)


class InteractionRuntime:
    """交互 Runtime。

    两条路径:
      1. 直接执行: Router 已识别出具体动作 (play_audio/switch_emotion/voice_wakeup)
         → 直接用 InteractionSkill 执行
      2. LLM 理解: Router 无法判断 → IntentAgent→LLM 识别意图
         → chat → DialogueAgent
         → interaction → InteractionSkill
         → motion/navigation → 返回给 Gateway 做二次路由
    """

    def __init__(self, intent_agent: IntentAgent, dialogue_agent: DialogueAgent,
                 interaction_skill: InteractionSkill):
        self._intent_agent = intent_agent
        self._dialogue_agent = dialogue_agent
        self._skill = interaction_skill

    def handle(self, message: RuntimeMessage) -> RuntimeResult:
        # 路径 1: Router 已预填了 action（关键词命中）
        direct_action = message.context.get("action", "")
        direct_params = message.context.get("params", {})

        if direct_action in ("play_audio", "switch_emotion", "voice_wakeup",
                              "volume", "led", "release_estop"):
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
            return self._dialogue_agent.handle(message)
        elif intent == "interaction":
            return self._skill.execute("interaction", {
                "action": action,
                **params,
            })
        elif intent in ("motion", "navigation"):
            # 返回给 Gateway 做二次路由
            return RuntimeResult(intent=intent, data=data)
        else:
            return self._dialogue_agent.handle(message)
