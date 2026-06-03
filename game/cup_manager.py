"""
杯管理器模块 - 管理单杯奶茶的完整生命周期

每杯 <= T 秒，最多接 n 个食材，杯结束时：
  - 无必接食材 → 本杯金额 = 0
  - 有必接食材 → 本杯金额 = 所有接住食材分值之和
  - 接到秘方 → 本杯金额 × 2
"""

from __future__ import annotations

import logging
import time

from config import (
    CUP_DURATION,
    DIFFICULTY_BASELINE,
    DIFFICULTY_BASELINE_MAX,
    DIFFICULTY_BASELINE_MIN,
    DIFFICULTY_ADAPT_WINDOW,
    INGREDIENT_POINTS,
    SECRET_RECIPE_OFFSET,
)

logger = logging.getLogger(__name__)


class CupManager:
    """管理单杯奶茶的生命周期和全局杯计数"""

    def __init__(
        self,
        has_required: bool = False,
        required_type: str | None = None,
        total_cups: int = 12,
        secret_recipe_interval: int = 3,
    ) -> None:
        self.has_required = has_required
        self.required_type = required_type
        self.total_cups = total_cups
        self.secret_recipe_interval = secret_recipe_interval

        self.cup_number: int = 0
        self.cup_start_time: float = 0.0
        self.catch_count: int = 0
        self.cup_required_caught: bool = False
        self.cup_money: int = 0
        self.cup_ended: bool = True
        self.cup_ended_reason: str = ""

        self.secret_recipe_spawned: bool = False
        self.secret_recipe_caught: bool = False

        self.cup_money_history: list[int] = []
        self.cup_secret_history: list[bool] = []
        self.total_money: int = 0
        self.secret_recipe_count: int = 0
        self.total_catches: int = 0

    def start_new_cup(self) -> None:
        self.cup_number += 1
        self.cup_start_time = time.time()
        self.catch_count = 0
        self.cup_required_caught = False
        self.cup_money = 0
        self.cup_ended = False
        self.cup_ended_reason = ""
        self.secret_recipe_spawned = False
        self.secret_recipe_caught = False

    def add_catch(self, ingredient_type: str, is_required: bool = False) -> int:
        points = INGREDIENT_POINTS.get(ingredient_type, 5)
        self.catch_count += 1
        self.total_catches += 1

        if ingredient_type == "秘方":
            self.secret_recipe_caught = True
            self.secret_recipe_count += 1
            return points

        if is_required or (self.has_required and ingredient_type == self.required_type):
            self.cup_required_caught = True

        self.cup_money += points
        return points

    def check_cup_end(self) -> bool:
        if self.cup_ended:
            return True

        elapsed = time.time() - self.cup_start_time
        if elapsed >= CUP_DURATION:
            self.cup_ended = True
            self.cup_ended_reason = "timeout"
            return True
        return False

    def settle_cup(self) -> int:
        if not self.cup_ended:
            self.cup_ended = True
            self.cup_ended_reason = "forced"

        final_money = 0 if (self.has_required and not self.cup_required_caught) else self.cup_money

        if self.secret_recipe_spawned:
            final_money *= 2

        self.cup_money_history.append(final_money)
        self.cup_secret_history.append(self.secret_recipe_spawned)
        self.total_money += final_money

        logger.info(
            "第 %s 杯结算: 金额=%s, 原因=%s, 接住=%s, 秘方=%s, 必接=%s",
            self.cup_number,
            final_money,
            self.cup_ended_reason,
            self.catch_count,
            self.secret_recipe_caught,
            self.cup_required_caught,
        )
        return final_money

    def trigger_secret_recipe(self) -> bool:
        if self.secret_recipe_spawned:
            return False
        self.secret_recipe_spawned = True
        return True

    def get_cup_elapsed(self) -> float:
        return time.time() - self.cup_start_time

    def get_cup_remaining(self) -> float:
        return max(0.0, CUP_DURATION - self.get_cup_elapsed())

    def all_cups_done(self) -> bool:
        return self.cup_number >= self.total_cups and self.cup_ended

    def is_game_time_exceeded(self, game_start_time: float) -> bool:
        max_time = self.total_cups * CUP_DURATION
        return (time.time() - game_start_time) >= max_time

    def should_force_secret_recipe(self) -> bool:
        if self.cup_number == 0:
            return False
        return (self.cup_number % self.secret_recipe_interval) == 0


class DifficultyAdapter:
    """难度自适应调节器 - 根据滚动窗口内的平均专注力动态调整基线"""

    def __init__(self) -> None:
        self.baseline: float = float(DIFFICULTY_BASELINE)
        self.window_duration: float = float(DIFFICULTY_ADAPT_WINDOW)
        self._samples: list[tuple[float, float]] = []

    def update(self, attention: float, dt: float) -> float:
        t = time.time()
        self._samples.append((t, attention))
        cutoff = t - self.window_duration
        self._samples = [(ts, v) for ts, v in self._samples if ts >= cutoff]

        if len(self._samples) >= 30:
            values = [v for _, v in self._samples]
            avg = sum(values) / len(values)
            self.baseline = max(
                DIFFICULTY_BASELINE_MIN,
                min(DIFFICULTY_BASELINE_MAX, avg),
            )
        return self.baseline

    def get_secret_threshold(self) -> float:
        return min(88.0, self.baseline + SECRET_RECIPE_OFFSET)
