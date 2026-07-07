"""
冲突仲裁器 — 跨 Runtime 跨任务冲突检测与仲裁。

对应设计文档 gateway/conflict_resolver.py。

典型冲突:
  1. 导航中用户要求跳舞 → 根据优先级判断
  2. 导航未结束又要求去另一个地点 → 取消旧任务，开始新任务
  3. Motion 正在执行动作时用户说停止 → 急停抢占
  4. Interaction 正在播报时用户打断 → 播报可被打断
  5. 遥操接管和自动任务冲突 → 遥操优先
  6. 多用户同时提出不同请求 → 按优先级排队

仲裁动作:
  - proceed: 继续（无冲突或新请求可并行）
  - preempt: 抢占（新请求优先级更高，中断当前任务）
  - queue: 排队（新请求优先级更低，等待当前任务完成）
  - refuse: 拒绝（当前任务不可中断且优先级更高）
  - confirm: 需要用户确认
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum

from gateway.priority_manager import PriorityManager, Priority

logger = logging.getLogger(__name__)


class ConflictAction(str, Enum):
    PROCEED = "proceed"
    PREEMPT = "preempt"
    QUEUE = "queue"
    REFUSE = "refuse"
    CONFIRM = "confirm"


@dataclass
class ConflictResult:
    """冲突仲裁结果。"""
    action: ConflictAction = ConflictAction.PROCEED
    reason: str = ""
    preempted_task: str | None = None  # 被抢占的任务名


class ConflictResolver:
    """跨 Runtime 冲突仲裁器。

    用法:
        resolver = ConflictResolver(priority_manager, session_router)
        result = resolver.check(new_msg, active_tasks)
        if result.action == ConflictAction.PREEMPT:
            # 中断当前任务，执行新请求
    """

    def __init__(self, enabled: bool = True,
                 priority_manager: PriorityManager | None = None):
        self._enabled = enabled
        self._pm = priority_manager or PriorityManager()

    @property
    def enabled(self) -> bool:
        return self._enabled

    def check(self,
              new_msg_priority: str,
              new_runtime: str,
              active_task: str | None = None,
              active_runtime: str | None = None,
              active_priority: str = Priority.NORMAL) -> ConflictResult:
        """检查新请求是否与当前活跃任务冲突。

        Args:
            new_msg_priority: 新请求的优先级
            new_runtime: 新请求的目标 Runtime
            active_task: 当前活跃任务名（None 表示无活跃任务）
            active_runtime: 当前活跃 Runtime
            active_priority: 当前活跃任务的优先级

        Returns:
            ConflictResult
        """
        if not self._enabled:
            return ConflictResult(action=ConflictAction.PROCEED,
                                  reason="冲突检测已关闭")

        # 无活跃任务 → 直接执行
        if active_task is None:
            return ConflictResult(action=ConflictAction.PROCEED,
                                  reason="无活跃任务")

        # 同 Runtime 且可并行 → 直接执行
        if new_runtime == active_runtime:
            return ConflictResult(action=ConflictAction.PROCEED,
                                  reason=f"同 Runtime {new_runtime}，可并行")

        # 新请求优先级更高 → 抢占
        if PriorityManager.can_preempt(new_msg_priority, active_priority):
            logger.info(
                f"ConflictResolver: {new_msg_priority} > {active_priority}，"
                f"抢占 {active_task}"
            )
            return ConflictResult(
                action=ConflictAction.PREEMPT,
                reason=f"优先级 {new_msg_priority} > {active_priority}，中断「{active_task}」",
                preempted_task=active_task,
            )

        # 新请求优先级更低 → 排队
        if PriorityManager.is_higher_than(active_priority, new_msg_priority):
            return ConflictResult(
                action=ConflictAction.QUEUE,
                reason=f"优先级 {new_msg_priority} < {active_priority}，等待「{active_task}」完成",
            )

        # 同级 → 按 Runtime 判断
        # Motion 和 Navigation 互斥（不能同时导航和跳舞）
        if {new_runtime, active_runtime} <= {"motion", "navigation"}:
            return ConflictResult(
                action=ConflictAction.CONFIRM,
                reason=f"{new_runtime} 与 {active_runtime} 互斥，需确认",
            )

        return ConflictResult(action=ConflictAction.PROCEED,
                              reason="无冲突")
