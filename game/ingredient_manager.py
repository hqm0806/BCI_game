"""
食材管理器模块 - 控制食材的生成时机、类型和速度（支持等级系统）
"""

from __future__ import annotations

import random
import time
from typing import Any

from config import INGREDIENT_SPAWN_INTERVAL, INGREDIENT_TIERS
from game.sprites import Ingredient


class IngredientManager:
    """食材生成管理器，按等级选择可用食材和必接食材"""

    def __init__(self, tier: int = 1) -> None:
        self.ingredients: list[Any] = []
        self.last_spawn_time = time.time()
        self.spawn_interval = INGREDIENT_SPAWN_INTERVAL / 1000.0
        self.last_type: str | None = None
        self._current_speed: float = -1.0
        self._spawn_random_offset = 0.0
        self._new_spawn_random_offset()
        self.set_tier(tier)
        self._required_prob = 0.5

    def _new_spawn_random_offset(self) -> None:
        self._spawn_random_offset = random.uniform(-0.3, 0.3)

    def set_tier(self, tier: int) -> None:
        self._tier = max(1, min(4, tier))
        self._available = INGREDIENT_TIERS[self._tier]["available"]
        self._required = INGREDIENT_TIERS[self._tier]["required"]

    def should_spawn(self) -> bool:
        current_time = time.time()
        if current_time - self.last_spawn_time >= self.spawn_interval + self._spawn_random_offset:
            self.last_spawn_time = current_time
            self._new_spawn_random_offset()
            return True
        return False

    def set_current_speed(self, speed: float) -> None:
        self._current_speed = speed

    def set_spawn_interval(self, interval: float) -> None:
        self.spawn_interval = interval

    def reset_spawn_timer(self) -> None:
        self.last_spawn_time = time.time()

    def set_required_probability(self, prob: float) -> None:
        self._required_prob = max(0.0, min(1.0, prob))

    def spawn_ingredient(self, required_types: list[str] | None = None) -> Ingredient:
        types = required_types if required_types else self._available
        available_types = [t for t in types if t != self.last_type]
        if not available_types:
            available_types = list(types)

        ing_type = random.choice(available_types)
        self.last_type = ing_type

        is_required = False
        if ing_type in self._required:
            is_required = random.random() < self._required_prob

        return Ingredient(ing_type, is_required, self._current_speed)

    def spawn_secret_recipe(self) -> Ingredient:
        return Ingredient("秘方", is_required=False, speed=self._current_speed)

    def update(self, required_types: list[str] | None = None) -> Ingredient | None:
        if self.should_spawn():
            return self.spawn_ingredient(required_types)
        return None
