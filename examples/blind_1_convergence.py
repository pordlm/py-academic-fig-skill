"""图 1：双栏左侧 —— 三种算法在 12 个 epoch 上的测试误差收敛曲线（标出各自最小值）。

数据为**合成数据**（指数衰减 + 固定随机种子的小幅扰动后强制单调），仅用于版式演示。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib
matplotlib.use("Agg")

import numpy as np
import academic_fig as afg

OUT = Path(__file__).resolve().parent / "out" / "blind"

# ---- 合成数据 -------------------------------------------------------------
rng = np.random.default_rng(7)
epoch = np.arange(1, 13)
curves = {
    "Ours": 0.030 + 0.90 * np.exp(-0.46 * epoch),
    "Baseline-A": 0.055 + 0.90 * np.exp(-0.30 * epoch),
    "Baseline-B": 0.072 + 0.88 * np.exp(-0.22 * epoch),
}
curves = {k: np.minimum.accumulate(v + rng.normal(0, 0.004, len(epoch))) for k, v in curves.items()}

# ---- 作图 -----------------------------------------------------------------
afg.apply_theme()
fig, ax = afg.paper_fig("single")

styles = {"Ours": dict(color=afg.palette.BLUE, ls="-", lw=1.5, marker="o"),
          "Baseline-A": dict(color=afg.palette.GREY, ls=(0, (4, 2)), lw=1.0, marker="s"),
          "Baseline-B": dict(color=afg.palette.SLATE, ls=(0, (1, 1.5)), lw=1.0, marker="^")}
for name, y in curves.items():
    st = styles[name]
    ax.plot(epoch, y, label=name, ms=4.5, mew=0.9, mfc="white",
            markevery=[0, 3, 6, 9, 11], **st)
    i = int(np.argmin(y))
    ax.plot(epoch[i], y[i], marker=st["marker"], ms=6.5, mfc=st["color"], mec=st["color"], lw=0)
    afg.annotate_point(ax, epoch[i], y[i], f"{y[i]:.3f}", xytext=(6, 4),
                       color=st["color"], fontsize=8.5, mark=False)

ax.set_yscale("log")
ax.set_xlim(0.4, 13.9)
ax.set_ylim(0.022, 1.25)
afg.legend(ax, loc="upper right")
afg.panel(ax, label="(a)", title="三种算法的测试误差收敛", xlabel="训练轮次 Epoch", ylabel="测试误差 MSE")
afg.footnote(fig, "数据来源：合成数据（12 epoch × 3 算法，指数衰减加扰动后强制单调），仅作版式示例；"
                  "纵轴为对数刻度，实心标记为各算法 12 轮内的最小值。")
afg.save(fig, OUT / "fig01_convergence")
print("done")