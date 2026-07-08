"""HData 5通道 EEG → 专注力 (0-100) 估计"""

from __future__ import annotations


class HDataAttentionEstimator:
    def __init__(self):
        self._attention: float = 50.0
        self._buffer: list[float] = []

    def feed(self, eeg_data: list[list[float]]) -> float:
        for row in eeg_data:
            energy = sum(abs(v) for v in row) / max(1, len(row))
            self._buffer.append(energy)
        if len(self._buffer) > 250:
            self._buffer = self._buffer[-250:]
        if self._buffer:
            avg = sum(self._buffer) / len(self._buffer)
            self._attention = min(100.0, max(0.0, avg * 0.08))
        return self._attention

    @property
    def attention(self):
        return self._attention
