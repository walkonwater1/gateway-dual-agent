"""
路由策略加载器 — 从 YAML 配置加载路由规则。

对应设计文档 gateway/route_policy.py。

职责:
  - 加载 config/routes.yaml
  - 提供最长关键词匹配查询
  - 返回 RouteMatch（runtime + action + params + priority）
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 匹配结果
# ---------------------------------------------------------------------------

@dataclass
class RouteMatch:
    """路由匹配结果。"""
    runtime: str              # 目标 Runtime 名
    action: str = ""          # 预填 action
    params: dict = field(default_factory=dict)
    priority: str = "normal"  # emergency / high / normal / low
    keyword: str = ""         # 命中的关键词（用于日志）


# ---------------------------------------------------------------------------
# RoutePolicy
# ---------------------------------------------------------------------------

class RoutePolicy:
    """从 YAML 文件加载路由策略，提供最长关键词匹配。

    用法:
        policy = RoutePolicy("config/routes.yaml")
        match = policy.match("四川话")
        if match:
            print(match.runtime)   # "interaction"
            print(match.action)    # "play_audio"
            print(match.params)    # {"name": "sch1"}
    """

    def __init__(self, config_path: str | Path | None = None):
        self._patterns: list[tuple[str, RouteMatch]] = []
        """扁平化的关键词→RouteMatch 列表，按 YAML 中定义顺序排列。"""

        self._default = RouteMatch(
            runtime="interaction",
            priority="normal",
        )

        if config_path is not None:
            self.load(config_path)

    # ------------------------------------------------------------------
    # 加载
    # ------------------------------------------------------------------

    def load(self, config_path: str | Path):
        """加载 YAML 路由配置文件。"""
        path = Path(config_path)
        if not path.exists():
            logger.warning(f"RoutePolicy: 配置文件不存在 {path}，使用默认路由")
            return

        with open(path, "r") as f:
            data = yaml.safe_load(f)

        if not data:
            logger.warning("RoutePolicy: 空配置文件")
            return

        routes = data.get("routes", data)

        # 加载默认路由
        default_cfg = routes.pop("default", {})
        if default_cfg:
            self._default = RouteMatch(
                runtime=default_cfg.get("runtime", "interaction"),
                priority=default_cfg.get("priority", "normal"),
            )

        # 加载各路由组
        self._patterns = []
        for _group_name, group_cfg in routes.items():
            runtime = group_cfg.get("runtime", "interaction")
            priority = group_cfg.get("priority", "normal")
            patterns = group_cfg.get("patterns", [])

            for pattern in patterns:
                keywords = pattern.get("keywords", [])
                action = pattern.get("action", "")
                params = pattern.get("params", {})

                for kw in keywords:
                    match = RouteMatch(
                        runtime=runtime,
                        action=action,
                        params=dict(params),  # 浅拷贝
                        priority=priority,
                        keyword=kw,
                    )
                    self._patterns.append((kw, match))

        # 按关键词长度降序排列（长关键词优先匹配）
        self._patterns.sort(key=lambda x: len(x[0]), reverse=True)

        logger.info(
            f"RoutePolicy: 加载 {len(self._patterns)} 条路由规则 "
            f"(默认→{self._default.runtime})"
        )

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    def match(self, text: str) -> RouteMatch | None:
        """在文本中查找最长匹配的关键词。

        Args:
            text: 用户输入文本

        Returns:
            RouteMatch 如果命中；否则 None（调用方应使用 get_default()）
        """
        for keyword, route_match in self._patterns:
            if keyword in text:
                logger.debug(
                    f"RoutePolicy: 「{text}」命中「{keyword}」"
                    f"→ {route_match.runtime}/{route_match.action}"
                )
                return route_match
        return None

    def get_default(self) -> RouteMatch:
        """返回默认路由（未命中时走 interaction + LLM）。"""
        return self._default

    # ------------------------------------------------------------------
    # 运行时查询
    # ------------------------------------------------------------------

    @property
    def pattern_count(self) -> int:
        return len(self._patterns)
