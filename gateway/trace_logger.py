"""
链路追踪 — 记录每条请求的完整处理链路。

对应设计文档 gateway/trace_logger.py。

记录内容:
  1. 输入是什么
  2. 归属哪个 Session
  3. 路由到了哪个 Runtime
  4. 是否触发 Safety Gate
  5. 是否触发优先级提升
  6. 是否发生冲突仲裁
  7. 调用了哪个 Runtime
  8. Runtime 是否成功
  9. 总耗时多少
  10. 最终返回了什么

用途: 调试、回放、Harness 测试、性能分析、安全审计。
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import date
from typing import Any

from shared.message import RuntimeMessage, RuntimeResult

logger = logging.getLogger(__name__)


class TraceLogger:
    """全链路 Trace 记录器。

    用法:
        tracer = TraceLogger()
        trace_id = tracer.start_trace(message)
        tracer.log_event(trace_id, "route_decided", {"target": "motion"})
        tracer.log_event(trace_id, "runtime_result", {"success": True})
        trace = tracer.get_trace(trace_id)
    """

    def __init__(self, max_traces: int = 1000, log_dir: str | None = None):
        self._traces: dict[str, dict] = {}
        self._max_traces = max_traces
        self._log_dir = log_dir
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Trace 生命周期
    # ------------------------------------------------------------------

    def start_trace(self, message: RuntimeMessage) -> str:
        """开始一条新 trace，返回 trace_id。

        如果 message 已有 trace_id 则复用，否则生成新的并写入 message。
        """
        trace_id = message.trace_id

        trace = {
            "trace_id": trace_id,
            "session_id": message.session_id,
            "input": message.text,
            "input_type": message.input_type,
            "source": message.source,
            "priority": message.priority,
            "events": [],
            "start_time": time.time(),
            "end_time": None,
            "total_duration_ms": None,
        }
        self._add_event(trace, "input_received", {
            "text": message.text,
            "priority": message.priority,
        })

        self._traces[trace_id] = trace
        self._evict_if_needed()

        logger.debug(f"TraceLogger: 开始 trace {trace_id[:8]}")
        return trace_id

    def finalize_trace(self, trace_id: str, result: RuntimeResult):
        """结束 trace，记录最终结果和耗时。"""
        trace = self._traces.get(trace_id)
        if not trace:
            return

        trace["end_time"] = time.time()
        trace["total_duration_ms"] = round(
            (trace["end_time"] - trace["start_time"]) * 1000, 2
        )

        self._add_event(trace, "final_result", {
            "success": result.success,
            "intent": result.intent,
            "reply": result.reply[:200] if result.reply else "",
            "error": result.error,
        })

        result.trace_id = trace_id

        duration = trace["total_duration_ms"]
        logger.info(
            f"TraceLogger: trace {trace_id[:8]} 完成 "
            f"({len(trace['events'])} events, {duration}ms)"
        )

        # 文件持久化
        if self._log_dir:
            self._write_to_file(trace)

    # ------------------------------------------------------------------
    # 事件记录
    # ------------------------------------------------------------------

    def log_event(self, trace_id: str, event_type: str,
                  payload: dict | None = None):
        """向 trace 添加一个事件。

        Args:
            trace_id: Trace ID
            event_type: 事件类型
                - "input_received"
                - "session_lookup"
                - "priority_assigned"
                - "safety_check"
                - "route_decided"
                - "conflict_check"
                - "runtime_called"
                - "reroute"
                - "runtime_result"
                - "final_result"
            payload: 事件附加数据
        """
        trace = self._traces.get(trace_id)
        if not trace:
            return
        self._add_event(trace, event_type, payload or {})

    # ------------------------------------------------------------------
    # 快捷方法
    # ------------------------------------------------------------------

    def log_route(self, trace_id: str, target: str, keyword: str = ""):
        self.log_event(trace_id, "route_decided", {
            "target_runtime": target,
            "keyword": keyword,
        })

    def log_dispatch(self, trace_id: str, runtime: str):
        self.log_event(trace_id, "runtime_called", {"runtime": runtime})

    def log_reroute(self, trace_id: str, target: str):
        self.log_event(trace_id, "reroute", {"target_runtime": target})

    def log_result(self, trace_id: str, result: RuntimeResult):
        self.log_event(trace_id, "runtime_result", {
            "success": result.success,
            "intent": result.intent,
        })

    def log_safety_block(self, trace_id: str, reason: str):
        self.log_event(trace_id, "safety_blocked", {"reason": reason})

    def log_priority_change(self, trace_id: str, old: str, new: str):
        self.log_event(trace_id, "priority_changed", {"from": old, "to": new})

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    def get_trace(self, trace_id: str) -> dict | None:
        """获取完整的 trace 记录。"""
        return self._traces.get(trace_id)

    def get_recent_traces(self, n: int = 10) -> list[dict]:
        """获取最近 N 条 trace（按开始时间倒序）。"""
        sorted_traces = sorted(
            self._traces.values(),
            key=lambda t: t["start_time"],
            reverse=True,
        )
        return sorted_traces[:n]

    def to_json(self, trace_id: str) -> str:
        """将 trace 序列化为 JSON 字符串。"""
        trace = self._traces.get(trace_id)
        if not trace:
            return "{}"
        return json.dumps(trace, ensure_ascii=False, indent=2, default=str)

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    def _write_to_file(self, trace: dict):
        """追加一条 trace 到 JSONL 日志文件。"""
        try:
            filename = f"trace_{date.today().isoformat()}.jsonl"
            filepath = os.path.join(self._log_dir, filename)
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(json.dumps(trace, ensure_ascii=False, default=str) + "\n")
        except Exception as e:
            logger.warning(f"TraceLogger: 写入文件失败: {e}")

    def _add_event(self, trace: dict, event_type: str, payload: dict):
        trace["events"].append({
            "type": event_type,
            "timestamp": time.time(),
            "payload": payload,
        })

    def _evict_if_needed(self):
        """超过最大容量时淘汰最旧的 trace。"""
        if len(self._traces) > self._max_traces:
            oldest = min(
                self._traces.keys(),
                key=lambda k: self._traces[k]["start_time"],
            )
            del self._traces[oldest]
