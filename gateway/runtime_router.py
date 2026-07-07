"""
Runtime 路由器 — 管理 Runtime 注册、分发、二次路由。

对应设计文档 gateway/runtime_router.py。

职责:
  - 维护 Runtime 注册表（name → runtime instance）
  - 首次分发（dispatch）
  - 二次路由（reroute）：InteractionRuntime 返回 motion/navigation 意图时
    将 IntentAgent 的结果转发给对应的 Runtime

架构约束:
  - 跨 Runtime 通信必须走 Gateway（_reroute）
  - Runtime 间禁止直接互调
"""

from __future__ import annotations

import logging
from typing import Any

from shared.message import RuntimeMessage, RuntimeResult

logger = logging.getLogger(__name__)


class RuntimeRouter:
    """Runtime 注册与分发。

    用法:
        router = RuntimeRouter()
        router.register("motion", motion_runtime)
        router.register("interaction", interaction_rt)
        router.register("navigation", navigation_rt)

        result = router.dispatch("motion", message)
        result = router.reroute("motion", message, intent_result)
    """

    def __init__(self):
        self._runtimes: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # 注册
    # ------------------------------------------------------------------

    def register(self, name: str, runtime):
        """注册一个 Runtime。

        Args:
            name: Runtime 名称（"interaction" / "motion" / "navigation"）
            runtime: Runtime 实例，必须实现 handle(message) -> RuntimeResult
        """
        self._runtimes[name] = runtime
        logger.info(f"RuntimeRouter: 注册 {name}")

    def unregister(self, name: str):
        """注销 Runtime。"""
        self._runtimes.pop(name, None)
        logger.info(f"RuntimeRouter: 注销 {name}")

    @property
    def runtime_names(self) -> list[str]:
        return list(self._runtimes.keys())

    # ------------------------------------------------------------------
    # 分发
    # ------------------------------------------------------------------

    def dispatch(self, target: str, message: RuntimeMessage) -> RuntimeResult:
        """将消息分发到目标 Runtime。

        Args:
            target: 目标 Runtime 名
            message: 标准消息

        Returns:
            RuntimeResult

        Raises:
            ValueError: 目标 Runtime 未注册
        """
        runtime = self._runtimes.get(target)
        if runtime is None:
            logger.error(f"RuntimeRouter: 未知 Runtime 「{target}」，已注册: {self.runtime_names}")
            return RuntimeResult(
                success=False,
                error=f"未知 Runtime: {target}",
                trace_id=message.trace_id,
            )

        logger.debug(f"RuntimeRouter: 分发 → {target}")
        return runtime.handle(message)

    # ------------------------------------------------------------------
    # 二次路由
    # ------------------------------------------------------------------

    def reroute(self, target: str, message: RuntimeMessage,
                previous_result: RuntimeResult) -> RuntimeResult:
        """二次路由：将 InteractionRuntime 返回的意图转发到 Motion/Navigation Runtime。

        典型场景:
            InteractionRuntime → IntentAgent(LLM) → 识别为 motion
            → Gateway 调用 reroute("motion", message, intent_result)
            → 将 intent_result.data 写入 message.context
            → 调用 MotionRuntime.handle(message)

        Args:
            target: 目标 Runtime 名
            message: 原始消息
            previous_result: InteractionRuntime 返回的意图结果

        Returns:
            目标 Runtime 的执行结果
        """
        logger.info(f"RuntimeRouter: 二次路由 → {target}")

        # 将意图解析结果写入 message context，下游 Agent 读取
        data = previous_result.data
        if data:
            message.context["action"] = data.get("action", message.context.get("action", ""))
            message.context["params"] = data.get("params", message.context.get("params", {}))

        return self.dispatch(target, message)
