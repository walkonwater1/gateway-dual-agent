"""
交互技能 — 音频、情绪、语音交互、氛围灯、音量。

底层通过 CMD_CORPUS(1007)→/eir/general_interface 或专门的设置指令。
"""

import logging

from capabilities.mqtt_client import RobotMqttClient
from shared.base import BaseSkill
from shared.message import RuntimeResult

logger = logging.getLogger(__name__)

# 可用音频
VALID_AUDIOS = ["sch1", "sch2", "pth1"]


class InteractionSkill(BaseSkill):
    """交互类能力：音频、情绪、语音开关、设置。"""

    def __init__(self, mqtt: RobotMqttClient):
        self._mqtt = mqtt

    def execute(self, intent: str, params: dict) -> RuntimeResult:
        action = params.get("action", "")

        if action == "play_audio":
            return self._play_audio(params)
        elif action == "switch_emotion":
            return self._switch_emotion()
        elif action == "voice_wakeup":
            return self._voice_wakeup(params.get("enable", True))
        elif action == "volume":
            return self._set_volume(params)
        elif action == "led":
            return self._set_led(params)
        else:
            return RuntimeResult(success=False, error=f"未知 action={action}")

    # ------------------------------------------------------------------
    # 音频播放 — 通过 general_interface
    # ------------------------------------------------------------------
    def _play_audio(self, params: dict) -> RuntimeResult:
        name = params.get("name", "")
        if name:
            if name not in VALID_AUDIOS:
                return RuntimeResult(
                    success=False,
                    error=f"不支持的音频: {name}，可用: {', '.join(VALID_AUDIOS)}"
                )
            data = {"type": "play_specific_audio", "value": {"name": name}}
            reply = f"播放音频: {name}"
        else:
            data = {"type": "play_audio_random"}
            reply = "随机播放音频"

        uuid = self._mqtt.send_corpus(data)
        logger.info(f"InteractionSkill: {reply}")
        return RuntimeResult(success=True, intent="audio",
                             data={"uuid": uuid}, reply=reply)

    # ------------------------------------------------------------------
    # 随机切换情绪 — 通过 general_interface
    # ------------------------------------------------------------------
    def _switch_emotion(self) -> RuntimeResult:
        data = {"type": "switch_emotion_random"}
        uuid = self._mqtt.send_corpus(data)
        logger.info(f"InteractionSkill: 随机切换情绪")
        return RuntimeResult(success=True, intent="emotion",
                             data={"uuid": uuid}, reply="情绪已随机切换！")

    # ------------------------------------------------------------------
    # 语音唤醒开关 — 通过 general_interface
    # ------------------------------------------------------------------
    def _voice_wakeup(self, enable: bool) -> RuntimeResult:
        data = {"type": "voice_interaction", "value": {"enable": enable}}
        uuid = self._mqtt.send_corpus(data)
        state = "开启" if enable else "关闭"
        logger.info(f"InteractionSkill: 语音唤醒{state}")
        return RuntimeResult(success=True, intent="voice",
                             data={"uuid": uuid}, reply=f"语音唤醒已{state}")

    # ------------------------------------------------------------------
    # 音量设置 (CMD 5002)
    # ------------------------------------------------------------------
    def _set_volume(self, params: dict) -> RuntimeResult:
        vol = params.get("volume", 80)
        uuid = self._mqtt.send_volume(vol)
        return RuntimeResult(success=True, intent="volume",
                             data={"uuid": uuid}, reply=f"音量设为 {vol}")

    # ------------------------------------------------------------------
    # 氛围灯 (CMD 5001)
    # ------------------------------------------------------------------
    def _set_led(self, params: dict) -> RuntimeResult:
        rgb = params.get("rgb", [255, 255, 255])
        brightness = params.get("brightness", 128)
        uuid = self._mqtt.send_led(rgb, brightness, 55, 80)
        return RuntimeResult(success=True, intent="led",
                             data={"uuid": uuid}, reply="氛围灯已设置")


