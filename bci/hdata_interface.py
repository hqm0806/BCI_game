"""直接 ctypes 版本 — 绕过 HDataInterface 类"""
import ctypes, os, threading, time, logging
from ctypes import CFUNCTYPE, POINTER, c_bool, c_char_p, c_int, c_long, c_uint, c_float, c_double

logger = logging.getLogger(__name__)


def _load_dll():
    dll_path = os.path.join(os.getcwd(), "libs", "HDataSystem.dll")
    if not os.path.exists(dll_path):
        raise FileNotFoundError(dll_path)
    return ctypes.CDLL(dll_path)


class HDataInterface:
    """直接 ctypes 包装 — 无 Python 类层级"""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance

    def _init(self):
        self._lib = _load_dll()
        self._lib.initSDK.restype = c_int
        self._lib.initSDK()

        self._searched = []
        self._connected = False
        self._sr = 0
        self._ech = 0
        self._gyro = (0, 0, 0)
        self._battery = 0
        self._stream_lock = threading.Lock()
        self._stream_data = []

        CbS = CFUNCTYPE(None, c_char_p)
        CbV = CFUNCTYPE(None)
        def _on_search(n): self._searched.append(n.decode())
        def _on_conn(): self._connected = True
        def _on_amp():
            self._sr = self._lib.getSamplingRate()
            self._ech = self._lib.getNumEEGChannels()
        self._cb_search = CbS(_on_search)
        self._cb_conn = CbV(_on_conn)
        self._cb_amp = CbV(_on_amp)

        self._lib.registerSearchedDeviceNameCallback(self._cb_search)
        self._lib.registerDataConnectedCallback(self._cb_conn)
        self._lib.registerAmpInfoUpdatedCallback(self._cb_amp)

        CbStream = CFUNCTYPE(None, POINTER(c_float), c_int, c_long)
        def _on_stream(pData, nSize, start):
            ch = self._ech
            if ch <= 0: return
            samples = nSize // (ch * 4)
            block = []
            for j in range(samples):
                row = [pData[i + j * ch] for i in range(ch)]
                block.append(row)
            with self._stream_lock:
                self._stream_data.append(block)
        self._cb_stream = CbStream(_on_stream)
        self._lib.registerStreamDataReadyCallback(self._cb_stream)

        self._gyro = (0, 0, 0)
        self._battery = 0
        self._wear_state = 0
        CbAdd = CFUNCTYPE(None, c_int, c_int, c_int, c_int, c_int)
        def _on_add(gx, gy, gz, wear, batt):
            self._gyro = (gx, gy, gz)
            self._battery = batt
            self._wear_state = wear
        self._cb_add = CbAdd(_on_add)
        self._lib.registerStreamingAdditionalDataReadyCallback(self._cb_add)

        self._lib.setDeviceType.argtypes = [c_int]
        self._lib.setDeviceType.restype = None
        self._lib.setTransportInfo.argtypes = [c_char_p, c_int]
        self._lib.setTransportInfo.restype = None
        self._lib.connectTransport.restype = None
        self._lib.disconnectTransport.restype = None
        self._lib.startSearchDevice.restype = None
        self._lib.stopSearchDevice.restype = None
        self._lib.startAcquisition.restype = c_bool
        self._lib.stopAcquisition.restype = c_bool
        self._lib.sendMark.argtypes = [c_uint]
        self._lib.sendMark.restype = None
        self._lib.setEpochLen.argtypes = [c_int]
        self._lib.setEpochLen.restype = None

    def start_search(self):
        self._searched = []
        self._lib.setDeviceType(0)
        self._lib.startSearchDevice()

    def stop_search(self):
        self._lib.stopSearchDevice()

    def connect_device(self, name: str):
        self._lib.setTransportInfo(name.encode(), 0)
        self._lib.connectTransport()

    def disconnect(self):
        self._lib.disconnectTransport()

    def start_acquisition(self):
        self._lib.startAcquisition()

    def stop_acquisition(self):
        self._lib.stopAcquisition()

    def send_mark(self, eid: int):
        self._lib.sendMark(eid)

    @property
    def searched_devices(self):
        return list(self._searched)

    @property
    def connected(self):
        return self._connected

    @property
    def sampling_rate(self):
        return self._sr

    @property
    def eeg_channels(self):
        return self._ech

    @property
    def gyro(self):
        return self._gyro

    @property
    def battery(self):
        return self._battery

    @property
    def total_channels(self):
        return self._ech

    def poll_stream_data(self):
        with self._stream_lock:
            if not self._stream_data:
                return None
            data = list(self._stream_data)
            self._stream_data = []
            return data

    def destroy(self):
        self._lib.destroy()
        HDataInterface._instance = None
