"""
生成 Agent Runtime 架构图、流程图、决策树。

用法:
    cd agent_demo/docs
    python generate_diagrams.py

输出: images/ 目录下的 PNG 图片
依赖: pip install graphviz
      系统需要安装 graphviz (apt install graphviz)
"""

import os
from graphviz import Digraph

OUT_DIR = os.path.join(os.path.dirname(__file__), "images")
os.makedirs(OUT_DIR, exist_ok=True)

# ============================================================================
# 颜色方案
# ============================================================================
C_BG        = "#0D1117"     # GitHub dark background
C_BORDER    = "#30363D"     # box border
C_TEXT      = "#E6EDF3"     # text
C_TITLE     = "#58A6FF"     # section title
C_GATEWAY   = "#1F6FEB"     # blue
C_RUNTIME   = "#238636"     # green
C_AGENT     = "#8957E5"     # purple
C_SKILL     = "#DB6D28"     # orange
C_CAP       = "#C2255C"     # red/pink
C_BRIDGE    = "#6E7681"     # gray
C_ROBOT     = "#6E7681"     # gray
C_ARROW     = "#8B949E"     # arrow
C_LLM       = "#D29922"     # yellow/amber for LLM
C_HIGHLIGHT = "#F78166"     # highlight


def style_graph(dot: Digraph, name: str):
    """统一样式。"""
    dot.attr(
        rankdir="TB",
        bgcolor=C_BG,
        fontname="Helvetica",
        fontcolor=C_TITLE,
        fontsize="20",
        label=f"\n{name}\n",
        labelloc="t",
        labeljust="c",
        pad="0.5",
        nodesep="0.4",
        ranksep="0.6",
        dpi="150",
    )
    dot.attr("node",
        fontname="Helvetica", fontsize="11",
        fontcolor=C_TEXT, color=C_BORDER,
        style="filled,rounded", penwidth="1.2",
    )
    dot.attr("edge",
        fontname="Helvetica", fontsize="9",
        color=C_ARROW, fontcolor=C_ARROW,
    )


def style_legend(dot: Digraph):
    """添加颜色图例。"""
    with dot.subgraph(name="cluster_legend") as leg:
        leg.attr(label="图例", fontcolor=C_TITLE, fontsize="11",
                 style="dashed", color=C_ARROW, bgcolor="#161B22")
        leg.node("leg_gw",   "Gateway 路由层",    shape="box", fillcolor=C_GATEWAY)
        leg.node("leg_rt",   "Runtime 编排层",   shape="box", fillcolor=C_RUNTIME)
        leg.node("leg_ag",   "Agent 决策层",     shape="box", fillcolor=C_AGENT)
        leg.node("leg_sk",   "Skill 执行层",     shape="box", fillcolor=C_SKILL)
        leg.node("leg_cap",  "Capability 能力层",  shape="box", fillcolor=C_CAP)
        leg.node("leg_br",   "Bridge / 机器人",     shape="box", fillcolor=C_BRIDGE)


# ============================================================================
# 1. 系统架构总览
# ============================================================================
def build_architecture():
    dot = Digraph(comment="Agent Runtime Architecture")
    style_graph(dot, "Agent Runtime 系统架构总览")

    # 用户
    dot.node("user", "👤 用户输入\n(文本/语音)", shape="plaintext", fontsize="14",
             fontcolor=C_TITLE)

    # Gateway 层 — 完整治理中枢
    with dot.subgraph(name="cluster_gateway") as c:
        c.attr(label="Gateway 路由与治理中枢 (11/13 模块)", style="rounded,dashed",
               fontcolor=C_GATEWAY, fontsize="13", color=C_GATEWAY, bgcolor="#161B22")
        c.node("gw", "Gateway.handle_text()\n────────\n① InputAdapter 多模态归一化\n② TraceLogger 生成trace_id\n③ SessionRouter 会话隔离\n④ PriorityManager 四级优先级\n⑤ SafetyGate 请求安全过滤\n⑥ Router YAML规则匹配(54条)\n⑦ ConflictResolver 冲突仲裁\n⑧ RuntimeRouter 分发+二次路由\n⑨ ResultAggregator 结果合并\n⑩ TraceLogger 记录结果", shape="box", fillcolor=C_GATEWAY)
        c.node("router", "Router + RoutePolicy\n────────\nYAML 54条规则\n最长关键词匹配\n→ 预填 action+params→ 免LLM直连", shape="box", fillcolor=C_GATEWAY)

    # Runtimes
    with dot.subgraph(name="cluster_runtimes") as c:
        c.attr(label="Runtimes 编排层", style="rounded,dashed",
               fontcolor=C_RUNTIME, fontsize="13", color=C_RUNTIME, bgcolor="#161B22")
        c.node("irt", "InteractionRuntime\n────\nLLM意图理解→MQTT指令\n[两条路径]", shape="box", fillcolor=C_RUNTIME)
        c.node("mrt", "MotionRuntime\n────\n动作/移动/急停\n运动模式", shape="box", fillcolor=C_RUNTIME)
        c.node("nrt", "NavigationRuntime\n────\n导航/建图\n(占位)", shape="box", fillcolor=C_RUNTIME)

    # Agents
    with dot.subgraph(name="cluster_agents") as c:
        c.attr(label="Agents 决策层", style="rounded,dashed",
               fontcolor=C_AGENT, fontsize="13", color=C_AGENT, bgcolor="#161B22")
        c.node("ia", "IntentAgent\nLLM意图识别", shape="box", fillcolor=C_AGENT)
        c.node("ma", "MotionAgent\n运动决策", shape="box", fillcolor=C_AGENT)
        c.node("na", "NavigationAgent\n导航决策", shape="box", fillcolor=C_AGENT)

    # Skills
    with dot.subgraph(name="cluster_skills") as c:
        c.attr(label="Skills 执行层", style="rounded,dashed",
               fontcolor=C_SKILL, fontsize="13", color=C_SKILL, bgcolor="#161B22")
        c.node("is_sk", "InteractionSkill\n音频/情绪/语音唤醒", shape="box", fillcolor=C_SKILL)
        c.node("ms_sk", "MotionSkill\n动作/移动/急停/模式", shape="box", fillcolor=C_SKILL)
        c.node("ns_sk", "NavigationSkill\n导航MQTT", shape="box", fillcolor=C_SKILL)

    # Capability
    dot.node("mqtt", "RobotMqttClient\n────\npaho-mqtt 协议封装\n30+ 指令ID · Topic路由 · QoS", shape="box", fillcolor=C_CAP)

    # Bridge + Robot
    dot.node("bridge", "eir_communication_bridge\nMQTT ↔ ROS2 透明中继", shape="box", fillcolor=C_BRIDGE)
    dot.node("robot", "ehr_ros_app + ehr_app_core\n机器人主控 (Orin)", shape="box", fillcolor=C_ROBOT)

    # Edges
    dot.edge("user", "gw", "文本输入", color=C_ARROW)
    dot.edge("gw", "router", style="dashed", color=C_GATEWAY)
    dot.edge("gw", "irt", "无关键词 →", color=C_ARROW)
    dot.edge("gw", "mrt", "关键词命中 →", color=C_ARROW)
    dot.edge("gw", "nrt", "关键词命中 →", color=C_ARROW)
    dot.edge("irt", "ia", color=C_AGENT, style="dashed")
    dot.edge("mrt", "ma", color=C_AGENT, style="dashed")
    dot.edge("nrt", "na", color=C_AGENT, style="dashed")
    dot.edge("ma", "ms_sk", color=C_SKILL)
    dot.edge("na", "ns_sk", color=C_SKILL)
    dot.edge("irt", "is_sk", "直接执行 →", color=C_SKILL)
    dot.edge("ms_sk", "mqtt", color=C_CAP)
    dot.edge("ns_sk", "mqtt", color=C_CAP)
    dot.edge("is_sk", "mqtt", color=C_CAP)
    dot.edge("mqtt", "bridge", "MQTT (mosquitto:8899)", color=C_ARROW)
    dot.edge("bridge", "robot", "ROS2 topics", color=C_ARROW)

    # LLM 标注（仅 IntentAgent 调用，做意图→MQTT指令映射）
    dot.node("llm", "🤖 LLM (意图识别)\nqwen2.5:0.5b\n(ollama)", shape="box", fillcolor=C_LLM, fontcolor="#0D1117")
    dot.edge("ia", "llm", "意图→MQTT映射", color=C_LLM, style="dashed")
    # 对话由机器人本地腾讯大模型处理
    dot.node("tencent_note", "🗣️ 机器人本地语音\n  (对话/ASR/TTS)\n  SDK内部闭环", shape="note",
             fillcolor="#161B22", fontcolor=C_HIGHLIGHT, fontsize="9")

    style_legend(dot)
    dot.render(os.path.join(OUT_DIR, "01_系统架构总览"), format="png", cleanup=True)
    print("✓ 01_系统架构总览.png")


# ============================================================================
# 2. 请求处理流程 — 两种路径
# ============================================================================
def build_request_flow():
    dot = Digraph(comment="Request Flow")
    style_graph(dot, "请求处理流程 — 两条路径对比")

    # 输入
    dot.node("input", "用户输入文本", shape="plaintext", fontsize="14", fontcolor=C_TITLE)

    dot.node("gw", "Gateway.handle_text()\n① 封装 RuntimeMessage\n② 调 Router\n③ 调 Runtime\n④ 二次分发(如需)", shape="box", fillcolor=C_GATEWAY)

    dot.node("router", "Router.route()\n────\n关键词匹配?", shape="diamond", fillcolor=C_GATEWAY,
             fontcolor=C_TEXT)

    # 路径 A
    dot.node("path_a_label", "路径 A: 关键词命中", shape="plaintext", fontcolor=C_HIGHLIGHT, fontsize="12")
    dot.node("a_ctx", "message.context ←\n{action, params}", shape="box", fillcolor="#1F6FEB30")
    dot.node("a_rt", "MotionRuntime\n/ InteractionRuntime\n(直接执行路径)", shape="box", fillcolor=C_RUNTIME)
    dot.node("a_agent", "Agent.handle()\n读 context 选 Skill", shape="box", fillcolor=C_AGENT)
    dot.node("a_skill", "Skill.execute()\nif/elif 分发 → MQTT", shape="box", fillcolor=C_SKILL)

    # 路径 B
    dot.node("path_b_label", "路径 B: 无匹配 → LLM", shape="plaintext", fontcolor=C_LLM, fontsize="12")
    dot.node("b_rt", "InteractionRuntime\n(LLM 理解路径)", shape="box", fillcolor=C_RUNTIME)
    dot.node("b_intent", "IntentAgent\n────\n① _fast_path()\n② _llm_path()", shape="box", fillcolor=C_AGENT)
    dot.node("b_llm", "LLM\nqwen2.5:0.5b", shape="box", fillcolor=C_LLM, fontcolor="#0D1117")
    dot.node("b_result", "LLM 返回 JSON\n{intent, action, params}", shape="box", fillcolor=C_LLM, fontcolor="#0D1117")
    dot.node("b_split", "intent?", shape="diamond", fillcolor=C_AGENT, fontcolor=C_TEXT)
    dot.node("b_chat", "机器人本地语音", shape="note", fillcolor="#161B22", fontcolor=C_HIGHLIGHT, fontsize="9")
    dot.node("b_motion", "→ Gateway._reroute()\n→ MotionRuntime", shape="box", fillcolor=C_HIGHLIGHT)

    # MQTT
    dot.node("mqtt", "RobotMqttClient\npublish(topic, payload)", shape="box", fillcolor=C_CAP)
    dot.node("bridge", "Bridge → ROS2 → 机器人", shape="box", fillcolor=C_BRIDGE)

    # Edges
    dot.edge("input", "gw")
    dot.edge("gw", "router")

    # 路径 A
    dot.edge("router", "a_ctx", "命中", color=C_HIGHLIGHT)
    dot.edge("a_ctx", "a_rt", style="invis")
    dot.edge("router", "a_rt", "写 context 后 →", color=C_HIGHLIGHT)
    dot.edge("a_rt", "a_agent", color=C_HIGHLIGHT)
    dot.edge("a_agent", "a_skill", color=C_HIGHLIGHT)
    dot.edge("a_skill", "mqtt", color=C_HIGHLIGHT)

    # 路径 B
    dot.edge("router", "b_rt", "未命中", color=C_LLM)
    dot.edge("b_rt", "b_intent", color=C_LLM)
    dot.edge("b_intent", "b_llm", color=C_LLM)
    dot.edge("b_llm", "b_result", color=C_LLM)
    dot.edge("b_result", "b_split", color=C_LLM)
    dot.edge("b_split", "b_chat", "chat", color=C_AGENT)
    dot.edge("b_split", "b_motion", "motion/nav", color=C_HIGHLIGHT)
    dot.edge("b_motion", "a_rt", "二次路由到\n同一 Runtime", color=C_HIGHLIGHT, style="dashed")
    dot.edge("b_chat", "b_rt", style="dashed", color=C_HIGHLIGHT, label="SDK内部闭环")

    dot.edge("mqtt", "bridge", "MQTT")

    # 标注
    dot.node("note_a", "⚡ 耗时 < 1ms，零 LLM 调用", shape="plaintext", fontcolor=C_HIGHLIGHT, fontsize="9")
    dot.node("note_b", "⏱ 耗时 ~100-500ms (LLM推理)", shape="plaintext", fontcolor=C_LLM, fontsize="9")
    dot.edge("a_skill", "note_a", style="invis")
    dot.edge("b_llm", "note_b", style="invis")

    style_legend(dot)
    dot.render(os.path.join(OUT_DIR, "02_请求处理流程"), format="png", cleanup=True)
    print("✓ 02_请求处理流程.png")


# ============================================================================
# 3. 路由决策树
# ============================================================================
def build_routing_tree():
    dot = Digraph(comment="Routing Decision Tree")
    style_graph(dot, "路由决策树 — 从输入到 MQTT 指令")

    # Root
    dot.node("input", "用户输入文本", shape="plaintext", fontsize="14", fontcolor=C_TITLE)
    dot.node("router", "Router.route()\n关键词最长匹配", shape="box", fillcolor=C_GATEWAY)

    # Keyword branches
    dot.node("kw_motion", "命中 → motion", shape="box", fillcolor=C_RUNTIME, fontsize="10")
    dot.node("kw_inter", "命中 → interaction", shape="box", fillcolor=C_RUNTIME, fontsize="10")
    dot.node("kw_nav", "命中 → navigation", shape="box", fillcolor=C_RUNTIME, fontsize="10")
    dot.node("no_match", "未命中\n→ interaction (默认)", shape="box", fillcolor=C_RUNTIME, fontsize="10")

    # Motion sub-tree
    dot.node("m_skill", "MotionSkill.execute()", shape="box", fillcolor=C_SKILL, fontsize="10")

    dot.node("m1", 'action="motion"\n→ send_motion(name)\n→ MQTT 1006', shape="box", fillcolor=C_SKILL, fontsize="9")
    dot.node("m2", 'action="move"\n→ send_move(lx,ly,az)\n→ MQTT 3001', shape="box", fillcolor=C_SKILL, fontsize="9")
    dot.node("m3", 'action="stop"\n→ send_estop(True)\n→ MQTT 9000', shape="box", fillcolor=C_SKILL, fontsize="9")
    dot.node("m4", 'action="loco_mode"\n→ send_loco_mode(mode)\n→ MQTT 1001', shape="box", fillcolor=C_SKILL, fontsize="9")
    dot.node("m5", 'action="oas"\n→ send_oas(enable)\n→ MQTT 1004', shape="box", fillcolor=C_SKILL, fontsize="9")

    # Interaction sub-tree
    dot.node("i_skill", "InteractionSkill.execute()", shape="box", fillcolor=C_SKILL, fontsize="10")
    dot.node("i1", 'action="play_audio"\n→ send_corpus({type,...})\n→ MQTT 1007', shape="box", fillcolor=C_SKILL, fontsize="9")
    dot.node("i2", 'action="switch_emotion"\n→ MQTT 1007', shape="box", fillcolor=C_SKILL, fontsize="9")
    dot.node("i3", 'action="voice_wakeup"\n→ MQTT 1007', shape="box", fillcolor=C_SKILL, fontsize="9")
    dot.node("i4", 'action="volume"\n→ send_volume(v)\n→ MQTT 5002', shape="box", fillcolor=C_SKILL, fontsize="9")
    dot.node("i5", 'action="led"\n→ send_led(...)\n→ MQTT 5001', shape="box", fillcolor=C_SKILL, fontsize="9")

    # Interaction → LLM fallback
    dot.node("intent_agent", "IntentAgent (LLM)", shape="box", fillcolor=C_AGENT, fontsize="10")
    dot.node("llm_chat", "chat\n→ 机器人本地语音", shape="note", fillcolor="#161B22", fontcolor=C_HIGHLIGHT, fontsize="9")
    dot.node("llm_motion", "motion/navigation\n→ Gateway._reroute()\n→ 回到 motion/nav", shape="box", fillcolor=C_HIGHLIGHT, fontsize="9")
    dot.node("llm_inter", "interaction\n→ InteractionSkill", shape="box", fillcolor=C_AGENT, fontsize="9")

    # Navigation
    dot.node("n_skill", "NavigationSkill.execute()\n→ send_navigation(params)\n→ MQTT 6001", shape="box", fillcolor=C_SKILL, fontsize="10")

    # MQTT + Bridge
    dot.node("mqtt", "RobotMqttClient\npublish(topic, payload)", shape="box", fillcolor=C_CAP)
    dot.node("bridge", "Bridge → ROS2 → 机器人执行", shape="box", fillcolor=C_BRIDGE, fontsize="10")

    # Edges
    dot.edge("input", "router")
    dot.edge("router", "kw_motion", '含"cqm1"/"前进"/"停"/"站立"...')
    dot.edge("router", "kw_inter", '含"四川话"/"换个表情"/"音量"...')
    dot.edge("router", "kw_nav", '含"带我去"/"导航"/"前往"...')
    dot.edge("router", "no_match", "其他所有文本")

    # Motion edges
    dot.edge("kw_motion", "m_skill")
    dot.edge("m_skill", "m1", 'action="motion"')
    dot.edge("m_skill", "m2", 'action="move"')
    dot.edge("m_skill", "m3", 'action="stop"')
    dot.edge("m_skill", "m4", 'action="loco_mode"')
    dot.edge("m_skill", "m5", 'action="oas"')

    # Interaction edges
    dot.edge("kw_inter", "i_skill", "context 已预填 action")
    dot.edge("i_skill", "i1", 'action="play_audio"')
    dot.edge("i_skill", "i2", 'action="switch_emotion"')
    dot.edge("i_skill", "i3", 'action="voice_wakeup"')
    dot.edge("i_skill", "i4", 'action="volume"')
    dot.edge("i_skill", "i5", 'action="led"')

    # LLM fallback
    dot.edge("no_match", "intent_agent", "context 无预填 →")
    dot.edge("intent_agent", "llm_chat", 'intent="chat"')
    dot.edge("intent_agent", "llm_motion", 'intent="motion|nav"')
    dot.edge("intent_agent", "llm_inter", 'intent="interaction"')
    dot.edge("llm_motion", "kw_motion", "Gateway._reroute()", style="dashed", color=C_HIGHLIGHT)
    dot.edge("llm_inter", "i_skill", style="dashed")

    # Navigation
    dot.edge("kw_nav", "n_skill")

    # All to MQTT
    dot.edge("m1", "mqtt")
    dot.edge("m2", "mqtt")
    dot.edge("m3", "mqtt")
    dot.edge("m4", "mqtt")
    dot.edge("m5", "mqtt")
    dot.edge("i1", "mqtt")
    dot.edge("i2", "mqtt")
    dot.edge("i3", "mqtt")
    dot.edge("i4", "mqtt")
    dot.edge("i5", "mqtt")
    dot.edge("n_skill", "mqtt")

    dot.edge("mqtt", "bridge")

    style_legend(dot)
    dot.render(os.path.join(OUT_DIR, "03_路由决策树"), format="png", cleanup=True)
    print("✓ 03_路由决策树.png")


# ============================================================================
# 4. 模块依赖关系图
# ============================================================================
def build_module_deps():
    dot = Digraph(comment="Module Dependencies")
    style_graph(dot, "模块依赖关系")

    # main.py
    dot.node("main", "main.py\nDI 组装 + 启动入口", shape="box", fillcolor=C_GATEWAY, fontsize="12")

    # Gateway
    with dot.subgraph(name="cluster_gw") as c:
        c.attr(label="gateway/", style="rounded,dashed", fontcolor=C_GATEWAY, fontsize="12", color=C_GATEWAY)
        c.node("gateway", "Gateway\nhandle_text()\n_reroute()", shape="box", fillcolor=C_GATEWAY)
        c.node("router_py", "Router\nroute()", shape="box", fillcolor=C_GATEWAY)

    # Runtimes
    with dot.subgraph(name="cluster_rt") as c:
        c.attr(label="runtimes/", style="rounded,dashed", fontcolor=C_RUNTIME, fontsize="12", color=C_RUNTIME)
        c.node("ir", "InteractionRuntime\n• intent_agent\n• interaction_skill", shape="box", fillcolor=C_RUNTIME)
        c.node("mr", "MotionRuntime\n• motion_agent", shape="box", fillcolor=C_RUNTIME)
        c.node("nr", "NavigationRuntime\n• nav_agent (占位)", shape="box", fillcolor=C_RUNTIME)

    # Agents
    with dot.subgraph(name="cluster_ag") as c:
        c.attr(label="agents/", style="rounded,dashed", fontcolor=C_AGENT, fontsize="12", color=C_AGENT)
        c.node("iag", "IntentAgent\nLLM→意图→MQTT", shape="box", fillcolor=C_AGENT)
        c.node("mag", "MotionAgent\n运动决策", shape="box", fillcolor=C_AGENT)
        c.node("nag", "NavigationAgent\n导航决策", shape="box", fillcolor=C_AGENT)

    # Skills
    with dot.subgraph(name="cluster_sk") as c:
        c.attr(label="skills/", style="rounded,dashed", fontcolor=C_SKILL, fontsize="12", color=C_SKILL)
        c.node("isk", "InteractionSkill\n音频/情绪/语音/设置", shape="box", fillcolor=C_SKILL)
        c.node("msk", "MotionSkill\n动作/移动/急停/模式", shape="box", fillcolor=C_SKILL)
        c.node("nsk", "NavigationSkill\n导航 MQTT", shape="box", fillcolor=C_SKILL)

    # Capabilities
    dot.node("mqtt_c", "RobotMqttClient\npaho-mqtt 封装", shape="box", fillcolor=C_CAP)

    # Shared
    with dot.subgraph(name="cluster_sh") as c:
        c.attr(label="shared/", style="rounded,dashed", fontcolor=C_ARROW, fontsize="12", color=C_ARROW)
        c.node("msg", "RuntimeMessage\nRuntimeResult", shape="box", fillcolor="#30363D")
        c.node("base", "BaseAgent\nBaseSkill", shape="box", fillcolor="#30363D")

    # External
    dot.node("llm_ext", "LLM 服务\n(ollama qwen2.5:0.5b)", shape="box", fillcolor=C_LLM, fontcolor="#0D1117")
    dot.node("bridge_ext", "Bridge + ROS2 + 机器人", shape="box", fillcolor=C_BRIDGE)

    # Edges — 构造时依赖
    dot.edge("main", "gateway", "注入 IRT,MRT,NRT")
    dot.edge("main", "ir")
    dot.edge("main", "mr")
    dot.edge("main", "nr")
    dot.edge("main", "mqtt_c", "注入到各 Skill")

    dot.edge("gateway", "router_py")
    dot.edge("gateway", "ir")
    dot.edge("gateway", "mr")
    dot.edge("gateway", "nr")

    dot.edge("ir", "iag", "has")
    dot.edge("ir", "isk", "has")
    dot.edge("mr", "mag", "has")
    dot.edge("nr", "nag", "has")

    dot.edge("iag", "llm_ext", "意图→MQTT映射", style="dashed")
    dot.edge("mag", "msk", "has")
    dot.edge("nag", "nsk", "has")

    dot.edge("msk", "mqtt_c", "发 MQTT")
    dot.edge("nsk", "mqtt_c", "发 MQTT")
    dot.edge("isk", "mqtt_c", "发 MQTT")

    dot.edge("mqtt_c", "bridge_ext", "MQTT → Bridge")

    # Shared used by all
    dot.edge("msg", "gateway", style="dotted", color=C_ARROW)
    dot.edge("base", "iag", style="dotted", color=C_ARROW)

    style_legend(dot)
    dot.render(os.path.join(OUT_DIR, "04_模块依赖关系"), format="png", cleanup=True)
    print("✓ 04_模块依赖关系.png")


# ============================================================================
# 5. 端到端时序图（详细）
# ============================================================================
def build_sequence():
    dot = Digraph(comment="Sequence Diagram")
    style_graph(dot, '端到端调用链 — 以 "cqm1" 为例')
    dot.attr(rankdir="LR")

    # Participants
    dot.node("u", "用户", shape="plaintext", fontsize="11", fontcolor=C_TITLE)
    dot.node("g", "Gateway", shape="box", fillcolor=C_GATEWAY, fontsize="9")
    dot.node("r", "Router", shape="box", fillcolor=C_GATEWAY, fontsize="9")
    dot.node("rt", "MotionRuntime", shape="box", fillcolor=C_RUNTIME, fontsize="9")
    dot.node("a", "MotionAgent", shape="box", fillcolor=C_AGENT, fontsize="9")
    dot.node("s", "MotionSkill", shape="box", fillcolor=C_SKILL, fontsize="9")
    dot.node("m", "MqttClient", shape="box", fillcolor=C_CAP, fontsize="9")
    dot.node("b", "Bridge+Robot", shape="box", fillcolor=C_BRIDGE, fontsize="9")

    # Steps (as edge labels)
    dot.edge("u", "g", '① 输入 "cqm1"', fontsize="9")
    dot.edge("g", "r", "② route()", fontsize="9")
    dot.edge("r", "g", '③ "motion"', fontsize="9", style="dashed")
    dot.edge("g", "rt", "④ handle(message)", fontsize="9")
    dot.edge("rt", "a", "⑤ handle(message)\ncontext={action:'motion'...}", fontsize="9")
    dot.edge("a", "s", "⑥ execute('motion',{name:'cqm1'})", fontsize="9")
    dot.edge("s", "m", "⑦ send_motion('cqm1')", fontsize="9")
    dot.edge("m", "b", '⑧ MQTT publish\n{cmd:1006,data:"cqm1"}', fontsize="9")
    dot.edge("b", "m", "⑨ 机器人执行...", fontsize="9", style="dashed")
    dot.edge("s", "a", "⑩ RuntimeResult", fontsize="9", style="dashed")
    dot.edge("a", "rt", "⑪ RuntimeResult", fontsize="9", style="dashed")
    dot.edge("rt", "g", "⑫ RuntimeResult", fontsize="9", style="dashed")
    dot.edge("g", "u", '⑬ 回复"执行动作:cqm1"', fontsize="9", style="dashed")

    # Invisible rank alignment
    dot.attr(rank="same")
    # just render

    dot.render(os.path.join(OUT_DIR, "05_端到端时序图"), format="png", cleanup=True)
    print("✓ 05_端到端时序图.png")


# ============================================================================
# 6. 分层架构 — 垂直切面
# ============================================================================
def build_layers():
    dot = Digraph(comment="Layered Architecture")
    style_graph(dot, "五层架构 — 垂直切面")
    dot.attr(rankdir="TB")

    # 设置各层严格垂直排列
    dot.attr("node", shape="box", fontsize="10")

    # Layer 1: User Input
    with dot.subgraph(name="cluster_L0") as c:
        c.attr(label="用户 / 外部", style="filled", fillcolor="#161B22",
               fontcolor=C_TITLE, fontsize="12", color=C_ARROW)
        c.node("l0", "文本 / 语音 / 系统事件", fillcolor="#30363D")

    # Layer 2: Gateway
    with dot.subgraph(name="cluster_L1") as c:
        c.attr(label="Layer 1: Gateway 薄中枢", style="filled", fillcolor="#161B22",
               fontcolor=C_GATEWAY, fontsize="12", color=C_GATEWAY)
        c.node("l1_in", "handle_text() / handle_event()", fillcolor=C_GATEWAY)
        c.node("l1_rt", "Router 关键词匹配 + 最长优先", fillcolor=C_GATEWAY)
        c.node("l1_reroute", "_reroute() 二次分发", fillcolor=C_GATEWAY)
        c.node("l1_rule", "❌ 不调LLM  ❌ 不做决策  ❌ 不发MQTT", shape="plaintext",
               fontcolor=C_HIGHLIGHT, fontsize="9")

    # Layer 3: Runtime
    with dot.subgraph(name="cluster_L2") as c:
        c.attr(label="Layer 2: Runtime 编排层", style="filled", fillcolor="#161B22",
               fontcolor=C_RUNTIME, fontsize="12", color=C_RUNTIME)
        c.node("l2_direct", "路径1: 直接执行\n(context 有预填 action)", fillcolor=C_RUNTIME)
        c.node("l2_llm", "路径2: LLM 理解\n→ IntentAgent → Gateway 二次路由", fillcolor=C_RUNTIME)
        c.node("l2_rule", "❌ 不直接发MQTT  ❌ 不调LLM(仅编排)", shape="plaintext",
               fontcolor=C_HIGHLIGHT, fontsize="9")

    # Layer 4: Agent
    with dot.subgraph(name="cluster_L3") as c:
        c.attr(label="Layer 3: Agent 决策层", style="filled", fillcolor="#161B22",
               fontcolor=C_AGENT, fontsize="12", color=C_AGENT)
        c.node("l3_ia", "IntentAgent\nLLM 意图→MQTT映射", fillcolor=C_AGENT)
        c.node("l3_ma", "MotionAgent\n运动决策", fillcolor=C_AGENT)
        c.node("l3_na", "NavigationAgent\n导航决策", fillcolor=C_AGENT)
        c.node("l3_rule", "✅ 调LLM(仅意图映射)  ❌ 不直接发MQTT\n对话由机器人本地腾讯大模型处理", shape="plaintext",
               fontcolor=C_LLM, fontsize="9")

    # Layer 5: Skill
    with dot.subgraph(name="cluster_L4") as c:
        c.attr(label="Layer 4: Skill 执行层", style="filled", fillcolor="#161B22",
               fontcolor=C_SKILL, fontsize="12", color=C_SKILL)
        c.node("l4_ms", "MotionSkill\nsend_motion/move/estop...", fillcolor=C_SKILL)
        c.node("l4_is", "InteractionSkill\nplay_audio/emotion/volume/led", fillcolor=C_SKILL)
        c.node("l4_ns", "NavigationSkill\nsend_navigation", fillcolor=C_SKILL)
        c.node("l4_rule", "✅ 发MQTT  ❌ 不做决策  ❌ 不判断", shape="plaintext",
               fontcolor=C_HIGHLIGHT, fontsize="9")

    # Layer 6: Capability + Bridge
    with dot.subgraph(name="cluster_L5") as c:
        c.attr(label="Layer 5: Capability 能力层 + Bridge + 机器人", style="filled",
               fillcolor="#161B22", fontcolor=C_CAP, fontsize="12", color=C_CAP)
        c.node("l5_mqtt", "RobotMqttClient\nMQTT 协议封装 · Topic 路由 · QoS · 30+指令ID", fillcolor=C_CAP)
        c.node("l5_bridge", "eir_communication_bridge\nMQTT ↔ ROS2 透明中继", fillcolor=C_BRIDGE)
        c.node("l5_robot", "ehr_ros_app + ehr_app_core\n机器人主控 (Orin)", fillcolor=C_ROBOT)

    # Vertical edges
    dot.edge("l0", "l1_in")
    dot.edge("l1_in", "l1_rt", style="dashed")
    dot.edge("l1_rt", "l1_reroute", style="dashed")
    dot.edge("l1_reroute", "l2_direct", style="invis")
    dot.edge("l2_direct", "l3_ma", style="dashed")
    dot.edge("l2_llm", "l3_ia", style="dashed")
    dot.edge("l3_ma", "l4_ms", style="dashed")
    dot.edge("l3_na", "l4_ns", style="dashed")
    dot.edge("l4_ms", "l5_mqtt", style="dashed")
    dot.edge("l4_is", "l5_mqtt", style="dashed")
    dot.edge("l4_ns", "l5_mqtt", style="dashed")
    dot.edge("l5_mqtt", "l5_bridge", "MQTT")
    dot.edge("l5_bridge", "l5_robot", "ROS2")

    # Cross-layer communication rules
    dot.node("rule_v", "⬆⬇ 跨层规则:\n"
             "Gateway → Runtime → Agent → Skill → MQTT Client\n"
             "每层只与相邻层通信，不可跨层调用", shape="note",
             fillcolor="#161B22", fontcolor=C_ARROW, fontsize="9")

    style_legend(dot)
    dot.render(os.path.join(OUT_DIR, "06_五层架构垂直切面"), format="png", cleanup=True)
    print("✓ 06_五层架构垂直切面.png")


# ============================================================================
# 7. 调用链路全景图 — 从用户输入到 MQTT 的完整路由决策链
# ============================================================================
def build_call_chain():
    dot = Digraph(comment="Complete Call Chain")
    style_graph(dot, "调用链路全景图 — 从用户输入到 MQTT 指令")

    # ------------------------------------------------------------------
    # 第一段: 用户输入
    # ------------------------------------------------------------------
    with dot.subgraph(name="cluster_input") as c:
        c.attr(label="① 用户输入", style="filled", fillcolor="#161B22",
               fontcolor=C_TITLE, fontsize="13", color=C_GATEWAY)
        c.node("txt", "用户文本", shape="plaintext", fontcolor=C_TEXT, fontsize="12")

    # ------------------------------------------------------------------
    # 第二段: Gateway
    # ------------------------------------------------------------------
    with dot.subgraph(name="cluster_step1") as c:
        c.attr(label="② Gateway.handle_text()", style="filled", fillcolor="#161B22",
               fontcolor=C_GATEWAY, fontsize="13", color=C_GATEWAY)
        c.node("gw_encap", "封装 RuntimeMessage\n{payload: {text: ...}, context: {}}", shape="box", fillcolor=C_GATEWAY)
        c.node("gw_call", "Router.route(message)", shape="box", fillcolor=C_GATEWAY)

    # ------------------------------------------------------------------
    # 第三段: Router 扫描 DIRECT_ROUTES
    # ------------------------------------------------------------------
    with dot.subgraph(name="cluster_router") as c:
        c.attr(label="③ Router 扫描 DIRECT_ROUTES 关键词表", style="filled", fillcolor="#161B22",
               fontcolor=C_TITLE, fontsize="13", color=C_TITLE)

        # 两个分支: 命中 vs 未命中
        c.node("rt_scan", "遍历 50 条关键词\n最长匹配原则", shape="box", fillcolor=C_GATEWAY)
        c.node("rt_hit", "✅ 命中！\n→ 写 message.context\n  {action, params}\n→ 返回 runtime 名", shape="box", fillcolor="#238636")
        c.node("rt_miss", "❌ 未命中\n→ 返回 \"interaction\"", shape="box", fillcolor="#C2255C")

        # 具体示例
        c.node("rt_ex1", '"cqm1" → motion\naction=motion, name=cqm1', shape="note", fillcolor="#0D2B15", fontcolor=C_RUNTIME, fontsize="9")
        c.node("rt_ex2", '"停" → motion\naction=stop', shape="note", fillcolor="#0D2B15", fontcolor=C_RUNTIME, fontsize="9")
        c.node("rt_ex3", '"四川话" → interaction\naction=play_audio, name=sch1', shape="note", fillcolor="#0D2B15", fontcolor=C_RUNTIME, fontsize="9")
        c.node("rt_ex4", '"带我去" → navigation\naction=navigate', shape="note", fillcolor="#0D2B15", fontcolor=C_RUNTIME, fontsize="9")
        c.node("rt_ex5", '"你好" → LLM 路径', shape="note", fillcolor="#2D0B15", fontcolor=C_SKILL, fontsize="9")
        c.node("rt_ex6", '"介绍一下爱湫" → LLM 路径', shape="note", fillcolor="#2D0B15", fontcolor=C_SKILL, fontsize="9")

    # ------------------------------------------------------------------
    # 第四段: Gateway 选 Runtime
    # ------------------------------------------------------------------
    with dot.subgraph(name="cluster_dispatch") as c:
        c.attr(label="④ Gateway 查 _runtimes 字典", style="filled", fillcolor="#161B22",
               fontcolor=C_GATEWAY, fontsize="13", color=C_GATEWAY)
        c.node("gw_dict", '{\n  "interaction": InteractionRuntime,\n  "motion": MotionRuntime,\n  "navigation": NavigationRuntime\n}', shape="note", fillcolor="#161B22", fontcolor=C_ARROW, fontsize="9")
        c.node("gw_disp", "runtime.handle(message)", shape="box", fillcolor=C_GATEWAY)

    # ------------------------------------------------------------------
    # 第五段: 三个 Runtime 内部逻辑
    # ------------------------------------------------------------------
    with dot.subgraph(name="cluster_runtimes_detail") as c:
        c.attr(label="⑤ Runtime 内部 dispatch（按 message.context 分发）", style="filled", fillcolor="#161B22",
               fontcolor=C_RUNTIME, fontsize="13", color=C_RUNTIME)

        # InteractionRuntime
        c.node("irt_label", "InteractionRuntime", shape="plaintext", fontcolor=C_RUNTIME, fontsize="11")
        c.node("irt_check", 'context["action"] 有值?', shape="diamond", fillcolor=C_AGENT, fontsize="9")
        c.node("irt_direct", "直接执行 InteractionSkill\n(play_audio/switch_emotion/\nvoice_wakeup/volume/led)", shape="box", fillcolor=C_SKILL)
        c.node("irt_llm", "调 IntentAgent (LLM)", shape="box", fillcolor=C_AGENT)
        c.node("irt_llm_out", "LLM 返回:\nchat→机器人本地语音(腾讯)\ninteraction→InteractionSkill\nmotion/nav→回Gateway二次路由", shape="box", fillcolor=C_AGENT, fontsize="9")

        # MotionRuntime
        c.node("mrt_label", "MotionRuntime", shape="plaintext", fontcolor=C_RUNTIME, fontsize="11")
        c.node("mrt_disp", "→ MotionAgent\n→ MotionSkill", shape="box", fillcolor=C_RUNTIME, fontsize="9")

        # NavigationRuntime
        c.node("nrt_label", "NavigationRuntime", shape="plaintext", fontcolor=C_RUNTIME, fontsize="11")
        c.node("nrt_disp", "→ NavigationAgent\n→ NavigationSkill", shape="box", fillcolor=C_RUNTIME, fontsize="9")

    # ------------------------------------------------------------------
    # 第六段: Gateway 二次路由
    # ------------------------------------------------------------------
    with dot.subgraph(name="cluster_reroute") as c:
        c.attr(label="⑥ Gateway 二次路由（仅当 Interaction → motion/navigation）",
               style="filled", fillcolor="#161B22",
               fontcolor=C_TITLE, fontsize="12", color=C_TITLE)
        c.node("reroute", 'if runtime_name == "interaction"\nand result.intent in ("motion", "navigation"):\n    更新 message.context → 分发到对应 Runtime', shape="box", fillcolor=C_GATEWAY, fontsize="9")

    # ------------------------------------------------------------------
    # 第七段: Skill → MQTT 映射
    # ------------------------------------------------------------------
    with dot.subgraph(name="cluster_skill_mqtt") as c:
        c.attr(label="⑦ Skill.execute() — 按 params[\"action\"] 分发 MQTT 指令",
               style="filled", fillcolor="#161B22",
               fontcolor=C_SKILL, fontsize="13", color=C_SKILL)

        c.node("sk_motion", "MotionSkill", shape="plaintext", fontcolor=C_SKILL, fontsize="10")
        c.node("sk_int", "InteractionSkill", shape="plaintext", fontcolor=C_SKILL, fontsize="10")
        c.node("sk_nav", "NavigationSkill", shape="plaintext", fontcolor=C_SKILL, fontsize="10")

        c.node("sk_t1", 'action="motion"\n→ CMD_ACTION(1006)\n   eir/operation_instructions\n   机器人执行动作', shape="note", fillcolor="#0D2B15", fontcolor=C_RUNTIME, fontsize="8")
        c.node("sk_t2", 'action="move"\n→ CMD_MOVE(3001)\n   eir/operation_move2\n   机器人移动', shape="note", fillcolor="#0D2B15", fontcolor=C_RUNTIME, fontsize="8")
        c.node("sk_t3", 'action="stop"\n→ CMD_SOFT_ESTOP(9000)\n   eir/soft_emergency_stop\n   机器人急停', shape="note", fillcolor="#0D2B15", fontcolor=C_RUNTIME, fontsize="8")
        c.node("sk_t4", 'action="loco_mode"\n→ CMD_LOCO_MODE(1001)\n   站立/趴下/起身/小跑', shape="note", fillcolor="#0D2B15", fontcolor=C_RUNTIME, fontsize="8")
        c.node("sk_t5", 'action="oas"\n→ CMD_OAS(1004)\n   避障开关', shape="note", fillcolor="#0D2B15", fontcolor=C_RUNTIME, fontsize="8")
        c.node("sk_t6", 'action="play_audio"\n→ CMD_CORPUS(1007)\n   eir/general_interface\n   播放音频', shape="note", fillcolor="#0D2B15", fontcolor=C_RUNTIME, fontsize="8")
        c.node("sk_t7", 'action="switch_emotion"\n→ CMD_CORPUS(1007)\n   随机切换情绪', shape="note", fillcolor="#0D2B15", fontcolor=C_RUNTIME, fontsize="8")
        c.node("sk_t8", 'action="volume"\n→ CMD_SETTING(5002)\n   eir/setting\n   设置音量', shape="note", fillcolor="#0D2B15", fontcolor=C_RUNTIME, fontsize="8")
        c.node("sk_t9", 'action="navigate"\n→ CMD_NAVIGATION(6001)\n   eir/slam_navigation\n   启动导航', shape="note", fillcolor="#0D2B15", fontcolor=C_RUNTIME, fontsize="8")

    # ------------------------------------------------------------------
    # 第八段: Bridge + 机器人
    # ------------------------------------------------------------------
    with dot.subgraph(name="cluster_final") as c:
        c.attr(label="⑧ 机器人执行", style="filled", fillcolor="#161B22",
               fontcolor=C_BRIDGE, fontsize="13", color=C_BRIDGE)
        c.node("bridge_f", "eir_communication_bridge\nMQTT → ROS2 topic 透明中继", shape="box", fillcolor=C_BRIDGE)
        c.node("robot_f", "ehr_ros_app → ehr_app_core\n动作/导航/语音/表情 执行", shape="box", fillcolor=C_ROBOT)

    # ==================================================================
    # EDGES
    # ==================================================================

    # ① → ②
    dot.edge("txt", "gw_encap", "文本", color=C_ARROW)
    dot.edge("gw_encap", "gw_call", color=C_ARROW)

    # ② → ③
    dot.edge("gw_call", "rt_scan", "传入 message", color=C_ARROW)

    # ③ 内部分支
    dot.edge("rt_scan", "rt_hit", "关键词匹配", color=C_RUNTIME)
    dot.edge("rt_scan", "rt_miss", "无匹配", color=C_CAP, style="dashed")
    dot.edge("rt_hit", "rt_ex1", style="dashed", color=C_ARROW)
    dot.edge("rt_hit", "rt_ex2", style="dashed", color=C_ARROW)
    dot.edge("rt_hit", "rt_ex3", style="dashed", color=C_ARROW)
    dot.edge("rt_hit", "rt_ex4", style="dashed", color=C_ARROW)
    dot.edge("rt_miss", "rt_ex5", style="dashed", color=C_ARROW)
    dot.edge("rt_miss", "rt_ex6", style="dashed", color=C_ARROW)

    # ③ → ④
    dot.edge("rt_hit", "gw_dict", '返回 "motion" / "interaction" / "navigation"', color=C_GATEWAY)
    dot.edge("rt_miss", "gw_dict", '返回 "interaction"', color=C_GATEWAY, style="dashed")
    dot.edge("gw_dict", "gw_disp", color=C_ARROW)

    # ④ → ⑤
    dot.edge("gw_disp", "irt_check", "→ interaction", color=C_RUNTIME)
    dot.edge("gw_disp", "mrt_disp", "→ motion", color=C_RUNTIME)
    dot.edge("gw_disp", "nrt_disp", "→ navigation", color=C_RUNTIME)

    # ⑤ 内部: InteractionRuntime
    dot.edge("irt_check", "irt_direct", "有值 (关键词命中)", color=C_SKILL)
    dot.edge("irt_check", "irt_llm", "空 (无关键词)", color=C_AGENT)
    dot.edge("irt_llm", "irt_llm_out", "LLM 返回意图", color=C_AGENT)

    # ⑤ → ⑥ 二次路由
    dot.edge("irt_llm_out", "reroute", "intent=motion/nav", color=C_GATEWAY)
    dot.edge("reroute", "mrt_disp", "→ motion Runtime", color=C_GATEWAY, style="dashed")
    dot.edge("reroute", "nrt_disp", "→ navigation Runtime", color=C_GATEWAY, style="dashed")

    # ⑤ → ⑦
    dot.edge("irt_direct", "sk_int", color=C_SKILL)
    dot.edge("mrt_disp", "sk_motion", color=C_SKILL)
    dot.edge("nrt_disp", "sk_nav", color=C_SKILL)

    # ⑦ 内部分支
    dot.edge("sk_motion", "sk_t1", style="dashed", color=C_ARROW)
    dot.edge("sk_motion", "sk_t2", style="dashed", color=C_ARROW)
    dot.edge("sk_motion", "sk_t3", style="dashed", color=C_ARROW)
    dot.edge("sk_motion", "sk_t4", style="dashed", color=C_ARROW)
    dot.edge("sk_motion", "sk_t5", style="dashed", color=C_ARROW)
    dot.edge("sk_int", "sk_t6", style="dashed", color=C_ARROW)
    dot.edge("sk_int", "sk_t7", style="dashed", color=C_ARROW)
    dot.edge("sk_int", "sk_t8", style="dashed", color=C_ARROW)
    dot.edge("sk_nav", "sk_t9", style="dashed", color=C_ARROW)

    # ⑦ → ⑧
    dot.edge("sk_t1", "bridge_f", "MQTT", color=C_ARROW)
    dot.edge("sk_t2", "bridge_f", "MQTT", color=C_ARROW)
    dot.edge("sk_t3", "bridge_f", "MQTT", color=C_ARROW)
    dot.edge("sk_t6", "bridge_f", "MQTT", color=C_ARROW)
    dot.edge("sk_t9", "bridge_f", "MQTT", color=C_ARROW)
    dot.edge("bridge_f", "robot_f", "ROS2", color=C_ARROW)

    # 路径标注
    dot.node("pathA", "🟠 路径 A (右): 关键词命中 → 免 LLM, < 1ms\n   例: cqm1/停/四川话/带我去", shape="plaintext", fontcolor=C_SKILL, fontsize="10")
    dot.node("pathB", "🟡 路径 B (左): 无关键词 → LLM 意图理解 → 二次路由, ~100-500ms\n   例: 你好/介绍一下爱湫/往前走", shape="plaintext", fontcolor=C_LLM, fontsize="10")

    style_legend(dot)
    dot.render(os.path.join(OUT_DIR, "07_调用链路全景图"), format="png", cleanup=True)
    print("✓ 07_调用链路全景图.png")


# ============================================================================
if __name__ == "__main__":
    build_architecture()
    build_request_flow()
    build_routing_tree()
    build_module_deps()
    build_sequence()
    build_layers()
    build_call_chain()
    print(f"\n全部图表已生成到: {OUT_DIR}/")
