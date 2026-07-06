# 爱啾 Agent Runtime — Demo

基于 [file_framework.md](../ros2_ws/ehr_ros_app/design/file_framework.md)
+ [gateway_readme.md](../ros2_ws/ehr_ros_app/design/gateway_readme.md)
+ [IMPLEMENTATION_ROADMAP.md](../ros2_ws/ehr_ros_app/design/IMPLEMENTATION_ROADMAP.md)
的完整分层实现。目标：**证明 Gateway + 三 Runtime + Agent/Skill 分层架构可行，并打通 Python → MQTT → Bridge → ROS2 → 机器人全链路。**

---

## 目录

- [1. 架构总览](#1-架构总览)
- [2. 分层设计](#2-分层设计)
- [3. 数据流详解](#3-数据流详解)
- [4. 路由决策](#4-路由决策)
- [5. 目录结构](#5-目录结构)
- [6. 快速开始](#6-快速开始)
- [7. 功能清单与验证状态](#7-功能清单与验证状态)
- [8. 与设计文档对应关系](#8-与设计文档对应关系)
- [9. 已确认限制](#9-已确认限制)
- [10. 后续路线](#10-后续路线)

---

## 1. 架构总览

```
用户输入 "cqm1"
       │
       ▼
┌──────────────────────────────────────────────────────────┐
│  Gateway (gateway/)                                       │
│  ├── handle_text()     ← 统一入口，封装 RuntimeMessage    │
│  └── Router            ← 关键词命中 → 直连 Runtime        │
│       │                   未命中      → Interaction (LLM)  │
│       │                                                   │
│       ├── 关键词命中 "cqm1" → Motion Runtime  (零 LLM)    │
│       ├── 关键词命中 "前进" → Motion Runtime               │
│       ├── 关键词命中 "停"   → Motion Runtime               │
│       ├── 关键词命中 "导航" → Navigation Runtime           │
│       └── 未命中            → Interaction Runtime (LLM)    │
└──────────────────────────────────────────────────────────┘
       │
       ├──────────────┬──────────────┬──────────────┐
       ▼              ▼              ▼              ▼
┌──────────┐ ┌──────────┐ ┌──────────────┐
│Interaction│ │  Motion  │ │  Navigation  │  ← Runtimes (runtimes/)
│ Runtime  │ │  Runtime │ │   Runtime    │     编排所属 Agent
│          │ │          │ │  (占位)      │
│ Intent   │ │ Motion   │ │ Navigation  │
│ Agent    │ │ Agent    │ │ Agent       │
│ Dialogue │ │          │ │             │
│ Agent    │ │          │ │             │
└────┬─────┘ └────┬─────┘ └──────┬──────┘  ← Agents (agents/)
     │            │              │            决策：调 LLM、选动作、定参数
     ▼            ▼              ▼
┌──────────┐ ┌──────────┐ ┌──────────────┐
│Dialogue  │ │ Motion   │ │ Navigation   │  ← Skills (skills/)
│Skill     │ │ Skill    │ │ Skill        │     执行：发 MQTT 指令
│(LLM对话) │ │(MQTT指令)│ │ (MQTT指令)   │
└────┬─────┘ └────┬─────┘ └──────┬──────┘
     │            │              │
     └────────────┼──────────────┘
                  ▼
     ┌──────────────────────┐
     │  RobotMqttClient     │  ← Capabilities (capabilities/)
     │  paho-mqtt 封装      │     协议适配，不含业务逻辑
     └──────────────────────┘
                  │ MQTT (mosquitto:8899)
                  ▼
     ┌──────────────────────┐
     │  eir_communication   │  ← Bridge (C++ ROS2 Node)
     │  _bridge             │     MQTT ↔ ROS2 透明中继
     └──────────────────────┘
                  │ ROS2 topics
                  ▼
     ┌──────────────────────┐
     │  ehr_ros_app +       │  ← 机器人主控 (Orin)
     │  ehr_app_core        │     执行层
     └──────────────────────┘
```

---

## 2. 分层设计

| 层级 | 目录 | 职责 | 不负责 | 有无 LLM |
|------|------|------|--------|----------|
| **Gateway** | `gateway/` | 入口、标准化、路由、二次分发、结果汇合 | 不调 LLM、不做动作、不做决策 | ❌ |
| **Runtime** | `runtimes/` | 编排所属 Agent、区分"直接执行"和"LLM 理解"两条路径 | 不直接操作硬件、不直接发 MQTT | ❌ |
| **Agent** | `agents/` | 决策：调 LLM、选意图、定参数 | 不直接发 MQTT | ✅ (Intent/Dialogue) |
| **Skill** | `skills/` | 执行：将决策翻译为 MQTT 指令 | 不做决策、不判断 | ❌ (DialogueSkill 例外) |
| **Capability** | `capabilities/` | MQTT 协议封装、topic 路由、QoS | 不含业务逻辑 | ❌ |
| **Shared** | `shared/` | RuntimeMessage / RuntimeResult 数据协议、基类 | — | ❌ |

> **核心原则：Agent 负责"用户想做什么"，Skill 负责"怎么让机器人做"。Gateway 是薄中枢，只路由不决策。**

---

## 3. 数据流详解

### 3.1 统一消息协议 (`shared/message.py`)

所有层之间使用两个 dataclass 通信，保证类型安全：

```python
@dataclass
class RuntimeMessage:
    message_id: str          # 自动生成
    session_id: str          # 单用户固定 "default"
    source: str              # "user" | "system" | "robot_event"
    input_type: str          # "text" | "asr" | "event"
    payload: dict            # {"text": "..."}
    context: dict            # Router 预填 action + params

@dataclass
class RuntimeResult:
    success: bool            # 执行是否成功
    reply: str               # 给用户的回复
    intent: str              # chat|motion|navigation|interaction|...
    data: dict               # {uuid, action, params, ...}
    error: Optional[str]
```

### 3.2 两种典型数据流

#### 路径 A：关键词直达（零 LLM 开销）

```
输入 "cqm1"
  ↓
Gateway.handle_text("cqm1")
  → RuntimeMessage(payload={"text": "cqm1"})
  ↓
Router.route()
  → "cqm1" ∈ DIRECT_ROUTES → 命中
  → message.context = {action: "motion", params: {name: "cqm1"}}
  → 返回 "motion"
  ↓
MotionRuntime.handle(message)
  → MotionAgent.handle()
    → action="motion", params={name: "cqm1"}
    → MotionSkill.execute()
      → _do_motion() → mqtt.send_motion("cqm1")
        → publish("eir/operation_instructions", {command:1006, commandData:"cqm1"})
          ↓
  RuntimeResult(success=True, reply="执行动作: cqm1")
```

**耗时：** < 1ms (无 LLM 调用)，纯 Python 函数调用链。

#### 路径 B：LLM 意图理解 + 二次路由

```
输入 "帮我做个欢迎动作"
  ↓
Router.route()
  → 无关键词命中 → 返回 "interaction"
  ↓
InteractionRuntime.handle(message)
  → message.context 无预填 action → 走路径 2 (LLM)
  → IntentAgent.handle()
    → _fast_path() 未命中
    → _llm_path() → LLM 返回 {intent:"motion", action:"motion", params:{name:"cqm1"}}
    → RuntimeResult(intent="motion", data={action:"motion", params:{name:"cqm1"}})
  ↓
Gateway._reroute("motion", ...)
  → message.context.update({action:"motion", params:{name:"cqm1"}})
  → MotionRuntime.handle(message)
  → ... (同路径 A)
```

**耗时：** LLM 推理时间（通常 100-500ms），其余路径同 A。

---

## 4. 路由决策

### 4.1 路由优先级

```
Router.route(text)
  │
  ├── 1. DIRECT_ROUTES 关键词匹配（最长优先）
  │       "解除急停"(4字) > "急停"(2字) > "停"(1字)
  │
  └── 2. 无匹配 → Interaction Runtime → IntentAgent(LLM) 判断意图
```

### 4.2 关键词路由表 (router.py)

| 类别 | 关键词示例 | → Runtime | → Action |
|------|-----------|-----------|----------|
| 急停 | 停、急停、停下、站住、别动 | motion | stop |
| 解除急停 | 解除急停、退出急停 | interaction | release_estop |
| 动作 | cqm1, cqm2, cqm3, 动作1/2/3 | motion | motion |
| 移动 | 前进、后退、左转、右转 | motion | move |
| 模式 | 站立、趴下、起身、小跑 | motion | loco_mode |
| 避障 | 开避障、关避障 | motion | oas |
| 音频 | 四川话、普通话、随机播放 | interaction | play_audio |
| 情绪 | 换个表情、切换情绪 | interaction | switch_emotion |
| 语音 | 开/关语音唤醒 | interaction | voice_wakeup |
| 设置 | 音量、氛围灯 | interaction | volume / led |
| 导航 | 带我去、导航到、前往、去 | navigation | navigate |

### 4.3 IntentAgent LLM 提示词

IntentAgent 使用 `qwen2.5:0.5b` (本地 ollama) 做意图分类，输出结构化 JSON：

```json
{"intent": "chat|motion|interaction|navigation|unknown",
 "action": "...",
 "params": {...}}
```

有快速路径（`_fast_path`）："你好"、"谢谢"、"再见" 等直接返回 chat，省一次 LLM 调用。

---

## 5. 目录结构

```
agent_demo/
├── main.py                       # 启动入口（DI 组装 + 交互循环 + 演示菜单）
├── step1_hello_mqtt.py           # 独立 MQTT 连通性测试（不依赖 LLM）
├── start.sh                      # 一键启动脚本（环境检查 + 依赖安装 + 启动）
│
├── gateway/                      # 中央路由层
│   ├── gateway.py                # handle_text() 主入口 + _reroute 二次路由
│   └── router.py                 # DIRECT_ROUTES 关键词表 + Router 最长匹配
│
├── runtimes/                     # Runtime 编排层
│   ├── interaction_runtime.py    # 对话 + LLM 意图理解（两条路径）
│   ├── motion_runtime.py         # 动作/移动/急停/运动模式
│   └── navigation_runtime.py     # 导航/建图（占位）
│
├── agents/                       # Agent 决策层
│   ├── intent_agent.py           # LLM 意图识别（快速路径 + LLM fallback）
│   ├── dialogue_agent.py         # 纯对话 → DialogueSkill
│   ├── motion_agent.py           # 运动决策 → MotionSkill
│   └── navigation_agent.py       # 导航决策 → NavigationSkill
│
├── skills/                       # Skill 执行层（发 MQTT 指令）
│   ├── motion_skill.py           # 动作/移动/急停/模式/步态/身高/避障/UWB
│   ├── dialogue_skill.py         # LLM 对话（OpenAI 兼容 API）
│   ├── interaction_skill.py      # 音频/情绪/语音唤醒/音量/氛围灯
│   └── navigation_skill.py       # 导航 MQTT 指令（占位）
│
├── capabilities/                 # 能力层
│   └── mqtt_client.py            # MQTT 客户端
│       ├── 完整 Bridge 协议封装（30+ 指令 ID 常量）
│       ├── Topic 自动路由（eir/operation_*, eir/setting, eir/slam_* 等）
│       ├── 状态订阅（info/often, eir/basic_heartbeat_callback）
│       └── 高层 API: send_motion/send_move/send_estop/send_volume/...
│
├── shared/                       # 公共协议
│   ├── message.py                # RuntimeMessage / RuntimeResult
│   └── base.py                   # BaseAgent / BaseSkill 抽象基类
│
├── config.example.yaml           # 配置模板
├── config.local.yaml             # 真实配置（git ignore）
├── .gitignore
├── requirements.txt              # paho-mqtt, openai, pyyaml
└── README.md
```

---

## 6. 快速开始

### 6.1 环境要求

- Python >= 3.10
- 机器人上运行: mosquitto (MQTT broker, port 8899) + Bridge + ehr_ros_app
- (可选) ollama 或 OpenAI 兼容 LLM 服务

### 6.2 安装

```bash
cd agent_demo
pip install -r requirements.txt
cp config.example.yaml config.local.yaml
# 编辑 config.local.yaml，填入:
#   - mqtt.host: 机器人 IP
#   - llm.base_url: LLM 地址
#   - llm.api_key: API Key
```

### 6.3 先测 MQTT 连通性

```bash
python step1_hello_mqtt.py --host 机器人IP --cmd 1006 --data cqm1
```

观察机器人日志是否收到 `motion playback cmd`，确认 Bridge 链路通。

### 6.4 一键启动

```bash
./start.sh              # 检查环境 + 启动（交互模式）
./start.sh --demo       # 演示菜单模式
./start.sh --mock       # 离线模式（不检查连通性）
./start.sh --check      # 仅检查环境，不启动
```

### 6.5 交互模式

```
你: cqm1          → 关键词直达 Motion Runtime，零 LLM
你: 前进          → 机器人向前移动
你: 停            → 急停
你: 四川话        → 播放 sch1 音频
你: 换个表情      → 随机切换情绪
你: 站立          → 切换运动模式
你: 你好          → LLM 对话
你: 带我去充电站  → 导航任务下发
你: /menu         → 切换到菜单模式
你: /q            → 退出
```

---

## 7. 功能清单与验证状态

### 7.1 已验证通过 ✅

| 功能 | 输入 | 链路 | 验证结果 |
|------|------|------|---------|
| 动作执行 | `cqm1`, `cqm2`, `cqm3` | Gateway→Router→MotionRT→Agent→Skill→MQTT(1006)→Bridge→ROS2→MotionManager | ✅ 全链路通，Motor acquired/released 正常。`motion_data_map_` 中缺少动作数据文件，需确认实际动作名 |
| 音频播放 | `四川话`, `普通话`, `随机播放` | ...→InteractionSkill→MQTT(1007)→general_interface→FileAudio | ✅ Speaker Acquire/Release 正常，6s 播放周期 |
| 对话 | `你好`, `你是谁` | ...→IntentAgent(fast path)→DialogueAgent→LLM | ✅ 快速路径命中，LLM 对话正常 |

### 7.2 代码就绪待验证 ⏳

这些功能代码已完整实现，MQTT 指令格式与 Bridge 协议对齐，逻辑上应通，但尚未逐条在机器人上验证：

| 功能 | 输入 | MQTT 指令 | Risk |
|------|------|-----------|------|
| 遥控移动 | `前进`/`后退`/`左转`/`右转` | 3001 → eir/operation_move2 | 低，与 cqm 同链路 |
| 急停 | `停`/`急停` | 9000 → eir/soft_emergency_stop | 中，topic 不同，需确认 Bridge 转发 |
| 解除急停 | `解除急停` | 9000 → eir/soft_emergency_stop | 中，同上 |
| 运动模式 | `站立`/`趴下`/`起身` | 1001 → eir/operation_instructions | 低 |
| 步态切换 | (需 LLM 识别) | 1002 | 低 |
| 身高调节 | (需 LLM 识别) | 1003 | 低 |
| 避障开关 | `开避障`/`关避障` | 1004 | 中，Bridge 可能未转发此 topic |
| 情绪切换 | `换个表情` | 1007 → general_interface | 中，依赖 UDP→UE 情绪引擎 |
| 语音唤醒 | `开/关语音唤醒` | 1007 → general_interface | 中 |
| 音量设置 | `音量80` | 5002 → eir/setting | **高**，此前验证收到的是 move2，Bridge 对 eir/setting 的处理待确认 |
| 氛围灯 | `氛围灯` | 5001 → eir/setting | 高，同上 |
| 导航 | `带我去充电站` | 6001 → eir/slam_navigation | 高，导航后端未确认 |

### 7.3 LLM 意图识别 ⏳

代码已实现，但依赖 LLM 服务可用。IntentAgent 的 `_fast_path` 覆盖了常见问候语，复杂意图（如"帮我做个动作"）需 LLM 判断。

---

## 8. 与设计文档对应关系

| 设计文档章节 | 对应代码 | 状态 |
|------------|---------|------|
| `gateway_readme.md` §4.1 gateway.py | `gateway/gateway.py` | ✅ 薄中枢原则 |
| `gateway_readme.md` §4.3 message_normalizer.py | `shared/message.py` | ✅ RuntimeMessage/RuntimeResult |
| `gateway_readme.md` §4.4 router.py | `gateway/router.py` | ✅ 关键词 + 最长匹配 |
| `gateway_readme.md` §4.5 route_policy.py | `gateway/router.py` (DIRECT_ROUTES) | ⚠️ 写死在代码中，未 YAML 化 |
| `gateway_readme.md` §4.6 runtime_router.py | `gateway/gateway.py` (`_runtimes` dict) | ✅ |
| `gateway_readme.md` §5 Gateway MVP | 整个 agent_demo | ✅ |
| `IMPLEMENTATION_ROADMAP.md` Phase 1 | 全部文件 | ✅ MVP 链路完成 |
| `IMPLEMENTATION_ROADMAP.md` Phase 2 | `router.py` + 三 Runtime | ⚠️ Navigation 占位，状态感知未实现 |
| `IMPLEMENTATION_ROADMAP.md` Phase 3 | — | ❌ Session/Priority/Safety/Trace 全未开始 |
| `IMPLEMENTATION_ROADMAP.md` Phase 4 | — | ❌ Knowledge/Memory/Harness 全未开始 |

---

## 9. 已确认限制

### 9.1 机器人侧

| 问题 | 现象 | 影响 |
|------|------|------|
| 动作数据缺失 | `cqm1/cqm2/cqm3` 不在 `motion_data_map_` 中 | 无法执行预设动作，需确认实际动作名 |
| `eir/setting` topic 路由异常 | 发音量指令(5002)，机器人收到 move2(3001) | 音量/氛围灯等设置类功能不可用，需排查 Bridge 或 PublicInterfaceManager |
| 情绪/表情走 UDP 旁路 | EmotionManager/ExpressionManager 经 UDP→UE，不经过 ROS2 | Agent 无法通过 MQTT 控制表情，需先在 ehr_ros_app 新建 ROS2 接口 |
| TTS/运动暂停未暴露 | 内部 SDK 调用，无 ROS2 topic | Agent 无法控制 TTS 播报和运动暂停/恢复 |
| 诊断播报干扰 | eir-diagnostician 每 30s 占 Speaker | 干扰音频验证，已通过 systemctl 禁用 |

### 9.2 Agent 侧

| 限制 | 说明 | 计划 |
|------|------|------|
| 无 Session 隔离 | 所有输入走 default_session | Phase 3 |
| 无优先级仲裁 | "停"和"前进"同时到达无仲裁 | Phase 3 |
| 无 Safety Gate | 不拦截"冲过去"等危险指令 | Phase 3 |
| 无 Trace 记录 | 无链路追踪 | Phase 3 |
| 无对话记忆 | 每次对话独立，无上下文 | Phase 4 |
| 路由表硬编码 | DIRECT_ROUTES 在代码中，未 YAML 化 | Phase 2 |
| 无 MQTT 状态反馈 | 订阅了 info/often 但未利用 | Phase 2 |

---

## 10. 后续路线

```
Phase 1 ✅  MVP 链路     text→Gateway→Runtime→Agent→Skill→MQTT→机器人
Phase 2 ⏳  完善          Navigation 充实 + 路由 YAML 化 + 状态闭环
Phase 3 ❌  治理          Session/Priority/Safety/Trace/Conflict
Phase 4 ❌  智能          Knowledge(RAG) + Memory(四层) + Harness(回放)
```

短期内优先：
1. **确认机器人实际动作名** → 更新 DIRECT_ROUTES 和 DEMO_MENU
2. **排查 `eir/setting` topic** → 确认 Bridge 转发是否正确
3. **验证移动链路** → `前进`/`后退`/`左转`/`右转` 端到端
4. **验证急停链路** → `停` 端到端
5. **路由表 YAML 化** → 不写死在 Python 代码中

---

## 参考文档

- [gateway_readme.md](../ros2_ws/ehr_ros_app/design/gateway_readme.md) — Gateway 专项设计（13 模块）
- [file_framework.md](../ros2_ws/ehr_ros_app/design/file_framework.md) — Robot Agent Runtime 完整架构
- [IMPLEMENTATION_ROADMAP.md](../ros2_ws/ehr_ros_app/design/IMPLEMENTATION_ROADMAP.md) — 四阶段实施路线图 + Bridge 接口差距分析
