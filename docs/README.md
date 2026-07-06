# Agent Runtime — 架构文档

## 图表目录

### 1. 系统架构总览

![系统架构总览](images/01_系统架构总览.png)

完整的五层架构图：用户输入 → Gateway → Runtime → Agent → Skill → MQTT Client → Bridge → 机器人。展示了所有模块及其依赖关系、LLM 调用边界、跨层通信规则。

---

### 2. 请求处理流程

![请求处理流程](images/02_请求处理流程.png)

两种请求处理路径的对比：
- **路径 A（橙色）**：关键词命中 → 直接执行 Skill，零 LLM 开销，< 1ms
- **路径 B（黄色）**：无关键词 → LLM 意图理解 → Gateway 二次路由 → 执行，~100-500ms

---

### 3. 路由决策树

![路由决策树](images/03_路由决策树.png)

从用户输入到 MQTT 指令的完整决策树。展示：
- Router 关键词匹配 → 三种 Runtime 的分流
- 每个 Runtime 内部 Agent/Skill 的 dispatch 逻辑
- LLM 意图理解的 fallback 路径
- 所有 MQTT 指令 ID 的映射关系

---

### 4. 模块依赖关系

![模块依赖关系](images/04_模块依赖关系.png)

Python 代码层面的模块依赖图。展示 `main.py` 的依赖注入关系、各 `__init__.py` 的导出、`shared/` 被所有模块引用、LLM 和 MQTT 的外部依赖边界。

---

### 5. 端到端时序图

![端到端时序图](images/05_端到端时序图.png)

以 `"cqm1"` 输入为例的完整时序图：用户 → Gateway → Router → MotionRuntime → MotionAgent → MotionSkill → MqttClient → Bridge → 机器人 → 返回结果，共 13 步，清晰展示每步的输入输出。

---

### 6. 五层架构垂直切面

![五层架构垂直切面](images/06_五层架构垂直切面.png)

五层架构的职责边界和通信规则：
- **Layer 1** Gateway 薄中枢：路由 + 分发，不调 LLM
- **Layer 2** Runtime 编排：两条执行路径，不发 MQTT
- **Layer 3** Agent 决策：调 LLM，选意图，不发 MQTT
- **Layer 4** Skill 执行：发 MQTT 指令，不做决策
- **Layer 5** Capability + Bridge + 机器人

---

## 重新生成图表

```bash
cd agent_demo/docs
python3 generate_diagrams.py
```

依赖：
```bash
pip install graphviz          # Python 绑定
sudo apt install graphviz     # 系统 graphviz (dot 渲染引擎)
```
