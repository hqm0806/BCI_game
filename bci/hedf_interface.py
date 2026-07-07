"""BDF 文件写入接口 — 无 Qt 依赖"""

from __future__ import annotations

import ctypes
from ctypes import POINTER, c_bool, c_char_p, c_double, c_int

import os


class HEdfInterface:
    _instance = None

    def __new__(cls):
        if not cls._instance:
            cls._instance = super().__new__(cls)
            cls._instance._init_dll()
        return cls._instance

    def _init_dll(self):
        dll_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "libs", "HEdfProcessor.dll")
        dll_path = os.path.normpath(dll_path)
        if not os.path.exists(dll_path):
            alt = os.path.join(os.getcwd(), "libs", "HEdfProcessor.dll")
            if os.path.exists(alt):
                dll_path = alt
        self._lib = ctypes.CDLL(dll_path)

        self._lib.open.argtypes = [c_char_p, c_int, c_int, c_int, c_int]
        self._lib.open.restype = c_int
        self._lib.writeBlockData.argtypes = [POINTER(c_double), c_int]
        self._lib.writeBlockData.restype = None
        self._lib.close.restype = None
        self._opened = False

    def open(self, filepath: str, eeg_channels: int, event_channels: int, sampling_rate: int) -> int:
        result = self._lib.open(
            filepath.encode("utf-8"),
            eeg_channels,
            event_channels,
            1,  # BDF_FORMAT
            sampling_rate,
        )
        if result == 0:
            self._opened = True
        return result

    def write_block(self, data: list[float], samples: int):
        if not self._opened:
            return
        arr = (c_double * len(data))(*data)
        self._lib.writeBlockData(arr, samples)

    def close(self):
        if self._opened:
            self._lib.close()
            self._opened = False
