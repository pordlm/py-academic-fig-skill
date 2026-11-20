# 机器学习与模型评估类图表规范 (prompts/30_cat_ml.md)

> 适用：《图表词典》第6类：机器学习性能评估、诊断与可解释性
> 与代码的对应：`academic_fig.plots.roc`, `academic_fig.plots.confusion`, `academic_fig.style`, `academic_fig.layout`

---

## 0. 何时用这一篇

用：机器学习与深度学习模型的性能评估、判别阈值敏感性分析与分类错误分布（如多模型 ROC/PR 曲线、多类别混淆矩阵、特征重要性）。
不用：若单纯比较各模型在离散测试集上的最终标量指标（如准确率、F1 分数）改用 30_cat_compare.md；若展示高维特征潜空间的降维聚类效果改用 30_cat_dimred.md。
边界：正负样本严重不平衡时严禁只用 ROC-AUC，必须切换或补充 PR 曲线；混淆矩阵必须指明是否按行归一化，深底必须反白显示格内数字。

## 1. 成员图型清单

| 图型 | Matplotlib / 推荐 API | 颜色角色 | 唯一必须注意的点 |
|---|---|---|---|
| ROC 曲线 (ROC Curve) | `academic_fig.plots.roc` / `ax.plot()` | 主模型 `BLUE`（1.5pt），对角偶然线 `GREY`（0.8pt 虚线） | 轴范围锁定 [0, 1]；图例中必须标明 AUC 数值（保留 3 位小数） |
| PR 精度召回曲线 (PR Curve) | `ax.plot(recall, precision)` | 核心模型 `BLUE`，对比模型 `SLATE` | 在图注中给出阳性类样本先验比例作为基线参考水平 |
| 模型校准曲线 (Calibration) | `ax.plot(prob_pred, prob_true)` + 对角线 | 校准曲线 `BLUE`（带点标记），完美校准线 `GREY`（虚线） | 必须同时下挂或内嵌直方图展示预测概率分布（Brier 分数） |
| 混淆矩阵 (Confusion Matrix) | `academic_fig.plots.confusion` / `imshow` | 单色顺序色图 `afg.palette.cmap_seq()` | 每个格子内写明数值与行归一化比例；高对比反色文字 |
| 决策边界图 (Decision Boundary) | `ax.contourf(xx, yy, Z)` + 散点数据 | 区域填充浅色系 `BLUE_T`/`WASH_COOL`，散点 `INK` | 严禁使用饱和红蓝大块涂抹，背景仅用低透明度平滑过渡 |
| 学习/验证曲线 (Learning Curve) | 训练与验证双折线 + CI 阴影带 | 训练集 `GREY`（虚线），验证集 `BLUE`（实线） | 横轴可采用对数尺度，必须同时给出标准差阴影以诊断过拟合 |
| 特征重要性条形图 (Importance) | `ax.barh(y, imp)` 水平降序条形 | Top 特征 `BLUE`，其余常规特征 `WASH` + `INK` 框 | 必须按重要性严格由大到小排序，且仅展示 Top-10~Top-15 |
| 决策曲线分析 (DCA) | 净收益曲线 `ax.plot(thresholds, net_benefit)` | 模型 `BLUE`，全治疗 `GREY`（实线），全不治零基线 | 横轴阈值概率合理截断，明确标注临床获益窗口范围 |

---

## 2. 本类专属风格塌陷点

1. **ROC 对角参考偶然线遗漏**：不画 (0,0) 到 (1,1) 的随机分类基准线，导致无法直观判断模型是否优于随机猜测；必须绘制 `0.8pt` 灰色虚线。
2. **混淆矩阵使用高温多色系**：使用黄绿蓝红这种 Rainbow 色图，导致对角线与非对角线对比度极其混乱；必须收敛为单色顺序（Sequential）灰-蓝过渡色系。
3. **格子文字与背景同色消失**：混淆矩阵中在深色格子里依然使用黑色字体，导致深色单元格数字完全不可见；必须基于格内亮度阈值自动切换黑/白文本。
4. **决策边界过度饱和刺眼**：分类超平面的填充使用纯蓝和纯红强饱和色，整个图面如同警报灯；必须将背景饱和度压制在 10%~20% 内。

---

## 3. 通用规范引用

- 色值与语义：严格遵守 `20_palette_typography.md`。
- 线宽规范：核心模型曲线 `1.5pt`，次要对比曲线 `1.0pt`，对角偶然线 `0.8pt` 虚线。
- 坐标轴细框：四边封闭，刻度朝内 `3.5pt`。

---

## 4. 核心代码骨架（ROC 多模型对比曲线，<=20 行）

```python
import academic_fig as afg
import numpy as np

afg.apply_theme()
fig, ax = afg.paper_fig("single", nrows=1)

fpr = np.linspace(0, 1, 100)
tpr_ours = 1 - (1 - fpr)**2.5
tpr_base = 1 - (1 - fpr)**1.5

ax.plot(fpr, tpr_ours, color=afg.palette.BLUE, lw=1.5, label="Ours (AUC = 0.924)")
ax.plot(fpr, tpr_base, color=afg.palette.SLATE, lw=1.0, label="Baseline (AUC = 0.812)")
ax.plot([0, 1], [0, 1], color=afg.palette.GREY, ls="--", lw=0.8, label="Chance")

ax.set_xlim(-0.02, 1.02); ax.set_ylim(-0.02, 1.02)
ax.legend(frameon=False, fontsize=9, loc="lower right")
afg.panel(ax, xlabel="假阳性率 (FPR)", ylabel="真阳性率 (TPR)", title="多模型分类性能 ROC 曲线")
afg.footnote(fig, "测试集样本总量 N=1,500；灰色虚线为随机猜测基线。")
afg.save(fig, "out/fig_cat_ml")
```

---

## 5. 自检要点

- [ ] ROC 曲线是否包含灰色对角随机基线与明确的 AUC 指标？
- [ ] 混淆矩阵单元格文字是否根据背景明度动态切换黑白？
- [ ] 轴范围是否严格规范在 [0, 1] 闭区间？
