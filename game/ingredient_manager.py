"""
食材管理器模块 - 控制食材的生成时机、类型和速度
"""

from __future__ import annotations

import random
import time
from typing import Any

from config import INGREDIENT_SPAWN_INTERVAL, INGREDIENT_TYPES
from game.sprites import Ingredient


class IngredientManager:
    """
    食材生成管理器，负责按间隔生成随机食材

    参数:
        无外部参数，使用 config.py 中的全局配置
    """

    def __init__(self) -> None:
        self.ingredients: list[Any] = []
        self.last_spawn_time = time.time()
        self.spawn_interval = INGREDIENT_SPAWN_INTERVAL / 1000.0
        self.last_type: str | None = None
        self._current_speed: float = -1.0
        self._spawn_random_offset = 0.0
        self._new_spawn_random_offset()

    def _new_spawn_random_offset(self) -> None:
        self._spawn_random_offset = random.uniform(-0.3, 0.3)

    def should_spawn(self) -> bool:
        current_time = time.time()
        if current_time - self.last_spawn_time >= self.spawn_interval + self._spawn_random_offset:
            self.last_spawn_time = current_time
            self._new_spawn_random_offset()
            return True
        return False

    def set_current_speed(self, speed: float) -> None:
        self._current_speed = speed

    def spawn_ingredient(self, required_types: list[str] | None = None) -> Ingredient:
        available_types = [t for t in INGREDIENT_TYPES if t != self.last_type]
        if not available_types:
            available_types = INGREDIENT_TYPES

        ing_type = random.choice(available_types)
        self.last_type = ing_type

        is_required = False
        if required_types and ing_type in required_types:
            is_required = True

        return Ingredient(ing_type, is_required, self._current_speed)

    def spawn_secret_recipe(self) -> Ingredient:
        return Ingredient("秘方", is_required=False, speed=self._current_speed)

    def update(self, required_types: list[str] | None = None) -> Ingredient | None:
        if self.should_spawn():
            return self.spawn_ingredient(required_types)
        return None
