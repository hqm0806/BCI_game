"""HData 陀螺仪 → 茶杯焦点 X 坐标映射 — 复用项目滤波器管线"""

from __future__ import annotations

from bci.filter import DeadZoneFilter, ExponentialSmoothing


class HDataGyroMapper:
    def __init__(self):
        self.focus_x: float = 640.0
        self._deadzone = DeadZoneFilter(threshold=5.0)
        self._smooth = ExponentialSmoothing(alpha=0.3)

    def update(self, gyro_y: float) -> float:
        yaw = self._deadzone.filter(gyro_y)
        yaw = self._smooth.smooth(yaw)
        self.focus_x += yaw * 8.0
        self.focus_x = max(40, min(1240, self.focus_x))
        return self.focus_x
