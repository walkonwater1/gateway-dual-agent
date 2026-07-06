"""
最简 MQTT 连通性测试 — 不依赖 LLM。

用法:
    python step1_hello_mqtt.py --host 机器人IP

预期: 脚本发送指令，观察机器人是否有反应。
如果机器人没反应，检查:
  1. MQTT broker 是否在运行（ssh 到机器人上 `systemctl status mosquitto`）
  2. Bridge 进程是否在运行
  3. 网络是否通（`ping 机器人IP`）
  4. 动作名是否正确（可用: cqm1, cqm2, cqm3）
"""

import argparse
import json
import sys
import uuid

try:
    import paho.mqtt.client as mqtt
except ImportError:
    print("请先安装: pip install paho-mqtt")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="MQTT 连通性测试")
    parser.add_argument("--host", default="127.0.0.1", help="MQTT broker IP")
    parser.add_argument("--port", type=int, default=8899, help="MQTT broker 端口")
    parser.add_argument("--cmd", type=int, default=1006,
                        help="指令编号（默认 1006 = 执行动作）")
    parser.add_argument("--data", default="cqm1",
                        help="指令数据（动作名 / 移动参数等）")
    args = parser.parse_args()

    print(f"→ 连接到 MQTT broker: {args.host}:{args.port}")
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"test_{uuid.uuid4().hex[:8]}")

    connected = False

    def on_connect(client, userdata, flags, reason_code, properties=None):
        nonlocal connected
        if reason_code == 0:
            connected = True
            print("✓ MQTT 连接成功")
        else:
            print(f"✗ MQTT 连接失败, reason_code={reason_code}")

    def on_disconnect(client, userdata, flags, reason_code, properties=None):
        print(f"! MQTT 断开, reason_code={reason_code}")

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect

    client.connect(args.host, args.port, keepalive=30)
    client.loop_start()

    # 等待连接
    import time
    deadline = time.time() + 5.0
    while not connected and time.time() < deadline:
        time.sleep(0.1)

    if not connected:
        print("✗ 无法连接到 MQTT broker，请检查 IP/端口")
        sys.exit(1)

    # 构造指令
    # 根据指令类型选择 topic
    topic_map = {
        1001: "eir/operation_instructions",
        1003: "eir/operation_instructions",
        1004: "eir/operation_instructions",
        1005: "eir/operation_instructions",
        1006: "eir/operation_instructions",
        1007: "eir/operation_instructions",
        1008: "eir/operation_instructions",
        1012: "eir/operation_instructions",
        2001: "eir/operation_extension",
        2002: "eir/operation_extension",
        2003: "eir/operation_extension",
        2004: "eir/operation_extension",
        2005: "eir/operation_extension",
        2006: "eir/operation_extension",
        3001: "eir/operation_move2",
        5000: "eir/setting",
        5001: "eir/setting",
        5002: "eir/setting",
        5003: "eir/setting",
        5004: "eir/setting",
        5555: "eir/setting",
        6000: "eir/slam_mapping",
        6001: "eir/slam_navigation",
        6002: "eir/slam_localization",
        8000: "eir/basic_heartbeat",
        9000: "eir/soft_emergency_stop",
    }
    topic = topic_map.get(args.cmd, "eir/operation_instructions")

    msg_uuid = str(uuid.uuid4())[:19]
    payload = json.dumps({
        "command": args.cmd,
        "uuid": msg_uuid,
        "commandData": args.data,
    }, ensure_ascii=False)

    print(f"→ 发送到 [{topic}]:")
    print(f"  {payload}")
    result = client.publish(topic, payload, qos=2)
    print(f"→ publish 返回: rc={result.rc}")

    time.sleep(0.5)
    client.loop_stop()
    client.disconnect()
    print("→ 测试完成，观察机器人是否有反应")


if __name__ == "__main__":
    main()
