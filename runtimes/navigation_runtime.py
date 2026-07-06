"""
导航 Runtime — 处理导航、建图、定位相关任务。

对应设计文档 runtimes/navigation_runtime/。
当前为占位，待 Bridge 导航接口完善后对接。
"""

import logging

from shared.message import RuntimeMessage, RuntimeResult
from agents.navigation_agent import NavigationAgent

logger = logging.getLogger(__name__)


class NavigationRuntime:
    """导航 Runtime：路径规划、导航执行、地图管理。"""

    def __init__(self, nav_agent: NavigationAgent):
        self._nav_agent = nav_agent

    def handle(self, message: RuntimeMessage) -> RuntimeResult:
        logger.info(f"NavigationRuntime: 收到消息 context={message.context}")
        return self._nav_agent.handle(message)
