"""
安全网关 — 请求级安全过滤。

对应设计文档 gateway/safety_gate.py。

职责:
  - 请求级安全过滤（不替代 Motion Runtime 的动作级安全）
  - 拦截明显危险的语义意图

安全分两层:
  Layer 1 (Gateway Safety Gate): 请求级 — 拦截"冲过去"等危险自然语言
  Layer 2 (Motion Runtime): 动作级 — 姿态、执行级安全检查

设计原则:
  - 只做前置过滤，不做动作级安全判断
  - 可配置拦截模式
  - 可通过 enabled=False 关闭
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from shared.message import RuntimeMessage

logger = logging.getLogger(__name__)


@dataclass
class SafetyResult:
    """安全检查结果。"""
    allowed: bool
    reason: str = ""


class SafetyGate:
    """请求级安全过滤器。

    用法:
        gate = SafetyGate(blocked_patterns=["冲过去", "撞过去"])
        result = gate.check(message)
        if not result.allowed:
            return RuntimeResult(success=False, reply=result.reason)
    """

    # 默认危险模式（设计文档 §4.9）
    DEFAULT_BLOCKED = [
        "冲过去",
        "撞过去",
        "推开他",
        "推开她",
        "快速跑向人群",
        "撞向他",
        "撞向她",
        "执行危险动作",
        "自毁",
        "攻击",
    ]

    def __init__(self, enabled: bool = True,
                 blocked_patterns: list[str] | None = None):
        self._enabled = enabled
        patterns = blocked_patterns if blocked_patterns is not None else self.DEFAULT_BLOCKED
        self._patterns = patterns
        # 预编译正则
        self._compiled = [re.compile(re.escape(p)) for p in patterns]

    @property
    def enabled(self) -> bool:
        return self._enabled

    def check(self, message: RuntimeMessage) -> SafetyResult:
        """检查消息是否安全。

        Args:
            message: 待检查的消息

        Returns:
            SafetyResult: allowed=True 放行；allowed=False 拦截
        """
        if not self._enabled:
            return SafetyResult(allowed=True)

        text = message.text

        for i, pattern in enumerate(self._compiled):
            if pattern.search(text):
                blocked = self._patterns[i]
                logger.warning(f"SafetyGate: 拦截危险指令「{text}」(匹配: {blocked})")
                return SafetyResult(
                    allowed=False,
                    reason=f"安全策略拦截：检测到危险指令「{blocked}」",
                )

        return SafetyResult(allowed=True)

    def add_pattern(self, pattern: str):
        """动态添加拦截模式。"""
        self._patterns.append(pattern)
        self._compiled.append(re.compile(re.escape(pattern)))
