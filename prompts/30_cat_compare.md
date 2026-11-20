# 比较与组成类图表规范 (prompts/30_cat_compare.md)

> 适用：《图表词典》第1类：基础比较与组成类可视化
> 与代码的对应：`academic_fig.plots.bar`, `academic_fig.style`, `academic_fig.layout`

---

## 0. 何时用这一篇

用：多类别离散对象之间比较单一指标数值大小、构成占比或排序差异（如各模型基准分数、分类耗时对比）。
不用：若类别过多（>8个）且关注排序差异改用本篇棒棒糖图；若连续变量随时间动态变化改用 30_cat_trend.md 的折线图；若需探究组内连续数值分布与离散度改用 30_cat_dist.md 的箱线图/小提琴图。
边界：柱状图基线（Y轴）严禁截断必须从 0 起始；若微小差异是核心分析点且刻度无法从 0 展示，改用点图、哑铃图或坡度图。

## 1. 成员图型清单

| 图型 | 专用渲染器 | Matplotlib / 推荐 API | 颜色角色 | 唯一必须注意的点 |
|---|---|---|---|---|
| 柱状图 (Bar Chart) | `academic_fig.plots.bar` | `ax.bar(x, y)` | 对照组 `WASH` + `INK` 边框，Ours 用 `BLUE_T` + `BLUE` 边框 | Y 轴严禁截断必须从 0 起始；柱宽固定 0.4~0.6 |
| 分组柱状图 (Grouped Bar) | `academic_fig.plots.grouped_bar` | 多组偏移 `ax.bar(x + offset, y, width)` | 第一组 `BASE`（灰），第二组 `GOOD`（蓝） | 组内必须紧凑对齐，不同组间必须留有 `>= 1` 柱宽空隙 |
| 堆叠柱状图 (Stacked Bar) | `academic_fig.plots.stacked_bar` | 累积 `bottom` 参数 `ax.bar(x, y, bottom=b)` | 自底向上明度渐浅（`BLUE` -> `SLATE` -> `GREY_LIGHT`） | 各分段在图例中的次序必须与柱内自上而下严格同序 |
| 百分比堆叠柱状图 (100% Stacked Bar) | `academic_fig.plots.stacked_bar(normalize=True)` | 归一化后 `bottom` 累加 | 同色系阶梯或对比色配对 | Y 轴上限严格锁定在 100%，并在轴标签标明 `%` |
| 点图 (Dot Plot) | 手写 | `ax.scatter(y, x, s=30)` | 核心类别 `BLUE`，对照类别 `GREY` | 水平布局优先；基线数据对齐使用单行弱虚线连接 |
| 棒棒糖图 (Lollipop Plot) | `academic_fig.plots.lollipop` | `ax.hlines(y, 0, x)` + `ax.scatter(x, y)` | 细线 `GREY`（0.8pt），端点 `BLUE` / `CLAY` | 类别过多（>8个）时优先按数值降序排列 |
| 坡度图 (Slope Chart) | 手写 | 双点连线 `ax.plot([0, 1], [y1, y2])` | 上升组 `BLUE`，下降组 `CLAY`，平稳组 `GREY` | 必须直接在线两端标注类别名与数值，省去图例 |
| 哑铃图 (Dumbbell Plot) | 手写 | `ax.hlines()` 连线 + 左右端点两组散点 | 起点 `GREY`，终点 `BLUE`，连线 `GREY_LIGHT` | 连线宽度固定 1.0pt；明确指示变化方向 |
| 瀑布图 (Waterfall Chart) | 手写 | 步进 `bottom` 计算正负增量柱 | 正向增量 `BLUE`，负向增量 `CLAY`，总计 `INK` | 必须画出相邻柱体顶底相接的水平断点虚线 |
| 帕累托图 (Pareto Chart) | 手写 | 降序柱状图 + `ax.twinx()` 累计百分比折线 | 频数柱 `WASH` + `INK`，累计折线 `CLAY` | 双 Y 轴各自标注量纲；80% 处画水平虚线标定关键因素 |
| 饼图 (Pie Chart) | 手写 | `ax.pie(...)` | 顺时针自大到小排列，最大片用 `BLUE`，其余浅灰灰阶 | 类别严格限制在 `<= 5`；扇区标签放外侧（`labeldistance` 1.05），不压扇区 |
| 环形图 (Donut Chart) | 手写 | `ax.pie(..., wedgeprops=dict(width=0.4, edgecolor='w'))` | 最大片 `BLUE`，其余浅灰灰阶 | 中央必须有总量文字（10pt），且字号小于扇区标签 |
| 华夫图 (Waffle Chart) | 手写 | `ax.add_patch(Rectangle(...))` 铺 10×10 方格 | 已达成 `BLUE_T` + `BLUE` 边框，未达成 `WASH` + `GREY_LIGHT` | 每格代表固定百分比（通常 1%）；格子等大等距、不留白缝 |
| 矩形树图 (Treemap) | 手写 | 递归矩形划分（仅供层次占比） | 大类用 `WASH`/`WASH_COOL`，关键类 `BLUE_T` | 文字必须完全内切于矩形，过小格子隐藏文字仅留图例 |
| 旭日图 (Sunburst Chart) | 手写 | 同心环 `ax.bar(..., width=..., bottom=...)` 后转极坐标 | 同一层级同色相不同明度，`BLUE` 只给关键路径 | 层级不超过 3 层；环间距固定 0.02，角度按占比分割 |

> 「手写」= 库内**没有**专用函数，用 `apply_theme() + paper_fig() + style_axes()` 自己画；不要在库里找 `waffle()` / `sunburst()` / `treemap()` / `pie()` / `dumbbell()` 这类不存在的渲染器。
> 有专用渲染器的只有前四行与棒棒糖图，直接 `academic_fig.plots.<name>(ax, labels, values)` 即可，不要手写坐标。

---

## 2. 本类专属风格塌陷点

1. **3D 柱体与渐变立体光泽**：千万不要生成带有斜面倒角、圆柱立体高光的柱子，一律回归二维扁平（Flat 2D），边框严格固定为 `0.8pt` 墨线。
2. **彩虹糖式多色分柱**：同一种指标的不同类别严禁给每个柱子涂一个高饱和色；统一使用 `WASH` 底色，仅对本文方法（Ours）或核心突破项使用 `BLUE` 强化。
3. **Y 轴基准零点截断**：柱状图的高度代表物理绝对量，截断 Y 轴（如从 90 开始）会人为夸大差异，属于学术制图失范行为；若微小差异是重点，应转为差异增量点图或哑铃图。
4. **柱体间距失调**：柱体过宽导致画面沉重黑压压一片，或过窄导致形如细针；标准柱宽比例应占组距的 `0.5~0.6`。

---

## 3. 通用规范引用

- 色值与语义：严格遵守 `20_palette_typography.md`。
- 坐标轴细框：四边封闭，线宽 `0.8pt`，刻度朝内 `3.5pt`。
- 字号：子图标题 11pt（正常字重），轴标签 10pt，刻度 9pt，图注 8.5pt。
- 极值高亮与标注：突出关键柱体或对比项时，除使用 `BLUE` 高亮外，还可调用 `afg.annotate_point(ax, x, y, "说明", mark=True)`（`mark=True` 绘制实心圆点高亮极值）进行数值或结论指向性标注。

---

## 4. 核心代码骨架（分组对比条形图，<=20 行）

```python
import academic_fig as afg
import numpy as np

afg.apply_theme()
fig, ax = afg.paper_fig("single", nrows=1)

groups = ["Task-A", "Task-B", "Task-C", "Task-D"]
x = np.arange(len(groups)); w = 0.32
base = [78.2, 81.5, 74.0, 83.1]; ours = [88.5, 92.0, 85.4, 91.2]

ax.bar(x - w/2, base, w, label="Baseline", color=afg.palette.WASH, ec=afg.palette.INK, lw=0.8)
ax.bar(x + w/2, ours, w, label="Ours", color=afg.palette.BLUE_T, ec=afg.palette.BLUE, lw=1.0)

ax.set_xticks(x); ax.set_xticklabels(groups); ax.set_ylim(0, 100)
ax.legend(frameon=False, fontsize=9, loc="upper left")
afg.panel(ax, xlabel="基准评估任务", ylabel="准确率 / %", title="多任务性能对比")
afg.footnote(fig, "数据来源：benchmark_summary.csv；Y 轴从 0 起始，蓝色为本文方法。")
afg.save(fig, "out/fig_cat_compare")
```

---

## 5. 自检要点

- [ ] Y 轴是否坚持了从 0 起始无虚假截断？
- [ ] 颜色使用是否保持克制（仅高亮核心组别）？
- [ ] 柱宽与组间距比例是否匀称协调？
