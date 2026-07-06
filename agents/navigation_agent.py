"""
导航 Agent — 处理导航请求。

对应设计文档 agents/navigation_agents/。
当前为占位，后续对接完整导航能力。
"""

import logging

from shared.base import BaseAgent
from shared.message import RuntimeMessage, RuntimeResult
from skills.navigation_skill import NavigationSkill

logger = logging.getLogger(__name__)


class NavigationAgent(BaseAgent):
    """处理导航请求。"""

    def __init__(self, skill: NavigationSkill):
        self._skill = skill

    def handle(self, message: RuntimeMessage) -> RuntimeResult:
        params = message.context.get("params", {})
        target = params.get("target", "未知目标")
        logger.info(f"NavigationAgent: 目标={target}")
        return self._skill.execute("navigation", params)
