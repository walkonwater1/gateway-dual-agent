"""
统一消息协议 — Gateway、Runtime、Agent 之间通信的唯一数据格式。

对应设计文档 shared/message.py。
"""

from dataclasses import dataclass, field
from typing import Any, Optional
import uuid


@dataclass
class RuntimeMessage:
    """Gateway 分发给 Runtime 的标准消息。

    无论输入来自文本、语音还是系统事件，都归一化为这个结构。
    """
    message_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    session_id: str = "default"
    source: str = "user"          # user / system / robot_event
    input_type: str = "text"      # text / asr / event
    payload: dict = field(default_factory=dict)
    context: dict = field(default_factory=dict)

    @classmethod
    def from_text(cls, text: str, session_id: str = "default") -> "RuntimeMessage":
        return cls(
            session_id=session_id,
            payload={"text": text},
        )

    @property
    def text(self) -> str:
        return self.payload.get("text", "")


@dataclass
class RuntimeResult:
    """Runtime 返回给 Gateway 的标准结果。"""
    success: bool = True
    reply: str = ""
    intent: str = "unknown"
    data: dict = field(default_factory=dict)
    error: Optional[str] = None
