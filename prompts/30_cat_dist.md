# 分布与描述统计类图表规范 (prompts/30_cat_dist.md)

> 适用：《图表词典》第3类：分布、离散度与描述统计
> 与代码的对应：`academic_fig.plots.violin`, `academic_fig.style`, `academic_fig.layout`

---

## 0. 何时用这一篇

用：探究单组或多组连续变量的概率分布形态、集中趋势、离散程度与偏态（如误差分布、潜空间激活值、响应时长）。
不用：若各组仅需对比单一聚合统计量（如均值）改用 30_cat_compare.md 的柱状图/点图；若关注变量之间的二维联合分布或相关性改用 30_cat_relation.md。
边界：样本量很小（N < 20）时严禁使用小提琴图（KDE 会产生虚假连续幻觉），应改用抖动散点图或箱线图；小提琴图必须内嵌中位数或真实数据散点。

## 1. 成员图型清单

| 图型 | Matplotlib / 推荐 API | 颜色角色 | 唯一必须注意的点 |
|---|---|---|---|
| 直方图 (Histogram) | `ax.hist(data, bins=N)` | 填充 `WASH`，边框 `INK`（0.8pt） | 必须明文声明 bin 宽度或区间数量；禁止 3D 立体柱 |
| 核密度估计 (KDE Plot) | 曲线拟合 + `ax.plot()` / `fill_between()` | 曲线 `BLUE`（1.5pt），填充 `BLUE_T`（alpha=0.2） | 带宽参数（bandwidth）敏感，须在图注说明估计方法 |
| 经验累积分布 (ECDF) | 排序后阶梯图 `ax.step(x_sort, y_ecdf)` | 比较组 `BLUE` 与 `GREY` | Y 轴区间严格限制在 [0, 1]；标示出中位数对应分位点 |
| 箱线图 (Boxplot) | `ax.boxplot()` 参数显式控制 | 箱体 `WASH`，中位线 `CLAY`（1.2pt），须 `INK` | 必须在图注说明须线（Whisker）定义（如 1.5 IQR 还是极值） |
| 小提琴图 (Violin Plot) | `academic_fig.plots.violin` / `ax.violinplot` | 主体 `BLUE_T`，轮廓 `BLUE`（0.8pt），内嵌中位点 | 仅在样本量充足（N >= 50）时使用；小样本改用散点抖动 |
| 雨云图 (Raincloud Plot) | 半提琴 (Half-violin) + 抖动散点 + 箱线 | 提琴 `BLUE_T`，散点 `INK`（alpha=0.3, s=8） | 空间自上而下或自左而右排列规整，避免元素遮挡 |
| 条带图 (Strip Plot) | `ax.scatter(x_cat, y, alpha=0.4, s=12)` | 分组色按语义，无强调一律 `INK` | 样本重叠严重时必须添加横向微抖动（Jitter） |
| 蜂群图 (Swarm Plot) | 确定性排斥无重叠散点 | 点集使用低饱和强调色或 `INK` | 样本量过大（>1000）会导致横向扩张爆框，此时改用密度图 |
| 山脊图 (Ridgeline Plot) | 垂直等距多子图或重叠坐标区堆叠 KDE | 梯度过渡（`SLATE` -> `BLUE` -> `WASH_COOL`） | 各条山脊基线垂直间距固定；各层重叠度保持 20%~40% |
| 误差棒图 (Errorbar Plot) | `ax.errorbar(x, y, yerr=e, capsize=3)` | 数据点 `BLUE`，误差须线 `INK`（0.8pt） | 必须且必须在轴标签或图注声明误差含义（SD、SEM 还是 95% CI） |

---

## 2. 本类专属风格塌陷点

1. **误差棒口径未知**：画了上下误差短线，但图上图下没有一个字说明这根棒是标准差（SD）、标准误（SEM）还是置信区间（CI），导致统计学歧义；必须强行在图注或 Y 轴写明。
2. **小样本硬画小提琴图**：在每组仅有 5~10 个样本的数据集上绘制光滑小提琴曲线，产生虚假密度峰值；少样本量时必须使用散点抖动图（Jitter/Dot plot）展示真实数据点。
3. **箱线图异常值（Outlier）盲目放大**：把离群点画成巨大的粗圆圈，严重破坏画面结构；异常点大小应限制为 `s=10~15`，颜色使用半透明 `GREY`。
4. **多组密度山脊严重遮挡**：在紧凑垂直轴上堆叠超过 6 组 KDE 时，未设置合适的透明度或层间距，后方分布峰被前方完全吞没；必须保持基线层次分明。

---

## 3. 通用规范引用

- 色值与语义：严格遵守 `20_palette_typography.md`。
- 线宽与标记：误差棒线宽 `0.8pt`，端点横杠 `capsize=3`；中位线 `1.2pt`。
- 坐标轴细框：四边封闭，刻度朝内 `3.5pt`。

---

## 4. 核心代码骨架（精细小提琴与箱线组合图，<=20 行）

```python
import academic_fig as afg
import numpy as np

afg.apply_theme()
fig, ax = afg.paper_fig("single", nrows=1)

np.random.seed(42)
data = [np.random.normal(loc, 1.2, 80) for loc in [4.5, 6.2, 5.8]]

parts = ax.violinplot(data, positions=[1, 2, 3], showmeans=False, showmedians=False, showextrema=False)
for pc in parts['bodies']:
    pc.set_facecolor(afg.palette.BLUE_T); pc.set_edgecolor(afg.palette.BLUE); pc.set_linewidth(0.8); pc.set_alpha(0.6)

ax.boxplot(data, positions=[1, 2, 3], widths=0.15, patch_artist=True,
           boxprops=dict(facecolor=afg.palette.PAPER, edgecolor=afg.palette.INK, linewidth=0.8),
           medianprops=dict(color=afg.palette.CLAY, linewidth=1.2), whiskerprops=dict(color=afg.palette.INK, linewidth=0.8))

ax.set_xticks([1, 2, 3]); ax.set_xticklabels(["Control", "Treatment-A", "Treatment-B"])
afg.panel(ax, xlabel="实验分组", ylabel="响应强度 / a.u.", title="不同处理下的响应分布")
afg.footnote(fig, "浅蓝提琴展示核密度分布；内嵌箱线中位线为红棕色，须线覆盖 1.5 IQR；N=80。")
afg.save(fig, "out/fig_cat_dist")
```

---

## 5. 自检要点

- [ ] 误差棒与箱线图的统计学口径（SD/SEM/CI/IQR）是否已在图注写明？
- [ ] 样本量是否与所选分布图型匹配（避免小样本套用 KDE 提琴）？
- [ ] 中位线与离群点视觉权重是否主次分明？
