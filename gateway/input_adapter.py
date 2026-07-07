"""
输入适配器 — 将多模态输入统一转为 RuntimeMessage。

对应设计文档 gateway/input_adapter.py。

职责:
  - 文本输入 → RuntimeMessage（from_text）
  - ASR 语音识别结果 → RuntimeMessage（from_asr）
  - 机器人事件 → RuntimeMessage（from_robot_event）
  - 系统事件 → RuntimeMessage（from_system_event）

所有输入最终归一化为相同的 RuntimeMessage 结构，
下游 Runtime 不需要关心输入来源。
"""

from __future__ import annotations

import logging
from typing import Any

from shared.message import RuntimeMessage

logger = logging.getLogger(__name__)


class InputAdapter:
    """将不同来源的输入统一转为 RuntimeMessage。

    用法:
        adapter = InputAdapter()
        msg = adapter.from_text("前进")
        msg = adapter.from_asr({"text": "前进", "confidence": 0.95})
        msg = adapter.from_robot_event({"type": "estop", "active": True})
    """

    # ------------------------------------------------------------------
    # 文本输入
    # ------------------------------------------------------------------

    def from_text(self, text: str, session_id: str = "default") -> RuntimeMessage:
        """用户文本输入（CLI / Web / App）。"""
        return RuntimeMessage.from_text(text, session_id)

    # ------------------------------------------------------------------
    # ASR 语音识别
    # ------------------------------------------------------------------

    def from_asr(self, asr_result: dict, session_id: str = "default") -> RuntimeMessage:
        """ASR 语音识别结果。

        Args:
            asr_result: {"text": "...", "confidence": 0.95, "is_final": True}
        """
        text = asr_result.get("text", "")
        msg = RuntimeMessage(
            source="user",
            input_type="asr",
            session_id=session_id,
            payload={
                "text": text,
                "confidence": asr_result.get("confidence", 1.0),
                "is_final": asr_result.get("is_final", True),
            },
        )
        logger.debug(f"InputAdapter: ASR → 「{text}」")
        return msg

    # ------------------------------------------------------------------
    # 机器人事件
    # ------------------------------------------------------------------

    def from_robot_event(self, event: dict, session_id: str = "system") -> RuntimeMessage:
        """机器人状态事件（如急停激活、电池低电量等）。

        Args:
            event: {"type": "estop", "active": True} 或
                   {"type": "battery_low", "level": 15}
        """
        event_type = event.get("type", "unknown")
        msg = RuntimeMessage(
            source="robot_event",
            input_type="event",
            session_id=session_id,
            payload=dict(event),
            priority="high" if event_type in ("estop", "battery_low") else "normal",
        )
        logger.info(f"InputAdapter: robot_event → {event_type}")
        return msg

    # ------------------------------------------------------------------
    # 系统事件
    # ------------------------------------------------------------------

    def from_system_event(self, event_type: str, payload: dict | None = None,
                          session_id: str = "system") -> RuntimeMessage:
        """系统内部事件（心跳超时、Bridge 断连等）。"""
        msg = RuntimeMessage(
            source="system",
            input_type="event",
            session_id=session_id,
            payload={
                "event_type": event_type,
                **(payload or {}),
            },
        )
        logger.info(f"InputAdapter: system_event → {event_type}")
        return msg
