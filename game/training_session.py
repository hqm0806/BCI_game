"""训练计划执行引擎 — 复用实验模式，仅自定义阶段时长"""

from __future__ import annotations

from data.training_plan import TrainingPlan


def run_training(
    screen, clock, plan: TrainingPlan, username: str,
    profile=None, control_mode: str = "bci", audio=None, context=None,
) -> str:
    session_num = plan.completed_sessions + 1
    if session_num > plan.total_sessions:
        return "complete"

    from game.experiment_mode import ExperimentSession

    mode_map = {"infinite": "warmup", "bci": "formal", "memory": "memory"}
    phase_durations = {}
    for p in plan.phases:
        key = mode_map.get(p["mode"], p["mode"])
        phase_durations[key] = p["duration"]

    exp = ExperimentSession(
        screen, clock,
        profile=profile,
        control_mode=control_mode,
        audio=audio,
        phase_durations=phase_durations,
        context=context,
    )
    result = exp.run()

    if result == "save" and profile:
        profile.save()
    plan.save_progress(session_num, 0)
    return result
