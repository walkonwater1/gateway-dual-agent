# Robot Agent Runtime 文件架构与模块关系说明

## 1. 项目定位

本项目是一个面向机器人本体的 **Agent Runtime 框架**，采用 **Gateway 中央路由 + 三 Runtime 子系统 + 三个 Multi-Agent 子系统** 的架构。

框架目标是将机器人系统中的 **交互、导航、运控** 三类复杂能力进行分层解耦，并通过统一 Gateway、统一消息协议、统一 Session、统一 Trace 和统一 Harness 体系进行组织、调度、治理和验证。

整体架构可以概括为：

```text
用户 / 环境 / 系统事件
        ↓
      apps
        ↓
     Gateway
        ↓
 ┌───────────────┬────────────────┬────────────────┐
 ↓               ↓                ↓
交互 Runtime     导航 Runtime      运控 Runtime
 ↓               ↓                ↓
交互 Agent 群    导航 Agent 群     运控 Agent 群
 ↓               ↓                ↓
交互 Skill       导航 Skill        运控 Skill
 ↓               ↓                ↓
Knowledge / Memory / Capabilities / Robot APIs
        ↓
Harness / Logs / Replay / Evaluation
```

一句话总结：

> Gateway 是中央协调层，三个 Runtime 是机器人智能系统的三个业务子系统；Agent 负责判断、规划和协作，Skill 负责业务执行，Knowledge、Memory 和 Capabilities 提供公共能力支撑，Harness 负责测试、仿真、回放和评估。

---

## 2. 顶层文件结构

```text
robot-agent-runtime/
├── apps/
├── shared/
├── gateway/
├── runtimes/
├── agents/
├── skills/
├── knowledge/
├── memory/
├── capabilities/
├── harness/
├── configs/
├── logs/
├── tests/
└── main.py
```

各模块的整体职责如下：

| 模块 | 作用 |
|---|---|
| `apps/` | 系统启动入口 |
| `shared/` | 全局公共协议、基类、日志、错误与 Trace |
| `gateway/` | 中央路由、状态同步、冲突仲裁和安全前置 |
| `runtimes/` | 三个 Runtime 子系统：交互、导航、运控 |
| `agents/` | 三类 Multi-Agent 子系统 |
| `skills/` | 交互、导航、运控业务技能 |
| `knowledge/` | 知识库、向量库、检索、RAG 与知识治理 |
| `memory/` | 工作记忆、短期记忆、本地长期记忆、云端长期记忆 |
| `capabilities/` | 边缘云、云端、机器人本体接口适配 |
| `harness/` | 测试、仿真、回放、评估与报告 |
| `configs/` | Gateway、Runtime、Agent、Skill、Knowledge、Memory 配置 |
| `logs/` | 运行日志、Trace、审计记录 |
| `tests/` | 单元测试 |
| `main.py` | 默认统一入口 |

---

## 3. apps：系统启动入口

```text
apps/
├── robot_app.py
├── interaction_app.py
├── navigation_app.py
├── motion_app.py
└── replay_app.py
```

`apps/` 用于定义不同运行模式下的启动入口。

主要职责：

- 启动完整机器人系统
- 单独启动某个 Runtime
- 加载配置
- 初始化 Gateway、Runtime、Agent、Skill 和 Capability
- 启动回放或测试模式

模块关系：

```text
apps
 ↓
读取 configs
 ↓
启动 Gateway 或指定 Runtime
 ↓
进入系统运行流程
```

典型入口：

- `robot_app.py`：启动完整机器人 Runtime 系统
- `interaction_app.py`：只启动交互 Runtime，用于调试语音、对话、知识问答
- `navigation_app.py`：只启动导航 Runtime，用于调试地图、路径规划和导航任务
- `motion_app.py`：只启动运控 Runtime，用于调试动作、Skill、VLA、遥操
- `replay_app.py`：启动日志回放和链路复现

---

## 4. shared：全局公共协议层

```text
shared/
├── message.py
├── result.py
├── event.py
├── trace.py
├── session.py
├── context.py
├── base_agent.py
├── base_runtime.py
├── base_skill.py
├── registry.py
├── permission.py
├── logger.py
└── errors.py
```

`shared/` 是整个框架的公共基础层，用于保证 Gateway、Runtime、Agent、Skill、Harness 之间使用同一套协议。

主要职责：

- 定义统一消息结构
- 定义统一返回结果
- 定义统一事件结构
- 定义统一 Trace 结构
- 定义 Session 与 Context 数据结构
- 定义 Agent / Runtime / Skill 基类
- 提供注册机制
- 提供权限模型
- 提供日志模型
- 提供统一错误类型

模块关系：

```text
Gateway 使用 shared/message.py
Runtime 使用 shared/base_runtime.py
Agent 使用 shared/base_agent.py
Skill 使用 shared/base_skill.py
Harness 使用 shared/trace.py 和 shared/result.py
```

设计原则：

> `shared/` 只定义协议和基础抽象，不写具体业务逻辑。

如果没有 `shared/`，三个 Runtime 会各自定义消息格式，后续会导致系统难以集成、调试和回放。

---

## 5. gateway：中央路由与协调中枢

```text
gateway/
├── app.py
├── gateway.py
├── router.py
├── route_policy.py
├── session_router.py
├── runtime_router.py
├── conflict_resolver.py
├── priority_manager.py
├── safety_gate.py
├── event_bus.py
└── config.yaml
```

Gateway 是三个 Runtime 之间的统一入口和协调中心。

主要职责：

- 接收用户输入、系统事件、机器人状态事件
- 判断请求类型
- 判断请求应进入哪个 Runtime
- 维护全局 Session 引用
- 管理跨 Runtime 的消息路由
- 管理 Runtime 之间的状态同步
- 处理任务优先级
- 处理打断、暂停、恢复
- 处理跨 Runtime 冲突
- 做安全前置过滤
- 记录全链路 Trace
- 广播 Runtime 间事件

Gateway 与 Runtime 的推荐关系：

```text
Interaction Runtime
        ↓
      Gateway
        ↓
Navigation Runtime
        ↓
      Gateway
        ↓
Motion Runtime
```

不推荐 Runtime 之间直接互调：

```text
Interaction Runtime → Navigation Runtime → Motion Runtime
```

Gateway 应该是“薄中枢”，只负责：

- 路由
- 仲裁
- 状态同步
- 权限判断
- 安全前置
- 事件分发

Gateway 不应该承担：

- 对话生成
- 路径规划
- 动作规划
- 知识问答
- 运控决策

专业决策应放在对应 Runtime 内部完成。

---

## 6. runtimes：三个 Runtime 子系统

```text
runtimes/
├── interaction_runtime/
├── navigation_runtime/
└── motion_runtime/
```

三个 Runtime 分别对应机器人系统中的三类核心能力：

```text
交互 Runtime：负责听懂人、回应人、维持交互体验
导航 Runtime：负责去哪儿、怎么走、如何避障
运控 Runtime：负责身体怎么动、动作如何安全执行
```

---

## 7. interaction_runtime：交互 Runtime

```text
runtimes/interaction_runtime/
├── app.py
├── runtime.py
├── channel.py
├── session_manager.py
├── dialogue_pipeline.py
├── emotion_pipeline.py
├── interruption_manager.py
├── response_streamer.py
├── agent_router.py
└── config.yaml
```

Interaction Runtime 负责人与机器人之间的实时交互链路。

主要职责：

- 语音输入接入
- ASR 流式文本处理
- 多轮对话管理
- 用户打断识别
- 追问、确认、澄清
- 情感状态接入
- 身份信息接入
- 知识问答
- 讲解词生成
- TTS 播报
- 表情策略
- 交互状态写入 Memory

主要调用的 Agent：

```text
agents/interaction_agents/
├── dialogue_agent/
├── emotion_agent/
├── identity_agent/
├── knowledge_agent/
├── memory_agent/
└── interruption_agent/
```

主要调用的 Skill：

```text
skills/interaction_skills/
├── speech_skill/
├── expression_skill/
└── guide_speech_skill/
```

调用关系：

```text
用户输入
 ↓
Gateway
 ↓
Interaction Runtime
 ↓
Dialogue / Knowledge / Memory / Emotion Agents
 ↓
Speech / Expression Skills
 ↓
Edge ASR / TTS / LLM
```

当交互请求涉及导航或动作时，Interaction Runtime 不直接调用导航或运控模块，而是通过 Gateway 请求对应 Runtime。

示例：

```text
用户：带我去爱湫展区
 ↓
Interaction Runtime 识别意图
 ↓
Gateway 路由
 ↓
Navigation Runtime 执行导航任务
```

---

## 8. navigation_runtime：导航 Runtime

```text
runtimes/navigation_runtime/
├── app.py
├── runtime.py
├── nav_task_manager.py
├── map_manager.py
├── localization_manager.py
├── path_planner.py
├── obstacle_manager.py
├── nav_state_sync.py
├── agent_router.py
└── config.yaml
```

Navigation Runtime 负责空间理解、地图、定位和导航任务。

主要职责：

- 目标点解析
- 地图管理
- 定位状态管理
- 路径规划
- 动态避障
- 导航任务执行
- 导航进度反馈
- 导航失败重规划
- 多机器人导航协同
- 导航状态同步

主要调用的 Agent：

```text
agents/navigation_agents/
├── map_agent/
├── localization_agent/
├── route_planner_agent/
├── obstacle_agent/
├── navigation_task_agent/
└── nav_safety_agent/
```

主要调用的 Skill：

```text
skills/navigation_skills/
├── navigate_to_skill/
├── follow_user_skill/
├── return_home_skill/
└── multi_robot_nav_skill/
```

调用关系：

```text
Gateway
 ↓
Navigation Runtime
 ↓
Map / Localization / Route Planner / Obstacle Agents
 ↓
Navigation Skills
 ↓
capabilities/robot/nav_api.py
 ↓
机器人本体导航系统
```

导航过程中的状态会回传给 Gateway，再由 Gateway 同步给 Interaction Runtime 进行语音播报或用户反馈。

示例：

```text
Navigation Runtime：当前已完成 60%
 ↓
Gateway
 ↓
Interaction Runtime
 ↓
Speech Skill：正在带您前往爱湫展区，马上就到
```

---

## 9. motion_runtime：运控 Runtime

```text
runtimes/motion_runtime/
├── app.py
├── runtime.py
├── motion_task_manager.py
├── skill_scheduler.py
├── action_sequence_manager.py
├── teleop_manager.py
├── vla_adapter.py
├── motion_safety_pipeline.py
├── robot_control_bridge.py
├── agent_router.py
└── config.yaml
```

Motion Runtime 负责机器人动作、姿态、动作序列、Skill 调度、VLA 和遥操承接。

主要职责：

- 动作 Skill 调度
- 动作序列执行
- 手势动作执行
- 姿态控制
- 步态协同
- VLA 动作承接
- 边缘云动作生成结果承接
- 遥操接管
- 运动安全检查
- 机器人本体控制接口调用

主要调用的 Agent：

```text
agents/motion_agents/
├── motion_planner_agent/
├── skill_agent/
├── action_sequence_agent/
├── gait_agent/
├── posture_agent/
├── manipulation_agent/
├── teleop_agent/
├── vla_agent/
└── motion_safety_agent/
```

主要调用的 Skill：

```text
skills/motion_skills/
├── wave_skill/
├── nod_skill/
├── gesture_skill/
├── action_sequence_skill/
├── teleop_skill/
└── vla_action_skill/
```

调用关系：

```text
Gateway
 ↓
Motion Runtime
 ↓
Motion Planner / Skill / Action Sequence / Safety Agents
 ↓
Motion Skills
 ↓
capabilities/robot/motion_api.py
 ↓
机器人本体控制系统
```

关键边界：

Motion Runtime 可以负责：

- 技能级动作
- 行为级动作
- 动作序列承接
- 姿态协同
- 遥操接管
- VLA 结果承接

Motion Runtime 不应该负责：

- 毫秒级电机控制
- 关节级闭环控制
- WBC / MPC 的实时底层求解
- 电机驱动控制

这些应由机器人本体控制系统负责。

---

## 10. agents：多 Agent 子系统

```text
agents/
├── interaction_agents/
├── navigation_agents/
└── motion_agents/
```

Agent 是 Runtime 内部的决策、规划、判断和协作单元。

Agent 负责：

- 理解任务
- 判断意图
- 拆解目标
- 协调工具与 Skill
- 读取 Knowledge
- 读取或写入 Memory
- 输出结构化结果
- 给 Runtime 提供决策建议

Agent 与 Runtime 的关系：

```text
Runtime
 ↓
Agent Router
 ↓
Agent
 ↓
AgentResult
 ↓
Runtime 汇聚结果
```

Agent 不应直接跨 Runtime 调用其他 Agent。跨 Runtime 协作应交给 Gateway。

Agent 与 Skill 的推荐关系：

```text
Runtime
 ↓
Agent
 ↓
Skill
 ↓
Capabilities
 ↓
Robot API
```

---

## 11. skills：业务能力执行单元

```text
skills/
├── interaction_skills/
├── navigation_skills/
└── motion_skills/
```

Skill 是完整业务能力的封装。

Agent 和 Skill 的区别：

```text
Agent：负责判断、规划、协作
Skill：负责执行具体业务能力
```

示例：

```text
Dialogue Agent 决定说什么
Speech Skill 负责播报

Navigation Task Agent 决定去哪里
Navigate To Skill 负责启动导航

Motion Planner Agent 决定做什么动作
Gesture Skill 负责执行动作
```

Skill 通过 `capabilities/` 调用具体外部能力或机器人本体接口。

```text
Speech Skill → capabilities/edge/tts_client.py
Navigate To Skill → capabilities/robot/nav_api.py
Gesture Skill → capabilities/robot/motion_api.py
```

---

## 12. knowledge：知识库与向量库系统

```text
knowledge/
├── document_store/
├── vector_store/
├── retrievers/
├── indexers/
├── embeddings/
├── rerankers/
├── policies/
└── cache/
```

Knowledge System 是框架内的一等模块，不只是一个简单工具。

主要职责：

- 文档存储
- 向量存储
- 关键词检索
- 向量检索
- 混合检索
- Embedding 生成
- Rerank
- 知识缓存
- 知识权限控制
- 知识新鲜度控制
- 对外口径控制

主要调用链路：

```text
用户提问
 ↓
Interaction Runtime
 ↓
Knowledge Agent
 ↓
knowledge/retrievers
 ↓
vector_store + document_store
 ↓
返回知识片段
 ↓
Dialogue Agent 生成回复
```

Knowledge 和 Memory 的区别：

```text
Knowledge：公共知识，例如公司、产品、技术、场景、FAQ
Memory：用户相关信息，例如偏好、上下文、历史交互、情感状态
```

---

## 13. memory：记忆与画像系统

```text
memory/
├── working_memory.py
├── short_term_memory.py
├── local_long_term_memory.py
├── cloud_long_term_memory.py
├── profile_store.py
└── memory_policy.py
```

Memory System 用于保存机器人与用户交互过程中产生的上下文和长期沉淀。

四层记忆：

```text
Working Memory：
当前轮输入、ASR 中间结果、TTS 状态、当前任务状态

Short-term Memory：
当前会话热数据、最近对话、临时偏好、任务中间结果

Local Long-term Memory：
本台机器人本地积累的用户偏好、场景习惯、交互摘要

Cloud Long-term Memory：
跨机器人、跨场景的长期用户画像和长期事实
```

长期写入建议通过 Memory Agent 和 Memory Policy 统一治理。

推荐关系：

```text
Runtime / Agent
 ↓
Memory Agent
 ↓
Memory Policy
 ↓
Working / Short-term / Local Long-term / Cloud Long-term Memory
```

---

## 14. capabilities：外部能力适配层

```text
capabilities/
├── edge/
├── cloud/
└── robot/
```

Capabilities 负责连接 Runtime、Skill 与外部能力。

### 14.1 edge：边缘云能力

```text
capabilities/edge/
├── asr_client.py
├── tts_client.py
├── fast_llm_client.py
├── vision_client.py
├── emotion_client.py
└── motion_generation_client.py
```

主要负责低时延能力：

- ASR
- TTS
- 快速 LLM
- Vision
- 情感识别
- 动作生成

### 14.2 cloud：云端能力

```text
capabilities/cloud/
├── reasoning_client.py
├── knowledge_client.py
├── profile_client.py
└── long_memory_client.py
```

主要负责重能力：

- 复杂推理
- 云端知识库
- 用户画像
- 长期记忆
- 跨机器人数据同步

### 14.3 robot：机器人本体接口

```text
capabilities/robot/
├── robot_api.py
├── ros_bridge.py
├── nav_api.py
├── motion_api.py
└── status_api.py
```

主要负责连接机器人本体软件：

- ROS Bridge
- 导航接口
- 动作接口
- 状态接口
- 机器人统一 API

Skill 与 Capability 的关系：

```text
Skill
 ↓
Capabilities
 ↓
Edge / Cloud / Robot
```

---

## 15. harness：测试、仿真、回放、评估系统

```text
harness/
├── gateway_harness/
├── interaction_harness/
├── navigation_harness/
├── motion_harness/
├── agent_harness/
├── skill_harness/
├── knowledge_harness/
├── memory_harness/
├── simulation/
├── replay/
├── evaluation/
├── mocks/
└── reports/
```

Harness 是工程验证系统，不是业务运行系统。

主要职责：

- 测试 Gateway 路由是否正确
- 测试三个 Runtime 是否能独立运行
- 测试三个 Runtime 是否能协同运行
- 测试 Agent 输入输出是否符合协议
- 测试 Skill 是否正确执行
- 测试 Knowledge 检索是否准确
- 测试 Memory 是否乱写
- 模拟 ASR / TTS / Robot API / Cloud API
- 回放真实运行日志
- 评估延迟、成功率、安全性和稳定性

Harness 与 Logs 的关系：

```text
Runtime / Gateway / Agent / Skill
 ↓
Trace / Logs
 ↓
Harness Replay
 ↓
Evaluation
 ↓
Reports
```

Harness 的价值在于：可以在不上真机的情况下验证大部分系统链路。

---

## 16. configs：配置中心

```text
configs/
├── gateway.yaml
├── interaction_runtime.yaml
├── navigation_runtime.yaml
├── motion_runtime.yaml
├── agents.yaml
├── skills.yaml
├── knowledge.yaml
├── memory.yaml
├── capabilities.yaml
└── safety.yaml
```

Configs 负责：

- Gateway 路由规则配置
- Runtime 启用配置
- Agent 注册配置
- Skill 注册配置
- Knowledge 参数配置
- Memory 策略配置
- Edge / Cloud / Robot 接口配置
- Safety 策略配置

模块关系：

```text
apps 启动
 ↓
读取 configs
 ↓
加载 Gateway / Runtime / Agent / Skill / Capability
```

新增 Agent 或 Skill 时，理想情况下不应修改 Runtime 主逻辑，只需要：

```text
1. 新增 Agent / Skill 文件夹
2. 增加 manifest 或 config
3. 在 configs 中注册
4. 使用 Harness 验证
```

---

## 17. logs：运行日志与 Trace

```text
logs/
```

Logs 用于保存运行过程中的链路日志和 Trace 信息。

建议记录：

- 输入事件
- Gateway 路由结果
- Runtime 调用链路
- Agent 消息
- Skill 执行状态
- Knowledge 检索结果
- Memory 写入记录
- 外部能力调用
- 错误和降级
- 延迟指标

Logs 与 Harness 的关系：

```text
logs
 ↓
harness/replay
 ↓
复现问题
 ↓
生成报告
```

---

## 18. tests：单元测试

```text
tests/
```

`tests/` 和 `harness/` 的区别：

```text
tests：
测试具体函数、类、模块是否正确

harness：
测试完整业务链路是否正确
```

示例：

```text
tests 测 Message 是否能序列化
harness 测“带我去爱湫展区并介绍一下爱湫”是否能完整跑通
```

---

## 19. main.py：统一默认入口

```text
main.py
```

`main.py` 是项目的默认入口，可以根据配置或命令行参数启动不同模式。

例如：

- 启动完整机器人系统
- 启动交互 Runtime
- 启动导航 Runtime
- 启动运控 Runtime
- 启动回放模式
- 启动 Harness 测试模式

---

## 20. 典型任务链路

### 20.1 普通知识问答

```text
用户：介绍一下爱湫
 ↓
Gateway
 ↓
Interaction Runtime
 ↓
Knowledge Agent
 ↓
Knowledge System
 ↓
Dialogue Agent
 ↓
Speech Skill
 ↓
TTS
```

### 20.2 导航任务

```text
用户：带我去爱湫展区
 ↓
Gateway
 ↓
Interaction Runtime：确认意图
 ↓
Gateway
 ↓
Navigation Runtime
 ↓
Navigation Agents
 ↓
Navigate To Skill
 ↓
Robot Nav API
 ↓
Gateway 回传状态
 ↓
Interaction Runtime 播报进度
```

### 20.3 动作任务

```text
用户：挥个手
 ↓
Gateway
 ↓
Interaction Runtime：理解意图
 ↓
Gateway
 ↓
Motion Runtime
 ↓
Motion Agents
 ↓
Wave Skill
 ↓
Robot Motion API
 ↓
Gateway 回传结果
 ↓
Interaction Runtime 回复用户
```

### 20.4 复杂组合任务

```text
用户：带我去爱湫展区，边走边介绍，到了以后做个欢迎动作
 ↓
Gateway
 ↓
Interaction Runtime：理解任务、生成初始回复
 ↓
Gateway
 ↓
Navigation Runtime：执行导航
 ↓
Gateway
 ↓
Interaction Runtime：边走边讲解
 ↓
Gateway
 ↓
Motion Runtime：到达后执行欢迎动作
 ↓
Gateway：持续同步状态、处理冲突、记录 Trace
```

---

## 21. 核心设计原则

### 21.1 Gateway 管路由，不管专业执行

Gateway 只负责：

- 接入
- 路由
- 仲裁
- 安全前置
- 状态同步
- Trace

Gateway 不负责：

- 对话生成
- 路径规划
- 动作规划
- 底层控制

---

### 21.2 Runtime 管子系统，Agent 管能力单元

```text
Interaction Runtime 管交互链路
Navigation Runtime 管导航链路
Motion Runtime 管运控链路

Agent 是 Runtime 内部的判断和协作单元
Skill 是 Runtime 调用的业务执行单元
```

---

### 21.3 跨 Runtime 通信统一走 Gateway

推荐：

```text
Runtime A
 ↓
Gateway
 ↓
Runtime B
```

不推荐：

```text
Runtime A
 ↓
Runtime B
```

这样可以保证所有跨 Runtime 行为都能被记录、治理、回放和审计。

---

### 21.4 LLM / Agent 不直接控制机器人底层

Agent Runtime 负责：

- 任务级决策
- 行为级决策
- Skill 级调度

机器人本体控制系统负责：

- 轨迹级执行
- 控制级执行
- 电机级执行

---

### 21.5 Knowledge 和 Memory 要分离

```text
Knowledge：
公司、产品、技术、场景、FAQ 等公共知识

Memory：
用户偏好、上下文、历史交互、身份、情感状态等用户相关信息
```

生成回复时可以融合：

```text
Knowledge Context + User Memory + Current Session
```

但两者的写入、读取、权限和生命周期需要分开治理。

---

## 22. 最终总结

当前文件架构可以概括为：

> 以 Gateway 为中央中枢，以 Interaction / Navigation / Motion 三个 Runtime 为业务子系统，以三类 Multi-Agent 子系统承担理解、规划、协作和决策，以 Skill 承接具体业务执行，以 Knowledge、Memory、Capabilities 提供公共能力支撑，并通过 Harness、Logs、Tests 实现测试、回放、评估和工程治理的机器人 Agent Runtime 框架。

该架构的核心价值不是简单地实现多个 Agent 对话，而是将机器人系统中的 **交互、导航、运控** 三个复杂子系统通过统一 Gateway 和统一协议组织起来，使 Agent 能够参与高层理解、任务规划、知识增强、记忆治理和安全协作，同时避免 Agent 越过安全边界直接控制机器人底层系统。
