"""
路由策略 — YAML 配置化关键词匹配 → 选 Runtime。

对应设计文档 gateway/router.py + gateway/route_policy.py。

路由优先级:
  1. YAML 关键词命中 → 目标 Runtime，预填 action+params+priority
  2. 未命中 → default Runtime (interaction)，由 IntentAgent(LLM) 判断

匹配规则：RoutePolicy 内部按关键词长度降序排列，首个命中即返回（最长匹配）。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from shared.message import RuntimeMessage
from gateway.route_policy import RoutePolicy, RouteMatch

logger = logging.getLogger(__name__)


@dataclass
class RouteResult:
    """路由结果 — 比 RouteMatch 多带了原始 message 引用。"""
    runtime: str
    action: str = ""
    params: dict | None = None
    priority: str = "normal"
    keyword: str = ""

    def __post_init__(self):
        if self.params is None:
            self.params = {}


class Router:
    """Router：输入文本 → 目标 Runtime + context + priority。

    最大匹配原则（由 RoutePolicy 保证）：长关键词优先
    （"解除急停" > "急停" > "停"）。

    用法:
        policy = RoutePolicy("config/routes.yaml")
        router = Router(policy)
        runtime_name = router.route(message)  # 返回 "motion"
        # message.context 已被填充 action + params
        # message.priority 已被设置
    """

    def __init__(self, route_policy: RoutePolicy | None = None):
        self._policy = route_policy or RoutePolicy()

    def route(self, message: RuntimeMessage) -> str:
        """对消息进行路由判断，写入 context 和 priority。

        Args:
            message: 待路由的消息（原地修改 context / priority）

        Returns:
            目标 Runtime 名称: "interaction" | "motion" | "navigation"
        """
        text = message.text
        match = self._policy.match(text)

        if match:
            message.context["action"] = match.action
            message.context["params"] = match.params
            message.priority = match.priority
            logger.info(
                f"Router: 「{text}」→ {match.runtime} "
                f"(关键词:「{match.keyword}」 action={match.action} "
                f"priority={match.priority})"
            )
            return match.runtime

        # 未命中 → 默认路由（interaction + LLM 理解）
        default = self._policy.get_default()
        message.priority = default.priority
        logger.info(f"Router: 「{text}」→ {default.runtime} (LLM 理解)")
        return default.runtime
