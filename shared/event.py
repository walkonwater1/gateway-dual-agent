"""
Runtime 间事件 — 通过 Event Bus 广播。

对应设计文档 shared/event.py。
"""

from dataclasses import dataclass, field
import time
import uuid


@dataclass
class RuntimeEvent:
    """Runtime 间事件，通过 Gateway Event Bus 广播。

    典型场景：
      - Navigation Runtime 发布导航进度 → Interaction Runtime 播报
      - Motion Runtime 发布动作完成 → Gateway 更新 Session 状态
      - Safety Gate 发布急停事件 → 所有 Runtime 收到通知
    """

    event_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    event_type: str = ""          # 如 "navigation.progress" / "motion.completed" / "safety.estop"
    source_runtime: str = ""      # 发布事件的 Runtime 名
    payload: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    # ------------------------------------------------------------------
    # 预定义事件类型常量
    # ------------------------------------------------------------------
    NAV_PROGRESS = "navigation.progress"
    NAV_COMPLETED = "navigation.completed"
    NAV_ERROR = "navigation.error"

    MOTION_STARTED = "motion.started"
    MOTION_COMPLETED = "motion.completed"
    MOTION_ERROR = "motion.error"

    SAFETY_ESTOP = "safety.estop"
    SAFETY_ESTOP_RELEASED = "safety.estop_released"

    INTERACTION_TTS_START = "interaction.tts_start"
    INTERACTION_TTS_END = "interaction.tts_end"

    ROBOT_STATUS = "robot.status"
    ROBOT_BATTERY_LOW = "robot.battery_low"

    @classmethod
    def create(cls, event_type: str, source_runtime: str,
               payload: dict | None = None) -> "RuntimeEvent":
        return cls(
            event_type=event_type,
            source_runtime=source_runtime,
            payload=payload or {},
        )
