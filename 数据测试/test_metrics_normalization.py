"""
3.2.1 注意力基线归一化算法准确性测试
测试指标：上/下界标准差、归一化误差分布、边界钳位正确性
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

from test_helpers import AttentionGenerator

PLAYER_TYPES = {
    "高专注型": "stable_high",
    "中等型": "medium",
    "低专注型": "low_fluctuating",
}
TRIALS = 20
WARMUP_SECONDS = 180
FPS = 60
LAST_30S_FRAMES = 30 * FPS


def compute_normalization(attn_sequence: np.ndarray) -> tuple[float, float]:
    last_30s = attn_sequence[-LAST_30S_FRAMES:]
    max_attn = float(np.max(last_30s))
    avg_attn = float(np.mean(last_30s))
    upper = min(max_attn, 100.0)
    lower = max(avg_attn - 15.0, 0.0)
    if upper - lower < 10.0:
        mid = (upper + lower) / 2.0
        lower = max(mid - 5.0, 0.0)
        upper = min(mid + 5.0, 100.0)
    return lower, upper


def normalize_value(attn: float, lower: float, upper: float) -> float:
    if upper - lower < 1.0:
        return 50.0
    norm = (attn - lower) / (upper - lower) * 99.0 + 1.0
    return max(1.0, min(100.0, norm))


def run():
    print("=" * 65)
    print("3.2.1 注意力基线归一化算法准确性测试")
    print("=" * 65)

    all_results = {}

    for pname, ptype in PLAYER_TYPES.items():
        upper_list = []
        lower_list = []
        errors_pct = []
        pct_in_range_list = []
        clamp_low_pcts = []
        clamp_high_pcts = []
        clamp_low_count = 0
        clamp_high_count = 0
        total_checks = 0

        for trial in range(TRIALS):
            gen = AttentionGenerator(ptype, seed=trial * 100 + 42)
            attn = gen.generate(WARMUP_SECONDS, FPS)

            lower, upper = compute_normalization(attn)
            upper_list.append(upper)
            lower_list.append(lower)

            last_30s = attn[-LAST_30S_FRAMES:]
            in_range_count = 0
            clamp_low_last = 0
            clamp_high_last = 0
            for a_val in last_30s:
                if a_val < lower:
                    clamp_low_last += 1
                elif a_val > upper:
                    clamp_high_last += 1
                else:
                    norm = normalize_value(a_val, lower, upper)
                    expected = (a_val - lower) / max(upper - lower, 1.0) * 99.0 + 1.0
                    error = abs(norm - expected) / 99.0 * 100.0
                    errors_pct.append(error)
                    in_range_count += 1

            pct_in_range = in_range_count / max(len(last_30s), 1) * 100.0
            pct_in_range_list.append(pct_in_range)
            clamp_low_last_pct = clamp_low_last / max(len(last_30s), 1) * 100.0
            clamp_high_last_pct = clamp_high_last / max(len(last_30s), 1) * 100.0
            clamp_low_pcts.append(clamp_low_last_pct)
            clamp_high_pcts.append(clamp_high_last_pct)

            for a_val in attn:
                total_checks += 1
                if a_val < lower:
                    clamp_low_count += 1
                if a_val > upper:
                    clamp_high_count += 1

        upper_std = float(np.std(upper_list))
        lower_std = float(np.std(lower_list))
        mean_error = float(np.mean(errors_pct)) if errors_pct else 0.0
        pct_under_2 = 100.0 if not errors_pct else float(np.mean(np.array(errors_pct) < 2.0)) * 100.0
        mean_in_range = float(np.mean(pct_in_range_list))
        mean_clamp_low = float(np.mean(clamp_low_pcts))
        mean_clamp_high = float(np.mean(clamp_high_pcts))

        all_results[pname] = {
            "upper_std": upper_std,
            "lower_std": lower_std,
            "mean_error": mean_error,
            "pct_under_2": pct_under_2,
            "pct_in_range": mean_in_range,
            "clamp_low_pct": mean_clamp_low,
            "clamp_high_pct": mean_clamp_high,
            "errors": errors_pct,
            "upper_mean": float(np.mean(upper_list)),
            "lower_mean": float(np.mean(lower_list)),
        }

    print()
    print(f"{'指标':<22} {'高专注型':>10} {'中等型':>10} {'低专注型':>10}")
    print("-" * 55)
    for key, label in [
        ("upper_std", "上界标准差"),
        ("lower_std", "下界标准差"),
        ("upper_mean", "上界均值"),
        ("lower_mean", "下界均值"),
        ("pct_in_range", "区间内样本比例(%)"),
        ("mean_error", "区间内归一化误差(%)"),
        ("pct_under_2", "误差<2%比例(%)"),
        ("clamp_low_pct", "下界钳位率(%)"),
        ("clamp_high_pct", "上界钳位率(%)"),
    ]:
        vals = [f"{all_results[p][key]:.2f}" if "pct" not in key and "error" not in key
                else f"{all_results[p][key]:.1f}" for p in PLAYER_TYPES]
        print(f"{label:<22} {vals[0]:>10} {vals[1]:>10} {vals[2]:>10}")

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))
    fig.suptitle("归一化误差分布 (3类用户 × 20次试验)", fontsize=13, fontweight="bold")

    for ax, (pname, data) in zip(axes, all_results.items()):
        errors = data["errors"]
        ax.hist(errors, bins=60, range=(0, 5), color="#4A90D9", edgecolor="white", alpha=0.85)
        ax.axvline(x=2.0, color="red", linestyle="--", linewidth=1.2, label="2% 误差线")
        ax.set_title(pname, fontsize=12)
        ax.set_xlabel("归一化误差 (%)")
        ax.set_ylabel("频次")
        ax.legend(fontsize=8)
        mean_e = data["mean_error"]
        pct = data["pct_under_2"]
        ax.text(0.95, 0.92, f"均值={mean_e:.1f}%\n<2%={pct:.1f}%",
                transform=ax.transAxes, ha="right", va="top",
                fontsize=9, bbox=dict(boxstyle="round,pad=0.3", facecolor="wheat", alpha=0.7))

    plt.tight_layout()
    out_dir = os.path.dirname(os.path.abspath(__file__))
    out_path = os.path.join(out_dir, "normalization_error.png")
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\n图表已保存: {os.path.abspath(out_path)}")
    print("测试完成。\n")


if __name__ == "__main__":
    run()
