"""图 5：双栏单张 —— 20×20 网格上每格被覆盖的次数（0~6 次）热力图。

数据为**合成数据**（几个高斯团簇叠加 + 取整裁剪到 0~6），仅用于版式演示。
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

# ---- 合成数据：空间上成团，不是均匀随机 --------------------------------
rng = np.random.default_rng(3)
n = 20
yy, xx = np.mgrid[0:n, 0:n]
field = np.zeros((n, n))
for cy, cx, amp, sd in [(5, 5, 4.6, 3.0), (14, 13, 5.2, 2.4), (6, 15, 2.8, 2.0), (15, 4, 2.2, 2.6)]:
    field += amp * np.exp(-((yy - cy) ** 2 + (xx - cx) ** 2) / (2 * sd ** 2))
field += rng.normal(0, 0.35, (n, n))
grid = np.clip(np.rint(field), 0, 6).astype(int)

# ---- 作图 -----------------------------------------------------------------
afg.apply_theme()
fig, ax = afg.paper_fig("double", height=7.0, margins=(0.12, 0.11, 0.90, 0.93))

afg.plots.heatmap(ax, grid, kind="disc", bins=7, cbar=True, cbar_label="覆盖次数（次）",
                  vmin=0, vmax=6,
                  rows=[str(i + 1) for i in range(n)], cols=[str(i + 1) for i in range(n)],
                  xlabel="网格列号", ylabel="网格行号")
ax.set_aspect("equal")
# 计数是整数，色条刻度也必须是整数（渲染器默认给了 6 等分的连续刻度）
cax = fig.axes[-1]
cax.set_yticks(range(0, 7))
cax.set_yticklabels([str(i) for i in range(0, 7)])
cax.set_ylabel("覆盖次数（次）", fontsize=9, labelpad=8)

# 色条把主轴挤窄后，整块内容偏在画布左侧；把主轴 + 色条一起平移回中线
p_ax, p_cb = ax.get_position(), cax.get_position()
shift = 0.5 - (p_ax.x0 + p_cb.x1) / 2.0
for p in (p_ax, p_cb):
    ax.figure.axes[0 if p is p_ax else -1].set_position([p.x0 + shift, p.y0, p.width, p.height])
afg.panel(ax, label="", title="20 × 20 网格的覆盖次数分布", xlabel="网格列号", ylabel="网格行号")
afg.footnote(fig, "数据来源：合成数据（4 个高斯团簇叠加 + N(0, 0.35) 扰动后取整并裁剪到 0~6，固定种子），"
                  "仅作版式示例；口径：色阶为 0~6 次的 7 档离散分级，格内不标数值，"
                  "聚集区为采样覆盖热点。")
afg.save(fig, OUT / "fig05_coverage_heatmap")
print("done", grid.min(), grid.max(), grid.mean().round(2))