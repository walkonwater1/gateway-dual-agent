"""
Session 路由器 — 多用户会话隔离与上下文管理。

对应设计文档 gateway/session_router.py。

职责:
  - 维护 session_id → Session 映射
  - 创建/获取/删除 Session
  - 更新 Session 上下文（当前任务、偏好等）
  - 记录交互历史

当前实现: 内存 dict，后续可扩展为 Redis/DB 后端。
"""

from __future__ import annotations

import logging
import time
from typing import Any

from shared.session import Session

logger = logging.getLogger(__name__)


class SessionRouter:
    """Session 管理器。

    用法:
        router = SessionRouter()
        session = router.get_or_create("user_001")
        router.update_context("user_001", "preferred_language", "zh")
        router.set_current_task("user_001", "navigate", "navigation")
    """

    def __init__(self, ttl_seconds: float = 3600.0):
        self._sessions: dict[str, Session] = {}
        self._ttl = ttl_seconds

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def get_or_create(self, session_id: str, user_id: str = "anonymous") -> Session:
        """获取或创建 Session。"""
        session = self._sessions.get(session_id)
        if session is None:
            session = Session(session_id=session_id, user_id=user_id)
            self._sessions[session_id] = session
            logger.info(f"SessionRouter: 新建 session {session_id}")
        else:
            session.touch()
        return session

    def get(self, session_id: str) -> Session | None:
        """获取 Session（不创建）。"""
        session = self._sessions.get(session_id)
        if session:
            session.touch()
        return session

    def delete(self, session_id: str):
        """删除 Session。"""
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info(f"SessionRouter: 删除 session {session_id}")

    # ------------------------------------------------------------------
    # 上下文操作
    # ------------------------------------------------------------------

    def update_context(self, session_id: str, key: str, value: Any):
        """更新 Session 上下文中的某个字段。"""
        session = self.get_or_create(session_id)
        session.context[key] = value

    def get_context(self, session_id: str, key: str, default: Any = None) -> Any:
        """读取 Session 上下文字段。"""
        session = self.get(session_id)
        if session is None:
            return default
        return session.context.get(key, default)

    # ------------------------------------------------------------------
    # 任务管理
    # ------------------------------------------------------------------

    def set_current_task(self, session_id: str, task: str, runtime: str):
        """记录当前活跃任务。"""
        session = self.get_or_create(session_id)
        session.set_task(task, runtime)
        logger.debug(f"SessionRouter: {session_id} 任务={task} runtime={runtime}")

    def clear_task(self, session_id: str):
        """清除当前任务。"""
        session = self.get(session_id)
        if session:
            session.clear_task()

    def get_active_task(self, session_id: str) -> tuple[str | None, str | None]:
        """返回 (current_task, current_runtime)。"""
        session = self.get(session_id)
        if session is None:
            return None, None
        return session.current_task, session.current_runtime

    # ------------------------------------------------------------------
    # 历史
    # ------------------------------------------------------------------

    def add_to_history(self, session_id: str, role: str, content: str):
        """添加一条交互记录。"""
        session = self.get_or_create(session_id)
        session.add_to_history(role, content)

    def get_history(self, session_id: str, n: int = 10) -> list[dict]:
        """获取最近 N 条交互历史。"""
        session = self.get(session_id)
        if session is None:
            return []
        return session.history[-n:]

    # ------------------------------------------------------------------
    # 维护
    # ------------------------------------------------------------------

    def cleanup_expired(self):
        """清理过期 Session。"""
        now = time.time()
        expired = [
            sid for sid, s in self._sessions.items()
            if now - s.last_active > self._ttl
        ]
        for sid in expired:
            del self._sessions[sid]
        if expired:
            logger.info(f"SessionRouter: 清理 {len(expired)} 个过期 session")

    @property
    def session_count(self) -> int:
        return len(self._sessions)
