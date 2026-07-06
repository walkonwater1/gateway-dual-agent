"""
导航技能 — 封装导航相关 MQTT 指令。

对应设计文档 skills/ 中的导航类 Skill。
当前为占位实现，待 Bridge 导航接口完善后对接真实导航。
"""

import logging

from capabilities.mqtt_client import RobotMqttClient
from shared.base import BaseSkill
from shared.message import RuntimeResult

logger = logging.getLogger(__name__)


class NavigationSkill(BaseSkill):
    """导航能力。当前为占位，桥接 CMD_NAVIGATION(6001)。"""

    def __init__(self, mqtt: RobotMqttClient):
        self._mqtt = mqtt

    def execute(self, intent: str, params: dict) -> RuntimeResult:
        # 当前只透传导航参数，具体点到点导航需后续完善
        msg_uuid = self._mqtt.send_navigation(params)
        logger.info(f"NavigationSkill: 导航 params={params} (uuid={msg_uuid})")
        return RuntimeResult(
            success=True,
            intent="navigation",
            data={"uuid": msg_uuid},
            reply=f"导航任务已下发 (uuid={msg_uuid})",
        )
