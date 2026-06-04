"""
注意力方差校准工具
连接头环后，先采集30s基线平均专注力μ，再计算30s方差，输出推荐的难度档位阈值
"""

import math
import sys
import time

from bci.data_reader import BCIDataReader


def connect_bci(reader: BCIDataReader) -> bool:
    print("\n正在连接头环...")
    if reader.connect():
        print(f"✓ 已连接到 {reader.server_ip}:{reader.server_port}")
        return True
    print("✗ 连接失败，请确认科创平台已启动且头环已连接")
    return False


def read_attention(reader: BCIDataReader, timeout: float = 0.1) -> int | None:
    result = reader.read_with_timeout()
    if result[0] is not None:
        return result[0]
    return None


def main() -> None:
    reader = BCIDataReader()

    print("=" * 56)
    print("  注意力方差校准工具")
    print("  用于调整 '必接概率（注意力方差调节）' 的阈值")
    print("=" * 56)

    if not connect_bci(reader):
        sys.exit(1)

    # ── 阶段一：采集30秒基线 ──
    print("\n【阶段一】采集 30 秒基线数据")
    print("  请保持正常专注状态，不要刻意发力...")
    print()

    baseline_samples: list[int] = []
    start = time.time()
    last_print = start

    try:
        while time.time() - start < 30.0:
            attn = read_attention(reader)
            if attn is not None:
                baseline_samples.append(attn)

            if time.time() - last_print >= 1.0:
                elapsed = time.time() - start
                bar_len = int(elapsed / 30.0 * 30)
                bar = "█" * bar_len + "░" * (30 - bar_len)
                current = attn if attn is not None else "?"
                print(f"\r  [{bar}] {elapsed:5.1f}s  当前专注力: {current}  ", end="", flush=True)
                last_print = time.time()

            time.sleep(0.05)
    except KeyboardInterrupt:
        print("\n\n用户中断")
        reader.disconnect()
        sys.exit(0)

    if len(baseline_samples) < 30:
        print("\n✗ 基线数据不足，请重试")
        reader.disconnect()
        sys.exit(1)

    mu = sum(baseline_samples) / len(baseline_samples)
    print(f"\n\n  基线采集完成！采集 {len(baseline_samples)} 个样本")
    print(f"  平均专注力 μ = {mu:.1f}")

    # ── 阶段二：计算方差 ──
    print(f"\n【阶段二】采集 30 秒方差数据")
    print(f"  继续正常游戏/专注，计算与基线 μ={mu:.1f} 的偏离方差...")
    print()

    offsets: list[float] = []
    start = time.time()
    last_print = start

    try:
        while time.time() - start < 30.0:
            attn = read_attention(reader)
            if attn is not None:
                offsets.append(float(attn) - mu)

            if time.time() - last_print >= 1.0:
                elapsed = time.time() - start
                bar_len = int(elapsed / 30.0 * 30)
                bar = "█" * bar_len + "░" * (30 - bar_len)
                current_offset = offsets[-1] if offsets else 0.0
                current_attn = attn if attn is not None else "?"
                print(
                    f"\r  [{bar}] {elapsed:5.1f}s  专注力: {current_attn}  offset: {current_offset:+.1f}  ",
                    end="",
                    flush=True,
                )
                last_print = time.time()

            time.sleep(0.05)
    except KeyboardInterrupt:
        print("\n\n用户中断")
        reader.disconnect()
        sys.exit(0)

    reader.disconnect()
    print("")

    if len(offsets) < 30:
        print("✗ 方差数据不足，请重试")
        sys.exit(1)

    n = len(offsets)
    offset_mean = sum(offsets) / n
    variance = sum((x - offset_mean) ** 2 for x in offsets) / n
    std_dev = math.sqrt(variance)

    # ── 判定模式 ──
    if variance < 50:
        mode = "简单模式"
        prob = "70%"
        desc = "注意力非常稳定，建议更多必接食材可用的游戏体验"
        suggestion = "当前阈值 (<50 / 50-150 / >150) 无需调整或可适当收紧"
    elif variance < 150:
        mode = "中等模式"
        prob = "50%"
        desc = "注意力有正常波动"
        suggestion = "当前阈值合适，无需调整"
    else:
        mode = "困难模式"
        prob = "30%"
        desc = "注意力波动较大，建议减少必接食材以降低无效结算"
        suggestion = "可尝试放宽阈值，例如改为 <80 / 80-200 / >200"

    # ── 输出结果 ──
    print()
    print("=" * 56)
    print("  校准结果")
    print("=" * 56)
    print(f"  基线均值 μ        : {mu:.1f}")
    print(f"  样本数量          : {n}")
    print(f"  offset 均值       : {offset_mean:+.2f}")
    print(f"  方差 (variance)   : {variance:.1f}")
    print(f"  标准差 (std)      : {std_dev:.1f}")
    print(f"  ─────────────────")
    print(f"  匹配模式          : {mode}")
    print(f"  推荐必接概率      : {prob}")
    print(f"  说明              : {desc}")
    print(f"  ─────────────────")
    print(f"  阈值调整建议      : {suggestion}")
    print()
    print("  在 config.py / session.py 中修改对应的方差阈值即可。")
    print("=" * 56)


if __name__ == "__main__":
    main()
