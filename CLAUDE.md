---
name: agent-demo
description: Agent Demo 项目架构、路由逻辑、关键决策
metadata: 
  node_type: memory
  type: project
  originSessionId: 3285250f-3a86-4c10-ad83-8c613bec147f
---

## Agent Demo 项目概览

位置: `/home/lixin/eir/agent_demo/`
GitHub: `github.com/walkonwater1/gateway-dual-agent`
分支: `main`

### 架构

五层架构: Gateway(路由+治理) → Runtime(编排) → Agent(决策) → Skill(执行) → Capability(MQTT)

```
用户输入 → Gateway.handle_text()
  → InputAdapter (多模态归一化)
  → TraceLogger (trace_id)
  → SessionRouter (会话隔离)
  → PriorityManager (优先级)
  → SafetyGate (安全过滤)
  → Router (YAML 54条规则, 最长匹配)
    → 命中: 免LLM, 直接分发
    → 未命中: InteractionRuntime → IntentAgent(LLM) 意图识别
  → ConflictResolver (冲突仲裁)
  → RuntimeRouter (分发/二次路由)
    → InteractionRuntime / MotionRuntime / NavigationRuntime
    → Agent → Skill → MQTT → Bridge → ROS2 → 机器人
```

### Gateway 模块 (13/13, 100%)

| 模块 | 状态 | 说明 |
|------|------|------|
| gateway.py | ✅ | 主入口, 10步处理链路 |
| input_adapter.py | ✅ | text/asr/robot_event 多模态 |
| router.py | ✅ | YAML规则匹配, 最长关键词 |
| route_policy.py | ✅ | 加载 config/routes.yaml (54条) |
| runtime_router.py | ✅ | Runtime注册/分发/二次路由 |
| session_router.py | ✅ | 多用户会话隔离+历史 |
| priority_manager.py | ✅ | emergency>high>normal>low |
| safety_gate.py | ✅ | 请求级安全过滤 |
| trace_logger.py | ✅ | trace_id 全链路10种事件 |
| conflict_resolver.py | ✅ | 跨Runtime仲裁(preempt/queue/refuse) |
| event_bus.py | ✅ | pub/sub, 默认关闭 |
| result_aggregator.py | ✅ | 多Runtime结果合并, 默认关闭 |
| message_normalizer.py | ⚠️ | 在 shared/message.py |
| session_router (完整版) | ❌ | 缺少多用户识别/身份绑定 |

### Shared 层

- `shared/message.py` — RuntimeMessage (含 trace_id/priority/timestamp) + RuntimeResult
- `shared/event.py` — RuntimeEvent (navigation.progress / motion.completed / safety.estop …)
- `shared/session.py` — Session (session_id, current_task, context, history)
- `shared/base.py` — BaseAgent / BaseSkill 抽象基类

### 路由机制 (双路径)

```
路径A (关键词命中, 免LLM, <1ms):
  输入 → Router(YAML匹配) → Runtime → Agent → Skill → MQTT

路径B (LLM理解, ~100-500ms):
  输入 → Router(未命中) → InteractionRuntime
    → IntentAgent(LLM qwen2.5:0.5b@NUC) 意图识别
    → chat → 机器人本地语音处理
    → interaction → InteractionSkill → MQTT
    → motion/navigation → Gateway二次路由 → 对应Runtime → Agent → Skill → MQTT
```

### 当前 Agent (3个)

- **IntentAgent** (`agents/intent_agent.py`): 唯一调 LLM 的 Agent，做意图→MQTT指令映射。LLM 运行在 NUC (192.168.2.105:11434, ollama)
- **MotionAgent** (`agents/motion_agent.py`): 参数适配，不调 LLM
- **NavigationAgent** (`agents/navigation_agent.py`): 参数适配，不调 LLM

### 关键决策

- **Gateway 薄中枢**: 不调 LLM、不做业务决策、不发 MQTT
- **YAML 配置化路由**: `config/routes.yaml` 54条规则, 改规则免改代码
- **模块可插拔**: 每个Gateway模块可通过config开关
- **DialogueAgent/DialogueSkill 已删除**: 机器人本体 SDK 内置语音系统处理对话/ASR/TTS，Agent 层不重复实现
- **跨 Runtime 通信走 Gateway**: RuntimeRouter.reroute()，禁止 Runtime 间直接互调
- **LLM 仅路径B调用**: 关键词命令不依赖NUC, NUC离线时关键词命令仍可用

### 配置

- `config/routes.yaml` — 54条路由规则 (YAML, 可热改)
- `config.local.yaml` — MQTT/LLM 连接配置 (git ignore)
- `config.example.yaml` — 配置模板

### 设计文档

- `docs/design/gateway_readme.md` — Gateway 13 模块设计
- `docs/design/file_framework.md` — 14 目录框架设计
- `docs/design/IMPLEMENTATION_ROADMAP.md` — 4 阶段路线图 + Bridge 接口差距
- `docs/GAP_ANALYSIS.md` — 逐模块差距分析

### 相关目录

- 机器人 C++ 代码: `/home/lixin/eir/ros2_ws/ehr_ros_app/`
- MQTT Bridge: `eir_communication_bridge` (ROS2 node, MQTT↔ROS2 透明中继)
- MQTT Broker: mosquitto, 端口 8899, 运行在机器人主控 (192.168.2.5)
- LLM: ollama + qwen2.5:0.5b, 运行在 NUC (192.168.2.105:11434)

相关记忆: [[project-structure]] [[architecture-decision]]
