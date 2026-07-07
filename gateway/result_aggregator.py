"""
结果汇聚器 — 多 Runtime 结果合并。

对应设计文档 gateway/result_aggregator.py。

职责:
  - 向多个 Runtime 并行分发消息
  - 收集各 Runtime 的返回结果
  - 合并为单个 RuntimeResult

典型场景:
  用户: "带我去爱湫展区，并介绍一下"
    → Interaction Runtime: 理解意图、生成讲解
    → Navigation Runtime: 执行导航
    → 结果汇聚: "好的，导航已启动。爱湫是..."

当前实现: 同步串行（Phase 3 MVP），后续可扩展为异步并行。
"""

from __future__ import annotations

import logging

from shared.message import RuntimeMessage, RuntimeResult

logger = logging.getLogger(__name__)


class ResultAggregator:
    """多 Runtime 结果汇聚器。

    用法:
        agg = ResultAggregator(runtime_router)
        result = agg.dispatch_and_collect(
            message,
            targets=["interaction", "navigation"],
        )
    """

    def __init__(self, enabled: bool = True, runtime_router=None):
        self._enabled = enabled
        self._runtime_router = runtime_router

    @property
    def enabled(self) -> bool:
        return self._enabled

    def aggregate(self, results: dict[str, RuntimeResult]) -> RuntimeResult:
        """将多个 Runtime 的结果合并为单个回复。

        Args:
            results: {"interaction": RuntimeResult, "navigation": RuntimeResult, ...}

        Returns:
            合并后的 RuntimeResult
        """
        if not self._enabled or not results:
            return RuntimeResult()

        # 收集回复
        replies = []
        all_success = True
        errors = []
        trace_ids = []

        for runtime_name, result in results.items():
            if result.reply:
                replies.append(result.reply)
            if not result.success:
                all_success = False
                if result.error:
                    errors.append(f"[{runtime_name}] {result.error}")
            if result.trace_id:
                trace_ids.append(result.trace_id)

        combined_reply = "\n".join(replies) if replies else ""

        return RuntimeResult(
            success=all_success,
            reply=combined_reply,
            intent="aggregated",
            data={
                "results": {name: {
                    "success": r.success,
                    "intent": r.intent,
                } for name, r in results.items()},
            },
            error="; ".join(errors) if errors else None,
            trace_id=",".join(trace_ids) if trace_ids else "",
        )

    def dispatch_and_collect(self, message: RuntimeMessage,
                             targets: list[str]) -> RuntimeResult:
        """向多个 Runtime 分发并收集结果（同步串行）。

        Args:
            message: 标准消息
            targets: 目标 Runtime 列表

        Returns:
            聚合后的 RuntimeResult
        """
        if not self._runtime_router:
            return RuntimeResult(
                success=False,
                error="ResultAggregator: runtime_router 未注入",
            )

        results = {}
        for target in targets:
            try:
                results[target] = self._runtime_router.dispatch(target, message)
            except Exception as e:
                logger.error(f"ResultAggregator: {target} 分发失败: {e}")
                results[target] = RuntimeResult(success=False, error=str(e))

        return self.aggregate(results)
