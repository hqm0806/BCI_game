"""
BCI 脑电数据读取模块
通过 TCP Socket 连接到科创平台，获取专注力和头动数据
连接后发送 ipc_algorithm_start_test 启动陀螺仪焦点算法
"""

import json
import logging
import socket
import struct
import time

from bci.config import load_bci_config
from config import BCI_CONNECTION_TIMEOUT, SCREEN_HEIGHT, SCREEN_WIDTH

logger = logging.getLogger(__name__)


class BCIDataReader:
    """脑电数据读取器 - 通过科创平台获取专注力和头动焦点坐标"""

    def __init__(self, ip=None, port=None):
        bci_config = load_bci_config()
        self.server_ip = ip or bci_config["server_ip"]
        self.server_port = port or bci_config["server_port"]

        self.attention = 50
        self.focus_x = SCREEN_WIDTH // 2
        self.focus_y = SCREEN_HEIGHT - 100
        self.raw_gyro_x = 0.0
        self.raw_gyro_y = 0.0
        self.raw_gyro_z = 0.0
        self.last_update_time = time.time()
        self.timeout = 2.0

        self.socket = None
        self.connected = False
        self.recv_buffer = b""

        self._attention_history: list[tuple[float, float]] = []
        self._rolling_avg = 50.0

    def get_rolling_attention(self) -> float:
        now = time.time()
        self._attention_history = [(t, v) for t, v in self._attention_history if now - t <= 3.0]
        if self._attention_history:
            self._rolling_avg = sum(v for _, v in self._attention_history) / len(self._attention_history)
        return self._rolling_avg

    def _record_attention(self, value: int) -> None:
        self._attention_history.append((time.time(), float(value)))

    def connect(self, ip=None, port=None):
        """连接 BCI 设备并启动陀螺仪算法"""
        if ip:
            self.server_ip = ip
        if port:
            self.server_port = port

        logger.info("[BCI] 尝试连接到 %s:%s...", self.server_ip, self.server_port)

        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(BCI_CONNECTION_TIMEOUT)
            self.socket.connect((self.server_ip, self.server_port))
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            self.socket.settimeout(0)
            self.connected = True
            self.recv_buffer = b""
            self.last_update_time = time.time()
            logger.info("[BCI] 已连接到科创平台 %s:%s", self.server_ip, self.server_port)

            self._send_ready()
            self._start_gyroscope_algorithm()

            return True
        except socket.timeout:
            logger.warning("[BCI] 连接超时（%s 秒）", BCI_CONNECTION_TIMEOUT)
            self.connected = False
        except ConnectionRefusedError:
            logger.error("[BCI] 连接被拒绝，请检查科创平台是否已启动（%s:%s）", self.server_ip, self.server_port)
            self.connected = False
        except Exception as e:
            logger.error("[BCI] 连接失败: %s", e)
            self.connected = False

        return False

    def disconnect(self):
        """断开 BCI 连接"""
        if self.socket:
            try:
                self._send({"msg": "ipc_algorithm_stop_test"})
            except Exception:
                pass
            try:
                self.socket.close()
            except Exception:
                pass
            self.socket = None
        self.connected = False
        logger.info("[BCI] 已断开连接")

    def _send(self, data: dict) -> None:
        if not self.socket or not self.connected:
            return
        msg = json.dumps(data, ensure_ascii=False).encode("utf-8")
        packet = struct.pack(">I", len(msg)) + msg
        self.socket.sendall(packet)

    def _send_ready(self) -> None:
        self._send({"type": "ready", "client": "crazy_milk_tea_cup"})
        logger.info("[BCI] 已发送就绪消息")

    def _start_gyroscope_algorithm(self) -> None:
        data = {
            "msg": "ipc_algorithm_start_test",
            "algorithm_name": "gyroscope",
            "algorithm_args": {
                "left": 0,
                "top": 0,
                "width": SCREEN_WIDTH,
                "height": SCREEN_HEIGHT,
                "sensitivityX": 10,
                "sensitivityY": 8,
            },
        }
        self._send(data)
        logger.info("[BCI] 已启动陀螺仪焦点算法（区域: %sx%s, 灵敏度: 8x8）", SCREEN_WIDTH, SCREEN_HEIGHT)

    def _recv_data(self):
        """接收 TCP 数据并解析为单条 JSON 消息"""
        if not self.socket or not self.connected:
            return None

        try:
            data = self.socket.recv(16384)
            if not data:
                logger.warning("[BCI] 连接被平台关闭")
                self.connected = False
                return None
            self.recv_buffer += data
        except BlockingIOError:
            return None
        except (ConnectionResetError, ConnectionAbortedError):
            logger.error("[BCI] 连接被重置")
            self.connected = False
            return None
        except Exception as e:
            logger.error("[BCI] 接收失败: %s", e)
            self.connected = False
            return None

        while len(self.recv_buffer) >= 4:
            payload_len = struct.unpack(">I", self.recv_buffer[:4])[0]
            total_len = 4 + payload_len
            if len(self.recv_buffer) < total_len:
                break

            payload = self.recv_buffer[4:total_len]
            self.recv_buffer = self.recv_buffer[total_len:]

            try:
                return json.loads(payload.decode("utf-8"))
            except json.JSONDecodeError:
                continue

        return None

    def read_data(self, verbose=False):
        """
        读取脑电数据，返回 (attention, focus_x, focus_y, gyro_x, gyro_y, gyro_z)
        每帧处理缓冲区中所有消息，只保留最新值，消除延迟
        """
        if not self.connected:
            return None, None, None, None, None, None

        msg_count = 0
        while True:
            msg = self._recv_data()
            if msg is None:
                break
            msg_count += 1
            try:
                msg_type = msg.get("msg", "")

                if msg_type == "ipc_algorithm_test":
                    algorithm_name = msg.get("algorithm_name", "")
                    result_args = msg.get("result_args", {})
                    data_content = result_args.get("data", None)

                    if algorithm_name == "attention" and data_content is not None:
                        self.attention = int(data_content)
                        self._record_attention(self.attention)
                        self.last_update_time = time.time()

                    elif algorithm_name == "gyroscope" and data_content is not None:
                        if isinstance(data_content, dict):
                            self.last_update_time = time.time()

                            fx = data_content.get("focus_x")
                            fy = data_content.get("focus_y")
                            if fx is not None:
                                self.focus_x = float(fx)
                            if fy is not None:
                                self.focus_y = float(fy)

                            self.raw_gyro_x = float(data_content.get("gyroscope_x", 0.0))
                            self.raw_gyro_y = float(data_content.get("gyroscope_y", 0.0))
                            self.raw_gyro_z = float(data_content.get("gyroscope_z", 0.0))

            except Exception as e:
                logger.error("[BCI] 解析数据失败: %s", e)

        if msg_count == 0 and time.time() - self.last_update_time > self.timeout:
            self.connected = False
            logger.warning("[BCI] 数据超时，连接已断开")

        return (
            self.attention,
            self.focus_x,
            self.focus_y,
            self.raw_gyro_x,
            self.raw_gyro_y,
            self.raw_gyro_z,
        )

    def read_with_timeout(self):
        """带超时的数据读取"""
        return self.read_data(verbose=True)
