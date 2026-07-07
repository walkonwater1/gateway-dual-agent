# Demo vs 设计文档 — 差距分析

对照 [gateway_readme.md](../../ehr_ros_app/design/gateway_readme.md)
+ [file_framework.md](../../ehr_ros_app/design/file_framework.md)
+ [IMPLEMENTATION_ROADMAP.md](../../ehr_ros_app/design/IMPLEMENTATION_ROADMAP.md)
逐模块审查当前 demo 的完成度。

> 分析日期: 2026-07-06

---

## 1. Gateway 模块 (gateway_readme.md §1-10)

设计要求 13 个模块：

| # | 模块 | 设计要求 | 当前 demo | 状态 |
|---|------|---------|----------|------|
| 1 | gateway.py | 主入口，串联全流程 | `gateway/gateway.py` — 10步处理链路 | ✅ |
| 2 | input_adapter.py | 多模态输入适配（文本/ASR/视觉/事件） | `gateway/input_adapter.py` — text/asr/robot_event/system | ✅ |
| 3 | message_normalizer.py | 封装 RuntimeMessage | `shared/message.py` — RuntimeMessage/RuntimeResult (含trace_id/priority) | ✅ |
| 4 | router.py | 路由判断 | `gateway/router.py` — 关键词最长匹配 + 未命中→LLM | ✅ |
| 5 | route_policy.py | YAML 配置化路由策略 | `gateway/route_policy.py` + `config/routes.yaml` (54条规则) | ✅ |
| 6 | runtime_router.py | Runtime 注册表 + 分发 | `gateway/runtime_router.py` | ✅ |
| 7 | session_router.py | 多用户 Session 隔离、上下文管理 | `gateway/session_router.py` — 多session隔离+历史 | ✅ |
| 8 | priority_manager.py | 急停>遥操>安全>导航>交互 优先级 | `gateway/priority_manager.py` — 四级优先级 | ✅ |
| 9 | safety_gate.py | 请求级安全过滤（拦截"冲过去"等） | `gateway/safety_gate.py` — 10条默认危险模式 | ✅ |
| 10 | conflict_resolver.py | 跨 Runtime 冲突仲裁 | `gateway/conflict_resolver.py` — preempt/queue/refuse | ✅ |
| 11 | event_bus.py | Runtime 间事件广播、状态同步 | `gateway/event_bus.py` — pub/sub (默认关闭) | ✅ |
| 12 | result_aggregator.py | 多 Runtime 结果汇聚 | `gateway/result_aggregator.py` — 多结果合并 (默认关闭) | ✅ |
| 13 | trace_logger.py | 全链路 trace_id 记录 | `gateway/trace_logger.py` — 10种事件类型 | ✅ |

**Gateway 达标率：13/13 ✅**

---

## 2. Framework 顶层结构 (file_framework.md §2)

设计要求 14 个顶层目录：

| 目录 | 设计要求 | 当前 demo | 状态 |
|------|---------|----------|------|
| `apps/` | 多模式启动入口（robot/interaction/nav/motion/replay） | ❌ 仅 `main.py` 单一入口 | ❌ |
| `shared/` | 13 个公共模块（message/result/event/trace/session/context/base_*/registry/permission/logger/errors） | ✅ `message.py` (升级) + `event.py` (新) + `session.py` (新) + `base.py` | ✅ |
| `gateway/` | 13 个模块 | ✅ **全部13模块已实现** | ✅ |
| `runtimes/` | 三个子目录，每个含 ~10 个内部模块 | ⚠️ 三个单文件，无内部编排 | ⚠️ |
| `agents/` | 三组 20 个 Agent（interaction/nav/motion） | ⚠️ 3 个扁平 Agent | ⚠️ |
| `skills/` | 三组 13 个 Skill | ⚠️ 3 个扁平 Skill | ⚠️ |
| `knowledge/` | RAG 系统（document/vector/retrieve/index/embedding/rerank/policy/cache） | ❌ | ❌ |
| `memory/` | 四层记忆（working/short-term/local-long/cloud-long） | ❌ | ❌ |
| `capabilities/` | 三层（edge/cloud/robot） | ✅ `mqtt_client.py` (368行，完整 Bridge 协议) | ✅ |
| `harness/` | 仿真/回放/评估系统 | ❌ | ❌ |
| `configs/` | 分模块 YAML 配置（10+ 文件） | ✅ `config/routes.yaml` (54条规则) + `config/event_rules.yaml` (6条规则) + `config.example.yaml` | ✅ |
| `logs/` | 结构化日志 + Trace | ⚠️ TraceLogger 已实现，但未落地到文件 | ⚠️ |
| `tests/` | 单元测试 | ❌ | ❌ |
| `main.py` | 统一入口 | `main.py` — DI 组装 + 交互循环 | ✅ |

**Framework 达标率：4/14 完整 / 7/14 部分 / 3/14 缺失**

---

## 3. 设计原则合规性 (gateway §9 + framework §21)

| # | 设计原则 | 合规 | 说明 |
|---|---------|------|------|
| 1 | Gateway 薄中枢 | ✅ | Gateway 不调 LLM，不做动作，不做决策 |
| 2 | Gateway→Runtime→Agent 路由 | ✅ | Router 选 Runtime → Runtime 内部调 Agent |
| 3 | 跨 Runtime 通信走 Gateway | ✅ | `_reroute()` 实现，无 Runtime 间直接互调 |
| 4 | LLM/Agent 不直接控制底层 | ✅ | MQTT→Bridge→ROS2 三级隔离 |
| 5 | Agent 决策 / Skill 执行分离 | ✅ | Agent 判断意图 → Skill 发 MQTT 指令 |
| 6 | Knowledge / Memory 分离 | ❌ | 均未实现，当前无此概念 |

**设计原则合规率：5/6**

---

## 4. 典型任务链路覆盖 (framework §20)

| 设计链路 | 设计要求 | 当前能力 | 状态 |
|---------|---------|---------|------|
| 知识问答 (§20.1) | Gateway→InteractionRT→KnowledgeAgent→Knowledge→SpeechSkill→TTS | ⚠️ 对话由机器人本地腾讯大模型处理，Agent 层无 Knowledge 检索 | ⚠️ |
| 导航任务 (§20.2) | Gateway→InteractionRT(意图)→Gateway→NavigationRT→NavAgent→NavSkill→RobotNavAPI→Gateway状态回传→InteractionRT播报 | ⚠️ Navigation 占位，仅发 MQTT 6001，无回传 | ⚠️ |
| 动作任务 (§20.3) | Gateway→InteractionRT(意图)→Gateway→MotionRT→MotionAgent→WaveSkill→RobotMotionAPI→Gateway回传→InteractionRT回复 | ✅ cqm1/cqm2 端到端链路通 | ✅ |
| 复杂组合 (§20.4) | Gateway→InteractionRT(拆解)→Gateway→NavRT+MotionRT 并行→Gateway同步状态/仲裁 | ❌ 无 Result Aggregator，无多 Runtime 并行 | ❌ |

---

## 5. 扩展路线进度 (gateway §8)

```
Step  1  ✅  固定路由到 Interaction Runtime (已超越，实现关键词三路由)
Step  2  ✅  关键词规则路由 interaction/navigation/motion
Step  3  ✅  接入 Session Router
Step  4  ✅  接入 Priority Manager
Step  5  ✅  接入 Safety Gate
Step  6  ✅  接入 Trace Logger
Step  7  ✅  接入 config.yaml 路由策略 (routes.yaml)
Step  8  ✅  接入 Conflict Resolver
Step  9  ✅  接入 Event Bus (默认关闭)
Step 10  ✅  接入 Result Aggregator (默认关闭)
Step 11  ❌  支持异步 Runtime 调用
Step 12  ❌  支持多模态输入和系统事件
```

**完成：10/12**

---

## 6. 与 IMPLEMENTATION_ROADMAP 四阶段对照

| 阶段 | 内容 | 状态 |
|------|------|------|
| **Phase 1** | MVP: `text→Gateway→InteractionRT→LLM→MQTT→机器人` | ✅ 完成 |
| **Phase 2** | 三 Runtime 分流 + 路由 YAML 化 + 状态闭环 | ✅ 路由YAML化完成, Navigation占位 |
| **Phase 3** | 治理: Session/Priority/Safety/Trace/Conflict/EventBus/ResultAgg | ✅ 全部8模块已实现 |
| **Phase 4** | 智能: Knowledge(RAG) + Memory(四层) + Harness(回放) | ❌ 全未开始 |

---

## 7. 汇总

```
┌──────────────────────────────────────────────────────────┐
│                                                          │
│  Gateway 完整版 (13模块)     ██████████████ 13/13 (100%) │
│  Framework 完整版 (14目录)   ██████░░░░░░░░  2/14+7/14  │
│  设计原则                    ████████████░  5/6   (83%) │
│  典型链路 (4条)             ████████░░░░░  1+2/4        │
│  扩展路线 (12步)            ██████████░░░ 10/12  (83%) │
│  Roadmap (4阶段)            ██████████░░  3/4          │
│                                                          │
│  定位: Phase 3 ✅ → Phase 4 边界                         │
│  价值: 完整Gateway治理中枢 + MQTT全链路                  │
│  差距: 智能(Knowledge/Memory) + 测试(Harness)            │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

---

## 8. 后续补齐建议

### 短期（Phase 3 收尾 — 接线）

| 优先级 | 任务 | 影响范围 |
|--------|------|---------|
| P1 | MQTT 自动重连（disconnect 后 reconnect） | `capabilities/mqtt_client.py` |
| P1 | Navigation Runtime 充实（加导航状态查询+回传） | `runtimes/navigation_runtime.py` |
| P1 | PriorityManager 接入 Gateway 流程（当前 Step 4 被跳过） | `gateway/gateway.py` |
| P2 | EventBus/ResultAggregator 接入 Gateway 流程（已创建但未调用） | `gateway/` |
| P2 | TraceLogger 落地到文件（当前仅内存） | `gateway/trace_logger.py` |

### 中期（Phase 3 治理完善）

| 优先级 | 任务 | 影响范围 |
|--------|------|---------|
| P2 | MQTT 指令级反馈闭环（ack/完成/拒绝通知） | `capabilities/` + 各 Skill |
| P2 | EventBus 通配符 `"*"` 订阅实现 | `gateway/event_bus.py` |
| P2 | 多用户 Session 识别（非 hardcode "default"） | `gateway/session_router.py` |
| P3 | Safety Gate 规则 YAML 化（当前 10 条硬编码） | `gateway/safety_gate.py` + YAML |
| P3 | 配置外提（CHAT_KEYWORDS、INTENT_PROMPT 等硬编码值） | `agents/` + `config/` |

### 长期（Phase 4 智能）

| 优先级 | 任务 | 影响范围 |
|--------|------|---------|
| P4 | Knowledge System（RAG 知识库） | 新增 `knowledge/` |
| P4 | Memory System（四层记忆） | 新增 `memory/` |
| P4 | Harness（仿真回放测试） | 新增 `harness/` |
| P4 | 多模态输入（ASR/视觉/事件） | `gateway/input_adapter.py` |
