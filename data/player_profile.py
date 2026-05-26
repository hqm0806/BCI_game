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

LEVEL_THRESHOLDS = [0, 80, 250, 600]
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
                    _username=username,
                )
                logger.info("加载账号 [%s]: 等级%s, 累计收益%s", username, profile.level, profile.cumulative_revenue)
                return profile
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning("存档损坏 [%s]: %s", username, e)
        logger.info("新账号 [%s]", username)
        return PlayerProfile(_username=username)

    @staticmethod
    def load(path: str | None = None) -> PlayerProfile:
        return PlayerProfile()

    def set_username(self, username: str) -> None:
        self._username = username

    def save(self) -> None:
        if not self._username:
            return
        path = _profile_path(self._username)
        data = {
            "level": self.level,
            "cumulative_revenue": self.cumulative_revenue,
            "total_games": self.total_games,
            "games_history": self.games_history[-20:],
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
            "duration": round(duration, 1),
            "date": timestamp,
        }
        if focus_samples:
            step = max(1, len(focus_samples) // 100)
            entry["focus_samples"] = focus_samples[::step]
        self.games_history.append(entry)
        self._check_level_up()
        if self.level > old_level:
            return self.level
        return 0

    def _check_level_up(self) -> None:
        for lv in range(4, 0, -1):
            if self.cumulative_revenue >= LEVEL_THRESHOLDS[lv - 1]:
                self.level = lv
                break

    def level_up_message(self) -> str | None:
        next_threshold = LEVEL_THRESHOLDS[self.level] if self.level < 4 else None
        if next_threshold is None:
            return "已满级！最高等级 Lv.4"
        remaining = next_threshold - self.cumulative_revenue
        return f"距下一级还需 {remaining} 元营业额"
