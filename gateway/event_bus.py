"""
事件总线 — Runtime 间事件广播与状态同步。

对应设计文档 gateway/event_bus.py。

职责:
  - Runtime 间事件发布/订阅
  - 状态广播（导航进度 → Interaction 播报）
  - 解耦 Runtime 之间的直接依赖

事件类型（见 shared/event.py）:
  - navigation.progress / .completed / .error
  - motion.started / .completed / .error
  - safety.estop / .estop_released
  - interaction.tts_start / .tts_end
  - robot.status / .battery_low

设计原则:
  - 进程内 pub/sub，不依赖外部消息队列
  - 线程安全
  - 可通过 enabled=False 关闭
  - 所有跨 Runtime 通信走 Gateway（Event Bus 是 Gateway 的一部分）
"""

from __future__ import annotations

import logging
import threading
from collections import defaultdict
from typing import Any, Callable

from shared.event import RuntimeEvent

logger = logging.getLogger(__name__)

# 回调签名: callback(event: RuntimeEvent) -> None
EventCallback = Callable[[RuntimeEvent], None]


class EventBus:
    """进程内事件总线。

    用法:
        bus = EventBus()

        # 订阅
        def on_nav_progress(event):
            print(f"导航进度: {event.payload}")

        bus.subscribe("navigation.progress", on_nav_progress)

        # 发布
        event = RuntimeEvent.create("navigation.progress", "navigation",
                                     {"percent": 60})
        bus.publish(event)

        # 取消订阅
        bus.unsubscribe("navigation.progress", on_nav_progress)
    """

    def __init__(self, enabled: bool = True):
        self._enabled = enabled
        self._subscribers: dict[str, list[EventCallback]] = defaultdict(list)
        self._lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        return self._enabled

    # ------------------------------------------------------------------
    # 发布
    # ------------------------------------------------------------------

    def publish(self, event: RuntimeEvent):
        """发布事件到所有订阅者。

        如果 EventBus 关闭，消息静默丢弃。
        """
        if not self._enabled:
            return

        event_type = event.event_type
        logger.debug(f"EventBus: 发布 {event_type} (source={event.source_runtime})")

        with self._lock:
            callbacks = list(self._subscribers.get(event_type, []))

        for callback in callbacks:
            try:
                callback(event)
            except Exception:
                logger.exception(
                    f"EventBus: 回调异常 {event_type} callback={callback}"
                )

    def emit(self, event_type: str, source_runtime: str,
             payload: dict | None = None):
        """快捷发布：直接传参，内部构造 RuntimeEvent。"""
        event = RuntimeEvent.create(event_type, source_runtime, payload)
        self.publish(event)

    # ------------------------------------------------------------------
    # 订阅
    # ------------------------------------------------------------------

    def subscribe(self, event_type: str, callback: EventCallback):
        """订阅事件类型。

        Args:
            event_type: 事件类型（如 "navigation.progress"），支持通配符 "*" 订阅所有事件
            callback: 回调函数 callback(event: RuntimeEvent) -> None
        """
        with self._lock:
            if callback not in self._subscribers[event_type]:
                self._subscribers[event_type].append(callback)
                logger.debug(f"EventBus: 订阅 {event_type}")

    def unsubscribe(self, event_type: str, callback: EventCallback):
        """取消订阅。"""
        with self._lock:
            subs = self._subscribers.get(event_type, [])
            if callback in subs:
                subs.remove(callback)
                logger.debug(f"EventBus: 取消订阅 {event_type}")
            if not subs:
                self._subscribers.pop(event_type, None)

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    @property
    def subscriber_count(self) -> int:
        """订阅者总数。"""
        with self._lock:
            return sum(len(cbs) for cbs in self._subscribers.values())

    def get_subscribers(self, event_type: str) -> list[EventCallback]:
        """获取某事件类型的所有订阅者。"""
        with self._lock:
            return list(self._subscribers.get(event_type, []))
