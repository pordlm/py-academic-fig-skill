"""图 4：双栏 —— 三分类任务的混淆矩阵 + ROC 曲线（一对其余）并排。

数据为**合成数据**（混淆矩阵行和 = 各类样本数；ROC 分数由固定种子生成），仅用于版式演示。
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
classes = ["类别 A", "类别 B", "类别 C"]

# 行 = 真实类别，行和 = 该类样本数（240 / 260 / 200）
cm = np.array([[198, 30, 12],
               [24, 210, 26],
               [18, 22, 160]], dtype=int)

# 一对其余：每个类别各有自己的「该类 vs 其余」判别分数（三类 OVR 需要三列分数）
rng = np.random.default_rng(11)
counts = [240, 260, 200]
y_true = np.repeat(classes, counts)
roc_curves = {}
for c, mu in zip(classes, [2.8, 2.1, 1.4]):
    mask = y_true == c
    score = rng.normal(0.0, 1.0, y_true.size)
    score[mask] = rng.normal(mu, 1.0, mask.sum())
    roc_curves[f"{c} vs 其余"] = (mask.astype(int), score)

# ---- 作图 -----------------------------------------------------------------
afg.apply_theme()
fig, ax = afg.paper_fig("double", ncols=2, height=2.75)

afg.plots.confusion(ax[0], cm, labels=classes, normalize=False, cbar=False)
afg.panel(ax[0], label="(a)", title="三分类混淆矩阵（计数）", xlabel="预测类别", ylabel="真实类别")

afg.plots.roc(ax[1], curves=roc_curves)
afg.panel(ax[1], label="(b)", title="ROC 曲线（一对其余）", xlabel="假阳性率 FPR", ylabel="真阳性率 TPR")

afg.footnote(fig, "数据来源：合成数据（混淆矩阵行和 = 各类样本数 240 / 260 / 200，总计 700；"
                  "ROC 由固定种子的正态分数生成，一对其余）；口径：混淆矩阵为原始计数、未按行归一化，"
                  "AUC 由渲染器按梯形法计算。")
afg.save(fig, OUT / "fig04_confusion_roc")
print("done")