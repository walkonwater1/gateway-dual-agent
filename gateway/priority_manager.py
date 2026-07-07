"""
优先级管理器 — 请求优先级管理。

对应设计文档 gateway/priority_manager.py。

优先级层级（从高到低）:
    emergency > high > normal > low

    emergency: 急停、安全事件
    high:      遥操接管、运动安全
    normal:    导航、普通交互
    low:       后台任务

职责:
  - 为消息分配/调整优先级
  - 判断新请求是否可以抢占当前任务
  - 与 Router 协作：将特定关键词自动提升为 emergency
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class Priority(str, Enum):
    """优先级枚举。"""
    EMERGENCY = "emergency"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


# 优先级数值（越小越紧急）
PRIORITY_ORDER: dict[str, int] = {
    Priority.EMERGENCY: 0,
    Priority.HIGH: 1,
    Priority.NORMAL: 2,
    Priority.LOW: 3,
}


@dataclass
class PriorityDecision:
    """优先级判断结果。"""
    allowed: bool            # 是否允许执行
    action: str = "proceed"  # proceed / preempt / queue / reject
    reason: str = ""


class PriorityManager:
    """优先级管理器。

    用法:
        pm = PriorityManager()
        can_run = pm.can_preempt("emergency", "normal")  # True
        decision = pm.resolve("emergency", "normal")      # action="preempt"
    """

    # 当前活跃请求的优先级（按 session 分）
    def __init__(self):
        self._active_priority: dict[str, str] = {}  # session_id → priority

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    @staticmethod
    def order(priority: str) -> int:
        """返回优先级的数值（越小越紧急）。"""
        return PRIORITY_ORDER.get(priority, 2)

    @staticmethod
    def can_preempt(new_priority: str, current_priority: str) -> bool:
        """新请求优先级是否高于当前任务，可以抢占。"""
        return PriorityManager.order(new_priority) < PriorityManager.order(current_priority)

    @staticmethod
    def is_higher_than(priority: str, other: str) -> bool:
        """priority 是否比 other 更紧急。"""
        return PriorityManager.order(priority) < PriorityManager.order(other)

    # ------------------------------------------------------------------
    # 活跃状态
    # ------------------------------------------------------------------

    def set_active(self, session_id: str, priority: str):
        """记录当前活跃请求的优先级。"""
        self._active_priority[session_id] = priority

    def clear_active(self, session_id: str):
        """清除活跃请求。"""
        self._active_priority.pop(session_id, None)

    def get_active(self, session_id: str) -> str:
        """获取当前活跃请求的优先级。"""
        return self._active_priority.get(session_id, Priority.NORMAL)

    # ------------------------------------------------------------------
    # 冲突判断
    # ------------------------------------------------------------------

    def resolve(self, new_priority: str,
                current_priority: str | None = None) -> PriorityDecision:
        """判断新请求与当前任务的关系。

        Args:
            new_priority: 新请求的优先级
            current_priority: 当前活跃任务的优先级（None 表示无活跃任务）

        Returns:
            PriorityDecision
        """
        if current_priority is None:
            return PriorityDecision(allowed=True, action="proceed",
                                    reason="无活跃任务")

        if self.can_preempt(new_priority, current_priority):
            return PriorityDecision(
                allowed=True, action="preempt",
                reason=f"{new_priority} > {current_priority}，抢占当前任务",
            )

        if new_priority == current_priority:
            return PriorityDecision(
                allowed=True, action="proceed",
                reason=f"同级优先级 {new_priority}",
            )

        # 新请求优先级更低 → 排队或拒绝
        return PriorityDecision(
            allowed=True, action="queue",
            reason=f"{new_priority} < {current_priority}，排队等待",
        )
