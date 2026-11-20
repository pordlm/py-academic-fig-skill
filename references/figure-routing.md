# 选图路由：什么结论配什么图（figure-routing）

**先定结论，再定图型。** 一句「我要画个图」不是需求；「我要让读者看到 A 组比 B 组高
10% 而方差没变大」才是。下面按大类给路由表，每类回答三件事：
这类图**负责说什么**、**用哪个 api**、**什么时候不该用**。

数据图 10 类（`afg.plots`，`python -m academic_fig.cli list` 可见 21 个渲染器），
示意图 5 类（`afg.diagrams`）。

---

## 一、数据图（10 大类 / 21 个渲染器）

### 1. 比较与组成 `compare`

| 结论长什么样 | 用 | 别用 |
|---|---|---|
| "A 比 B 高，C 最高" | `bar` —— 单序列，只强调 1–2 根（`highlight=[i]`），带误差棒与显著性括号 | 类目 > 8 个还画竖柱（换 `lollipop` 或横柱） |
| "三个方案在两批类别上都比" | `grouped_bar` —— 颜色 + 纹理双编码 | 组数 > 5（颜色不够用，改小倍数面板） |
| "组成随时间变了" | `stacked_bar`（`normalize=True` 看占比） | 类别 > 6 还堆叠（最上面一段读不出来） |
| "排序后的排名对比" | `lollipop` —— 比柱图轻，适合 8–20 项 | 只有 2–3 项（柱图更直观） |
| 流程中各环节的量分解 | `sankey`（见 §10） | 想做"累计贡献"（那是瀑布图，未实现） |

```python
afg.plots.bar(ax, ["对照", "低剂量", "高剂量"], [41, 49, 60],
              errors=[1.6, 2.3, 2.4], highlight=[2], brackets=[(0, 2, "*")],
              ylabel="响应值（a.u.）")
```

### 2. 趋势 `trend`

| 结论 | 用 | 别用 |
|---|---|---|
| "随年份上升，本文方法更快" | `line` —— 多序列 + 置信带（`band=`），>3 条自动换线型 | x 是类别而非连续量（用 `bar`/`grouped_bar`） |
| "某事件后水平突变" | `line(step="steps-post")` | 用折线画阶梯（会显示不存在的斜边） |
| "总量随时间的累积构成" | `area`（`stacked=True`） | 序列 > 5（同上，改小倍数） |

`line` 的两条硬规矩：**第 2 条起必须虚线/换 marker**；置信带用
`afg.palette.tint()` 的浅色填充（不要半透明黑）。

### 3. 分布 `distribution`

| 结论 | 用 | 别用 |
|---|---|---|
| "两组形状不同，不只是均值不同" | `violin(show_points=True)` —— 形状 + 抖动散点 + 中位/四分位 | 每组 n < 8（小提琴会画出假的"双峰"） |
| "看中位数与离群点" | `box` —— 须线到 1.5 IQR，组名带 (n=…) | 分布明显双峰（箱线图看不出来） |
| "看形状与偏态，或叠加 KDE" | `hist(kde=True)` | 多组叠加超过 3 组（改 `violin`） |

### 4. 关系 `relation`

| 结论 | 用 | 别用 |
|---|---|---|
| "两者线性相关，R²=0.99" | `scatter(fit=True)` —— 回归线 + 95% 带 + 角标 R²/n | 样本 < 5 还拟合（写"示意"） |
| "分组的点云各自成团" | `scatter(groups=…)` 或 `background=` 背景点云 + `highlight=` | 上万点（改 `hexbin`，未实现，可用 `hist2d` 手写） |
| "多变量之间的相关结构" | `corr(mask_upper=True)` —— 双色 cmap + 格内系数 + n | 变量 > 12（字会挤，改只画下三角 + 字体 8） |

### 5. 统计推断 `inference`

| 结论 | 用 | 别用 |
|---|---|---|
| "5 个研究的效应量一致指向有效，合并后仍显著" | `forest` —— 方块面积 ∝ 权重、虚线为无效线（OR=1 / MD=0）、底部合并菱形 | 只有 1 个研究（直接报点估计 + CI） |

### 6. 机器学习 `ml`

| 结论 | 用 | 别用 |
|---|---|---|
| "A 模型 ROC 更好（AUC 0.96 vs 0.85）" | `roc(curves={...})` —— AUC 写进图例，对角线是随机基线 | 类别极不均衡时只用 ROC（补 `pr`） |
| "正类稀少时看精确率-召回率" | `pr` —— 含 prevalence 基线，AP 写图例 | 均衡数据（与 ROC 重复） |
| "错在哪几类" | `confusion` —— 格内直接标数，`normalize="row"` 看召回 | 类别 > 10（数字挤，改只标错分格） |

### 7. 降维与多维 `dimred`

| 结论 | 用 | 别用 |
|---|---|---|
| "三工况在前两个主成分上分得开" | `pca(groups=…, ellipse=True)` —— 95% 置信椭圆 + 轴标解释方差 | 解释方差 < 40% 还说"分得开"（要说明） |
| "哪些特征主导这两个轴" | `pca(biplot=True, feature_names=[…])` | 特征 > 8（箭头会糊） |
| "多维指标的综合轮廓" | `radar` —— 3–8 个指标，**轴序必须在图注里说明** | 指标 > 8 或需要精确比较（雷达图读不出数值差） |

### 8. 生存分析 `survival`

| 结论 | 用 | 别用 |
|---|---|---|
| "联合方案生存率更高，且风险人数足够" | `km(risk_table=True, risk_times=[…])` —— 阶梯线 + 删失竖线 + 风险人数表 | 不写风险人数（审稿人必问）；两组曲线交叉时别只说"更好" |

### 9. 组学 `omics`

| 结论 | 用 | 别用 |
|---|---|---|
| "这些基因显著上调/下调" | `volcano` —— 阈值线 + 只标 top 几个基因名 | 把 30 个基因名都标上（必定重叠） |
| "样本聚类 / 基因表达模式" | `heatmap(kind="div", row_zscore=True)` —— 逐行 z-score + colorbar | 行内不做标准化就说"上调"（量纲不同不可比） |

### 10. 流程与流向 `flow`

| 结论 | 用 | 别用 |
|---|---|---|
| "生源流向各去向的比例" | `sankey` —— 纯 matplotlib 手绘，不依赖第三方 | 有环/自环（会被拒），或层级 > 2（改成两张图） |

---

## 二、示意图（5 类 / `afg.diagrams`）

示意图的规矩与数据图一致（白纸墨线、低饱和、细框、无阴影），但**内容由你给结构，不由数据算**。
每个渲染器都返回 `ax`（`ax.figure` 可直接交给 `afg.save`），spec 是 dict，也可从 JSON 读
（`examples/data/diagrams/*.json` 是最小样例）。

| 类 | 负责说什么 | 入口 | 典型 spec 关键字段 |
|---|---|---|---|
| **框架与结构** `framework` | "系统分几层、层里有哪些模块、谁喂谁" | `diagrams.architecture(spec, width="double")` | `layers=[{name, modules:[…]}]`、`links`、`highlight` |
| **流程与时序** `process` | "先做什么后做什么、分支在哪、谁负责" | `diagrams.flow(spec)` | `steps`、`branches`、`lanes`（泳道） |
| **场量与响应面** `field` | "两个因素如何共同影响响应，最优区在哪" | `diagrams.field(spec, kind="surface")` | `x/y` 网格、`z` 或 `kind="gaussian"/"surface"`、`contours` |
| **几何与覆盖** `geometry` | "覆盖范围/重叠区/环带关系" | `diagrams.geometry(spec)` | `shapes`、`coverage`、`rings` |
| **门限与权衡** `tradeoff` | "在哪个门限上最优，帕累托前沿长什么样" | `diagrams.gate(spec)` | `points`、`frontier`、`threshold` |

`architecture` 会**先算版式再画**：高度不够会直接抛
`ValueError: architecture(): height=2.00in 装不下内容（至少需要 4.26in）`——
这是特性，不是 bug：与其画出重叠的框，不如让你加高或减层。
`afg.checks.check_box_overflow(ax, strict=False)` / `afg.checks.check_text_hits(ax, strict=False)` 可在画完之后自查：
模块框里的文字是否撑破边框、标签是否压在连线上（strict=True 时直接抛异常，默认 strict=False 返回 issue 列表）。
它们是纯检查，不改像素，可以放心在出图后调用一次。

```python
import json, academic_fig as afg
spec = json.load(open("examples/data/diagrams/arch_layers.json", encoding="utf-8"))
ax = afg.diagrams.architecture(spec, width="double", note="数据来源：自绘；口径：模块仅表层级关系")
afg.save(ax.figure, "fig05_framework")
```

---

## 三、没有专用渲染器时怎么办（覆盖 ~200 种图的真正手段）

`docs/图表词典.md` 列了 14 大类约 200 种图，本框架只给最常用的 26 个（21 数据 + 5 示意）。
**剩下的不是不能画，而是不值得为它写一个渲染器**——用通用原语手写，风格一样成立：

```python
import matplotlib; matplotlib.use("Agg")
import academic_fig as afg

afg.apply_theme()                                  # 1. 主题（白底/无网格/中文字体）
fig, ax = afg.paper_fig("single")                  # 2. 画布（3.35in）
ax.plot(x, y, color=afg.palette.CATEGORICAL[0], lw=1.0)   # 3. 你的画法
afg.style_axes(ax)                                 # 4. 四边框/刻度朝内/字号
afg.panel(ax, label="(a)", title="…", xlabel="…", ylabel="…")
afg.legend(ax, loc="auto")                          # 图例自动避开数据
afg.footnote(fig, "数据来源：…；口径：…")
afg.save(fig, "fig07_custom")
```

这就是「任意 matplotlib 代码经本框架后自动合规」的含义：
`apply_theme` + `style_axes` 两支原语接管了配色/字体/线宽/刻度/图例，
你只需要负责"用哪种几何形状表达结论"。

**没做的图型**（有意留白）：`pareto` / `waterfall` / `ecdf` / `bubble` / `hexbin` / `qq` /
`cicurve` / `learning_curve` / `feature_importance` / `parallel_coords` / `dendrogram` /
`upset` / `venn` / `streamplot` / `quiver` / `contour` / `3d_surface` / `ternary` /
`spectrum` / `nyquist` / `bode` / `iv_curve`。它们都能用上面 10 行手写出来；
其中 `contour`/`quiver`/`streamplot` 直接是 matplotlib 现成函数，套 `style_axes` 即可。
`cli list` 只列真正能跑的，不会把没实现的名字列进去。