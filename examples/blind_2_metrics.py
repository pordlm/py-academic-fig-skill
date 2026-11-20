"""图 2：双栏右侧 —— 三种方法的最终误差与耗时（两个指标量纲不同，统一折算成相对值）。

数据为**合成数据**，与 blind_1_convergence.py 的收敛曲线同源（取第 12 轮误差）。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib
matplotlib.use("Agg")

import academic_fig as afg

OUT = Path(__file__).resolve().parent / "out" / "blind"

# ---- 合成数据（绝对值） ---------------------------------------------------
methods = ["Ours", "Baseline-A", "Baseline-B"]
err = {"Ours": 0.035, "Baseline-A": 0.081, "Baseline-B": 0.132}
sec = {"Ours": 41.2, "Baseline-A": 58.4, "Baseline-B": 73.1}

# 量纲不同 -> 各自除以 Baseline-A 折成百分比（同一把尺子才能并排比）
rel_err = [err[m] / err["Baseline-A"] * 100 for m in methods]
rel_sec = [sec[m] / sec["Baseline-A"] * 100 for m in methods]

# ---- 作图 -----------------------------------------------------------------
afg.apply_theme()
fig, ax = afg.paper_fig("single")

afg.plots.grouped_bar(ax, methods, {"最终误差": rel_err, "训练耗时": rel_sec}, hatch=True)
afg.refline(ax, 100)
ax.set_ylim(0, 190)
afg.panel(ax, label="(b)", title="最终误差与训练耗时", xlabel="方法", ylabel="相对值（Baseline-A = 100 %）")
afg.footnote(fig, "数据来源：合成数据（与图 a 同源，取第 12 轮误差）；口径：误差 0.035 / 0.081 / 0.132 MSE，"
                  "耗时 41.2 / 58.4 / 73.1 s，各自除以 Baseline-A 折成百分比；虚线为基线 100 %。")
afg.save(fig, OUT / "fig02_metrics")
print("done")