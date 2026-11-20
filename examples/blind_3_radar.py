"""图 3：单栏 —— 五个方法 × 8 个指标的综合评分雷达图（目标：一眼看出谁最均衡）。

数据为**合成数据**（0~100 的评分类指标），仅用于版式演示。
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
metrics = ["精度", "召回", "F1", "鲁棒性", "效率", "可解释性", "泛化", "稳定性"]
scores = {
    "本文方法": [88, 85, 87, 82, 79, 76, 84, 86],
    "对比-A": [92, 80, 86, 61, 70, 55, 72, 64],
    "对比-B": [74, 90, 82, 70, 88, 62, 66, 71],
    "对比-C": [81, 77, 79, 84, 64, 80, 60, 78],
    "对比-D": [69, 72, 70, 66, 85, 88, 74, 58],
}

# 均衡度：8 个指标的标准差越小越均衡（写进图例，代替在图上贴数字）
spread = {k: float(np.std(v)) for k, v in scores.items()}
labels = [f"{k} σ{spread[k]:.1f}" for k in scores]

# ---- 作图 -----------------------------------------------------------------
afg.apply_theme()
fig, ax = afg.paper_fig("single", height=4.6, subplot_kw={"projection": "polar"})

afg.plots.radar(ax, metrics, {lab: scores[k] for lab, k in zip(labels, scores)},
                fill=False, rmax=100, tick_labels=False, legend=False)
# 单栏放不下「圆 + 右侧图例」（3 点钟方向的轴标签会被图例压住），
# 改成圆在上、图例横排两列压在圆的上方，轴标签四周都不再被遮。
ax.set_position([0.10, 0.38, 0.80, 0.46])
afg.legend(ax, loc="lower center", bbox_to_anchor=(0.5, 1.16), ncol=2)
afg.footnote(fig, "数据来源：合成数据（0~100 评分类指标，5 方法 × 8 指标）；口径：各轴均为正向指标、"
                  "已在同一 0~100 标尺上归一，轴序按「精度→召回→F1→鲁棒性→效率→可解释性→泛化→稳定性」排列；"
                  "σ 为 8 项得分的标准差，越小越均衡。")
afg.save(fig, OUT / "fig03_radar")
print("done")
