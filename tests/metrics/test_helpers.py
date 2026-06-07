"""
游戏逻辑模拟器 — 从 GameSession 提取核心算法，支持无 pygame 的精准测试
用于 3.2.1 ~ 3.2.3 三个测试节的指标测算
"""
from __future__ import annotations

import math
import random
import time as _time
from collections import deque
from typing import Any

import numpy as np

from config import (
    ARTIFACT_ATTENTION_THRESHOLD,
    ARTIFACT_PENALTY_DURATION,
    ARTIFACT_STILL_DURATION,
    ARTIFACT_STILL_THRESHOLD,
    CUP_SPEED,
    CUP_WIDTH,
    FORMAL_SPEED_MAX,
    FORMAL_SPEED_MIN,
    INGREDIENT_LANE_INDICES,
    INGREDIENT_POINTS,
    INGREDIENT_TIERS,
    LANE_WIDTH,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    SECRET_RECIPE_SUSTAIN,
    WARMUP_FREEZE_TIME,
    WARMUP_LOW_THRESHOLD,
    WARMUP_RESUME_TIME,
    get_attention_coefficient,
)
from data.player_profile import LEVEL_THRESHOLDS
from game.cup_manager import CupManager
from game.ingredient_manager import IngredientManager


class AttentionGenerator:
    """生成不同类型玩家的模拟注意力序列（随机游走 + 约束 + 偶发走神）"""

    PROFILES = {
        "stable_high": {
            "baseline": 75.0, "std": 1.5, "pullback": 0.15,
            "drop_prob": 0.0001, "drop_depth": (20.0, 30.0),
            "burst_prob": 0.0003, "burst_duration": (420, 720), "burst_elevation": 10.0,
        },
        "medium": {
            "baseline": 55.0, "std": 2.0, "pullback": 0.12,
            "drop_prob": 0.0008, "drop_depth": (10.0, 25.0),
            "burst_prob": 0.0003, "burst_duration": (300, 540), "burst_elevation": 15.0,
        },
        "low_fluctuating": {
            "baseline": 30.0, "std": 4.0, "pullback": 0.06,
            "drop_prob": 0.002, "drop_depth": (3.0, 12.0), "drop_sustain": (240, 480),
            "burst_prob": 0.0001, "burst_duration": (200, 360), "burst_elevation": 20.0,
        },
    }

    def __init__(self, player_type: str, seed: int = None) -> None:
        if player_type not in self.PROFILES:
            raise ValueError(f"未知玩家类型: {player_type}，可选: {list(self.PROFILES)}")
        cfg = self.PROFILES[player_type]
        self.baseline = cfg["baseline"]
        self.std = cfg["std"]
        self.pullback = cfg.get("pullback", 0.05)
        self.drop_prob = cfg["drop_prob"]
        self.drop_depth = cfg["drop_depth"]
        self.drop_sustain = cfg.get("drop_sustain", None)
        self.burst_prob = cfg.get("burst_prob", 0.0)
        self.burst_duration = cfg.get("burst_duration", (0, 0))
        self.burst_elevation = cfg.get("burst_elevation", 10.0)
        self.rng = random.Random(seed) if seed is not None else random.Random()
        self._np_rng = np.random.RandomState(seed) if seed is not None else np.random.RandomState()

    def generate(self, total_seconds: float, fps: int = 60) -> np.ndarray:
        frames = int(total_seconds * fps)
        attn = np.zeros(frames, dtype=np.float64)
        attn[0] = self.baseline

        i = 1
        burst_frames_left = 0
        drop_frames_left = 0
        burst_active = False
        drop_active = False
        drop_value = 0.0

        while i < frames:
            if burst_frames_left > 0:
                burst_active = True
                burst_frames_left -= 1
            else:
                burst_active = False

            if drop_frames_left > 0:
                drop_active = True
                drop_frames_left -= 1
            else:
                drop_active = False

            step = float(self._np_rng.normal(0, self.std * 1.5))
            pull = (self.baseline - attn[i - 1]) * self.pullback
            val = attn[i - 1] + step + pull

            if burst_active:
                val += self.burst_elevation

            if drop_active:
                val = drop_value + float(self._np_rng.normal(0, 2.0))
            else:
                if self.rng.random() < self.drop_prob:
                    if self.drop_sustain:
                        lo, hi = self.drop_depth
                        drop_value = self.rng.uniform(lo, hi)
                        lo_d, hi_d = self.drop_sustain
                        drop_frames_left = self.rng.randint(lo_d, hi_d)
                    else:
                        lo, hi = self.drop_depth
                        val = self.rng.uniform(lo, hi)

            if self.burst_prob > 0 and not burst_active and not drop_active:
                if self.rng.random() < self.burst_prob:
                    lo_d, hi_d = self.burst_duration
                    burst_frames_left = self.rng.randint(lo_d, hi_d)

            attn[i] = float(np.clip(val, 0.0, 100.0))
            i += 1

        return attn


class GyroGenerator:
    """生成陀螺仪三轴模拟数据，用于防作弊检测测试"""

    def __init__(self, total_frames: int, cheat_ratio: float = 0.05, seed: int = None) -> None:
        self.total_frames = total_frames
        self.cheat_ratio = cheat_ratio
        self.rng = np.random.RandomState(seed) if seed is not None else np.random.RandomState()
        self.data = self._generate()

    def _generate(self) -> np.ndarray:
        data = np.zeros((self.total_frames, 3), dtype=np.float64)
        data[0] = self.rng.uniform(-5, 5, 3)

        for i in range(1, self.total_frames):
            if self.rng.random() < self.cheat_ratio:
                data[i] = data[i - 1] + self.rng.uniform(-0.05, 0.05, 3)
            else:
                data[i] = data[i - 1] + self.rng.normal(0, 1.5, 3)
            data[i] = np.clip(data[i], -30, 30)

        return data

    def get_frame(self, idx: int) -> tuple[float, float, float]:
        idx = idx % self.total_frames
        return float(self.data[idx, 0]), float(self.data[idx, 1]), float(self.data[idx, 2])


class GameSimulator:
    """
    无 pygame 依赖的逐帧游戏模拟器
    从 GameSession 移植全部核心算法，复现完整的归一化→速度→方差→冰块→秘方→防作弊→冻结→结算流程
    """

    def __init__(
        self,
        warmup_attn: np.ndarray,
        formal_attn: np.ndarray,
        gyro_generator: GyroGenerator,
        tier: int = 1,
        seed: int = None,
    ) -> None:
        self.warmup_attn = warmup_attn
        self.formal_attn = formal_attn
        self.gyro = gyro_generator

        self.rng = random.Random(seed) if seed is not None else random.Random()

        self.CUP_DURATION = 20
        self.TOTAL_CUPS = 36
        self.WARMUP_DURATION = 180

        self._tier = tier
        self._init_state()

    def _init_state(self) -> None:
        self.normalization_lower = 0.0
        self.normalization_upper = 100.0

        self.cup_x = float(SCREEN_WIDTH // 2)
        self.cup_target = 2

        self._falling_ingredients: list[dict[str, Any]] = []

        self.cup_manager = CupManager(
            has_required=False,
            total_cups=self.TOTAL_CUPS,
            secret_recipe_interval=3,
        )

        self.ingredient_manager = IngredientManager(tier=self._tier)
        self.ingredient_manager.spawn_interval = 1.2
        self.ingredient_manager.set_current_speed(3.0)

        self.attention: float = 50.0
        self._cup_baseline: float = 40.0
        self._cup_attn_samples: list[float] = []
        self._attn_offsets: deque[float] = deque(maxlen=60)

        self.focus_above_seconds: float = 0.0
        self._secret_popup_timer: float = 0.0

        self._paused: bool = False
        self._low_attn_seconds: float = 0.0
        self._high_attn_seconds: float = 0.0

        self._artifact_frozen: bool = False
        self._artifact_penalty_timer: float = 0.0
        self._gyro_still_timer: float = 0.0
        self._prev_gyro: tuple[float, float, float] = (0.0, 0.0, 0.0)

        self.warmup_all_attn: list[float] = []
        self._warmup_paused: bool = False
        self._warmup_low_timer: float = 0.0
        self._warmup_high_timer: float = 0.0

        self._frame_idx: int = 0
        self._sim_time: float = 0.0
        self._last_spawn_time: float = 0.0
        self._spawn_random_offset: float = self.rng.uniform(-0.3, 0.3)
        self._cup_start_time: float = 0.0

        self.metrics: dict[str, Any] = {
            "revenue": 0,
            "cups": 0,
            "secrets": 0,
            "zero_revenue_cups": 0,
            "freeze_count": 0,
            "artifact_count": 0,
            "total_catches": 0,
            "total_spawns": 0,
            "cup_money_list": [],
            "avg_attention": 0.0,
            "level": 1,
        }

    def _normalize_to_range(self, attention: float) -> float:
        if self.normalization_upper - self.normalization_lower < 1.0:
            return 50.0
        norm = (attention - self.normalization_lower) / (
            self.normalization_upper - self.normalization_lower
        ) * 99.0 + 1.0
        return max(1.0, min(100.0, norm))

    def run_warmup(self) -> tuple[float, float]:
        dt = 1.0 / 60.0
        for i in range(len(self.warmup_attn)):
            self.attention = float(self.warmup_attn[i])
            self._check_warmup_freeze(dt)
            if not self._warmup_paused:
                self.warmup_all_attn.append(self.attention)
            self._frame_idx += 1
        return self._transition_to_formal()

    def _transition_to_formal(self) -> tuple[float, float]:
        warmup_last_30s_frames = int(30 * 60)
        last_30s = (
            self.warmup_all_attn[-warmup_last_30s_frames:]
            if len(self.warmup_all_attn) >= warmup_last_30s_frames
            else self.warmup_all_attn
        )
        if last_30s:
            max_attn = float(max(last_30s))
            avg_attn = float(sum(last_30s) / len(last_30s))
            self.normalization_upper = min(max_attn, 100.0)
            self.normalization_lower = max(avg_attn - 15.0, 0.0)
            if self.normalization_upper - self.normalization_lower < 10.0:
                mid = (self.normalization_upper + self.normalization_lower) / 2.0
                self.normalization_lower = max(mid - 5.0, 0.0)
                self.normalization_upper = min(mid + 5.0, 100.0)
        else:
            self.normalization_lower = 30.0
            self.normalization_upper = 70.0
            max_attn = 70.0
            avg_attn = 50.0

        self._cup_baseline = float(avg_attn) if avg_attn > 0 else 40.0
        self.cup_manager.start_new_cup()
        self.ingredient_manager.reset_spawn_timer()
        self._last_spawn_time = self._sim_time
        self._cup_start_time = self._sim_time

        return self.normalization_lower, self.normalization_upper

    def run_formal(self) -> dict[str, Any]:
        dt = 1.0 / 60.0
        total_attention = 0.0
        attn_count = 0

        for i in range(len(self.formal_attn)):
            self.attention = float(self.formal_attn[i])
            total_attention += self.attention
            attn_count += 1
            self._frame_idx += 1

            self._tick(dt)

            if self.cup_manager.all_cups_done():
                break

        self.metrics["avg_attention"] = total_attention / max(attn_count, 1)
        self.metrics["level"] = self._tier
        return self.metrics

    def _tick(self, dt: float) -> None:
        if self._artifact_frozen:
            self._update_artifact_freeze(dt)
            self._sim_time += dt
            return

        if self._paused:
            self._update_pause_state(dt)
            self._sim_time += dt
            return

        self._sim_time += dt

        norm = self._normalize_to_range(self.attention)
        speed = FORMAL_SPEED_MAX - (norm - 1.0) / 99.0 * (FORMAL_SPEED_MAX - FORMAL_SPEED_MIN)
        self.ingredient_manager.set_current_speed(speed)

        speed_ratio = speed / 3.0 if 3.0 > 0 else 1.0
        self.ingredient_manager.spawn_interval = max(0.3, min(3.0, 1.2 * (0.7 + 0.6 * speed_ratio)))

        self._update_attention_variance()

        if self._sim_time - self._last_spawn_time >= self.ingredient_manager.spawn_interval + self._spawn_random_offset:
            ing = self._spawn_ingredient(speed)
            if ing:
                self._falling_ingredients.append(ing)
                self._last_spawn_time = self._sim_time
                self.rng.random()
                self._spawn_random_offset = self.rng.uniform(-0.3, 0.3)
                self.metrics["total_spawns"] += 1

        if self._cup_attn_samples is not None:
            self._cup_attn_samples.append(self.attention)

        self._update_cup_target()
        self._do_move_cup()
        self._move_and_check_ingredients()
        self._check_secret_recipe(dt)
        self._check_artifact(dt)
        self._update_pause_state(dt)
        self._check_cup_end()

    def _spawn_ingredient(self, speed: float) -> dict[str, Any] | None:
        tier_cfg = INGREDIENT_TIERS.get(self._tier, INGREDIENT_TIERS[1])
        available = tier_cfg["available"]
        ing_type = self.rng.choice(available)

        if self.ingredient_manager._ice_probability > 0:
            if self.rng.random() < self.ingredient_manager._ice_probability:
                ing_type = "冰块"

        occupied = set()
        for ing in self._falling_ingredients:
            if ing["y"] < SCREEN_HEIGHT * 0.35:
                occupied.add(ing["lane"])
        free = [ln for ln in INGREDIENT_LANE_INDICES if ln not in occupied]
        if not free:
            return None

        lane = self.rng.choice(free)
        x = float(lane * LANE_WIDTH + LANE_WIDTH // 2)

        return {"type": ing_type, "x": x, "y": 0.0, "speed": speed, "lane": lane}

    def _update_cup_target(self) -> None:
        if not self._falling_ingredients:
            return
        urgent = min(self._falling_ingredients, key=lambda ing: ing["y"] - ing["speed"] * 0)
        best = None
        best_time = float("inf")
        for ing in self._falling_ingredients:
            remaining_y = max(0.0, float(SCREEN_HEIGHT - 100) - ing["y"])
            eta = remaining_y / max(ing["speed"], 0.5)
            needed_x = float(ing["lane"] * LANE_WIDTH + LANE_WIDTH // 2)
            dist_x = abs(needed_x - self.cup_x)
            travel_time = dist_x / max(CUP_SPEED, 0.5)
            if eta < best_time and travel_time < eta:
                best_time = eta
                best = ing
        if best is not None:
            self.cup_target = best["lane"]

    def _do_move_cup(self) -> None:
        target_x = float(self.cup_target * LANE_WIDTH + LANE_WIDTH // 2)
        dx = target_x - self.cup_x
        if abs(dx) < 0.5:
            return
        move = min(abs(dx), CUP_SPEED)
        self.cup_x += move * (1.0 if dx > 0 else -1.0)
        self.cup_x = max(float(CUP_WIDTH // 2), min(float(SCREEN_WIDTH - CUP_WIDTH // 2), self.cup_x))

    def _move_and_check_ingredients(self) -> None:
        cup_y = float(SCREEN_HEIGHT - 100)
        survived: list[dict[str, Any]] = []

        for ing in self._falling_ingredients:
            ing["y"] += ing["speed"]

            if ing["y"] >= cup_y:
                if abs(ing["x"] - self.cup_x) < 80.0:
                    self.metrics["total_catches"] += 1
                    is_req = ing["type"] in INGREDIENT_TIERS.get(self._tier, {}).get("required", [])
                    self.cup_manager.add_catch(ing["type"], is_required=is_req)
                else:
                    if ing["type"] in INGREDIENT_TIERS.get(self._tier, {}).get("required", []):
                        pass
            else:
                survived.append(ing)

        self._falling_ingredients = survived

    def _update_attention_variance(self) -> None:
        baseline = self._cup_baseline if self._cup_baseline > 0 else 40.0
        offset = self.attention - baseline
        self._attn_offsets.append(offset)

        if len(self._attn_offsets) >= 5:
            mean_val = sum(self._attn_offsets) / len(self._attn_offsets)
            variance = sum((x - mean_val) ** 2 for x in self._attn_offsets) / len(self._attn_offsets)

            if variance < 50:
                ice_prob = 0.2
            elif variance < 150:
                ice_prob = 0.5
            else:
                if self.attention < 20:
                    ice_prob = 1.0
                else:
                    ice_prob = 0.8

            self.ingredient_manager.set_ice_probability(ice_prob)

    def _check_secret_recipe(self, dt: float) -> None:
        if self._secret_popup_timer > 0:
            self._secret_popup_timer -= dt
            return
        if self.cup_manager.secret_recipe_spawned:
            return
        if self.cup_manager.cup_ended:
            return

        threshold = self._cup_baseline + 10
        if self.attention > threshold:
            self.focus_above_seconds += dt
        else:
            self.focus_above_seconds = 0.0

        if self.focus_above_seconds >= SECRET_RECIPE_SUSTAIN:
            if self.cup_manager.trigger_secret_recipe():
                self._secret_popup_timer = 2.0
                self.focus_above_seconds = 0.0
                self.metrics["secrets"] += 1

    def _check_artifact(self, dt: float) -> None:
        if self._artifact_frozen:
            return

        gx_raw, gy_raw, gz_raw = self.gyro.get_frame(self._frame_idx)
        gx = abs(gx_raw - self._prev_gyro[0])
        gy = abs(gy_raw - self._prev_gyro[1])
        gz = abs(gz_raw - self._prev_gyro[2])
        self._prev_gyro = (gx_raw, gy_raw, gz_raw)

        is_still = gx < ARTIFACT_STILL_THRESHOLD and gy < ARTIFACT_STILL_THRESHOLD and gz < ARTIFACT_STILL_THRESHOLD

        if is_still and self.attention > ARTIFACT_ATTENTION_THRESHOLD:
            self._gyro_still_timer += dt
        else:
            self._gyro_still_timer = 0.0

        if self._gyro_still_timer >= ARTIFACT_STILL_DURATION:
            self._artifact_frozen = True
            self._artifact_penalty_timer = ARTIFACT_PENALTY_DURATION
            self._gyro_still_timer = 0.0
            self.metrics["artifact_count"] += 1

    def _update_artifact_freeze(self, dt: float) -> None:
        self._artifact_penalty_timer -= dt
        if self._artifact_penalty_timer <= 0.0:
            self._artifact_frozen = False
            self._artifact_penalty_timer = 0.0
            self._prev_gyro = self.gyro.get_frame(self._frame_idx)

    def _update_pause_state(self, dt: float) -> None:
        if self.attention <= WARMUP_LOW_THRESHOLD:
            self._low_attn_seconds += dt
            self._high_attn_seconds = 0.0
        elif self.attention > 15:
            self._high_attn_seconds += dt
            self._low_attn_seconds = 0.0
        else:
            self._low_attn_seconds = 0.0
            self._high_attn_seconds = 0.0

        if not self._paused and self._low_attn_seconds >= WARMUP_FREEZE_TIME:
            self._paused = True
            self.metrics["freeze_count"] += 1
            self._low_attn_seconds = 0.0
            self._high_attn_seconds = 0.0
        elif self._paused and self._high_attn_seconds >= WARMUP_RESUME_TIME:
            self._paused = False
            self._low_attn_seconds = 0.0
            self._high_attn_seconds = 0.0

    def _check_warmup_freeze(self, dt: float) -> None:
        if self.attention <= WARMUP_LOW_THRESHOLD:
            self._warmup_low_timer += dt
            self._warmup_high_timer = 0.0
        elif self.attention > 15:
            self._warmup_high_timer += dt
            self._warmup_low_timer = 0.0
        else:
            self._warmup_low_timer = 0.0
            self._warmup_high_timer = 0.0

        if not self._warmup_paused and self._warmup_low_timer >= WARMUP_FREEZE_TIME:
            self._warmup_paused = True
            self._warmup_low_timer = 0.0
            self._warmup_high_timer = 0.0
        elif self._warmup_paused and self._warmup_high_timer >= WARMUP_RESUME_TIME:
            self._warmup_paused = False
            self._warmup_low_timer = 0.0
            self._warmup_high_timer = 0.0

    def _check_cup_end(self) -> None:
        elapsed = self._sim_time - self._cup_start_time
        cup_ended = elapsed >= self.CUP_DURATION

        if cup_ended:
            self.cup_manager.cup_ended = True
            if self._cup_attn_samples:
                self._cup_baseline = sum(self._cup_attn_samples) / len(self._cup_attn_samples)
            self._cup_attn_samples = []

            cup_money = self.cup_manager.settle_cup()

            if cup_money > 0.0:
                norm = self._normalize_to_range(self.attention)
                coeff = get_attention_coefficient(norm)
                cup_money = int(cup_money * coeff)

            self.metrics["cup_money_list"].append(cup_money)
            self.metrics["revenue"] += cup_money
            if cup_money == 0:
                self.metrics["zero_revenue_cups"] += 1
            self.metrics["cups"] += 1

            self.cup_manager.cup_ended = True
            self._attn_offsets.clear()
            self.focus_above_seconds = 0.0

            cups_per_tier = max(1, self.TOTAL_CUPS // 4)
            new_tier = min(4, (self.cup_manager.cup_number // cups_per_tier) + 1)
            if new_tier != self._tier:
                self._tier = new_tier
                self.ingredient_manager.set_tier(self._tier)
                self.metrics["level"] = self._tier

            if not self.cup_manager.all_cups_done():
                self.cup_manager.start_new_cup()
                self.ingredient_manager.reset_spawn_timer()
                self._last_spawn_time = self._sim_time
                self._cup_start_time = self._sim_time
                self._falling_ingredients.clear()
