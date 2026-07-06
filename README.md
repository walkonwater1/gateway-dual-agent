# 爱啾 Agent Runtime — Demo

基于设计文档 `file_framework.md` + `gateway_readme.md` 的完整分层实现。

## 架构

```
用户输入 "cqm1"
       │
       ▼
┌──────────────────────────────────────────────────────────┐
│  Gateway (gateway/)                                       │
│  ├── handle_text()     ← 统一入口                         │
│  └── Router            ← 关键词/LLM 路由到 Runtime         │
│       │                                                   │
│       ├── 关键词命中 "cqm1" → Motion Runtime  (无LLM开销)  │
│       ├── 关键词命中 "导航" → Navigation Runtime           │
│       └── 未命中           → Interaction Runtime (LLM理解) │
└──────────────────────────────────────────────────────────┘
       │
       ├──────────┬──────────────┬──────────────┐
       ▼          ▼              ▼              ▼
┌──────────┐ ┌──────────┐ ┌──────────────┐
│Interaction│ │  Motion  │ │  Navigation  │  ← Runtimes (runtimes/)
│ Runtime  │ │  Runtime │ │   Runtime    │     编排所属 Agent
│          │ │          │ │ (占位)       │
│ Intent   │ │ Motion   │ │ Navigation  │
│ Agent    │ │ Agent    │ │ Agent       │
│ Dialogue │ │          │ │             │
│ Agent    │ │          │ │             │
└────┬─────┘ └────┬─────┘ └──────┬──────┘  ← Agents (agents/)
     │            │              │            决策：调 LLM、选动作
     ▼            ▼              ▼
┌──────────┐ ┌──────────┐ ┌──────────────┐
│Dialogue  │ │ Motion   │ │ Navigation   │  ← Skills (skills/)
│Skill     │ │ Skill    │ │ Skill        │     执行：发 MQTT 指令
└────┬─────┘ └────┬─────┘ └──────┬──────┘
     │            │              │
     └────────────┼──────────────┘
                  ▼
     ┌──────────────────────┐
     │  RobotMqttClient     │  ← Capabilities (capabilities/)
     │  MQTT → Bridge       │
     └──────────────────────┘
                  │
                  ▼
     Bridge → ROS2 → ehr_ros_app → 机器人
```


## 目录结构

```
agent_demo/
├── main.py                       # 启动入口（依赖注入 + 交互循环）
│
├── gateway/                      # 中央路由层
│   ├── gateway.py                # handle_text() 主入口 + 二次路由
│   └── router.py                 # 关键词快速路由 → 选 Runtime
│
├── runtimes/                     # Runtime 编排层（三 Runtime 系统）
│   ├── interaction_runtime.py    # 对话 + LLM 意图理解
│   ├── motion_runtime.py         # 动作/移动/急停
│   └── navigation_runtime.py     # 导航/建图 (占位)
│
├── agents/                       # Agent 决策层
│   ├── intent_agent.py           # LLM 意图识别 (快速关键词 + LLM fallback)
│   ├── dialogue_agent.py         # 纯对话
│   ├── motion_agent.py           # 运动决策 → MotionSkill
│   └── navigation_agent.py       # 导航决策 → NavigationSkill (占位)
│
├── skills/                       # Skill 执行层
│   ├── motion_skill.py           # 封装所有运动 MQTT 指令
│   ├── dialogue_skill.py         # LLM 对话
│   └── navigation_skill.py       # 封装导航 MQTT 指令 (占位)
│
├── capabilities/                 # 能力层（机器人接口）
│   └── mqtt_client.py            # MQTT 客户端，封装全部 Bridge 指令
│
├── shared/                       # 公共协议
│   ├── message.py                # RuntimeMessage / RuntimeResult
│   └── base.py                   # BaseAgent / BaseSkill 基类
│
├── step1_hello_mqtt.py           # 独立 MQTT 连通性测试（不依赖 LLM）
│
├── start.sh                       # 一键启动脚本
├── config.local.yaml             # 真实配置（MQTT IP, LLM API）
├── config.example.yaml           # 配置模板
├── .gitignore
└── requirements.txt
```

## 各层职责

| 层级 | 目录 | 职责 | 禁止 |
|------|------|------|------|
| Gateway | `gateway/` | 入口、标准化、路由、二次分发、结果汇合 | 不调 LLM、不做动作 |
| Runtime | `runtimes/` | 编排所属 Agent、任务调度 | 不直接操作硬件 |
| Agent | `agents/` | 决策：调 LLM、选意图、定参数 | 不直接发 MQTT |
| Skill | `skills/` | 执行：将决策翻译为 MQTT 指令 | 不做决策 |
| Capability | `capabilities/` | MQTT 协议封装 | 不含业务逻辑 |

> **Agent ≠ Skill**：Agent 负责判断（"用户想挥手"），Skill 负责执行（`mqtt.send_motion("wave")`）。

## 路由决策流程

```
用户输入
  │
  ▼
Router.route()
  ├── 关键词命中"cqm1" → context={action:"motion", params:{name:"cqm1"}} → Motion Runtime
  ├── 关键词命中"停"   → context={action:"stop", params:{}}              → Motion Runtime
  ├── 关键词命中"前进" → context={action:"move", params:{lx:0.5,...}}  → Motion Runtime
  ├── 关键词命中"导航" → context={action:"navigate", params:{}}         → Navigation Runtime
  │
  └── 未命中 → Interaction Runtime
                   │
                   ▼
             IntentAgent(LLM)
                   │
         ┌─────────┼─────────┐
         ▼         ▼         ▼
       chat     motion   navigation
         │         │         │
     Dialogue   Gateway    Gateway
     Agent      二次路由    二次路由
         │         │         │
         ▼         ▼         ▼
      回复     Motion     Navigation
               Runtime    Runtime
```

## 快速开始

### 1. 一键启动（推荐）

```bash
cd agent_demo
./start.sh                 # 检查环境 + 启动
./start.sh --check         # 仅检查环境，不启动
./start.sh --mock          # 离线模式（跳过连通性检查）
```

### 2. 手动启动

安装依赖:

```bash
cd agent_demo
pip install -r requirements.txt
```

编辑 `config.local.yaml`:

```yaml
mqtt:
  host: "192.168.2.5"       # 机器人 IP
  port: 8899

llm:
  base_url: "http://192.168.2.105:11434/v1"  # NUC ollama
  api_key: "ollama"
  model: "qwen2.5:0.5b"     # 轻量够快，正式用可换 7b
```

### 3. 先测连通性

```bash
python step1_hello_mqtt.py --host 192.168.2.5 --cmd 1006 --data cqm1
```

### 4. 启动完整 Agent Runtime

```bash
python main.py
```

### 5. 试试这些

```
你: 你好          → chat, LLM 回复
你: cqm1          → motion, 关键词命中，无 LLM 开销
你: 前进          → move, 往前走
你: 停            → stop, 急停
你: 四川话        → 播放 sch1 音频
你: 换个表情      → 随机切换情绪
你: 站立 / 趴下   → 切换运动模式
你: 带我去充电站  → navigation, 导航任务下发
```

## 与设计文档的对应关系

| 设计文档 | 对应代码 | 状态 |
|---------|---------|------|
| `gateway/gateway.py` | `gateway/gateway.py` | ✅ |
| `gateway/router.py` | `gateway/router.py` | ✅ 关键词 + LLM 二级 |
| `gateway/route_policy.py` | `gateway/router.py` (DIRECT_ROUTES) | ✅ |
| `runtimes/interaction_runtime/` | `runtimes/interaction_runtime.py` | ✅ |
| `runtimes/motion_runtime/` | `runtimes/motion_runtime.py` | ✅ |
| `runtimes/navigation_runtime/` | `runtimes/navigation_runtime.py` | ⚠️ 占位 |
| `agents/interaction_agents/` | `agents/intent_agent.py` + `dialogue_agent.py` | ✅ |
| `agents/motion_agents/` | `agents/motion_agent.py` | ✅ |
| `agents/navigation_agents/` | `agents/navigation_agent.py` | ⚠️ 占位 |
| `skills/` | `skills/*.py` | ✅ |
| `capabilities/` | `capabilities/mqtt_client.py` | ✅ |
| `shared/message.py` | `shared/message.py` | ✅ |
| `shared/base_agent.py` | `shared/base.py` | ✅ |
| `main.py` | `main.py` (DI 组装) | ✅ |
| Gateway 薄中枢原则 | Gateway 不调 LLM，不做动作 | ✅ |
| Agent ≠ Skill | Agent 决策，Skill 执行 | ✅ |
| 跨 Runtime 走 Gateway | 二次路由只通过 Gateway._reroute | ✅ |

## 已知限制

- 不支持多 Session 隔离（Phase 3）
- 无优先级仲裁 / 安全 Gate（Phase 3）
- 无 Trace 记录（Phase 3）
- Navigation Runtime 为占位
- 部分 Bridge 能力（情绪、TTS、颈部控制）暂不可用
- 对话无历史记忆
