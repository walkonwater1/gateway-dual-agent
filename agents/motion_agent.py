"""
运动 Agent — 将意图识别结果翻译为具体运动指令。

对应设计文档 agents/motion_agents/。
"""

import logging

from shared.base import BaseAgent
from shared.message import RuntimeMessage, RuntimeResult
from skills.motion_skill import MotionSkill

logger = logging.getLogger(__name__)


class MotionAgent(BaseAgent):
    """处理运动控制。

    接收已解析的意图（来自 IntentAgent 的 LLM 结果或 Router 的关键词命中），
    调用 MotionSkill 执行。
    """

    def __init__(self, skill: MotionSkill):
        self._skill = skill

    def handle(self, message: RuntimeMessage) -> RuntimeResult:
        action = message.context.get("action", "")
        params = message.context.get("params", {})
        logger.info(f"MotionAgent: action={action} params={params}")
        return self._skill.execute("motion", {"action": action, **params})
