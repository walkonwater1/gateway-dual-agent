"""
Gateway — 中央路由与协调中枢。

对应设计文档 gateway/gateway.py。

职责:
  1. 接收用户输入（当前仅文本）
  2. 封装为 RuntimeMessage
  3. 调用 Router 判断目标 Runtime
  4. 分发消息到对应 Runtime
  5. 处理跨 Runtime 的二次路由（Interaction → Motion/Navigation）
  6. 返回结果

不负责:
  - 对话生成（交给 Interaction Runtime）
  - 路径规划（交给 Navigation Runtime）
  - 动作执行（交给 Motion Runtime）
"""

import logging

from gateway.router import Router
from shared.message import RuntimeMessage, RuntimeResult

logger = logging.getLogger(__name__)


class Gateway:
    """中央路由中枢。

    用法:
        gw = Gateway(interaction_rt, motion_rt, navigation_rt)
        result = gw.handle_text("挥个手")
        print(result.reply)
    """

    def __init__(self, interaction_runtime, motion_runtime, navigation_runtime):
        self._router = Router()
        self._runtimes = {
            "interaction": interaction_runtime,
            "motion": motion_runtime,
            "navigation": navigation_runtime,
        }

    def handle_text(self, text: str, session_id: str = "default") -> RuntimeResult:
        """处理用户文本输入 — Gateway 主入口。

        Args:
            text: 用户输入文本
            session_id: 会话 ID（单用户场景固定为 default）

        Returns:
            RuntimeResult: 包含回复和执行结果
        """
        # 1. 封装为标准消息
        message = RuntimeMessage.from_text(text, session_id)
        logger.info(f"Gateway: 收到「{text}」")

        # 2. 路由到目标 Runtime
        runtime_name = self._router.route(message)
        runtime = self._runtimes[runtime_name]

        # 3. 首次分发
        result = runtime.handle(message)

        # 4. 二次路由：如果 Interaction Runtime 判断意图是 motion/navigation
        #    则将解析结果转发到对应的 Runtime
        if runtime_name == "interaction" and result.intent in ("motion", "navigation"):
            result = self._reroute(result.intent, message, result)

        logger.info(f"Gateway: 回复「{result.reply}」")
        return result

    def _reroute(self, target_runtime: str, message: RuntimeMessage,
                 intent_result: RuntimeResult) -> RuntimeResult:
        """二次路由：将 IntentAgent 的解析结果交给对应 Runtime 执行。"""
        logger.info(f"Gateway: 二次路由 → {target_runtime}")

        # 将意图解析结果写入 context
        message.context.update(intent_result.data)

        runtime = self._runtimes.get(target_runtime)
        if runtime is None:
            return RuntimeResult(
                success=False,
                error=f"未知 Runtime: {target_runtime}",
            )

        return runtime.handle(message)
