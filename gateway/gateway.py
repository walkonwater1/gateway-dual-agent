"""
Gateway — 中央路由与治理中枢。

对应设计文档 gateway/gateway.py（13 模块完整版）。

处理链路（10 步）:
  输入事件
    → InputAdapter      # 多模态归一化
    → TraceLogger       # 生成 trace_id
    → SessionRouter     # 获取/创建 Session
    → PriorityManager   # 设置优先级
    → SafetyGate        # 安全检查
    → Router            # YAML 规则匹配
    → ConflictResolver  # 冲突检测
    → RuntimeRouter     # 分发/二次路由
    → ResultAggregator  # 结果汇聚
    → TraceLogger       # 记录结果

设计原则:
  - 薄中枢：不调 LLM、不做业务决策、不发 MQTT
  - 模块可插拔：每个模块通过 enabled 开关控制
  - 向后兼容：旧的 Gateway(ir, mr, nr) 构造方式仍可用
"""

from __future__ import annotations

import logging
from typing import Any

from shared.message import RuntimeMessage, RuntimeResult
from shared.event import RuntimeEvent

from gateway.router import Router
from gateway.route_policy import RoutePolicy
from gateway.input_adapter import InputAdapter
from gateway.runtime_router import RuntimeRouter
from gateway.session_router import SessionRouter
from gateway.priority_manager import PriorityManager
from gateway.safety_gate import SafetyGate
from gateway.trace_logger import TraceLogger
from gateway.event_bus import EventBus
from gateway.conflict_resolver import ConflictResolver, ConflictAction
from gateway.result_aggregator import ResultAggregator

logger = logging.getLogger(__name__)


class Gateway:
    """中央路由中枢 — 完整 10 步处理链路。

    用法（新方式，推荐）:
        gw = Gateway(
            interaction_runtime=interaction_rt,
            motion_runtime=motion_rt,
            navigation_runtime=navigation_rt,
            route_policy=policy,
            trace_logger=tracer,
            session_router=sessions,
            priority_manager=priorities,
            safety_gate=safety,
            conflict_resolver=conflicts,
            event_bus=events,
            result_aggregator=aggregator,
        )
        result = gw.handle_text("前进")

    用法（旧方式，兼容）:
        gw = Gateway(interaction_rt, motion_rt, navigation_rt)
        result = gw.handle_text("前进")
    """

    def __init__(self, *args, **kwargs):
        """初始化 Gateway。

        兼容两种构造方式:
          - 旧: Gateway(interaction_rt, motion_rt, navigation_rt)
          - 新: Gateway(interaction_runtime=..., motion_runtime=..., ...)
        """

        # --- 解析参数（兼容旧接口） ---
        if len(args) == 3:
            interaction_runtime, motion_runtime, navigation_runtime = args
        else:
            interaction_runtime = kwargs.get("interaction_runtime")
            motion_runtime = kwargs.get("motion_runtime")
            navigation_runtime = kwargs.get("navigation_runtime")

        # --- Runtime 路由器 ---
        self._runtime_router = RuntimeRouter()
        if interaction_runtime:
            self._runtime_router.register("interaction", interaction_runtime)
        if motion_runtime:
            self._runtime_router.register("motion", motion_runtime)
        if navigation_runtime:
            self._runtime_router.register("navigation", navigation_runtime)

        # --- 路由策略 ---
        route_policy = kwargs.get("route_policy")
        self._router = Router(route_policy)

        # --- 可插拔模块 ---
        self._input_adapter = kwargs.get("input_adapter", InputAdapter())
        self._trace_logger = kwargs.get("trace_logger", TraceLogger())
        self._session_router = kwargs.get("session_router")
        self._priority_manager = kwargs.get("priority_manager")
        self._safety_gate = kwargs.get("safety_gate")
        self._conflict_resolver = kwargs.get("conflict_resolver")
        self._result_aggregator = kwargs.get("result_aggregator")
        self._event_bus = kwargs.get("event_bus", EventBus())

    # ==================================================================
    # 公开入口
    # ==================================================================

    def handle_text(self, text: str, session_id: str = "default") -> RuntimeResult:
        """处理用户文本输入 — Gateway 主入口。

        完整 10 步处理链路，每步检查模块是否启用。

        Args:
            text: 用户输入文本
            session_id: 会话 ID

        Returns:
            RuntimeResult: 包含回复和执行结果
        """
        # Step 1: 输入适配（多模态归一化）
        message = self._input_adapter.from_text(text, session_id)

        # Step 2: 开始 Trace
        trace_id = self._trace_logger.start_trace(message)
        message.trace_id = trace_id

        logger.info(f"Gateway: 收到「{text}」(trace={trace_id[:8]})")

        # Step 3: Session 管理
        if self._session_router:
            session = self._session_router.get_or_create(session_id)
            self._session_router.add_to_history(session_id, "user", text)
            self._trace_logger.log_event(trace_id, "session_lookup", {
                "session_id": session_id,
                "active_task": session.current_task,
            })

        # Step 4: 优先级管理
        if self._priority_manager:
            # 优先级由 Router 在路由时设置，此处记录
            pass

        # Step 5: 安全过滤
        if self._safety_gate and self._safety_gate.enabled:
            safety_result = self._safety_gate.check(message)
            self._trace_logger.log_event(trace_id, "safety_check", {
                "allowed": safety_result.allowed,
            })
            if not safety_result.allowed:
                self._trace_logger.log_safety_block(trace_id, safety_result.reason)
                result = RuntimeResult(
                    success=False,
                    reply=safety_result.reason,
                    intent="safety_blocked",
                    trace_id=trace_id,
                )
                self._trace_logger.finalize_trace(trace_id, result)
                return result

        # Step 6: 路由判断
        runtime_name = self._router.route(message)
        self._trace_logger.log_route(trace_id, runtime_name)

        # Step 7: 冲突检测
        if self._conflict_resolver and self._conflict_resolver.enabled:
            active_task, active_runtime = None, None
            active_priority = "normal"
            if self._session_router:
                active_task, active_runtime = (
                    self._session_router.get_active_task(session_id)
                )
            conflict = self._conflict_resolver.check(
                new_msg_priority=message.priority,
                new_runtime=runtime_name,
                active_task=active_task,
                active_runtime=active_runtime,
                active_priority=active_priority,
            )
            self._trace_logger.log_event(trace_id, "conflict_check", {
                "action": conflict.action.value,
                "reason": conflict.reason,
            })

            if conflict.action == ConflictAction.REFUSE:
                result = RuntimeResult(
                    success=False,
                    reply=conflict.reason,
                    trace_id=trace_id,
                )
                self._trace_logger.finalize_trace(trace_id, result)
                return result

            if conflict.action == ConflictAction.PREEMPT and self._session_router:
                self._session_router.clear_task(session_id)

        # Step 8: 首次分发
        self._trace_logger.log_dispatch(trace_id, runtime_name)
        result = self._runtime_router.dispatch(runtime_name, message)
        self._trace_logger.log_result(trace_id, result)

        # Step 9: 二次路由
        if runtime_name == "interaction" and result.intent in ("motion", "navigation"):
            self._trace_logger.log_reroute(trace_id, result.intent)
            result = self._runtime_router.reroute(result.intent, message, result)
            self._trace_logger.log_result(trace_id, result)

        # Step 10: 记录 Session 状态
        if self._session_router:
            self._session_router.add_to_history(session_id, "assistant", result.reply)
            if result.intent in ("motion", "navigation") and result.success:
                self._session_router.set_current_task(
                    session_id, result.intent, result.intent
                )

        # 完成 Trace
        self._trace_logger.finalize_trace(trace_id, result)

        logger.info(f"Gateway: 回复「{result.reply[:80]}」")
        return result

    def handle_event(self, event: dict, session_id: str = "system") -> RuntimeResult:
        """处理系统/机器人事件。

        Args:
            event: 事件字典 {"type": "estop", ...}
            session_id: 会话 ID

        Returns:
            RuntimeResult
        """
        message = self._input_adapter.from_robot_event(event, session_id)
        trace_id = self._trace_logger.start_trace(message)
        message.trace_id = trace_id

        logger.info(f"Gateway: 收到事件 {event.get('type')}")

        # 事件直接路由到对应 Runtime（不经过 Router）
        event_type = event.get("type", "")
        if event_type in ("estop", "estop_released"):
            runtime_name = "motion"
        else:
            runtime_name = "interaction"

        result = self._runtime_router.dispatch(runtime_name, message)
        self._trace_logger.finalize_trace(trace_id, result)
        return result

    # ==================================================================
    # 属性访问
    # ==================================================================

    @property
    def event_bus(self) -> EventBus:
        """事件总线，供 Runtime 订阅。"""
        return self._event_bus

    @property
    def trace_logger(self) -> TraceLogger:
        return self._trace_logger

    @property
    def session_router(self) -> SessionRouter | None:
        return self._session_router

    @property
    def runtime_router(self) -> RuntimeRouter:
        return self._runtime_router

    def register_runtime(self, name: str, runtime):
        """动态注册 Runtime。"""
        self._runtime_router.register(name, runtime)
