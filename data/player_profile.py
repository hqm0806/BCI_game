"""
玩家档案系统 — 持久化保存游戏等级、累计营业额、游戏历史
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

LEVEL_THRESHOLDS = [0, 150, 400, 1000]
PROFILES_DIR = "profiles"


def _profile_path(username: str) -> str:
    os.makedirs(PROFILES_DIR, exist_ok=True)
    return os.path.join(PROFILES_DIR, f"{username}.json")


@dataclass
class PlayerProfile:
    level: int = 1
    cumulative_revenue: int = 0
    total_games: int = 0
    games_history: list[dict] = field(default_factory=list)
    training_history: list[dict] = field(default_factory=list)
    _username: str = ""

    @staticmethod
    def load_for_user(username: str) -> PlayerProfile:
        path = _profile_path(username)
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                profile = PlayerProfile(
                    level=data.get("level", 1),
                    cumulative_revenue=data.get("cumulative_revenue", 0),
                    total_games=data.get("total_games", 0),
                    games_history=data.get("games_history", []),
                    training_history=data.get("training_history", []),
                    _username=username,
                )
                logger.info("加载账号 [%s]: 等级%s, 累计收益%s", username, profile.level, profile.cumulative_revenue)
                return profile
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning("存档损坏 [%s]: %s", username, e)
        logger.info("新账号 [%s]", username)
        return PlayerProfile(_username=username)

    def save(self) -> None:
        if not self._username:
            return
        path = _profile_path(self._username)
        self._recalculate()
        data = {
            "level": self.level,
            "cumulative_revenue": self.cumulative_revenue,
            "total_games": self.total_games,
            "games_history": self.games_history[-30:],
            "training_history": self.training_history[-30:],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info("存档已保存 [%s]: 等级%s, 累计收益%s", self._username, self.level, self.cumulative_revenue)

    def add_game_result(
        self,
        revenue: int,
        mode: str,
        cups: int,
        secrets: int,
        avg_attention: float,
        duration: float = 0.0,
        focus_samples: list | None = None,
        last_5min_avg_attention: float = 0.0,
    ) -> int:
        old_level = self.level
        self.cumulative_revenue += revenue
        self.total_games += 1
        timestamp = time.strftime("%Y-%m-%d %H:%M")
        entry = {
            "mode": mode,
            "revenue": revenue,
            "cups": cups,
            "secrets": secrets,
            "avg_attention": round(avg_attention, 1),
            "last_5min_avg_attention": round(last_5min_avg_attention, 1),
            "duration": round(duration, 1),
            "date": timestamp,
        }
        if focus_samples:
            step = max(1, len(focus_samples) // 100)
            entry["focus_samples"] = focus_samples[::step]
        self.games_history.append(entry)
        self._check_level_up()
        if self.level > old_level + 1:
            self.level = old_level + 1
        if self.level > old_level:
            return self.level
        return 0

    def add_training_result(
        self,
        total_money: int,
        total_cups: int,
        secret_count: int,
        failed_cup_count: int,
        memory_successes: int,
        memory_failures: int,
        avg_attention: float,
        stage1_avg: float,
        stage2_avg: float,
        stage3_avg: float,
        all_focus_samples: list | None = None,
        stage1_focus: list | None = None,
        stage2_focus: list | None = None,
        stage3_focus: list | None = None,
        duration: float = 0.0,
        stage1_min: int = 0,
        stage2_min: int = 0,
        stage3_min: int = 0,
        rounds: int = 0,
    ) -> None:
        timestamp = time.strftime("%Y-%m-%d %H:%M")
        entry = {
            "mode": "training",
            "total_money": total_money,
            "total_cups": total_cups,
            "secret_count": secret_count,
            "failed_cup_count": failed_cup_count,
            "memory_successes": memory_successes,
            "memory_failures": memory_failures,
            "avg_attention": round(avg_attention, 1),
            "stage1_avg": round(stage1_avg, 1),
            "stage2_avg": round(stage2_avg, 1),
            "stage3_avg": round(stage3_avg, 1),
            "duration": round(duration, 1),
            "stage1_min": stage1_min,
            "stage2_min": stage2_min,
            "stage3_min": stage3_min,
            "rounds": rounds,
            "date": timestamp,
        }
        if all_focus_samples:
            step = max(1, len(all_focus_samples) // 100)
            entry["focus_samples"] = all_focus_samples[::step]
        for key, samples in [("stage1_focus", stage1_focus), ("stage2_focus", stage2_focus), ("stage3_focus", stage3_focus)]:
            if samples:
                step = max(1, len(samples) // 50)
                entry[key] = samples[::step]
        self.training_history.append(entry)

    def remove_game(self, index: int) -> None:
        if 0 <= index < len(self.games_history):
            del self.games_history[index]
            self._recalculate()

    def remove_training(self, index: int) -> None:
        if 0 <= index < len(self.training_history):
            del self.training_history[index]
            self._recalculate()

    def clear_history(self) -> None:
        self.games_history.clear()
        self._recalculate()

    def _recalculate(self) -> None:
        self.total_games = len(self.games_history)
        self.cumulative_revenue = sum(g.get("revenue", g.get("total_money", 0)) for g in self.games_history)
        self._check_level_up()

    def _check_level_up(self) -> None:
        for lv in range(4, 0, -1):
            if self.cumulative_revenue >= LEVEL_THRESHOLDS[lv - 1]:
                self.level = lv
                break
