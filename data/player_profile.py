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

LEVEL_THRESHOLDS = [0, 35, 100, 300]  # 升级所需累计营业额：L1起始, L2=35, L3=100, L4=300
SAVE_FILE = "player_profile.json"


@dataclass
class PlayerProfile:
    level: int = 1
    cumulative_revenue: int = 0
    total_games: int = 0
    games_history: list[dict] = field(default_factory=list)

    def add_game_result(
        self,
        revenue: int,
        mode: str,
        cups: int,
        secrets: int,
        avg_attention: float,
    ) -> int:
        """记录一局游戏结果，返回新等级（如有升级则返回新等级号，否则返回0）"""
        old_level = self.level

        self.cumulative_revenue += revenue
        self.total_games += 1
        self.games_history.append(
            {
                "mode": mode,
                "revenue": revenue,
                "cups": cups,
                "secrets": secrets,
                "avg_attention": round(avg_attention, 1),
                "date": time.strftime("%Y-%m-%d"),
            }
        )

        self._check_level_up()

        if self.level > old_level:
            return self.level
        return 0

    def _check_level_up(self) -> None:
        for lv in range(4, 0, -1):
            if self.cumulative_revenue >= LEVEL_THRESHOLDS[lv - 1]:
                self.level = lv
                break

    def save(self, path: str | None = None) -> None:
        filepath = path or SAVE_FILE
        data = {
            "level": self.level,
            "cumulative_revenue": self.cumulative_revenue,
            "total_games": self.total_games,
            "games_history": self.games_history[-20:],
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info("存档已保存: 等级%s, 累计收益%s", self.level, self.cumulative_revenue)

    @classmethod
    def load(cls, path: str | None = None) -> PlayerProfile:
        filepath = path or SAVE_FILE
        if os.path.exists(filepath):
            try:
                with open(filepath, encoding="utf-8") as f:
                    data = json.load(f)
                profile = cls(
                    level=data.get("level", 1),
                    cumulative_revenue=data.get("cumulative_revenue", 0),
                    total_games=data.get("total_games", 0),
                    games_history=data.get("games_history", []),
                )
                logger.info("存档已加载: 等级%s, 累计收益%s", profile.level, profile.cumulative_revenue)
                return profile
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning("存档损坏或格式错误: %s，将使用新档", e)
        logger.info("未找到存档，创建新档案")
        return cls()

    def level_up_message(self) -> str | None:
        """返回升级提示文字，未升级返回 None"""
        next_threshold = LEVEL_THRESHOLDS[self.level] if self.level < 4 else None
        if next_threshold is None:
            return "已满级！最高等级 Lv.4"
        remaining = next_threshold - self.cumulative_revenue
        return f"距下一级还需 {remaining} 元营业额"
