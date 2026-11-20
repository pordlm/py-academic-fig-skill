# 趋势与时间序列类图表规范 (prompts/30_cat_trend.md)

> 适用：《图表词典》第2类：趋势、时序与动态演化
> 与代码的对应：`academic_fig.plots.line`, `academic_fig.style`, `academic_fig.layout`

---

## 0. 何时用这一篇

用：连续变量随时间、步数、轮次、温度等有序自变量的连续演化轨迹或累积趋势（如训练损失曲线、消融迭代历程）。
不用：若只有离散几个类别或测试集单点对比改用 30_cat_compare.md 的柱状图/点图；若仅关注两变量非时间相关性改用 30_cat_relation.md 的散点图。
边界：折线序列原则上不超过 4 条且标记点需稀疏化；当数据点极度密集且无时序关联时切勿连线，改用散点图或热力图。

## 1. 成员图型清单

| 图型 | Matplotlib / 推荐 API | 颜色角色 | 唯一必须注意的点 |
|---|---|---|---|
| 单折线图 (Line Chart) | `ax.plot(x, y)` | 主线 `BLUE`（1.5pt） | 必须配置微小标记 `markersize=3.5`；点位过密时隔点标注 |
| 多折线图 (Multi-line) | 循环 `ax.plot()` | 主线 `BLUE`，对照 `SLATE`/`GREY`（1.0pt） | 曲线严格 `<= 4` 条；线端直接文字标注优先于大图例框 |
| 面积图 (Area Chart) | `ax.fill_between(x, 0, y)` | 底色 `BLUE_T`，顶边 `BLUE`（1.2pt） | 下方填充透明度 `alpha=0.15~0.25`，禁止使用全不透明重色 |
| 堆叠面积图 (Stacked Area) | 累加 `fill_between()` | 阶梯明度 `SLATE` -> `BLUE` -> `WASH_COOL` | 只用于总量守恒指标；各层间画 0.6pt 白色或浅灰微隔离线 |
| 阶梯图 (Step Chart) | `ax.step(x, y, where='mid')` | 状态转换 `BLUE` 或 `INK` | 明确 step 逻辑位置（'pre'、'mid' 还是 'post'）并在图注说明 |
| 带状置信区间图 (Ribbon) | `ax.fill_between(x, y_lo, y_hi)` + `plot` | 均值线 `BLUE`，区间 `BLUE_T`（alpha=0.2） | 置信度（如 95% CI）必须在轴标签或图注中明文声明 |
| 事件时序图 (Event Plot) | `ax.eventplot(positions)` | 事件脉冲 `INK`，预警 `CLAY` | 线段高度一致；多通道时增加通道 Y 轴刻度标签 |
| 甘特图 (Gantt Chart) | 水平条 `ax.barh(y, width, left=start)` | 进行中 `BLUE`，未开始 `WASH`，延期 `CLAY` | 起止时间刻度规整；条块高度适中（0.4~0.5）避免挤压 |

---

## 2. 本类专属风格塌陷点

1. **彩虹毛线团式多线混杂**：同图塞入 6~10 条不同颜色的细线，既没有主次层次，又严重干扰视觉；应收敛为不超过 4 条，或拆分为 Small Multiples（多子图栅格）。
2. **过于密集的重叠 Marker**：在数百个密集时间点上逐点打大圆点，导致折线变成一根长满刺的毛毛虫；点数多时应隐藏 Marker 或使用 `markevery=N` 稀疏采样。
3. **图例框遮挡核心趋势拐点**：把带有白色填充和厚黑边框的图例直接扔在坐标轴中央，恰好压住最关键的极大值或相交点；优先在线条尾端标注文本，或置于空白角落并设置 `frameon=False`。
4. **时间轴刻度标签倾斜拥挤**：日期时间格式写得过长（如 `2026-11-04 12:00:00`）导致标签层叠或 90 度旋转；应简化时间粒度并保持刻度水平排布。

---

## 3. 通用规范引用

- 色值与语义：严格遵守 `20_palette_typography.md`。
- 线宽规范：核心折线 `1.5pt`，次要对比线 `1.0pt`，基准线 `0.8pt` 虚线。
- 坐标轴细框：四边封闭，刻度朝内 `3.5pt`。
- 极值标注：曲线拐点或极值点需做指向性标注。标注极值的标准动作是调用 `afg.annotate_point(ax, x, y, "说明", mark=True)`（`mark=True` 会自动将极值点填实并绘制高亮实心圆点），或通过 `afg.plots.base.annotate_point(ax, x, y, "说明", mark=True)` 调用。

---

## 4. 核心代码骨架（带置信区间折线图，<=20 行）

```python
import academic_fig as afg
import numpy as np

afg.apply_theme()
fig, ax = afg.paper_fig("single", nrows=1)

x = np.linspace(0, 10, 60)
y_mean = np.sin(x) * 10 + 20; y_std = 2.0 + 0.5 * np.cos(x)

ax.plot(x, y_mean, label="Ours (Mean)", color=afg.palette.BLUE, lw=1.5)
ax.fill_between(x, y_mean - y_std, y_mean + y_std, color=afg.palette.BLUE_T, alpha=0.25, label="±1 Std")
ax.axhline(20, color=afg.palette.GREY, ls="--", lw=0.8, label="Baseline")

ax.legend(frameon=False, fontsize=9, loc="upper right")
afg.panel(ax, xlabel="训练轮次 / Epoch", ylabel="收敛指标 / a.u.", title="训练收敛曲线与稳定性")
afg.footnote(fig, "浅蓝带状区域表示 5 次独立实验的 ±1 标准差区间。")
afg.save(fig, "out/fig_cat_trend")
```

---

## 5. 自检要点

- [ ] 折线数量是否控制在 4 条以内？
- [ ] 阴影区间是否使用低饱和底色且设置透明度？
- [ ] 图例或线尾标注是否避开了数据转折拐点？
