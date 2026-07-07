"""头环录制管理器 — 非阻塞帧驱动版本"""

from __future__ import annotations

import json
import logging
import os
import time as time_module
from datetime import datetime

from bci.hdata_interface import HDataInterface
from bci.hedf_interface import HEdfInterface

logger = logging.getLogger(__name__)

CONFIG_PATH = "bci/hdata_config.json"
DEFAULT_CONFIG = {"device_name": "", "save_dir": "recordings", "enabled": False}


def load_hdata_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                return {**DEFAULT_CONFIG, **json.load(f)}
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()


class HDataRecorder:

    STATE_IDLE = "idle"
    STATE_SEARCHING = "searching"
    STATE_CONNECTING = "connecting"
    STATE_WAITING_AMP = "waiting_amp"
    STATE_RECORDING = "recording"
    STATE_FAILED = "failed"

    def __init__(self, username: str = "default"):
        self._username = username
        self._cfg = load_hdata_config()
        self._hdata = HDataInterface()
        self._hedf = HEdfInterface()
        self._state = self.STATE_IDLE
        self._state_timer = 0.0
        self._recording = False
        self._filepath = ""

    @property
    def enabled(self) -> bool:
        return self._cfg.get("enabled", False)

    @property
    def connected(self) -> bool:
        return self._hdata.connected

    @property
    def recording(self) -> bool:
        return self._recording

    @property
    def is_ready(self) -> bool:
        return self._hdata.sampling_rate > 0 and self._hdata.eeg_channels > 0

    @property
    def state(self) -> str:
        return self._state

    def start(self):
        """帧驱动状态机入口 — 每帧调用"""
        if self._state == self.STATE_IDLE:
            device_name = self._cfg.get("device_name", "")
            if not device_name:
                self._state = self.STATE_FAILED
                logger.warning("[HData] 未配置设备名称")
                return
            self._hdata.start_search()
            self._state_timer = time_module.time()
            self._state = self.STATE_SEARCHING
            logger.info("[HData] 开始搜索设备...")
            return

        if self._state == self.STATE_SEARCHING:
            elapsed = time_module.time() - self._state_timer
            if len(self._hdata.searched_devices) > 0:
                dev = self._hdata.searched_devices[0]
                self._hdata.stop_search()
                self._hdata.connect_device(dev)
                self._state_timer = time_module.time()
                self._state = self.STATE_CONNECTING
                logger.info("[HData] 连接设备: %s", dev)
                return
            if elapsed > 15:
                self._state = self.STATE_FAILED
                logger.warning("[HData] 搜索超时")
                return

        if self._state == self.STATE_CONNECTING:
            elapsed = time_module.time() - self._state_timer
            if self._hdata.connected:
                self._state_timer = time_module.time()
                self._state = self.STATE_WAITING_AMP
                logger.info("[HData] 已连接，等待放大器...")
                return
            if elapsed > 10:
                self._state = self.STATE_FAILED
                logger.warning("[HData] 连接超时")
                return

        if self._state == self.STATE_WAITING_AMP:
            elapsed = time_module.time() - self._state_timer
            if self.is_ready:
                self._hdata.start_acquisition()
                self._start_recording()
                self._state = self.STATE_RECORDING
                return
            if elapsed > 15:
                self._state = self.STATE_FAILED
                logger.warning("[HData] 放大器信息超时")
                return

        if self._state == self.STATE_RECORDING:
            self.write_pending_data()

    def _start_recording(self):
        save_dir = self._cfg.get("save_dir", "recordings")
        os.makedirs(save_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self._username}_{ts}.bdf"
        self._filepath = os.path.join(save_dir, filename)
        ch = self._hdata.eeg_channels
        sr = self._hdata.sampling_rate
        r = self._hedf.open(self._filepath, ch, 1, sr)
        if r != 0:
            logger.error("[HData] BDF 打开失败: %s", self._filepath)
            return
        self._hdata.send_mark(1)
        self._recording = True
        logger.info("[HData] 开始录制: %s  打标=1", self._filepath)

    def stop(self):
        if self._recording:
            self._hdata.send_mark(2)
            self._hedf.close()
            self._recording = False
            logger.info("[HData] 停止录制: %s", self._filepath)
        self._state = self.STATE_IDLE

    def write_pending_data(self):
        if not self._recording:
            return
        data = self._hdata.poll_stream_data()
        if data is None:
            return
        channels = self._hdata.eeg_channels
        for block in data:
            if not block:
                continue
            samples = len(block)
            flat = []
            for j in range(samples):
                for i in range(channels):
                    flat.append(block[j][i] if i < len(block[j]) else 0.0)
            if flat:
                self._hedf.write_block(flat, samples)

    def destroy(self):
        if self._recording:
            self.stop()
        self._hdata.disconnect()
        self._hdata.destroy()
        self._state = self.STATE_IDLE
        logger.info("[HData] 已销毁")
