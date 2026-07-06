"""
运动 Runtime — 处理所有需要机器人身体执行的任务。

对应设计文档 runtimes/motion_runtime/。
"""

import logging

from shared.message import RuntimeMessage, RuntimeResult
from agents.motion_agent import MotionAgent

logger = logging.getLogger(__name__)


class MotionRuntime:
    """运动 Runtime：动作执行、移动控制、急停、运动模式切换。

    接收 Gateway 路由过来的运动类请求（已解析好的意图），
    交由 MotionAgent 决策后执行。
    """

    def __init__(self, motion_agent: MotionAgent):
        self._motion_agent = motion_agent

    def handle(self, message: RuntimeMessage) -> RuntimeResult:
        logger.info(f"MotionRuntime: 收到消息 context={message.context}")
        return self._motion_agent.handle(message)
