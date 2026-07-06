# Gateway README

## 1. Gateway 定位

Gateway 是机器人 Agent Runtime 框架中的**统一入口、Runtime 路由中枢和运行治理层**。

在当前架构中，系统包含三个 Runtime：

1. **Interaction Runtime**：负责交互、对话、知识问答、情感、记忆、TTS 等。
2. **Navigation Runtime**：负责地图、定位、路径规划、避障、导航任务等。
3. **Motion Runtime**：负责动作、姿态、Skill 调度、动作序列、VLA、遥操和运动安全等。

Gateway 位于三者之间，负责把用户输入、系统事件、机器人状态事件统一接入、标准化、路由和治理。

整体关系如下：

```text
用户 / 环境 / 系统事件
        ↓
      Gateway
        ↓
 ┌───────────────┬────────────────┬────────────────┐
 ↓               ↓                ↓
交互 Runtime     导航 Runtime      运控 Runtime
```

Gateway 不是简单的文本路由器。

更准确地说：

> Gateway = 多模态输入入口 + 消息标准化 + 意图分流 + Runtime 路由 + Session 管理 + 优先级管理 + 安全前置 + 冲突仲裁 + 事件同步 + Trace 记录。

---

## 2. Gateway 的核心职责

Gateway 主要负责以下工作：

```text
1. 接收输入
2. 标准化消息
3. 识别意图
4. 判断目标 Runtime
5. 分发消息
6. 管理 Session
7. 管理优先级
8. 做安全前置过滤
9. 处理 Runtime 间冲突
10. 广播事件和同步状态
11. 汇聚多个 Runtime 的结果
12. 记录 Trace 和日志
```

Gateway 不负责具体专业决策。

它不应该承担：

```text
1. 对话生成
2. 路径规划
3. 动作规划
4. 知识检索
5. 底层控制
6. 复杂任务执行
```

这些工作应该交给对应 Runtime 和 Agent 子系统完成。

---

## 3. Gateway 文件结构

完整版本 Gateway 建议包含以下文件：

```text
gateway/
├── gateway.py              # Gateway 主入口
├── input_adapter.py        # 输入接入
├── message_normalizer.py   # 消息标准化
├── router.py               # 路由判断
├── route_policy.py         # 路由策略
├── runtime_router.py       # Runtime 分发
├── session_router.py       # Session 管理
├── priority_manager.py     # 优先级管理
├── safety_gate.py          # 安全前置过滤
├── conflict_resolver.py    # 冲突仲裁
├── event_bus.py            # 事件总线
├── result_aggregator.py    # 结果汇聚
├── trace_logger.py         # Trace 记录
└── config.yaml             # Gateway 配置
```

---

## 4. 各模块说明

### 4.1 gateway.py

`gateway.py` 是 Gateway 的主入口。

负责：

```text
1. 接收外部调用
2. 调用 Input Adapter
3. 调用 Message Normalizer
4. 调用 Session Router
5. 调用 Safety Gate
6. 调用 Router
7. 调用 Runtime Router
8. 调用 Result Aggregator
9. 返回最终结果
```

典型入口函数：

```python
class Gateway:
    def handle_text(self, text: str, session_id: str = "default_session"):
        ...
        
    def handle_event(self, event: dict):
        ...
```

第一阶段可以只实现：

```python
handle_text(text)
```

后续再扩展：

```python
handle_asr_event(event)
handle_vision_event(event)
handle_robot_status(event)
handle_remote_control_event(event)
```

---

### 4.2 input_adapter.py

`input_adapter.py` 负责接收不同来源的输入，并转换为内部可处理的初始事件。

输入来源包括：

```text
1. 用户文本
2. ASR 语音识别结果
3. 视觉事件
4. 情感识别结果
5. 机器人状态事件
6. 导航状态事件
7. 运控状态事件
8. 遥操接管事件
9. VLA 输出
10. 边缘云动作生成结果
11. 多机器人协作事件
```

第一版只需要支持：

```text
text input
```

---

### 4.3 message_normalizer.py

`message_normalizer.py` 负责把不同来源的输入统一封装成标准消息。

建议统一为：

```json
{
  "message_id": "msg_001",
  "trace_id": "trace_001",
  "session_id": "session_001",
  "source": "user",
  "input_type": "text",
  "intent": "user_text_input",
  "payload": {
    "text": "介绍一下爱湫"
  },
  "context": {},
  "priority": "normal"
}
```

这样后续 Runtime 不需要关心输入来自文本、语音、视觉还是系统事件。

---

### 4.4 router.py

`router.py` 是 Gateway 的路由判断模块。

它负责判断当前消息应该进入哪个 Runtime。

典型路由规则：

```text
普通对话 / 知识问答 → interaction_runtime

导航请求 → navigation_runtime

动作请求 / 姿态控制 / 动作序列 / VLA / 遥操 → motion_runtime

停止 / 暂停 / 急停 → high_priority_interrupt
```

第一版可以使用规则路由：

```python
class GatewayRouter:
    def route(self, message):
        text = message.payload.get("text", "")

        if self.is_interrupt_request(text):
            return "high_priority_interrupt"

        if self.is_navigation_request(text):
            return "navigation_runtime"

        if self.is_motion_request(text):
            return "motion_runtime"

        return "interaction_runtime"
```

---

### 4.5 route_policy.py

`route_policy.py` 负责管理路由策略。

路由策略不建议长期写死在代码中，应逐步配置化。

例如：

```yaml
routes:
  interaction:
    runtime: interaction_runtime
    keywords:
      - 介绍
      - 什么是
      - 你好
      - 讲一下

  navigation:
    runtime: navigation_runtime
    keywords:
      - 带我去
      - 导航到
      - 前往
      - 去

  motion:
    runtime: motion_runtime
    keywords:
      - 挥手
      - 点头
      - 转身
      - 跳舞

  interrupt:
    priority: high
    keywords:
      - 停
      - 停止
      - 别动
      - 暂停
```

后续可以从规则路由升级为：

```text
规则路由 + 小模型分类 + LLM Router + Session 状态判断
```

---

### 4.6 runtime_router.py

`runtime_router.py` 负责真正把消息分发到目标 Runtime。

它需要管理 Runtime 注册表：

```python
runtimes = {
    "interaction_runtime": InteractionRuntime(),
    "navigation_runtime": NavigationRuntime(),
    "motion_runtime": MotionRuntime(),
}
```

典型调用：

```python
result = runtime_router.dispatch(
    target_runtime="interaction_runtime",
    message=message
)
```

第一版可以同步调用：

```python
runtime.handle(message)
```

后续可以扩展为：

```text
1. 异步任务
2. 事件队列
3. HTTP 调用
4. WebSocket 调用
5. gRPC 调用
6. ROS2 Topic / Service 调用
```

---

### 4.7 session_router.py

`session_router.py` 负责 Session 管理和上下文路由。

需要维护：

```text
1. session_id
2. user_id
3. 当前用户上下文
4. 当前任务上下文
5. 当前 Runtime 状态
6. 当前活跃任务
7. 多用户上下文隔离
8. 身份切换后的 Session 恢复
```

第一版可以简化为：

```text
所有输入都进入 default_session
```

后续再增加：

```text
1. 多用户识别
2. 身份绑定
3. Session 切换
4. 上下文恢复
5. 用户记忆隔离
```

---

### 4.8 priority_manager.py

`priority_manager.py` 负责请求优先级管理。

机器人系统中，不同事件优先级不同。

建议优先级：

```text
Emergency / 急停
    ↓
Teleop / 遥操接管
    ↓
Motion Safety / 运控安全
    ↓
Navigation / 导航任务
    ↓
Interaction / 普通交互
    ↓
Background / 后台任务
```

例如用户说：

```text
停一下
```

Gateway 不应把它当成普通聊天，而应提升为高优先级事件。

---

### 4.9 safety_gate.py

`safety_gate.py` 是 Gateway 的安全前置模块。

它负责请求级安全过滤。

例如拦截：

```text
1. 冲过去
2. 撞过去
3. 推开他
4. 快速跑向人群
5. 执行危险动作
```

注意：

Gateway 的 Safety Gate 只做前置请求级安全，不替代 Motion Runtime 的动作级安全。

安全应分两层：

```text
Gateway Safety Gate：
请求级安全过滤

Motion Runtime Safety Pipeline：
动作级、姿态级、执行级安全检查
```

---

### 4.10 conflict_resolver.py

`conflict_resolver.py` 负责跨 Runtime 和跨任务冲突仲裁。

典型冲突包括：

```text
1. 导航中用户要求跳舞
2. 导航未结束又要求去另一个地点
3. Motion Runtime 正在执行动作时用户说停止
4. Interaction Runtime 正在播报时用户打断
5. 遥操接管和自动任务冲突
6. 多用户同时提出不同请求
```

Gateway 需要根据优先级和当前状态判断：

```text
1. 继续当前任务
2. 暂停当前任务
3. 取消当前任务
4. 切换到新任务
5. 请求用户确认
6. 触发安全停止
```

---

### 4.11 event_bus.py

`event_bus.py` 负责事件广播和状态同步。

典型场景：

```text
Navigation Runtime：导航进度 60%
        ↓
Gateway Event Bus
        ↓
Interaction Runtime：播报“马上到达”
```

或者：

```text
Motion Runtime：动作执行失败
        ↓
Gateway Event Bus
        ↓
Interaction Runtime：告诉用户“动作没有完成”
```

Event Bus 用于：

```text
1. Runtime 状态同步
2. 任务进度广播
3. 错误事件广播
4. 打断事件广播
5. 安全事件广播
6. 多 Agent / 多 Runtime 状态通知
```

第一版可以不实现 Event Bus，后续再加。

---

### 4.12 result_aggregator.py

`result_aggregator.py` 负责结果汇聚。

有些请求可能涉及多个 Runtime。

例如：

```text
带我去爱湫展区，并介绍一下爱湫
```

可能需要：

```text
Interaction Runtime：理解任务、生成讲解
Navigation Runtime：执行导航
Motion Runtime：执行表情或手势
```

Gateway 最终需要汇聚多个结果：

```text
1. 导航已启动
2. 讲解内容已生成
3. 表情动作已安排
4. 返回用户：好的，我现在带您去爱湫展区，路上为您介绍。
```

第一版可以只返回单个 Runtime 的结果。

---

### 4.13 trace_logger.py

`trace_logger.py` 负责链路记录。

每个输入都应该生成一个 `trace_id`。

建议记录：

```text
1. 输入是什么
2. 归属哪个 Session
3. 路由到了哪个 Runtime
4. 是否触发 Safety Gate
5. 是否触发优先级提升
6. 是否发生冲突仲裁
7. 调用了哪个 Runtime
8. Runtime 是否成功
9. 总耗时多少
10. 最终返回了什么
```

Trace 示例：

```json
{
  "trace_id": "trace_001",
  "events": [
    {
      "type": "input_received",
      "runtime": "gateway",
      "payload": "带我去爱湫展区"
    },
    {
      "type": "route_decided",
      "target_runtime": "navigation_runtime"
    },
    {
      "type": "runtime_called",
      "target_runtime": "navigation_runtime"
    },
    {
      "type": "runtime_result",
      "success": true
    }
  ]
}
```

Trace 的作用：

```text
1. 调试
2. 回放
3. Harness 测试
4. 性能分析
5. 安全审计
```

---

## 5. Gateway 的处理流程

完整 Gateway 处理流程如下：

```text
输入事件
  ↓
Input Adapter
  ↓
Message Normalizer
  ↓
Session Router
  ↓
Priority Manager
  ↓
Safety Gate
  ↓
Router / Route Policy
  ↓
Conflict Resolver
  ↓
Runtime Router
  ↓
目标 Runtime
  ↓
Runtime Result
  ↓
Result Aggregator
  ↓
Trace Logger
  ↓
返回结果 / 广播事件
```

---

## 6. Gateway 与三个 Runtime 的关系

### 6.1 Interaction Runtime

负责：

```text
1. 对话
2. 知识问答
3. 情感交互
4. 身份识别
5. 记忆
6. TTS / 表情反馈
```

Gateway 路由到 Interaction Runtime 的请求包括：

```text
1. 普通聊天
2. 产品介绍
3. 技术问答
4. 用户追问
5. 澄清确认
6. 进度播报
7. 情感反馈
```

---

### 6.2 Navigation Runtime

负责：

```text
1. 地图管理
2. 定位
3. 目标点解析
4. 路径规划
5. 避障
6. 导航任务执行
7. 导航状态反馈
```

Gateway 路由到 Navigation Runtime 的请求包括：

```text
1. 带我去某地
2. 导航到某地
3. 跟随用户
4. 返回充电桩
5. 暂停 / 恢复导航
```

---

### 6.3 Motion Runtime

负责：

```text
1. 动作 Skill 调度
2. 动作序列执行
3. 手势动作
4. 姿态控制
5. VLA 动作承接
6. 遥操接管
7. 运动安全检查
```

Gateway 路由到 Motion Runtime 的请求包括：

```text
1. 挥手
2. 点头
3. 转身
4. 做欢迎动作
5. 执行动作序列
6. 遥操接管
7. 停止动作
```

---

## 7. Gateway MVP 版本

第一阶段不需要完整实现所有模块。

MVP 只需要实现：

```text
1. input_adapter.py
接收文本

2. message_normalizer.py
封装 RuntimeMessage

3. router.py
固定路由到 Interaction Runtime

4. runtime_router.py
调用 Interaction Runtime

5. gateway.py
串联整个流程
```

MVP 链路：

```text
Text Input
  ↓
Gateway.handle_text()
  ↓
RuntimeMessage
  ↓
Router: interaction_runtime
  ↓
InteractionRuntime.handle()
  ↓
DialogueAgent.handle()
  ↓
Response
```

MVP 目标：

```text
text → gateway → interaction_runtime → dialogue_agent → response
```

只要这个跑通，就说明 Gateway 的最小功能已经成立。

---

## 8. Gateway 后续扩展路线

建议按以下顺序扩展：

```text
Step 1：固定路由到 Interaction Runtime
Step 2：关键词规则路由 interaction / navigation / motion
Step 3：接入 Session Router
Step 4：接入 Priority Manager
Step 5：接入 Safety Gate
Step 6：接入 Trace Logger
Step 7：接入 config.yaml 路由策略
Step 8：接入 Conflict Resolver
Step 9：接入 Event Bus
Step 10：接入 Result Aggregator
Step 11：支持异步 Runtime 调用
Step 12：支持多模态输入和系统事件
```

---

## 9. 设计原则

### 9.1 Gateway 是薄中枢

Gateway 应该保持轻量，不要变成巨型大脑。

Gateway 只做：

```text
1. 接入
2. 标准化
3. 路由
4. 仲裁
5. 安全前置
6. 状态同步
7. Trace
```

专业能力交给 Runtime 和 Agent。

---

### 9.2 Gateway 路由 Runtime，不直接管理所有 Agent

推荐链路：

```text
Gateway
  ↓
Runtime
  ↓
Runtime 内部 Agent Router
  ↓
Agent
```

不建议：

```text
Gateway
  ↓
直接调用所有 Agent
```

否则 Gateway 会越来越复杂。

---

### 9.3 跨 Runtime 通信统一走 Gateway

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

这样可以保证所有跨 Runtime 行为都能被记录、治理、回放和安全控制。

---

### 9.4 LLM / Agent 不直接控制机器人底层

Gateway 和 Agent Runtime 只负责任务级、行为级、Skill 级调度。

底层控制应由机器人本体系统负责。

边界如下：

```text
Agent Runtime：
任务级决策、行为级决策、Skill 调度

机器人本体控制：
轨迹执行、控制执行、电机级执行
```

---

## 10. 一句话总结

Gateway 的完整版本应该包含：

> 输入接入、消息标准化、Session 管理、意图路由、Runtime 分发、优先级管理、安全前置、冲突仲裁、事件总线、结果汇聚、Trace 日志和配置化路由策略。

但第一阶段只需要实现：

> 文本输入 + 标准消息 + 固定路由 + 调用 Interaction Runtime + 返回 Dialogue Agent 输出。
