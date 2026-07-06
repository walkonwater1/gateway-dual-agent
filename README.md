# 爱啾 Agent Runtime — Demo

基于 [file_framework.md](../ros2_ws/ehr_ros_app/design/file_framework.md)
+ [gateway_readme.md](../ros2_ws/ehr_ros_app/design/gateway_readme.md)
+ [IMPLEMENTATION_ROADMAP.md](../ros2_ws/ehr_ros_app/design/IMPLEMENTATION_ROADMAP.md)
的完整分层实现。目标：**证明 Gateway + 三 Runtime + Agent/Skill 分层架构可行，并打通 Python → MQTT → Bridge → ROS2 → 机器人全链路。**

---

## 目录

- [1. 架构总览](#1-架构总览)
- [2. 分层设计](#2-分层设计)
- [3. 调用关系图](#3-调用关系图)
- [4. 请求处理全流程](#4-请求处理全流程)
- [5. 路由决策树](#5-路由决策树)
- [6. 决策树与调用链对照](#6-决策树与调用链对照)
- [7. 目录结构](#7-目录结构)
- [8. 快速开始](#8-快速开始)
- [9. 功能清单与验证状态](#9-功能清单与验证状态)
- [10. 与设计文档对应关系](#10-与设计文档对应关系)
- [11. 已确认限制](#11-已确认限制)
- [12. 后续路线](#12-后续路线)

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

## 3. 调用关系图

### 3.1 模块依赖关系

```
                                  ┌─────────────────────┐
                                  │       main.py        │
                                  │  DI 组装 + 启动入口   │
                                  └──────────┬──────────┘
                                             │ 注入依赖
               ┌─────────────────────────────┼──────────────────────────┐
               ▼                             ▼                          ▼
  ┌────────────────────────┐  ┌────────────────────────┐  ┌────────────────────────┐
  │   InteractionRuntime   │  │     MotionRuntime      │  │   NavigationRuntime    │
  │   runtimes/            │  │   runtimes/            │  │   runtimes/            │
  │                        │  │                        │  │                        │
  │  _intent_agent ────────┤  │  _motion_agent ────────┤  │  _nav_agent ───────────┤
  │       │                │  │       │                │  │       │                │
  │  _dialogue_agent ──────┤  │       ▼                │  │       ▼                │
  │       │                │  │  MotionSkill            │  │  NavigationSkill        │
  │  _skill ───────────────┤  │       │                │  │       │                │
  │       │                │  │       ▼                │  │       ▼                │
  └───────┼────────────────┘  └───────┼────────────────┘  └───────┼────────────────┘
          │                           │                           │
          │     ┌─────────────────────┼───────────────────────────┤
          │     │                     │                           │
          ▼     ▼                     ▼                           ▼
  ┌───────────────┐    ┌─────────────────────────────────────────────┐
  │  Gateway      │    │              RobotMqttClient                │
  │  gateway/     │    │              capabilities/                  │
  │               │    │                                             │
  │  _router ─────┼────┤  send_motion()  send_move()  send_estop()  │
  │  _runtimes {} │    │  send_volume()  send_led()  send_corpus()  │
  │               │    │  send_navigation()  ...                    │
  └───────────────┘    └──────────────────────────┬──────────────────┘
                                                  │ MQTT
                                                  ▼
                                        ┌──────────────────┐
                                        │  Bridge (C++)    │
                                        │  MQTT ↔ ROS2     │
                                        └──────────────────┘
```

### 3.2 Gateway → 三 Runtime 路由关系

```
                        ┌─────────────┐
                        │   Gateway   │
                        │ handle_text │
                        └──────┬──────┘
                               │
                        ┌──────▼──────┐
                        │   Router    │
                        │  .route()   │
                        └──────┬──────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
   ┌─────────────────┐ ┌─────────────┐ ┌─────────────────┐
   │  "interaction"  │ │  "motion"   │ │  "navigation"   │
   │  (默认 / LLM)   │ │  (关键词)   │ │  (关键词)       │
   └────────┬────────┘ └──────┬──────┘ └────────┬────────┘
            │                 │                  │
   ┌────────▼────────┐ ┌──────▼──────┐ ┌────────▼────────┐
   │InteractionRuntime│ │MotionRuntime│ │NavigationRuntime│
   │                  │ │             │ │   (占位)        │
   │ 两条路径:         │ │ MotionAgent │ │ NavigationAgent │
   │ ①直接Skill执行    │ │     │       │ │     │           │
   │ ②LLM→IntentAgent │ │ MotionSkill  │ │ NavigationSkill │
   │     │             │ │     │       │ │     │           │
   │ ①DialogueSkill   │ │ send_motion │ │ send_navigation │
   │ ②InteractionSkill│ │ send_move   │ │                 │
   └──────────────────┘ │ send_estop  │ └─────────────────┘
                         └─────────────┘
```

---

## 4. 请求处理全流程

### 4.1 统一消息协议 (`shared/message.py`)

所有层之间通过两个 dataclass 传递数据。**`context` 字段是 Gateway 和 Runtime/Agent 之间的核心契约：**

```python
@dataclass
class RuntimeMessage:
    message_id: str          # 自动生成
    session_id: str          # 单用户固定 "default"
    source: str              # "user" | "system" | "robot_event"
    input_type: str          # "text" | "asr" | "event"
    payload: dict            # {"text": "..."}              ← 原始输入
    context: dict            # {"action": "motion", ...}    ← Router 预填

@dataclass
class RuntimeResult:
    success: bool            # 执行是否成功
    reply: str               # 给用户的回复
    intent: str              # chat|motion|navigation|interaction
    data: dict               # {uuid, action, params, ...}
    error: Optional[str]
```

### 4.2 完整时序流程图

```
用户输入文本
      │
      ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Gateway.handle_text(text)                       gateway/gateway.py  │
│                                                                     │
│   1. RuntimeMessage.from_text(text)  ← 封装                         │
│   2. self._router.route(message)     ← 选 Runtime                  │
│   3. self._runtimes[name].handle()   ← 首次分发                    │
│   4. if intent in (motion,navigation) → _reroute()  ← 二次路由     │
│   5. return RuntimeResult                                           │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │   Router.route()    │  gateway/router.py
                    │   关键词最大匹配      │
                    │   命中 → 写 context  │
                    │   未命中→interaction │
                    └──────────┬──────────┘
                               │
          ┌────────────────────┼──────────────────────┐
          ▼                    ▼                      ▼
  ┌───────────────┐   ┌───────────────┐   ┌───────────────────┐
  │  interaction  │   │    motion     │   │    navigation     │
  └───────┬───────┘   └───────┬───────┘   └────────┬──────────┘
          │                   │                    │
          ▼                   ▼                    ▼
┌─────────────────────┐ ┌───────────────┐ ┌───────────────────┐
│ InteractionRuntime  │ │ MotionRuntime │ │ NavigationRuntime │
│   .handle(message)  │ │ .handle(msg)  │ │  .handle(msg)     │
│                     │ │               │ │                   │
│ 读 context["action"]│ │ → MotionAgent │ │ → NavigationAgent │
│                     │ │     .handle() │ │     .handle()     │
│ ┌─ 路径1 ─────────┐ │ │      │        │ │      │            │
│ │action已预填      │ │ │ MotionSkill  │ │ NavigationSkill   │
│ │→直接调Skill执行  │ │ │  .execute()  │ │  .execute()       │
│ │(零LLM)           │ │ │      │        │ │      │            │
│ └─────────────────┘ │ │  if/elif:    │ │  send_navigation  │
│                     │ │  "motion"→   │ │  → MQTT 6001      │
│ ┌─ 路径2 ─────────┐ │ │  send_motion │ │                   │
│ │action未预填      │ │  "move"→      │ └───────────────────┘
│ │→ IntentAgent     │ │  send_move    │
│ │   .handle()      │ │  "stop"→      │
│ │   ┌──────────┐   │ │  send_estop   │
│ │   │快速路径   │   │ │  ...          │
│ │   │LLM路径   │   │ └───────────────┘
│ │   └──────────┘   │
│ │   ↓               │
│ │ chat → Dialogue   │
│ │   Agent → LLM回复 │
│ │ motion/nav → 返回 │
│ │   result给Gateway │
│ │   (触发二次路由)  │
│ │ interaction →     │
│ │   InteractionSkill│
│ └─────────────────┘ │
└─────────────────────┘
```

### 4.3 路径 A：关键词直达（以 `cqm1` 为例）

```
输入: "cqm1"

  [Gateway]  handle_text("cqm1")
      │       ① RuntimeMessage(payload={"text":"cqm1"})
      │       ② router.route(message) → "motion"
      │       ③ runtimes["motion"].handle(message)
      ▼
  [Router]   route()
      │       "cqm1" in DIRECT_ROUTES → 命中
      │       message.context = {"action":"motion", "params":{"name":"cqm1"}}
      │       return "motion"
      ▼
  [MotionRuntime]  handle(message)
      │       → motion_agent.handle(message)
      ▼
  [MotionAgent]  handle(message)
      │       action=context["action"]="motion"
      │       params=context["params"]={"name":"cqm1"}
      │       → skill.execute("motion", {"action":"motion","name":"cqm1"})
      ▼
  [MotionSkill]  execute(intent="motion", params={...})
      │       if params["action"] == "motion":
      │           _do_motion({"name":"cqm1"})
      │               mqtt.send_motion("cqm1")          ← 唯一 MQTT 调用点
      ▼
  [RobotMqttClient]  send_command(1006, "cqm1")
      │       topic = "eir/operation_instructions"
      │       publish({"command":1006, "uuid":"...", "commandData":"cqm1"})
      ▼
  [MQTT] → [Bridge] → [ROS2] → [MotionManager]
      │
      └──→ RuntimeResult(success=True, reply="执行动作: cqm1")

  耗时: < 1ms (无 LLM)
```

### 4.4 路径 B：LLM 意图理解 + 二次路由（以 `帮我做个欢迎动作` 为例）

```
输入: "帮我做个欢迎动作"

  [Gateway]  handle_text("帮我做个欢迎动作")
      │       ② router.route(message) → 无关键词命中 → "interaction"
      │       ③ runtimes["interaction"].handle(message)
      ▼
  [InteractionRuntime]  handle(message)
      │       context["action"] 为空 → 走路径 2 (LLM)
      │       → intent_agent.handle(message)
      ▼
  [IntentAgent]  handle(message)
      │       _fast_path("帮我做个欢迎动作") → None (不匹配快速路径)
      │       _llm_path()
      │         → LLM(qwen2.5:0.5b) ← 唯一 LLM 调用点
      │         → {"intent":"motion","action":"motion","params":{"name":"cqm1"}}
      ▼
      │       return RuntimeResult(
      │           intent="motion",
      │           data={"action":"motion","params":{"name":"cqm1"}}
      │       )
      ▼
  [InteractionRuntime]  result.intent == "motion" → 返回给 Gateway
      ▼
  [Gateway]  result.intent in ("motion","navigation")
      │       → _reroute("motion", message, result)
      │          message.context.update({"action":"motion","params":{"name":"cqm1"}})
      │          → runtimes["motion"].handle(message)
      ▼
  [MotionRuntime→MotionAgent→MotionSkill→MQTT]  ← 后续同路径 A

  耗时: LLM 推理 ~100-500ms + 调用链 < 1ms
```

### 4.5 路径 C：Interaction 类关键词直达（以 `四川话` 为例）

```
输入: "四川话"

  [Router]   "四川话" in DIRECT_ROUTES → ("interaction", "play_audio", {"name":"sch1"})
      │       message.context = {"action":"play_audio", "params":{"name":"sch1"}}
      │       return "interaction"
      ▼
  [InteractionRuntime]  handle(message)
      │       action = context["action"] = "play_audio"  ← 已预填
      │       → 直接执行 InteractionSkill
      │       (跳过 IntentAgent，零 LLM 开销)
      ▼
  [InteractionSkill]  execute({action:"play_audio", name:"sch1"})
      │       _play_audio({"name":"sch1"})
      │           mqtt.send_corpus({"type":"play_specific_audio","value":{"name":"sch1"}})
      ▼
  [RobotMqttClient]  send_command(1007, {...}) → topic="eir/operation_instructions"
      ▼
  [Bridge→ROS2→general_interface→FileAudio]  ← 播放音频

  耗时: < 1ms (无 LLM)
```

---

## 5. 路由决策树

### 5.1 决策树（从输入到 MQTT 指令）

```
                              用户输入文本
                                    │
                                    ▼
                          ┌─────────────────┐
                          │  Router.route() │
                          │ 关键词最长匹配     │
                          └────────┬────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    │ 命中          │ 未命中         │
                    ▼              ▼              │
           ┌──────────────┐  ┌──────────────┐     │
           │ 写 context:  │  │ 无预填        │     │
           │ action="x"   │  │ 默认 →        │     │
           │ params={...} │  │ interaction   │     │
           └──────┬───────┘  └──────┬───────┘     │
                  │                 │              │
    ┌─────────────┼─────────┐       │              │
    │             │         │       ▼              │
    ▼             ▼         ▼  ┌──────────────────────┐
  motion    interaction  navigation  │ InteractionRuntime   │
    │             │         │  │ handle(message)       │
    │             │         │  │                       │
    │             │         │  │ context["action"]? ───┤
    │             │         │  │   │                   │
    │             │         │  │  有 → 直接Skill执行   │
    │             │         │  │   │  (play_audio/     │
    │             │         │  │   │   switch_emotion/ │
    │             │         │  │   │   voice_wakeup/   │
    │             │         │  │   │   volume/led)     │
    │             │         │  │   │                   │
    │             │         │  │  无 → IntentAgent     │
    │             │         │  │       LLM 意图识别    │
    │             │         │  │         │             │
    │             │         │  │   ┌─────┼──────┐      │
    │             │         │  │   ▼     ▼      ▼      │
    │             │         │  │ chat motion navigation│
    │             │         │  │   │     │      │      │
    │             │         │  │   ▼     ▼      ▼      │
    │             │         │  │Dialogue 返回   返回    │
    │             │         │  │Agent  Gateway Gateway │
    │             │         │  │  │  (二次路由)(二次路由)│
    │             │         │  └──┼──────┼──────┼──────┘
    │             │         │     │      │      │
    └─────────────┼─────────┘     │      │      │
                  └───────────────┼──────┼──────┘
                                  │      │
                        ┌─────────┘      └──────────┐
                        ▼                           ▼
                  ┌───────────┐             ┌───────────────┐
                  │  Motion   │             │  Navigation   │
                  │  Runtime  │             │  Runtime      │
                  │     │     │             │     │         │
                  │  Motion  │             │  Navigation   │
                  │  Agent   │             │  Agent        │
                  │     │     │             │     │         │
                  │  Motion  │             │  Navigation   │
                  │  Skill   │             │  Skill        │
                  └────┬─────┘             └──────┬────────┘
                       │                          │
            ┌──────────┼──────────┐               │
            ▼          ▼          ▼               ▼
       send_motion  send_move send_estop   send_navigation
       (1006)       (3001)    (9000)       (6001)
            │          │          │               │
            └──────────┼──────────┼───────────────┘
                       ▼          ▼
              ┌─────────────────────────────┐
              │      RobotMqttClient        │
              │  publish(topic, payload)    │
              └─────────────┬───────────────┘
                            │ MQTT
                            ▼
                     ┌────────────┐
                     │   Bridge   │
                     │ MQTT↔ROS2  │
                     └────────────┘
```

### 5.2 Skill 内部分发（if/elif 路由）

以 MotionSkill 为例，从 Agent 传入的 `params["action"]` 决定最终 MQTT 指令：

```
MotionSkill.execute(intent, params)
  │
  │  action = params["action"]
  │
  ├── "motion"       → send_motion(name)        → MQTT 1006, eir/operation_instructions
  ├── "move"         → send_move(lx,ly,az)      → MQTT 3001, eir/operation_move2
  ├── "stop"         → send_estop(True)         → MQTT 9000, eir/soft_emergency_stop
  ├── "release_estop"→ send_estop(False)        → MQTT 9000, eir/soft_emergency_stop
  ├── "loco_mode"    → send_loco_mode(mode)     → MQTT 1001, eir/operation_instructions
  ├── "gait"         → send_gait(mode)          → MQTT 1002, eir/operation_instructions
  ├── "body_height"  → send_body_height(h)      → MQTT 1003, eir/operation_instructions
  ├── "orientation"  → send_body_orientation()  → MQTT 1008, eir/operation_instructions
  ├── "oas"          → send_oas(enable)         → MQTT 1004, eir/operation_instructions
  └── "uwb"          → send_uwb(enable)         → MQTT 1005, eir/operation_instructions

InteractionSkill.execute(intent, params)
  │
  ├── "play_audio"    → send_corpus({type, name}) → MQTT 1007, eir/operation_instructions
  ├── "switch_emotion"→ send_corpus({type})       → MQTT 1007, eir/operation_instructions
  ├── "voice_wakeup"  → send_corpus({type})       → MQTT 1007, eir/operation_instructions
  ├── "volume"        → send_volume(vol)          → MQTT 5002, eir/setting
  └── "led"           → send_led(rgb, ...)        → MQTT 5001, eir/setting
```

---

## 6. 决策树与调用链对照

以三种典型输入展示 Router 匹配 → context 填充 → Skill 分发 → MQTT 的完整链路：

```
┌──────────┬──────────────┬────────────┬─────────────┬─────────────┬────────────┐
│  输入     │ Router 关键词 │ → Runtime  │ context      │ Skill 分发   │ MQTT 指令  │
│          │              │            │ action       │             │            │
├──────────┼──────────────┼────────────┼─────────────┼─────────────┼────────────┤
│ "cqm1"   │ "cqm1" 命中  │ motion     │ "motion"    │ _do_motion  │ 1006 cqm1  │
│ "前进"   │ "前进" 命中  │ motion     │ "move"      │ _do_move    │ 3001 [0.5] │
│ "停"     │ "停" 命中    │ motion     │ "stop"      │ _do_estop   │ 9000 "1"   │
│ "站立"   │ "站立" 命中  │ motion     │ "loco_mode" │ _do_loco    │ 1001 10    │
│ "四川话" │ "四川话" 命中 │ interaction│ "play_audio"│ _play_audio │ 1007 sch1  │
│ "换个表情"│ "换个表情" 命中│interaction│ "switch_…   │ _switch_…   │ 1007 random│
│ "音量80" │ "音量" 命中  │ interaction│ "volume"    │ _set_volume │ 5002 80    │
│ "带我去" │ "带我去" 命中│ navigation│ "navigate"  │ send_nav    │ 6001 {...} │
│ "你好"   │ 未命中       │ interaction│ (空)        │ IntentAgent │ → Dialogue │
│          │ 默认         │            │             │ chat→LLM回复│ Agent      │
│ "帮我做…"│ 未命中       │ interaction│ (空)        │ IntentAgent │ → reroute  │
│          │ 默认         │            │             │ motion→     │ → 1006     │
└──────────┴──────────────┴────────────┴─────────────┴─────────────┴────────────┘
```

---

## 7. 目录结构

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

## 8. 快速开始

### 8.1 环境要求

- Python >= 3.10
- 机器人上运行: mosquitto (MQTT broker, port 8899) + Bridge + ehr_ros_app
- (可选) ollama 或 OpenAI 兼容 LLM 服务

### 8.2 安装

```bash
cd agent_demo
pip install -r requirements.txt
cp config.example.yaml config.local.yaml
# 编辑 config.local.yaml，填入:
#   - mqtt.host: 机器人 IP
#   - llm.base_url: LLM 地址
#   - llm.api_key: API Key
```

### 8.3 先测 MQTT 连通性

```bash
python step1_hello_mqtt.py --host 机器人IP --cmd 1006 --data cqm1
```

观察机器人日志是否收到 `motion playback cmd`，确认 Bridge 链路通。

### 8.4 一键启动

```bash
./start.sh              # 检查环境 + 启动（交互模式）
./start.sh --demo       # 演示菜单模式
./start.sh --mock       # 离线模式（不检查连通性）
./start.sh --check      # 仅检查环境，不启动
```

### 8.5 交互模式

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

## 9. 功能清单与验证状态

### 9.1 已验证通过 ✅

| 功能 | 输入 | 链路 | 验证结果 |
|------|------|------|---------|
| 动作执行 | `cqm1`, `cqm2`, `cqm3` | Gateway→Router→MotionRT→Agent→Skill→MQTT(1006)→Bridge→ROS2→MotionManager | ✅ 全链路通，Motor acquired/released 正常。`motion_data_map_` 中缺少动作数据文件，需确认实际动作名 |
| 音频播放 | `四川话`, `普通话`, `随机播放` | ...→InteractionSkill→MQTT(1007)→general_interface→FileAudio | ✅ Speaker Acquire/Release 正常，6s 播放周期 |
| 对话 | `你好`, `你是谁` | ...→IntentAgent(fast path)→DialogueAgent→LLM | ✅ 快速路径命中，LLM 对话正常 |

### 9.2 代码就绪待验证 ⏳

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

### 9.3 LLM 意图识别 ⏳

代码已实现，但依赖 LLM 服务可用。IntentAgent 的 `_fast_path` 覆盖了常见问候语，复杂意图（如"帮我做个动作"）需 LLM 判断。

---

## 10. 与设计文档对应关系

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

## 11. 已确认限制

### 11.1 机器人侧

| 问题 | 现象 | 影响 |
|------|------|------|
| 动作数据缺失 | `cqm1/cqm2/cqm3` 不在 `motion_data_map_` 中 | 无法执行预设动作，需确认实际动作名 |
| `eir/setting` topic 路由异常 | 发音量指令(5002)，机器人收到 move2(3001) | 音量/氛围灯等设置类功能不可用，需排查 Bridge 或 PublicInterfaceManager |
| 情绪/表情走 UDP 旁路 | EmotionManager/ExpressionManager 经 UDP→UE，不经过 ROS2 | Agent 无法通过 MQTT 控制表情，需先在 ehr_ros_app 新建 ROS2 接口 |
| TTS/运动暂停未暴露 | 内部 SDK 调用，无 ROS2 topic | Agent 无法控制 TTS 播报和运动暂停/恢复 |
| 诊断播报干扰 | eir-diagnostician 每 30s 占 Speaker | 干扰音频验证，已通过 systemctl 禁用 |

### 11.2 Agent 侧

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

## 12. 后续路线

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
