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

    # 聊天/问答类关键词 — 命中则直接返回 chat，不调 LLM
    _CHAT_KEYWORDS = (
        # 问候
        "你好", "谢谢", "再见", "早", "晚安",
        # 身份/能力
        "你是谁", "你能做什么", "你叫什么", "你的名字",
        # 天气/时间/知识问答
        "天气", "几点了", "几点", "日期", "今天几号", "星期",
        "温度", "湿度", "会不会下雨", "冷不冷", "热不热",
        # 闲聊
        "爱你", "我喜欢你", "你真", "好可爱", "你真棒", "你真聪明",
        "讲个笑话", "讲笑话", "唱首歌", "唱个歌",
    )

    # 疑问句式关键词 — 包含这些的问句大概率是 chat
    _QUESTION_PATTERNS = (
        "怎么样", "是什么", "为什么", "什么意思", "怎么", "吗",
        "谁", "哪里", "哪儿", "什么时候", "多少", "能不能",
    )

    def _fast_path(self, text: str) -> RuntimeResult | None:
        t = text.strip()

        # 1. 日志模拟事件检测 — 模拟 MQTT 日志喂给 Gateway 的场景
        sim = self._simulate_log_event(t)
        if sim:
            return sim

        # 2. 精确/前缀匹配聊天关键词
        if any(c in t for c in self._CHAT_KEYWORDS):
            return RuntimeResult(intent="chat",
                                data={"action": "chat", "params": {}})

        # 3. 疑问句式检测：包含疑问词且不以动作动词开头
        if any(q in t for q in self._QUESTION_PATTERNS):
            # 排除明显是动作指令的（如"怎么走"→navigation）
            if not any(t.startswith(v) for v in ("走", "去", "到", "前进", "后退", "停")):
                return RuntimeResult(intent="chat",
                                    data={"action": "chat", "params": {}})

        return None

    @staticmethod
    def _simulate_log_event(text: str) -> RuntimeResult | None:
        """识别模拟日志事件输入（如 "电量低于15%" → 导航回充电站）。

        支持格式:
          - 电量/电池 低于/< X%  → navigation: 导航回充电站
          - 电机温度 > X         → motion: 急停
          - 电机过热              → motion: 急停
        """
        import re

        # --- 电池低电量 → 导航回充电站 ---
        battery_match = re.match(
            r"(电量|电池|battery)\s*(低于|<|小于|<=)\s*(\d+)\s*%?",
            text, re.IGNORECASE
        )
        if battery_match:
            pct = int(battery_match.group(3))
            return RuntimeResult(
                intent="navigation",
                data={
                    "action": "navigate",
                    "params": {"target": "充电站"},
                },
                reply=f"🔋 模拟日志事件: 电量 {pct}% < 20% → 自动导航回充电站",
            )

        # --- 电机过热 → 急停 ---
        motor_match = re.match(
            r"(电机|马达|motor)\s*(温度)?\s*(>|大于|超过|>=|过热)\s*(\d+)?\s*°?C?",
            text, re.IGNORECASE
        )
        if motor_match:
            temp = motor_match.group(4)
            temp_str = f" {temp}°C" if temp else ""
            return RuntimeResult(
                intent="motion",
                data={
                    "action": "stop",
                    "params": {},
                },
                reply=f"🔥 模拟日志事件: 电机温度{temp_str}超过安全阈值 → 急停",
            )

        # --- CPU 过热 → 交互通知 ---
        cpu_match = re.match(
            r"(CPU|cpu)\s*(温度)?\s*(>|大于|超过|>=)\s*(\d+)\s*°?C?",
            text, re.IGNORECASE
        )
        if cpu_match:
            temp = cpu_match.group(4)
            return RuntimeResult(
                intent="interaction",
                data={
                    "action": "switch_emotion",
                    "params": {},
                },
                reply=f"🌡️ 模拟日志事件: CPU 温度 {temp}°C 过高 → 切换表情提醒",
            )

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
