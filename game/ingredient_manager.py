"""
食材管理器模块 - 控制食材的生成时机、类型和速度（支持等级系统）
"""

from __future__ import annotations

import random
import time

import pygame

from config import INGREDIENT_SPAWN_INTERVAL, INGREDIENT_TIERS, OUTLET_BLOCK_RADIUS, OUTLET_POSITIONS, SCREEN_HEIGHT
from game.sprites import Ingredient


class IngredientManager:
    """食材生成管理器，按等级选择可用食材和必接食材"""

    def __init__(self, tier: int = 1) -> None:
        self.ingredients: list = []
        self.last_spawn_time = time.time()
        self.spawn_interval = INGREDIENT_SPAWN_INTERVAL / 1000.0
        self.last_type: str | None = None
        self._current_speed: float = -1.0
        self._spawn_random_offset = 0.0
        self._new_spawn_random_offset()
        self.set_tier(tier)
        self._required_prob = 0.2
        self._ice_probability = 0.0

    def _new_spawn_random_offset(self) -> None:
        self._spawn_random_offset = random.uniform(-0.3, 0.3)

    def set_tier(self, tier: int) -> None:
        self._tier = max(1, min(4, tier))
        self._available = INGREDIENT_TIERS[self._tier]["available"]
        self._required = INGREDIENT_TIERS[self._tier]["required"]

    def should_spawn(self) -> bool:
        current_time = time.time()
        return current_time - self.last_spawn_time >= self.spawn_interval + self._spawn_random_offset

    def _on_spawned(self) -> None:
        self.last_spawn_time = time.time()
        self._new_spawn_random_offset()

    def set_current_speed(self, speed: float) -> None:
        self._current_speed = speed

    def set_spawn_interval(self, interval: float) -> None:
        self.spawn_interval = interval

    def reset_spawn_timer(self) -> None:
        self.last_spawn_time = time.time()

    def set_required_probability(self, prob: float) -> None:
        self._required_prob = max(0.0, min(1.0, prob))

    def set_ice_probability(self, prob: float) -> None:
        self._ice_probability = max(0.0, min(1.0, prob))

    def spawn_ingredient(
        self,
        required_types: list[str] | None = None,
        allowed_outlets: list[int] | None = None,
    ) -> Ingredient:
        if required_types:
            types = required_types
            available_types = [t for t in types if t != self.last_type]
            if not available_types:
                available_types = list(types)
            ing_type = random.choice(available_types)
            is_required = ing_type in self._required
        else:
            is_required = random.random() < self._required_prob

            if is_required:
                pick_from = [t for t in self._required if t != self.last_type]
                if not pick_from:
                    pick_from = list(self._required)
                ing_type = random.choice(pick_from)
            else:
                optional = [t for t in self._available if t != self.last_type and t not in self._required]
                if not optional:
                    optional = [t for t in self._available if t != self.last_type]
                if not optional:
                    optional = list(self._available)
                ing_type = random.choice(optional)

        self.last_type = ing_type

        if self._ice_probability > 0 and random.random() < self._ice_probability:
            ing_type = "冰块"
            is_required = False

        return Ingredient(ing_type, is_required, self._current_speed, allowed_lanes=allowed_outlets)

    def spawn_secret_recipe(self, allowed_outlets: list[int] | None = None) -> Ingredient:
        return Ingredient("秘方", is_required=False, speed=self._current_speed, allowed_lanes=allowed_outlets)

    def update(
        self,
        required_types: list[str] | None = None,
        ingredients_group: pygame.sprite.Group | None = None,
    ) -> Ingredient | None:
        if self.should_spawn():
            allowed = self._free_outlets(ingredients_group) if ingredients_group else None
            if allowed is None or allowed:
                ingredient = self.spawn_ingredient(required_types, allowed)
                self._on_spawned()
                return ingredient
        return None

    @staticmethod
    def _free_outlets(ingredients_group: pygame.sprite.Group) -> list[int]:
        occupied = set()
        for ing in ingredients_group:
            if ing.rect.y < SCREEN_HEIGHT * 0.35:
                for i, (ox, oy) in enumerate(OUTLET_POSITIONS):
                    dx = ing.rect.centerx - ox
                    dy = ing.rect.centery - oy
                    if dx * dx + dy * dy < OUTLET_BLOCK_RADIUS * OUTLET_BLOCK_RADIUS:
                        occupied.add(i)
        return [i for i in range(len(OUTLET_POSITIONS)) if i not in occupied]
