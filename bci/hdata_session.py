"""HData 统一会话 — 替代 BCIDataReader，提供相同接口"""

from __future__ import annotations

import json
import logging
import os
import time as time_module
from datetime import datetime

from bci.hdata_interface import HDataInterface
from bci.hedf_interface import HEdfInterface
from bci.hdata_gyro import HDataGyroMapper
from bci.hdata_attention import HDataAttentionEstimator

logger = logging.getLogger(__name__)

CONFIG_PATH = "bci/hdata_config.json"
DEFAULT_CONFIG = {"device_name": "TH25A", "save_dir": "recordings", "enabled": False}


def load_hdata_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                return {**DEFAULT_CONFIG, **json.load(f)}
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()


class HDataSession:
    STATE_INIT = "init"
    STATE_SEARCHING = "searching"
    STATE_CONNECTING = "connecting"
    STATE_WAITING_AMP = "waiting_amp"
    STATE_READY = "ready"
    STATE_FAILED = "failed"

    def __init__(self, username: str = "default"):
        self._username = username
        self._cfg = load_hdata_config()
        self._hdata = HDataInterface()
        self._hedf = HEdfInterface()
        self._gyro_mapper = HDataGyroMapper()
        self._attn_estimator = HDataAttentionEstimator()

        self.attention: float = 50.0
        self.focus_x: float = 640.0
        self.focus_y: float = 620.0
        self.raw_gyro_x: float = 0.0
        self.raw_gyro_y: float = 0.0
        self.raw_gyro_z: float = 0.0
        self.connected = False

        self._state = self.STATE_INIT
        self._state_timer = 0.0
        self._recording = False
        self._filepath = ""

    @property
    def enabled(self) -> bool:
        return self._cfg.get("enabled", False)

    def connect(self, connect_timeout: float | None = None) -> bool:
        self._state_timer = time_module.time()
        self._hdata.start_search()
        self._state = self.STATE_SEARCHING
        logger.info("[HData] 开始搜索连接...")
        return True

    def drive(self):
        """每帧调用 — 推进状态机"""
        elapsed = time_module.time() - self._state_timer

        if self._state == self.STATE_SEARCHING:
            if len(self._hdata.searched_devices) > 0:
                dev = self._hdata.searched_devices[0]
                self._hdata.stop_search()
                self._hdata.connect_device(dev)
                self._state = self.STATE_CONNECTING
                self._state_timer = time_module.time()
                logger.info("[HData] 连接: %s", dev)
                return
            if elapsed > 15:
                self._state = self.STATE_FAILED
                logger.warning("[HData] 搜索超时")
                return

        elif self._state == self.STATE_CONNECTING:
            if self._hdata.connected:
                self._state_timer = time_module.time()
                self._state = self.STATE_WAITING_AMP
                logger.info("[HData] 等待放大器...")
                return
            if elapsed > 10:
                self._state = self.STATE_FAILED
                logger.warning("[HData] 连接超时")
                return

        elif self._state == self.STATE_WAITING_AMP:
            if self._hdata.sampling_rate > 0 and self._hdata.eeg_channels > 0:
                self._hdata.start_acquisition()
                self._start_recording()
                self._state = self.STATE_READY
                self.connected = True
                logger.info("[HData] 就绪 sr=%d ch=%d", self._hdata.sampling_rate, self._hdata.eeg_channels)
                return
            if elapsed > 15:
                self._state = self.STATE_FAILED
                logger.warning("[HData] 放大器超时")
                return

    def read_with_timeout(self):
        """返回 (attention, focus_x, focus_y, gyro_x, gyro_y, gyro_z) — 兼容 BCIDataReader 接口"""
        if not self.connected or self._state != self.STATE_READY:
            return None, None, None, None, None, None

        gx, gy, gz = self._hdata.gyro
        self.raw_gyro_x = gx
        self.raw_gyro_y = gy
        self.raw_gyro_z = gz
        self.focus_x = self._gyro_mapper.update(gy)

        eeg_data = self._hdata.poll_stream_data()
        if eeg_data is not None:
            for block in eeg_data:
                self._attn_estimator.feed(block)
        self.attention = self._attn_estimator.attention

        if self._recording:
            self._write_pending_data(eeg_data)

        return (self.attention, self.focus_x, self.focus_y, self.raw_gyro_x, self.raw_gyro_y, self.raw_gyro_z)

    def disconnect(self):
        if self._recording:
            self._stop_recording()
        self._hdata.stop_acquisition()
        self._hdata.disconnect()
        self._hdata.destroy()
        self.connected = False
        self._state = self.STATE_INIT
        logger.info("[HData] 已断开")

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
        logger.info("[HData] 录制开始: %s", self._filepath)

    def _stop_recording(self):
        if self._recording:
            self._hdata.send_mark(2)
            self._hedf.close()
            self._recording = False
            logger.info("[HData] 录制结束: %s", self._filepath)

    def _write_pending_data(self, data):
        if data is None:
            return
        for block in data:
            if not block:
                continue
            samples = len(block)
            ch = self._hdata.eeg_channels
            flat = []
            for j in range(samples):
                for i in range(ch):
                    flat.append(block[j][i] if i < len(block[j]) else 0.0)
            if flat:
                self._hedf.write_block(flat, samples)


_hdata_instance: HDataSession | None = None


def get_instance() -> HDataSession | None:
    return _hdata_instance


def create_instance(username: str = "default") -> HDataSession:
    global _hdata_instance
    if _hdata_instance is None:
        _hdata_instance = HDataSession(username=username)
    return _hdata_instance


def destroy_instance():
    global _hdata_instance
    if _hdata_instance is not None:
        _hdata_instance.disconnect()
        _hdata_instance = None
