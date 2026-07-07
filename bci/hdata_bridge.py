"""HData 游戏桥接 — 帧驱动状态机"""

from __future__ import annotations

import logging

from bci.hdata_recorder import HDataRecorder

logger = logging.getLogger(__name__)


_hdata_recorder: HDataRecorder | None = None
_hdata_done = False


def init_hdata(context: dict):
    global _hdata_recorder, _hdata_done
    if _hdata_recorder is not None:
        return  # 主菜单已启动
    rec = context.get("hdata_recorder")
    if rec is not None and rec.enabled:
        _hdata_recorder = rec
        _hdata_done = False
        logger.info("[HData] 桥接初始化")


def tick_hdata():
    """每帧在主循环中调用 — 非阻塞驱动状态机"""
    global _hdata_done
    if _hdata_recorder is None or _hdata_done:
        return
    s = _hdata_recorder.state
    if s in (HDataRecorder.STATE_RECORDING, HDataRecorder.STATE_FAILED):
        _hdata_done = True
    _hdata_recorder.start()


def stop_hdata():
    global _hdata_recorder
    if _hdata_recorder is not None:
        _hdata_recorder.stop()
        _hdata_recorder.destroy()
        _hdata_recorder = None
