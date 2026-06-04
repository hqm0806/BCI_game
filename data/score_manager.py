"""
分数和金钱管理系统 - 跟踪玩家得分、金钱，与杯管理器协作
"""

import logging

from config import INGREDIENT_POINTS

logger = logging.getLogger(__name__)


class ScoreManager:
    """
    分数和金钱管理系统

    属性:
        score: 总分，接到食材时累加
        money: 总金钱（由杯管理器结算后同步）
        current_cup_ingredients: 当前杯子已接住的食材列表
        total_money: 整局总金钱
    """

    def __init__(self) -> None:
        self.score: int = 0
        self.money: int = 0
        self.total_money: int = 0
        self.current_cup_ingredients: list[str] = []
        self.has_required: bool = False
        self.required_ingredient: str | None = None
        self.ingredient_points: dict[str, int] = {}

        self.cup_count: int = 0
        self.secret_recipe_count: int = 0
        self.cup_money_history: list[int] = []

    def set_required_ingredient(self, ingredient_type: str) -> None:
        self.required_ingredient = ingredient_type
        self.has_required = False
        self.current_cup_ingredients = []

    def add_ingredient(self, ingredient_type: str, is_required: bool = False) -> int:
        points = INGREDIENT_POINTS.get(ingredient_type, 5)
        self.score += points
        self.current_cup_ingredients.append(ingredient_type)
        self.ingredient_points[ingredient_type] = self.ingredient_points.get(ingredient_type, 0) + points
        if is_required:
            self.has_required = True
            self.money += points
        elif self.has_required:
            self.money += points
        return points

    def add_cup_money(self, amount: int, had_secret: bool = False) -> None:
        self.total_money += amount
        self.money = self.total_money
        self.cup_count += 1
        self.cup_money_history.append(amount)
        if had_secret:
            self.secret_recipe_count += 1

    def reset_cup_ingredients(self) -> None:
        self.current_cup_ingredients = []

    def get_max_cup_money(self) -> int:
        return max(self.cup_money_history) if self.cup_money_history else 0
