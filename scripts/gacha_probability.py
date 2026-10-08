"""抽卡概率统计验证：对 draw_once 抽 10000 次，做卡方拟合优度检验 + SSR 95% 置信区间。

用法：python scripts/gacha_probability.py [seed]

统计口径（显著性水平 α=0.05）：
- 卡方拟合优度：SSR/SR/R 实际频数 vs 设定概率（3%/15%/82%），自由度 df=2，临界值 5.991。
- SSR 单概率 Wilson 95% 置信区间：检验理论 SSR 概率 0.03 是否落在区间内。

注意：α=0.05 意味着「系统没问题但被误判」的概率约 5%（第一类错误）。
单次「未通过」不代表系统坏了，可换 seed 复跑确认；若多次未通过才需排查 draw_once。
"""
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server import config, gacha

N = 10_000
ALPHA = 0.05
Z = 1.96  # 95% 置信水平

# 卡方分布上分位数表（α=0.05）
_CHI2_CRITICAL = {1: 3.841, 2: 5.991, 3: 7.815, 4: 9.488, 5: 11.070}


def chi_square_critical(df: int) -> float:
    return _CHI2_CRITICAL[df]


def wilson_interval(successes: int, n: int, z: float = Z):
    """Wilson score interval，适合低概率比例（SSR=3%）的置信区间。"""
    p = successes / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return center - margin, center + margin


def run(seed=None):
    if seed is not None:
        random.seed(seed)

    counts = {r: 0 for r in config.GACHA_RATES}
    for _ in range(N):
        counts[gacha.draw_once()] += 1

    rates = config.GACHA_RATES
    observed = [counts[r] for r in rates]
    expected = [N * p for p in rates.values()]

    chi2 = sum((o - e) ** 2 / e for o, e in zip(observed, expected))
    df = len(rates) - 1
    critical = chi_square_critical(df)

    ssr_lo, ssr_hi = wilson_interval(counts["SSR"], N)
    ssr_theoretical = rates["SSR"]

    print("=" * 60)
    print(f"抽卡概率验证  （样本 {N} 次，α={ALPHA}）")
    print("=" * 60)
    for i, r in enumerate(rates):
        print(f"{r:>4}  实际 {observed[i]:>5} ({observed[i]/N*100:.2f}%)  期望 {expected[i]:>7.1f}")
    print("-" * 60)
    print(f"卡方统计量 chi2 = {chi2:.3f}（自由度 {df}，临界值 {critical}）")
    chi2_ok = chi2 < critical
    print(f"卡方拟合优度：{'通过（分布符合设定概率）' if chi2_ok else '未通过'}")
    print("-" * 60)
    print(f"SSR 95% 置信区间（Wilson）：[{ssr_lo*100:.2f}%, {ssr_hi*100:.2f}%]")
    print(f"SSR 理论概率：{ssr_theoretical*100:.2f}%")
    ci_ok = ssr_lo <= ssr_theoretical <= ssr_hi
    print(f"置信区间检验：{'通过（理论值落在区间内）' if ci_ok else '未通过'}")
    print("=" * 60)
    return chi2_ok and ci_ok


if __name__ == "__main__":
    # Windows 默认 GBK 控制台无法编码 Unicode（如 χ²），强制 UTF-8 输出避免崩溃/乱码
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else None
    ok = run(seed)
    sys.exit(0 if ok else 1)
