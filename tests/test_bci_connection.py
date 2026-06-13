"""HybridBCI 平台连接测试脚本
用于验证与 HybridBCI 科研科创平台的 TCP 连接和数据接收

使用方法:
    python test_bci_connection.py                    # 读取 bci_config.json 配置
    python test_bci_connection.py 192.168.1.100 8000 # 命令行参数优先

配置文件 (bci_config.json):
    {
        "server_ip": "127.0.0.1",
        "server_port": 8000
    }
"""

import json
import os
import socket
import struct
import sys
import time


def get_script_dir():
    """获取脚本/exe 所在目录（兼容 pyinstaller 打包）"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def load_config(script_dir):
    """从 bci_config.json 加载配置"""
    config_path = os.path.join(script_dir, "bci_config.json")
    default = {"server_ip": "127.0.0.1", "server_port": 8000}

    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            print(f"[配置] 读取 bci_config.json: {cfg}")
            return cfg
        except Exception as e:
            print(f"[配置] 读取 bci_config.json 失败: {e}，使用默认配置")
            return default
    else:
        print(f"[配置] 未找到 bci_config.json，使用默认配置")
        print(f"[配置] 可在以下位置创建: {config_path}")
        return default


class BCITestClient:
    """HybridBCI 平台 TCP 测试客户端"""

    def __init__(self, host: str = "127.0.0.1", port: int = 8000):
        self.host = host
        self.port = port
        self.socket = None
        self.recv_buffer = b""
        self.reconnect_delay = 3
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5

    def connect(self) -> bool:
        """连接到 HybridBCI 平台服务器"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10.0)
            self.socket.connect((self.host, self.port))
            print(f"[✓] 已连接到 HybridBCI 平台: {self.host}:{self.port}")
            self.reconnect_attempts = 0
            return True
        except ConnectionRefusedError:
            print(f"[✗] 连接被拒绝: {self.host}:{self.port}")
            print("    请确认 HybridBCI 平台已启动并开启了服务器")
            return False
        except socket.timeout:
            print(f"[✗] 连接超时: {self.host}:{self.port}")
            return False
        except Exception as e:
            print(f"[✗] 连接失败: {e}")
            return False

    def disconnect(self):
        """断开连接"""
        if self.socket:
            self.socket.close()
            self.socket = None
            print("[!] 已断开连接")

    def reconnect(self) -> bool:
        """自动重连"""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            print(f"[✗] 达到最大重连次数 ({self.max_reconnect_attempts})，停止重连")
            return False

        self.reconnect_attempts += 1
        wait = self.reconnect_delay * self.reconnect_attempts
        print(f"\n[重试] 第 {self.reconnect_attempts} 次重连，{wait} 秒后尝试...")
        time.sleep(wait)

        return self.connect()

    def receive_data(self) -> dict | None:
        """接收并解析一条完整消息"""
        # 先接收 4 字节长度前缀
        while len(self.recv_buffer) < 4:
            chunk = self.socket.recv(4096)
            if not chunk:
                return None
            self.recv_buffer += chunk

        # 解析负载长度
        payload_len = struct.unpack(">I", self.recv_buffer[:4])[0]
        self.recv_buffer = self.recv_buffer[4:]

        # 接收完整负载
        while len(self.recv_buffer) < payload_len:
            chunk = self.socket.recv(4096)
            if not chunk:
                return None
            self.recv_buffer += chunk

        payload = self.recv_buffer[:payload_len]
        self.recv_buffer = self.recv_buffer[payload_len:]

        return json.loads(payload.decode("utf-8"))

    def run(self):
        """运行主循环（支持自动重连）"""
        while True:
            if not self.connect():
                if not self.reconnect():
                    break
                continue

            print("\n[提示] 按 Ctrl+C 停止测试\n")
            print("等待平台数据...")
            print("-" * 60)

            try:
                while True:
                    try:
                        data = self.receive_data()
                        if data is None:
                            continue
                        self._handle_data(data)
                    except ConnectionError:
                        print("\n[!] 服务器断开连接")
                        break
                    except json.JSONDecodeError:
                        print("[!] 收到无效 JSON 数据")
            except KeyboardInterrupt:
                print("\n[!] 用户中断测试")
                self.disconnect()
                return

            self.disconnect()
            if not self.reconnect():
                break

    def _handle_data(self, data: dict):
        """处理接收到的数据"""
        msg = data.get("msg", "")

        if msg == "ipc_algorithm_test":
            algorithm_name = data.get("algorithm_name", "")
            result_args = data.get("result_args", {})
            data_content = result_args.get("data", None)

            timestamp = time.strftime("%H:%M:%S")

            if algorithm_name == "attention" and data_content is not None:
                print(f"[{timestamp}] 专注力: {data_content}")

            elif algorithm_name == "gyroscope" and data_content is not None:
                if isinstance(data_content, dict):
                    gyro_x = data_content.get("gyroscope_x", 0.0)
                    gyro_y = data_content.get("gyroscope_y", 0.0)
                    gyro_z = data_content.get("gyroscope_z", 0.0)
                    print(
                        f"[{timestamp}] 头动 - X: {gyro_x:.2f}, "
                        f"Y: {gyro_y:.2f}, Z: {gyro_z:.2f}"
                    )

            elif algorithm_name == "blink" and data_content is not None:
                print(f"[{timestamp}] 眨眼: {data_content}")

            else:
                print(f"[{timestamp}] 未知算法: {algorithm_name}")

        elif msg == "ipc_user_info":
            layout_type = data.get("layout_type", 0)
            print(f"[用户信息] 布局类型: {layout_type}")

        else:
            print(f"[未知消息] 类型: {msg}")
            print(f"    原始数据: {json.dumps(data, ensure_ascii=False, indent=2)}")


def main():
    print("=" * 60)
    print("  HybridBCI 平台连接测试工具")
    print("=" * 60)

    script_dir = get_script_dir()

    if len(sys.argv) >= 3:
        host = sys.argv[1]
        port = int(sys.argv[2])
        print(f"[配置] 使用命令行参数: {host}:{port}")
    else:
        config = load_config(script_dir)
        host = config.get("server_ip", "127.0.0.1")
        port = config.get("server_port", 8000)

    client = BCITestClient(host, port)
    client.run()


if __name__ == "__main__":
    main()
