"""训练计划数据模型 — 多阶段 × 多轮次个性化训练方案"""

from __future__ import annotations

import json
import os
import sys

DEFAULT_PLAN = {
    "phases": [
        {"mode": "infinite", "name": "热身阶段", "duration": 180},
        {"mode": "bci", "name": "特调阶段", "duration": 420},
        {"mode": "memory", "name": "忆调阶段", "duration": 300},
    ],
    "total_sessions": 16,
    "completed_sessions": 0,
    "current_phase": 0,
}

PLAN_FILE = "training_plan.json"


def _get_plan_path() -> str:
    if getattr(sys, "frozen", False):
        return os.path.join(os.path.dirname(sys.executable), PLAN_FILE)
    return PLAN_FILE


def load_all_plans() -> dict:
    path = _get_plan_path()
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_all_plans(plans: dict) -> None:
    path = _get_plan_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(plans, f, indent=2, ensure_ascii=False)


class TrainingPlan:
    def __init__(self, username: str, data: dict | None = None) -> None:
        self.username = username
        d = data or DEFAULT_PLAN
        self.phases: list[dict] = d.get("phases", DEFAULT_PLAN["phases"])
        self.total_sessions: int = d.get("total_sessions", DEFAULT_PLAN["total_sessions"])
        self.completed_sessions: int = d.get("completed_sessions", 0)
        self.current_phase: int = d.get("current_phase", 0)

    @classmethod
    def load_for_user(cls, username: str) -> TrainingPlan:
        all_plans = load_all_plans()
        data = all_plans.get(username)
        return cls(username, data)

    def save(self) -> None:
        all_plans = load_all_plans()
        all_plans[self.username] = {
            "phases": self.phases,
            "total_sessions": self.total_sessions,
            "completed_sessions": self.completed_sessions,
            "current_phase": self.current_phase,
        }
        save_all_plans(all_plans)

    def save_progress(self, session: int, phase: int) -> None:
        self.completed_sessions = session
        self.current_phase = phase
        self.save()

    def is_complete(self) -> bool:
        return self.completed_sessions >= self.total_sessions

    @property
    def total_minutes(self) -> float:
        t = sum(p.get("duration", 0) for p in self.phases) * self.total_sessions
        return t / 60.0

    @property
    def progress_str(self) -> str:
        s = self.completed_sessions + (1 if self.current_phase > 0 else 0)
        return f"{min(s, self.total_sessions)}/{self.total_sessions}"

    def reset_progress(self) -> None:
        self.completed_sessions = 0
        self.current_phase = 0
        self.save()
