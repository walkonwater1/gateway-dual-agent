# Gateway + Multi-Agent AI 开发实施路线图

## 1. 文档说明

本文档将 `file_framework.md`（Agent Runtime 架构）和 `gateway_readme.md`（Gateway 专项设计）与当前代码现状对接，给出具体的实施路径。

### 相关文档

- [file_framework.md](./file_framework.md) — Robot Agent Runtime 完整架构设计
- [gateway_readme.md](./gateway_readme.md) — Gateway 模块专项设计

---

## 2. 完整架构全景图

```
┌──────────────────────────────────────────────────┐
│  agent_runtime/ (Python, 待新建)                 │
│  Gateway / Runtimes / Agents / Skills            │
│  Knowledge / Memory / Harness                    │
│  部署位置: 云端或机器人伴算计算机                  │
│  通信方式: MQTT (mosquitto)                      │
└──────────────────┬───────────────────────────────┘
                   │ MQTT (JSON, 命令ID + UUID)
                   ▼
┌──────────────────────────────────────────────────┐
│  eir_communication_bridge (C++, 已有)             │
│  robot_local_communication_server (ROS2 Node)     │
│  职责: MQTT ↔ ROS2 topic 透明中继                │
│  部署位置: 机器人主控                             │
└──────────────────┬───────────────────────────────┘
                   │ ROS2 topics (/eir/hl/*)
                   ▼
┌──────────────────────────────────────────────────┐
│  ehr_ros_app (C++, 已有)                         │
│  PublicInterfaceManager 订阅 /eir/hl/* topics    │
│  Manager / Voice|Motion|Expression|Emotion        │
│  部署位置: 机器人主控 (Orin)                      │
└──────────────────┬───────────────────────────────┘
                   │ Public API (ehr_*.h)
                   ▼
┌──────────────────────────────────────────────────┐
│  ehr_app_core (C++, 已有)                        │
│  TaskManager / ResourceManager / StateMachine     │
│  audio / voice / motion / nav / vla               │
│  部署位置: 机器人主控 (Orin)                      │
└──────────────────────────────────────────────────┘
```

**关键认知：**
- Agent Runtime 层通过 **MQTT** 与机器人通信，不是 gRPC
- Bridge 是 **透明中继**，不包含业务逻辑，只做 MQTT↔ROS2 转换
- Agent Runtime 可以部署在**云端**或**机器人伴算计算机**上，只要网络能通 MQTT broker

---

## 3. 已有仓库与能力

### 3.1 仓库矩阵

| 仓库 | 语言 | 状态 | 说明 |
|------|------|------|------|
| `ehr_app_core` | C++ | ✅ | 能力 SDK，语音/运动/导航/VLA/表情/安全 |
| `ehr_ros_app` | C++ | ✅ | 业务编排层，订阅 `/eir/hl/*` 执行机器人操作 |
| `eir_communication_bridge` | C++ | ✅ | MQTT↔ROS2 中继，cloud↔robot 通信桥梁 |
| Agent Runtime | Python | ❌ 待新建 | Gateway + Runtime + Agent 层 |

### 3.2 Bridge 详解 (`eir_communication_bridge`)

**身份：** ROS2 包 `robot_local_communication_server`，一个 `rclcpp::Node`

**通信协议：** MQTT (mosquitto broker)，QoS 支持 0/1/2

**消息格式：** JSON，统一结构：
```json
{
  "command": 1006,
  "uuid": "a1b2c3d4-e5f6-...",
  "commandData": "wave"
}
```

**已支持的机器人指令（完整清单）：**

| 命令ID | 功能 | commandData 格式 | 对应 ROS2 Topic |
|--------|------|-----------------|-----------------|
| 1001 | 切换运动模式 | `uint8` (LocoMode) | `/eir/hl/loco_mode_switch` |
| 1003 | 调节身体高度 | `float` | `/eir/hl/body_height_adjust` |
| 1004 | 避障开关 | `uint8` | `/eir/hl/oas_logic_switch` |
| 1005 | UWB 开关 | `int` | `/eir/hl/uwb_enable_ctrl` |
| **1006** | **执行动作** | `string` (动作名) | `/eir/hl/motion_playback` |
| **1007** | **语料/对话** | JSON (intent+param) | `/eir/general_interface` |
| 1008 | 调整姿态 | `{roll, pitch}` | `/eir/hl/body_orientation_cmd` |
| 1012 | 诊断告警检查 | `int` | `/eir/diagnostic_alerts_check` |
| 2001 | 设置昵称 | `string` | 本地处理 |
| 2002-2006 | 声纹管理 | `string` | `/eir/hl/voiceprint_manage` |
| **3001** | **遥控移动** | `[lx,ly,az,swing,gait]` | `/eir/hl/move2` |
| 5000 | 数位人视角调节 | `float` | `/eir/hl/face_adjust` |
| 5001-5555 | 设置 (LED/音量/欢迎语/模式) | JSON | `/eir/update_config` |
| **6000** | **建图控制** | JSON | `/eir/slam_mapping` |
| **6001** | **导航控制** | JSON | `/eir/slam_navigation` |
| 6002 | 定位控制 | JSON | `/eir/slam_localization` |
| 8000 | 心跳 | - | `/eir/basic_heartbeat` |
| 9000 | 软急停 | - | `/eir/hl/soft_estop_ctrl` |

**状态上报（机器人→云端）：**

| 上报 | MQTT Topic | 内容 |
|------|-----------|------|
| 高频状态 | `info/often` | 电池、里程、loco mode、硬件状态 |
| 心跳回传 | `eir/basic_heartbeat_callback` | 心跳应答 |
| 建图进度 | `eir/slam_map_opt_progress` | 建图优化进度 |
| 定位状态 | `eir/slam_localization_state` | 定位状态变化 |
| 导航错误 | `eir/slam_nav_global_error` | 导航全局错误 |

**Bridge 不做什么：**
- 不做意图理解、不做业务编排
- 不做状态机判断、不做安全检查
- 只是把 MQTT JSON 原样转成 ROS2 message 发布出去

---

## 4. 实施阶段

### Phase 1: MVP — 打通完整链路

**目标：** `文本 → Gateway → Interaction Runtime → LLM → MQTT指令 → 机器人动作`

**前提：** MQTT broker 已在机器人上运行（mosquitto，端口 8899）

**Python 侧需新建（放在 `ros2_ws/ehr_ros_app/agent/` 或独立目录）：**

```
agent/
├── main.py                          # 启动入口
├── shared/
│   ├── message.py                   # RuntimeMessage 统一协议
│   ├── result.py                    # RuntimeResult
│   ├── trace.py                     # TraceContext
│   ├── session.py                   # Session
│   └── base_agent.py                # Agent 基类
├── gateway/
│   ├── gateway.py                   # handle_text() 入口
│   ├── input_adapter.py             # 文本→初始事件
│   ├── message_normalizer.py        # 封装 RuntimeMessage
│   ├── router.py                    # Phase 1: 固定路由到 Interaction
│   └── runtime_router.py            # 调用 Runtime
├── runtimes/
│   └── interaction_runtime/
│       ├── runtime.py
│       └── agent_router.py
├── agents/
│   └── interaction_agents/
│       └── dialogue_agent/
│           ├── agent.py             # LLM 对话 + 意图→MQTT指令映射
│           └── prompts.py           # System prompt
├── capabilities/
│   └── mqtt_client.py               # MQTT 客户端（paho-mqtt）
│                                     # 封装 send_command() / subscribe_status()
└── configs/
    └── gateway.yaml                 # MQTT broker 地址、LLM 配置等
```

**Phase 1 核心代码示意：**

```python
# capabilities/mqtt_client.py
import paho.mqtt.client as mqtt
import json, uuid

class RobotMqttClient:
    def __init__(self, broker_host="127.0.0.1", broker_port=8899):
        self.client = mqtt.Client()
        self.client.connect(broker_host, broker_port)
        self.client.loop_start()

    def send_command(self, command_id: int, command_data) -> str:
        """发送指令到机器人, 返回 uuid"""
        msg_uuid = str(uuid.uuid4())[:19]
        payload = json.dumps({
            "command": command_id,
            "uuid": msg_uuid,
            "commandData": command_data
        })
        # 根据命令类型选择 MQTT topic
        topic = self._topic_for(command_id)
        self.client.publish(topic, payload, qos=2)
        return msg_uuid

    def _topic_for(self, command_id: int) -> str:
        if command_id in (1001, 1003, 1004, 1005, 1006, 1007, 1008, 1012):
            return "eir/operation_instructions"
        if command_id == 3001:
            return "eir/operation_move2"
        if command_id in (6000, 6001, 6002):
            return "eir/slam_navigation"  # 具体按类型再分
        return "eir/operation_instructions"
```

```python
# agents/dialogue_agent/agent.py
class DialogueAgent:
    SYSTEM_PROMPT = """你是一个机器人助手。根据用户输入判断意图并输出JSON:
    {"intent": "chat|motion|navigation|move|stop", "params": {...}}
    
    可用动作 motion: wave(挥手), nod(点头), dance(跳舞)
    可用导航 navigation: {"position": "地点名"}
    可用移动 move: {"lx": 0.5, "ly": 0, "az": 0}
    """

    def handle(self, message: RuntimeMessage) -> RuntimeResult:
        text = message.payload["text"]
        
        # 调 LLM 判断意图
        llm_response = self.call_llm(text)
        intent = llm_response["intent"]
        params = llm_response["params"]
        
        # 映射到 Bridge 指令
        if intent == "motion":
            mqtt.send_command(1006, params["name"])      # CMD_ACTION
        elif intent == "navigation":
            mqtt.send_command(6001, params)               # CMD_NAVIGATION
        elif intent == "move":
            mqtt.send_command(3001, [params["lx"], params["ly"], params["az"]])
        elif intent == "stop":
            mqtt.send_command(9000, 1)                    # CMD_SOFT_ESTOP
        
        return RuntimeResult(success=True, ...)
```

**Phase 1 数据流：**

```
用户文本 "挥手"
  → Gateway.handle_text()
  → MessageNormalizer → RuntimeMessage{trace_id, payload: {text: "挥手"}}
  → Router → "interaction_runtime"
  → DialogueAgent: LLM 返回 {intent: "motion", params: {name: "wave"}}
  → mqtt_client.send_command(1006, "wave")
  → MQTT publish: {"command":1006, "uuid":"...", "commandData":"wave"}
  → Bridge 收到 → 发布 /eir/hl/motion_playback → PublicInterfaceManager → ehr_app_core
  → 机器人挥手
```

**Phase 1 不做的：**
- Session 多用户隔离
- Priority/Safety/Conflict
- Event Bus / 状态订阅
- Navigation/Motion Runtime（Phase 1 由 DialogueAgent 直接发 MQTT 指令）

---

### Phase 2: 三 Runtime 分流 + 状态感知

**新增：**

1. **关键词路由 → LLM Router 升级：**
```python
# gateway/router.py
route_policy = {
    "navigation_runtime": ["带我去", "导航到", "前往", "去"],
    "motion_runtime":      ["挥手", "点头", "转身", "跳舞"],
    "interrupt":           ["停", "停止", "别动", "暂停"],
}
# 默认 → interaction_runtime
# 后续可用小模型或 LLM 做语义路由
```

2. **MQTT 状态订阅：** Agent 层订阅 `info/often` 获取电池/里程/运动模式等机器人状态，让 Agent 做决策时感知上下文

3. **新增 Navigation/Motion Runtime + Agent：**
```
runtimes/
├── navigation_runtime/
│   ├── runtime.py                   # 导航任务编排
│   └── agent_router.py
└── motion_runtime/
    ├── runtime.py                   # 动作任务编排
    └── agent_router.py

agents/
├── navigation_agents/
│   └── navigation_task_agent/       # 导航目标解析、路径确认
└── motion_agents/
    └── motion_planner_agent/        # 动作选择、序列编排
```

**核心规则：跨 Runtime 通信必须走 Gateway，禁止 Runtime 间直接互调。**

---

### Phase 3: 治理能力

按 `gateway_readme.md` 的纵向扩展路线：

| Step | 模块 | 功能 |
|------|------|------|
| 3 | Session Router | 多用户上下文隔离 |
| 4 | Priority Manager | 急停(9000) > 遥操 > 安全 > 导航 > 交互 |
| 5 | Safety Gate | 请求级过滤，拦截"冲过去"等危险指令 |
| 6 | Trace Logger | 全链路 trace_id 记录 |
| 7 | 配置化路由 | YAML 加载，路由规则可配置 |
| 8 | Conflict Resolver | 导航中要求跳舞 → 判断优先级 |
| 9 | Event Bus | Runtime 间状态广播 |
| 10 | Result Aggregator | "带我去X并介绍" → 多 Runtime 并行+汇聚 |

---

### Phase 4: Knowledge + Memory + Harness

- `knowledge/` — RAG 知识库（展览信息、FAQ）
- `memory/` — 四层记忆（工作记忆 → 短期 → 本地长期 → 云端长期）
- `harness/` — 仿真回放测试（录制 MQTT 消息回放，不上真机验证链路）

---

## 5. 关键架构决策

### 5.1 通信协议: MQTT + JSON

Bridge 使用的是 mosquitto MQTT broker + JSON 消息，不是 gRPC。Agent 层选择 paho-mqtt 即可，Python 生态成熟，无需编译 proto。

### 5.2 Agent 层部署位置

Agent Runtime 可部署在**云端**（低延迟网络环境）或**机器人伴算计算机**上。MQTT broker 在机器人本地（`127.0.0.1:8899`），如果 Agent 在云端需要桥接 MQTT 到公网。

### 5.3 Gateway 保持薄中枢

Gateway 只做：接入 → 标准化 → 路由 → 仲裁 → 安全 → Trace。
不调用 LLM、不做知识检索、不做路径规划。

### 5.4 当前 Manager 保留为 fallback

`manager.cpp` 中硬编码的 intent 处理保留。当 Agent 层不可用时，C++ 侧仍可通过 MQTT 指令执行基本技能。

### 5.5 Agent 不直接控制底层

```
Agent Runtime：任务级决策、行为级决策、Skill 调度
Bridge + ehr_ros_app + ehr_app_core：指令中继 + 执行
机器人本体控制：轨迹执行、控制执行、电机级执行
```

### 5.6 Knowledge ≠ Memory

```
Knowledge：公共知识（展览信息、FAQ），写入和读取权限集中管控
Memory：用户相关信息（偏好、上下文、历史交互），四层分级治理
```

---

## 6. 当前最优先的任务

| # | 任务 | 说明 | 预计工作量 |
|---|------|------|-----------|
| 1 | 确认 MQTT broker 连通性 | 从 Agent 部署环境能否 ping 通 mosquitto (端口 8899) | 0.5 天 |
| 2 | 实现 `capabilities/mqtt_client.py` | Python MQTT 客户端，封装 send_command / subscribe_status | 1 天 |
| 3 | 实现 `shared/message.py` + `gateway/gateway.py` | 统一消息协议 + Gateway 主链路 | 1 天 |
| 4 | 实现 `agents/dialogue_agent/agent.py` | LLM 意图识别 + MQTT 指令映射 | 2-3 天 |
| 5 | 端到端集成测试 | `文本输入 → MQTT → 机器人动作` 全链路验证 | 1 天 |

---

## 7. 参考：Bridge 完整指令速查表

### 运动控制 (topic: `eir/operation_instructions`)

| CMD | 功能 | commandData |
|-----|------|-------------|
| 1001 | 切换运动模式 | `uint8` |
| 1003 | 身体高度 | `float` |
| 1004 | 避障开关 | `uint8` |
| 1005 | UWB 开关 | `int` |
| **1006** | **执行动作** | **`string` (动作名)** |
| **1007** | **语料/对话** | **JSON** |
| 1008 | 姿态调整 | `{roll, pitch}` |
| 1012 | 诊断检查 | `int` |

### 移动控制 (topic: `eir/operation_move2`)

| CMD | 功能 | commandData |
|-----|------|-------------|
| 3001 | 遥控移动 | `[lx, ly, az, swing_height, gait_period]` |

### 导航与建图 (topic: `eir/slam_navigation` / `eir/slam_mapping` / `eir/slam_localization`)

| CMD | 功能 | commandData |
|-----|------|-------------|
| 6000 | 建图 | JSON |
| 6001 | 导航 | JSON |
| 6002 | 定位 | JSON |

### 设置 (topic: `eir/setting`)

| CMD | 功能 | commandData |
|-----|------|-------------|
| 5000 | 数位人视角 | `float` |
| 5001 | LED 设置 | JSON |
| 5002 | 音量设置 | JSON |
| 5003 | 欢迎语 | JSON |
| 5555 | 恢复默认 | JSON |

### 安全 (topic: `eir/soft_emergency_stop`)

| CMD | 功能 | commandData |
|-----|------|-------------|
| 9000 | 软急停 | `int` |

### 声纹管理 (topic: `eir/operation_extension`)

| CMD | 功能 |
|-----|------|
| 2002 | 获取声纹列表 |
| 2003 | 开始注册 |
| 2004 | 完成注册 |
| 2005 | 取消注册 |
| 2006 | 删除声纹 |

---

## 8. 参考：设计文档典型任务链路（MQTT 版本）

### 8.1 动作执行

```
用户: "挥个手"
  → Gateway → Interaction Runtime
  → DialogueAgent: LLM 判断 intent=motion:wave
  → mqtt_client.publish("eir/operation_instructions",
       {"command":1006, "uuid":"...", "commandData":"wave"})
  → Bridge → /eir/hl/motion_playback → 机器人挥手
```

### 8.2 导航任务

```
用户: "带我去爱湫展区"
  → Gateway → Interaction Runtime: 确认意图
  → Gateway → Navigation Runtime
  → NavigationAgent: 解析目标 + 发起导航
  → mqtt_client.publish("eir/slam_navigation",
       {"command":6001, "uuid":"...", "commandData":{...}})
  → Bridge → ROS2 → ehr_app_core 执行导航
  → 状态通过 info/often 回传 → Agent 播报进度
```

### 8.3 复杂组合任务

```
用户: "带我去爱湫展区，边走边介绍，到了做个欢迎动作"
  → Gateway → Interaction Runtime: LLM 拆解为三个子任务
  → [子任务1] Navigation Runtime: 发起导航
  → [子任务2] Interaction Runtime: 边走边讲解（监听导航进度）
  → [子任务3] Motion Runtime: 到达后 CMD_ACTION "welcome"
  → Gateway: 持续同步状态、处理冲突
```

---

## 9. Bridge 接口差距分析

### 9.1 当前状态

Bridge 目前已暴露了核心的运动控制、导航、安全等能力，但通过对比 `eir_communication_bridge`（MQTT→ROS2）和 `ehr_ros_app`（ROS2→SDK API）两端的代码，发现部分能力**存在于 ehr_ros_app 但未通过 Bridge 暴露给 Agent 层**。

**关键发现：差距分为两个层级。** 部分能力 Bridge 只需新增 MQTT 指令即可（ROS2 topic 已存在）；但另一些能力连 ROS2 topic 都没有——它们通过内部 UDP 或直接调用 ehr_app_core SDK 实现，完全绕过了 ROS2 层。后者需要先在 ehr_ros_app 中新建 ROS2 接口，然后 Bridge 才能暴露。

```
能力层级示意：

① 有 ROS2 topic，缺 Bridge 指令  →  只改 Bridge 即可
② 无 ROS2 topic，走内部 SDK/UDP  →  需先改 ehr_ros_app，再改 Bridge
```

### 9.2 差距明细

#### A. Bridge 已有但 ROS 侧未对接（指令无效）

| Bridge CMD | 功能 | Bridge 发布的 ROS2 Topic | 问题 |
|-----------|------|------------------------|------|
| 1004 | 避障开关(OAS) | `/eir/hl/oas_logic_switch` | PublicInterfaceManager **未订阅此 topic**（可能由其他节点消费，需确认） |
| 1012 | 诊断告警检查 | `/eir/diagnostic_alerts_check` | PublicInterfaceManager **未订阅此 topic**（可能由其他节点消费，需确认） |

#### B. 仅需扩展 Bridge（ROS2 topic 已存在）

这些能力在 ehr_ros_app 中已有 ROS2 接口，Bridge 只需新增对应的 MQTT 命令即可：

| 缺失能力 | ROS2 接口 | 建议新 CMD | 优先级 |
|---------|----------|-----------|--------|
| **颈部/头部控制** | `/eir/neck_ctrl_cmd` (yaw/pitch/roll) | 1009 | 高 |
| **配置查询** | `query_config` ROS2 服务 | 新增 eir/setting 响应处理 | 低 |

#### C. 需先改 ehr_ros_app，再改 Bridge（无 ROS2 topic，走内部 SDK/UDP）

这些能力目前**完全绕过了 ROS2 层**，通过内部 UDP 套接字或直接调用 ehr_app_core SDK 实现。Agent 要能调用，需要先在 ehr_ros_app 中新建 ROS2 接口，然后 Bridge 新增 MQTT 指令：

| 缺失能力 | 当前实现方式 | 缺失的 ROS2 接口 | 优先级 |
|---------|------------|-----------------|--------|
| **TTS 语音合成** | `VoiceManager::GenerateTts(text)` 直接调用 SDK，无 topic | 需新建 `/eir/hl/tts` topic 或 service | **高** |
| **运动暂停/恢复/停止** | `MotionManager::PauseMotion()` / `ResumeMotion()` / `StopMotion()` 直接调用 SDK | 需新建 `/eir/hl/motion_control` topic | **高** |
| **情绪/表情切换** | `EmotionManager` 通过 UDP(端口1035) → UE 情绪引擎，`ExpressionManager` 通过 UDP(端口1036) → UE 渲染引擎，均绕过 ROS2 | 需新建 `/eir/hl/emotion` topic | **高** |
| **表情播放** | `ExpressionManager::PlayExpression(id)` / `SwitchMesh(id)` 内部 UDP | 需新建 `/eir/hl/expression` topic | 中 |
| **VLA(视觉语言动作)** | 头文件引用了 `high_level_vla_cmd`，但无实现 | 需实现订阅逻辑 | 低 |

> **注意：** C 类是真正的瓶颈。表情和情绪引擎通过 UDP 直连 UE 渲染引擎，这条链路完全不在 ROS2 体系中，Bridge 根本看不到。Agent 如果想控制机器人表情和情绪，需要在 ehr_ros_app 的 PublicInterfaceManager 中新增订阅，作为 UDP 调用的桥梁。

#### D. general_interface 通道能力浪费

`/eir/general_interface` 是一个灵活的 JSON 通道，PublicInterfaceManager 已支持多种 `type`：

```cpp
// public_interface_manager.cpp 已支持的 JSON type
"play_audio_random"       // 随机播放音频
"voice_interaction"       // 开关语音唤醒
"switch_emotion_random"   // 随机切换情绪
"play_specific_audio"     // 播放指定音频文件
```

但 Bridge 的 `CMD_CORPUS (1007)` 只把 `commandData` 当作语料文本转发，Agent 无法使用上述 type。**`general_interface` 本质上是 ehr_ros_app 最灵活的外部控制入口，但 Bridge 未将其能力充分暴露。**

#### E. 遥测差距（机器人→Agent 方向）

以下数据 ehr_ros_app 有发布，但 Bridge 未订阅并转发给 Agent，导致 Agent 缺少重要的上下文感知能力：

| ROS2 Topic | 消息类型 | 内容 | 对 Agent 的价值 |
|-----------|---------|------|---------------|
| `/eir/vad_state` | VadState | 是否检测到语音活动 | 判断用户是否在说话，决定 Agent 是否插话 |
| `/eir/head_key_event` | HeadKeyEvent | 头部物理按键事件 | 用户通过物理按键交互（音量调节等） |
| `/eir/ultrasonic_sensor` | UltrasonicArray | 超声波距离数据 | 感知周围障碍物 |
| `/eir/hl/uwb_enable_state` | Bool | UWB 模式启用状态 | 判断当前是否在 UWB 遥控模式 |

### 9.3 解决路径

> **核心认知：** Gap 修复的工作量取决于能力属于 B 类（仅改 Bridge）还是 C 类（先改 ehr_ros_app，再改 Bridge）。C 类能力需要两个仓库协作才能完成。

#### 方案 A：扩展 Bridge（推荐）

**仅适用于 B 类差距**（ROS2 topic 已存在），直接新增 MQTT 指令即可：

| 新增 CMD | 功能 | MQTT Topic | ROS2 目标 | 差距类型 |
|---------|------|-----------|----------|---------|
| 1009 | 颈部控制 | `eir/operation_instructions` | `/eir/neck_ctrl_cmd` | B |
| 1007(改造) | general_interface 全功能透传 | `eir/operation_instructions` | `/eir/general_interface` JSON 透传 | D |
| — | 配置查询 | `eir/setting`(改造) | `query_config` 服务 | B |

**适用于 C 类差距**（无 ROS2 topic），需先在 ehr_ros_app 中新建 ROS2 接口，再在 Bridge 中新增指令：

| 新增 CMD | 功能 | 需先在 ehr_ros_app 中新建 | 再在 Bridge 中新增 |
|---------|------|------------------------|-----------------|
| 1010 | 情绪切换 | PublicInterfaceManager 订阅 `/eir/hl/emotion` → 调用 `SetEmotionType()` | CMD_EMOTION → `/eir/hl/emotion` |
| 1011 | TTS 语音 | PublicInterfaceManager 订阅 `/eir/hl/tts` → 调用 `GenerateTts()` | CMD_TTS → `/eir/hl/tts` |
| 1013 | 运动控制(暂停/恢复/停止) | PublicInterfaceManager 订阅 `/eir/hl/motion_control` → 调用 `Pause/Resume/StopMotion()` | CMD_MOTION_CTRL → `/eir/hl/motion_control` |
| 1014 | 表情播放 | PublicInterfaceManager 订阅 `/eir/hl/expression` → 调用 `PlayExpression()` | CMD_EXPRESSION → `/eir/hl/expression` |

同时修复 A 类问题（确认 1004/1012 的实际消费方，如果是死信令则补充订阅或移除）。

**优点：**
- Agent 层只需维护一种通信方式（MQTT）
- 后续新增能力走统一模式，易扩展
- Bridge 本身定位就是"透明中继"，新增指令是自然扩展

**缺点：**
- C 类能力需同时修改 ehr_ros_app 和 Bridge 两个仓库
- 依赖 Bridge 仓库的修改权限和发布节奏
- 需要和 Bridge 维护方协商接口定义

**优点：**
- Agent 层只需维护一种通信方式（MQTT）
- 后续新增能力走统一模式，易扩展
- Bridge 本身定位就是"透明中继"，新增指令是自然扩展

**缺点：**
- 依赖 Bridge 仓库的修改权限和发布节奏
- 需要和 Bridge 维护方协商接口定义

#### 方案 B：Agent 混合通信

Agent 层同时走 MQTT（已有指令）+ ROS2 bridge（缺失能力），例如用 `rosbridge_suite` 或直接引入 `rclpy`：

```
Agent (Python)
  ├── MQTT (paho-mqtt)      → 已有指令（运动/导航/安全）
  └── ROS2 (rclpy/rosbridge) → 缺失能力（颈部/情绪/VLA/音频）
```

**优点：**
- 不依赖 Bridge 仓库修改，Agent 侧可独立推进
- 能立即用上所有 ehr_ros_app 已实现的能力

**缺点：**
- Agent 需维护两套通信栈，增加复杂度
- 部署环境需要 ROS2 运行时（`rclpy` 依赖）
- 两套通信的身份认证、断线重连需独立处理
- 与"Bridge 作为统一对外接口"的架构设计背道而驰

#### 方案 C：ehr_ros_app 内新增轻量 MQTT

在 ehr_ros_app 进程内直接嵌入 MQTT 客户端，旁路 Bridge，自主暴露完整接口：

```
Agent (Python) → MQTT → ehr_ros_app 内置 MQTT → 直接调用所有 SDK
```

**优点：**
- 不需要 Bridge 修改，不需要 Agent 引入 ROS2
- ehr_ros_app 团队可自主控制接口

**缺点：**
- 架构侵入性强，需要在 C++ ROS2 进程中嵌入 MQTT 逻辑
- 可能出现 Bridge MQTT 和 ehr_ros_app MQTT 两套消息体系的混乱
- 安全相关逻辑（estop 等）在 Bridge 中已有，需在 ehr_ros_app 中重复实现

### 9.4 近期建议

1. **短期（无需改代码，验证+绕过）**：
   - 测试 `CMD_CORPUS (1007)` 的实际转发行为——如果 Bridge 对 commandData 是原样 JSON 透传，Agent 可直接构造 `{"type": "play_specific_audio", "value": {"name": "xxx"}}` 来利用 general_interface 通道
   - 确认 1004(OAS) 和 1012(诊断) 的实际消费方——这两个 topic 可能被 ehr_ros_app 之外的其他节点订阅，如果确实是死信令，记录并规划修复

2. **中期（B 类优先 — 只改 Bridge）**：
   - 补齐仅需 Bridge 修改的高价值指令：颈部控制(1009)、general_interface 全能力透传(1007改造)
   - 新增遥测回传：VAD 状态、头部按键事件等，让 Agent 具备上下文感知
   
3. **中期（C 类 — 需两仓库协作）**：
   - **第一步（ehr_ros_app）**：在 PublicInterfaceManager 中新增订阅 `/eir/hl/tts`、`/eir/hl/motion_control`、`/eir/hl/emotion`，桥接内部 SDK/UDP 调用到 ROS2
   - **第二步（Bridge）**：新增对应的 MQTT 命令 ID 和转发逻辑
   - 建议优先做 TTS 和运动控制（暂停/恢复/停止），因为这两个对 Agent 交互体验影响最大

4. **长期**：建立规范的 Bridge 接口扩展流程，ehr_ros_app 每新增一个 PublicInterface 能力，同步规划 Bridge 指令的配套更新

---

## 10. 架构问题：PublicInterfaceManager 并非统一入口

### 10.1 问题概述

从外部看，架构应该是：

```
Agent → MQTT → Bridge → PublicInterfaceManager → 所有子系统 → ehr_app_core
```

但实际代码中，**PublicInterfaceManager 只是多个控制路径之一**，并非统一入口。

### 10.2 实际架构

`ehr_ros_app` 内部由多个独立的 ROS2 Node 组成，各自有独立的 topic/service 接口：

```
ehr_ros_app (进程)
  │
  ├── PublicInterfaceManager (Node: "high_level_api")
  │   → 订阅 /eir/hl/* 外部指令
  │   → 调用 motion/body/face/safety 相关 API
  │   → 不控制 emotion, expression, neck, TTS
  │
  ├── VoiceManager (Node: "voice_manager")  
  │   → Service: /eir/hl/voiceprint_manage
  │   → 内部: TTS, ASR, Wakeup, DoA, VAD
  │   → 回调驱动 expression_manager_ 播放音频
  │
  ├── EmotionManager (Node: "emotion_engine")
  │   → 订阅 /eir/emotion_state
  │   → UDP(端口1035) → UE 情绪引擎
  │   → 回调驱动 motion + expression 切换情绪
  │
  ├── MotionManager (独立实例，非 Node)
  │   → 被 PublicInterfaceManager 和内部回调同时调用
  │
  ├── ExpressionManager (独立实例，非 Node)
  │   → 被 PublicInterfaceManager 和内部回调同时调用
  │   → UDP(端口1036) → UE 渲染引擎
  │
  └── NeckController (独立实例，非 Node)
      → Pub/Sub: /eir/neck_ctrl_cmd, /eir/gaze_feedback
      → 不在 PublicInterfaceManager 管辖范围
```

`Manager::Spin()` 中可以看到它们是平等注册的多个 Node：

```cpp
// manager.cpp:353-359
executor.add_node(emotion_manager_);
executor.add_node(public_interface_manager_);
executor.add_node(voice_manager_);
executor.add_node(motion_manager_);
```

PublicInterfaceManager 虽然名字叫 "high_level_api"，但实际上只是众多 Node 中的一个，不具备中心调度地位。

### 10.3 内部回调链路（旁路外部接口）

`Manager::Init()` 中注册了大量回调，形成了一条**独立于外部接口的控制链路**：

```cpp
// 链路1: 情绪 → 自动驱动动作+表情（Agent 不可见）
emotion_manager_->RegisterEmotionChangeCallback([](Emotion emotion) {
    motion_manager_->SetEmotionType(emotion);       // ← 直接调用，不经过 PublicInterfaceManager
    expression_manager_->SetEmotionType(emotion);   // ← 同样直接
});

// 链路2: TTS 音频 → 自动驱动表情口型（Agent 不可见）
voice_manager_->RegisterTtsResCallback([](uuid, data, len) {
    expression_manager_->FeedAudioData(data, len, uuid);  // ← 直接调用
});

// 链路3: 音频录制 → 自动送情绪引擎（Agent 不可见）
voice_manager_->RegisterRecorderCallback([](data, len) {
    emotion_manager_->SendAudio(data, len, "");     // ← 内部闭环
});
```

这意味着：**即使 Agent 什么都不做，机器人内部也在自主运行着"语音→情绪→表情→动作"的闭环**。Agent 发的指令可能与内部状态冲突。

### 10.4 多控制源冲突风险

当前存在**至少三条控制链路**同时驱动同一硬件资源：

| 控制源 | 路径 | 控制范围 |
|-------|------|---------|
| **Agent (外部)** | MQTT → Bridge → PublicInterfaceManager | motion, move, body, face, safety |
| **本地语音 (内部)** | VoiceManager → Manager::ProcessIntent | intent 驱动的动作（当前仅 LOG，未来会执行） |
| **情绪引擎 (内部)** | EmotionManager → UDP → 回调 → motion/expression | 自动切换动作风格和面部表情 |

三者都可以调用 `motion_manager_->SetEmotionType()` 或 `EHR_APP_CORE::ExecuteMotion()`，但**没有任何仲裁机制**：

```
时刻 T1: Agent 发送 CMD_ACTION "dance"  → motion_manager 开始跳舞
时刻 T2: EmotionManager 检测到愤怒情绪   → motion_manager->SetEmotionType(Anger) 
时刻 T3: 本地语音识别到 "停下"          → ProcessIntent 处理（目前只打日志）
```

底层 ResourceManager（ehr_app_core 中）只管理硬件资源（Speaker/Microphone/Motor/Camera/LED）的互斥，不管业务层面的优先级仲裁。

### 10.5 Agent 侧缺乏状态反馈

Agent 发出一条指令后：

- **无确认**：不知道指令是否被接收（MQTT QoS 只管消息送达，不管业务执行）
- **无拒绝通知**：estop 激活时 PublicInterfaceManager 会静默拒绝 loco_mode_switch（代码中只有 `LOG_WARN`，不回报）
- **无完成通知**：不知道动作何时执行完毕
- **无状态查询**：不知道当前机器人正在做什么动作、什么情绪

Agent 只能订阅 `info/often` 获取电池/里程等硬件状态，缺少任务级的状态反馈。

### 10.6 情绪/表情的 UDP 旁路

最关键的一条旁路——情绪和表情引擎通过 UDP 直连 UE（Unreal Engine）渲染：

```
EmotionManager  ──UDP:1035──→  UE 情绪引擎
ExpressionManager ──UDP:1036──→  UE 渲染引擎
```

这两个 UDP 通道**完全不在 ROS2 体系中**，Bridge 根本感知不到。Agent 如果想控制机器人的情绪和表情，有三个选择：

1. 在 PublicInterfaceManager 中新增 ROS2 订阅，作为 UDP 调用的桥梁（需改 ehr_ros_app）
2. Agent 直接走 UDP 发指令（需知道 UE 引擎的协议和端口）
3. 保持现状，Agent 只做物理动作控制，表情/情绪由内部引擎自主驱动

### 10.7 架构改进方向

小组讨论时可以围绕以下问题展开：

1. **PublicInterfaceManager 应不应该成为唯一入口？** 如果是，内部回调链（情绪→动作、TTS→表情）需要通过 PublicInterfaceManager 还是保持直接调用？
2. **Agent 与内部引擎的职责边界在哪里？** 情绪是 Agent 控制还是内部自主？表情是 Agent 驱动还是跟随语音自动？
3. **仲裁层放在哪里？** 放在 Gateway（Agent 侧）、PublicInterfaceManager（ehr_ros_app 侧）、还是 ResourceManager（ehr_app_core 侧）？
4. **是否需要指令级的响应机制？** Agent 发指令后是否需要同步等待结果（类似 request-response），还是继续异步（fire-and-forget + 状态轮询）？
