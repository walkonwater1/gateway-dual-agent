"""
Agent 基类。

对应设计文档 shared/base_agent.py。
"""

from shared.message import RuntimeMessage, RuntimeResult


class BaseAgent:
    """所有 Agent 的基类。

    Agent 的职责：决策。接收消息，返回结果。不直接操作硬件。
    """

    def handle(self, message: RuntimeMessage) -> RuntimeResult:
        raise NotImplementedError


class BaseSkill:
    """所有 Skill 的基类。

    Skill 的职责：执行。将 Agent 的决策翻译为具体操作（MQTT 指令等）。
    """

    def execute(self, intent: str, params: dict) -> RuntimeResult:
        raise NotImplementedError
