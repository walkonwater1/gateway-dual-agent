"""
意图识别 Agent — LLM 理解用户意图。

使用 qwen2.5 模型做意图分类，输出结构化的意图+动作+参数。
"""

import json
import logging

from openai import OpenAI

from shared.base import BaseAgent
from shared.message import RuntimeMessage, RuntimeResult

logger = logging.getLogger(__name__)

INTENT_PROMPT = """你是机器人意图识别助手。分析用户输入，输出 JSON。

## 意图类型

### motion — 控制机器人身体
- 动作 (action=motion): 可用动作: cqm1, cqm2, cqm3
- 移动 (action=move): {"lx": 线速度, "ly": 横向, "az": 角速度}
- 急停 (action=stop): 说"停"/"停下"时
- 解除急停 (action=release_estop): 说"解除急停"/"可以动了"时
- 切换模式 (action=loco_mode): 站立/趴下/起身/小跑 → {"mode": "stand"/"still"/"getup"/"ppowalk"}
- 避障 (action=oas): 开/关避障 → {"enable": true/false}

### interaction — 交互类
- 音频 (action=play_audio): 播放音频，可选音频名 sch1/sch2/pth1
- 情绪 (action=switch_emotion): 切换表情情绪
- 语音唤醒 (action=voice_wakeup): 开/关语音唤醒
- 音量 (action=volume): 设置音量

### chat — 纯对话
问候、闲聊、知识问答。

### navigation — 导航
带有明确目的地的请求。

### unknown — 无法理解

## 示例
"你好" → {"intent":"chat","action":"chat","params":{}}
"做个动作" → {"intent":"motion","action":"motion","params":{"name":"cqm1"}}
"往前走" → {"intent":"motion","action":"move","params":{"lx":0.5,"ly":0,"az":0}}
"停下" → {"intent":"motion","action":"stop","params":{}}
"播放四川话" → {"intent":"interaction","action":"play_audio","params":{"name":"sch1"}}
"换个表情" → {"intent":"interaction","action":"switch_emotion","params":{}}
"关掉语音唤醒" → {"intent":"interaction","action":"voice_wakeup","params":{"enable":false}}
"带我去充电站" → {"intent":"navigation","action":"navigate","params":{"target":"充电站"}}
"""


class IntentAgent(BaseAgent):
    """LLM 意图识别。"""

    def __init__(self, llm: OpenAI, model: str, temperature: float = 0.1, max_tokens: int = 256):
        self._llm = llm
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens

    def handle(self, message: RuntimeMessage) -> RuntimeResult:
        text = message.text

        # 快速路径：常见命令直接命中，省 LLM
        fast = self._fast_path(text)
        if fast:
            return fast

        return self._llm_path(text)

    def _fast_path(self, text: str) -> RuntimeResult | None:
        t = text.strip()

        # 纯聊天类
        chats = ("你好", "谢谢", "再见", "早", "晚安", "你是谁", "你能做什么")
        if any(t.startswith(c) for c in chats):
            return RuntimeResult(intent="chat",
                                data={"action": "chat", "params": {}})

        return None

    def _llm_path(self, text: str) -> RuntimeResult:
        try:
            resp = self._llm.chat.completions.create(
                model=self._model,
                temperature=self._temperature,
                max_tokens=self._max_tokens,
                messages=[
                    {"role": "system", "content": INTENT_PROMPT},
                    {"role": "user", "content": text},
                ],
                response_format={"type": "json_object"},
            )
            content = resp.choices[0].message.content
            result = json.loads(content)
            return RuntimeResult(
                intent=result.get("intent", "unknown"),
                data={
                    "action": result.get("action", ""),
                    "params": result.get("params", {}),
                },
            )
        except Exception as e:
            logger.error(f"IntentAgent LLM 失败: {e}")
            return RuntimeResult(intent="unknown",
                                 data={"action": "none", "params": {}})
