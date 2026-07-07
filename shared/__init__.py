"""共享层 — 消息协议、事件、会话、基类。"""
from shared.message import RuntimeMessage, RuntimeResult
from shared.event import RuntimeEvent
from shared.session import Session
from shared.base import BaseAgent, BaseSkill

__all__ = [
    "RuntimeMessage",
    "RuntimeResult",
    "RuntimeEvent",
    "Session",
    "BaseAgent",
    "BaseSkill",
]
