"""
Session 管理 — 会话上下文与用户隔离。

对应设计文档 shared/session.py。
"""

from dataclasses import dataclass, field
from typing import Any, Optional
import time


@dataclass
class Session:
    """用户会话，承载跨轮对话的上下文。

    Gateway 的 SessionRouter 使用它来隔离多用户请求。
    """

    session_id: str
    user_id: str = "anonymous"
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    current_task: Optional[str] = None     # 当前活跃任务（如 "navigate_to_charging_station"）
    current_runtime: Optional[str] = None  # 当前活跃的 Runtime
    context: dict = field(default_factory=dict)   # 会话级上下文（用户偏好等）
    history: list = field(default_factory=list)   # 最近 N 条消息记录 [{role, content, timestamp}]

    MAX_HISTORY = 20

    def add_to_history(self, role: str, content: str):
        self.history.append({
            "role": role,
            "content": content,
            "timestamp": time.time(),
        })
        if len(self.history) > self.MAX_HISTORY:
            self.history = self.history[-self.MAX_HISTORY:]

    def touch(self):
        """更新最后活跃时间。"""
        self.last_active = time.time()

    def set_task(self, task: str, runtime: str):
        self.current_task = task
        self.current_runtime = runtime

    def clear_task(self):
        self.current_task = None
        self.current_runtime = None
