"""
对话 Agent — 纯聊天，不操作硬件。

对应设计文档 agents/interaction_agents/dialogue_agent/。
"""

import logging

from shared.base import BaseAgent
from shared.message import RuntimeMessage, RuntimeResult
from skills.dialogue_skill import DialogueSkill

logger = logging.getLogger(__name__)


class DialogueAgent(BaseAgent):
    """处理纯对话交互。"""

    def __init__(self, skill: DialogueSkill):
        self._skill = skill

    def handle(self, message: RuntimeMessage) -> RuntimeResult:
        text = message.text
        logger.info(f"DialogueAgent: 收到「{text}」")
        return self._skill.execute("chat", {"text": text})
