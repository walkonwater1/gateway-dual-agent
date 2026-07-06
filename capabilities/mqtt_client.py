"""
MQTT 客户端 — 严格对齐 Bridge API 协议文档 v0.3。

协议要点:
  - 消息格式: {"uuid": "...", "command": <int>, "commandData": <any>}
  - 动作名: cqm1, cqm2, cqm3
  - 音频名: sch1, sch2, pth1
  - EStop: commandData 为字符串 "1"/"0"
  - 移动: topic=eir/operation_move2, QoS=1
"""

import json
import logging
import uuid
import time

import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)

# ============================================================================
# 指令 ID 常量
# ============================================================================
# 基础指令 (10xx)
CMD_LOCO_MODE = 1001             # 模式切换
CMD_GAIT = 1002                  # 步态切换
CMD_BODY_HEIGHT = 1003           # 身高切换
CMD_OAS = 1004                   # 避障模式
CMD_UWB = 1005                   # UWB 跟随
CMD_ACTION = 1006                # 动作执行 (cqm1/cqm2/cqm3)
CMD_CORPUS = 1007                # 调试/扩展 (general_interface)
CMD_BODY_ORIENTATION = 1008      # 身体姿态调节 (roll/pitch)

# 扩展指令 (20xx) — topic: eir/operation_extension
CMD_NICKNAME = 2001              # 设置昵称
CMD_VOICE_GET_LIST = 2002        # 声纹获取
CMD_VOICE_ENROLL_START = 2003    # 声纹注册开始
CMD_VOICE_ENROLL_END = 2004      # 声纹注册结束
CMD_VOICE_ENROLL_CANCEL = 2005   # 声纹注册取消
CMD_VOICE_DEL = 2006             # 声纹删除

# 移动指令 (30xx) — topic: eir/operation_move2
CMD_MOVE = 3001                  # 移动 [lx,ly,az,swing_height,gait_period]

# 状态指令 (40xx) — 机器人→客户端
CMD_BODY_HEIGHT_STATUS = 4000
CMD_NICK_NAME_STATUS = 4001
CMD_BATTERY_STATUS = 4002
CMD_OBS_STATUS = 4003
CMD_LOCO_MODE_STATUS = 4004
CMD_GAIT_STATUS = 4005
CMD_HOST_STATUS = 4006
CMD_MOTOR_STATUS = 4007
CMD_DRIVER_STATUS = 4008
CMD_OBS_DETECT_STATUS = 4009
CMD_TOPOGRAPHY_STATUS = 4010

# 设置指令 (50xx) — topic: eir/setting
CMD_FACE_ADJUST = 5000           # 视野调整
CMD_SETTING_LED = 5001           # 氛围灯
CMD_SETTING_VOLUME = 5002        # 播报音量
CMD_SETTING_WELCOME = 5003       # 欢迎语
CMD_SETTING_UE_CHANGE = 5004     # UE 动画模式切换
CMD_SETTING_DEFAULT = 5555       # 恢复出厂设置

# SLAM (60xx)
CMD_MAPPING = 6000
CMD_NAVIGATION = 6001
CMD_LOCALIZATION = 6002

# 心跳 (80xx) — topic: eir/basic_heartbeat, QoS=0
CMD_HEARTBEAT = 8000

# 紧急 (90xx) — topic: eir/soft_emergency_stop, QoS=2
CMD_SOFT_ESTOP = 9000

# ============================================================================
# 运动模式枚举
# ============================================================================
LOCO_MODE = {
    "still": 1,          # MODE_STILL — 静止
    "ready": 2,          # MODE_READY — 就绪
    "getup": 3,          # MODE_GETUP — 起身
    "stand": 10,         # MODE_STAND_JOF — 站立
    "ppowalk": 20,       # MODE_PPOWALK
    "ampwalk": 21,       # MODE_AMPWALK
    "qpwalk": 22,        # MODE_QPWALK
}
LOCO_MODE_NAMES = {v: k for k, v in LOCO_MODE.items()}

# 步态枚举
GAIT_MODE = {
    "normal": 1,         # GAIT_NORMAL
    "ramp": 2,           # GAIT_RAMP
    "obstacle": 3,       # GAIT_OBSTACLE
    "stair": 4,          # GAIT_STAIR
    "stair_ramp": 5,     # GAIT_STAIR_RAMP
    "stair_45": 6,       # GAIT_STAIR_45
}

# ============================================================================
# Topic 路由
# ============================================================================
_TOPIC_INSTRUCTIONS = "eir/operation_instructions"     # QoS 1
_TOPIC_EXT = "eir/operation_extension"                  # QoS 2
_TOPIC_MOVE = "eir/operation_move2"                     # QoS 1
_TOPIC_SETTING = "eir/setting"
_TOPIC_SLAM_NAV = "eir/slam_navigation"
_TOPIC_SLAM_MAP = "eir/slam_mapping"
_TOPIC_SLAM_LOC = "eir/slam_localization"
_TOPIC_HEARTBEAT = "eir/basic_heartbeat"                # QoS 0
_TOPIC_ESTOP = "eir/soft_emergency_stop"                # QoS 2


def _route(cmd_id: int) -> tuple[str, int]:
    """返回 (topic, qos)。"""
    if cmd_id in (1001, 1002, 1003, 1004, 1005, 1006, 1007, 1008, 1012):
        return _TOPIC_INSTRUCTIONS, 1
    if cmd_id in (2001, 2002, 2003, 2004, 2005, 2006):
        return _TOPIC_EXT, 2
    if cmd_id == 3001:
        return _TOPIC_MOVE, 1
    if cmd_id in (5000, 5001, 5002, 5003, 5004, 5555):
        return _TOPIC_SETTING, 0
    if cmd_id == 6000:
        return _TOPIC_SLAM_MAP, 2
    if cmd_id == 6001:
        return _TOPIC_SLAM_NAV, 2
    if cmd_id == 6002:
        return _TOPIC_SLAM_LOC, 2
    if cmd_id == 8000:
        return _TOPIC_HEARTBEAT, 0
    if cmd_id == 9000:
        return _TOPIC_ESTOP, 2
    return _TOPIC_INSTRUCTIONS, 1


# ============================================================================
# 客户端
# ============================================================================
class RobotMqttClient:
    """MQTT 客户端，严格按 Bridge API 协议文档 v0.3。"""

    def __init__(self, broker_host: str = "127.0.0.1", broker_port: int = 8899):
        self._host = broker_host
        self._port = broker_port
        self._client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"agent_{uuid.uuid4().hex[:8]}"
        )
        self._connected = False
        self._on_status = None

    # ------------------------------------------------------------------
    # 连接
    # ------------------------------------------------------------------
    def connect(self) -> bool:
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message
        try:
            self._client.connect(self._host, self._port, keepalive=30)
            self._client.loop_start()
            deadline = time.time() + 5.0
            while not self._connected and time.time() < deadline:
                time.sleep(0.1)
            if not self._connected:
                logger.error(f"MQTT 连接超时 ({self._host}:{self._port})")
                return False
            logger.info(f"MQTT 已连接 → {self._host}:{self._port}")
            return True
        except Exception as e:
            logger.error(f"MQTT 连接失败: {e}")
            return False

    def disconnect(self):
        self._client.loop_stop()
        self._client.disconnect()
        self._connected = False

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        if reason_code == 0:
            self._connected = True
            # 订阅状态上报
            client.subscribe("info/often", qos=0)
            client.subscribe("info/setting", qos=0)
            client.subscribe("eir/basic_heartbeat_callback", qos=0)
            logger.info("MQTT 连接成功，已订阅状态主题")
        else:
            logger.error(f"MQTT 连接被拒绝, rc={reason_code}")

    def _on_disconnect(self, client, userdata, flags, reason_code, properties=None):
        self._connected = False
        logger.warning(f"MQTT 断开, rc={reason_code}")

    def _on_message(self, client, userdata, msg):
        if self._on_status:
            self._on_status(msg.topic, msg.payload)

    def on_status(self, callback):
        self._on_status = callback

    # ------------------------------------------------------------------
    # 底层发送
    # ------------------------------------------------------------------
    def send_command(self, cmd_id: int, command_data=None, qos: int = None) -> str:
        msg_uuid = str(uuid.uuid4())
        topic, default_qos = _route(cmd_id)
        if qos is None:
            qos = default_qos

        payload = json.dumps({
            "uuid": msg_uuid,
            "command": cmd_id,
            "commandData": command_data,
        }, ensure_ascii=False)

        self._client.publish(topic, payload, qos=qos)
        logger.info(f"MQTT → [{topic}] cmd={cmd_id} qos={qos} "
                     f"data={json.dumps(command_data, ensure_ascii=False)[:80]}")
        return msg_uuid

    # ------------------------------------------------------------------
    # 动作执行 (1006)
    # ------------------------------------------------------------------
    def send_motion(self, name: str) -> str:
        """执行动作。可用: cqm1, cqm2, cqm3"""
        return self.send_command(CMD_ACTION, name)

    # ------------------------------------------------------------------
    # 移动 (3001) — topic=eir/operation_move2, QoS=1
    # ------------------------------------------------------------------
    def send_move(self, linear_x: float, linear_y: float = 0.0,
                  angular_z: float = 0.0, swing_height: float = 0.1,
                  gait_period: float = 0.5, keep_trotting: bool = False) -> str:
        """遥控移动。

        Args:
            linear_x: 前后线速度 (m/s)，正值前进
            linear_y: 横向线速度 (m/s)
            angular_z: 角速度 (rad/s)，正值左转
            swing_height: 抬腿高度
            gait_period: 步频
            keep_trotting: 保持站立
        """
        data = [linear_x, linear_y, angular_z, swing_height, gait_period]
        msg_uuid = self.send_command(CMD_MOVE, data)
        if keep_trotting:
            # keepTrotting 需要在消息中单独传
            topic, _ = _route(CMD_MOVE)
            payload = json.dumps({
                "uuid": msg_uuid,
                "command": CMD_MOVE,
                "commandData": data,
                "keepTrotting": 1,
            }, ensure_ascii=False)
            self._client.publish(topic, payload, qos=1)
        return msg_uuid

    # ------------------------------------------------------------------
    # 运动模式 (1001)
    # ------------------------------------------------------------------
    def send_loco_mode(self, mode) -> str:
        """切换运动模式。mode 可以是 int 或字符串名。"""
        if isinstance(mode, str):
            mode = LOCO_MODE.get(mode.lower(), 2)
        return self.send_command(CMD_LOCO_MODE, mode)

    # ------------------------------------------------------------------
    # 步态切换 (1002)
    # ------------------------------------------------------------------
    def send_gait(self, gait) -> str:
        """切换步态。gait 可以是 int 或字符串名。"""
        if isinstance(gait, str):
            gait = GAIT_MODE.get(gait.lower(), 1)
        return self.send_command(CMD_GAIT, gait)

    # ------------------------------------------------------------------
    # 身高 (1003)
    # ------------------------------------------------------------------
    def send_body_height(self, height: float) -> str:
        """调节身高（0.0~1.0）。"""
        return self.send_command(CMD_BODY_HEIGHT, height)

    # ------------------------------------------------------------------
    # 避障 (1004)
    # ------------------------------------------------------------------
    def send_oas(self, enable: bool) -> str:
        """避障开关。enable=True→避障, False→停障"""
        return self.send_command(CMD_OAS, 0 if enable else 1)

    # ------------------------------------------------------------------
    # UWB 跟随 (1005)
    # ------------------------------------------------------------------
    def send_uwb(self, enable: bool) -> str:
        """UWB 跟随开关。"""
        return self.send_command(CMD_UWB, 1 if enable else 0)

    # ------------------------------------------------------------------
    # 姿态调节 (1008)
    # ------------------------------------------------------------------
    def send_body_orientation(self, roll: float, pitch: float) -> str:
        """调节身体姿态。"""
        return self.send_command(CMD_BODY_ORIENTATION, {"roll": roll, "pitch": pitch})

    # ------------------------------------------------------------------
    # 语料 / general_interface (1007)
    # ------------------------------------------------------------------
    def send_corpus(self, data) -> str:
        """发送 general_interface JSON。"""
        return self.send_command(CMD_CORPUS, data)

    # ------------------------------------------------------------------
    # 急停 (9000) — commandData 为字符串 "1"/"0" !
    # ------------------------------------------------------------------
    def send_estop(self, enable: bool = True) -> str:
        """急停/解除。"""
        return self.send_command(CMD_SOFT_ESTOP, "1" if enable else "0")

    # ------------------------------------------------------------------
    # 导航 (6001)
    # ------------------------------------------------------------------
    def send_navigation(self, params: dict) -> str:
        return self.send_command(CMD_NAVIGATION, params)

    # ------------------------------------------------------------------
    # 设置
    # ------------------------------------------------------------------
    def send_led(self, rgb: list, brightness: int, duty_cycle: int, period: int) -> str:
        """设置氛围灯。"""
        return self.send_command(CMD_SETTING_LED, {
            "ambient_light": {
                "rgb": rgb,
                "brightness": brightness,
                "duty_cycle": duty_cycle,
                "period": period,
            }
        })

    def send_volume(self, volume: int) -> str:
        """设置播报音量 (0-100)。"""
        return self.send_command(CMD_SETTING_VOLUME, {
            "audio": {"output": {"volume": volume}}
        })

    def send_welcome(self, greeting: str) -> str:
        """设置开机欢迎语。"""
        return self.send_command(CMD_SETTING_WELCOME, {
            "interaction": {"wakeup": {"greetings": greeting}}
        })

    def send_face_adjust(self, value: float) -> str:
        """视野调整。"""
        return self.send_command(CMD_FACE_ADJUST, value)

    # ------------------------------------------------------------------
    # 心跳 (8000)
    # ------------------------------------------------------------------
    def send_heartbeat(self) -> str:
        return self.send_command(CMD_HEARTBEAT, None)

    # ------------------------------------------------------------------
    # 属性
    # ------------------------------------------------------------------
    @property
    def is_connected(self) -> bool:
        return self._connected
