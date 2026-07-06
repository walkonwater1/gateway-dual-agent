"""
对话技能 — 纯 LLM 对话，不操作机器人。

对应设计文档 skills/ 中的交互类 Skill。
"""

import json
import logging

from openai import OpenAI

from shared.base import BaseSkill
from shared.message import RuntimeResult

logger = logging.getLogger(__name__)


class DialogueSkill(BaseSkill):
    """LLM 对话能力。"""

    SYSTEM_PROMPT = """你是爱啾（AIQ），一个友善的机器人助手。
请用自然、亲切的中文回复用户。
回复要简短（2-3句话），像人类对话一样。"""

    def __init__(self, llm: OpenAI, model: str, temperature: float = 0.7, max_tokens: int = 256):
        self._llm = llm
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens

    def execute(self, intent: str, params: dict) -> RuntimeResult:
        text = params.get("text", "")
        reply = self._chat(text)
        return RuntimeResult(
            success=True,
            intent="chat",
            reply=reply,
        )

    def _chat(self, text: str) -> str:
        try:
            resp = self._llm.chat.completions.create(
                model=self._model,
                temperature=self._temperature,
                max_tokens=self._max_tokens,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": text},
                ],
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"DialogueSkill 调用失败: {e}")
            return "嗯…我暂时没法回答这个问题 😅"
