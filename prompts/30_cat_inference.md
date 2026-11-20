# 假设检验与 Meta 分析类图表规范 (prompts/30_cat_inference.md)

> 适用：《图表词典》第5类：假设检验、效应量与 Meta 分析
> 与代码的对应：`academic_fig.style`, `academic_fig.layout`, `academic_fig.palette`

---

## 0. 何时用这一篇

用：展示统计推断结果、假设检验置信区间、多中心/多数据集 Meta 分析合并效应量或回归系数估计值（如森林图、优势比 CI、敏感性分析）。
不用：若仅呈现无统计检验/置信区间的确定性单点数值对比改用 30_cat_compare.md；若展示机器学习模型多折交叉验证 ROC 分布改用 30_cat_ml.md。
边界：森林图必须明确标定零效应线（无效线，加法为 0，比值对数标度为 1）；置信区间断开处必须在图注注明截断原因，严禁隐瞒跨越无效线的统计结论。

## 1. 成员图型清单

| 图型 | Matplotlib / 推荐 API | 颜色角色 | 唯一必须注意的点 |
|---|---|---|---|
| 森林图 (Forest Plot) | 水平 `errorbar()` + 汇总菱形 `Polygon` | 研究点 `INK`，汇总菱形 `BLUE`，无效线 `CLAY`（虚线） | 效应量与 95% CI 必须在右侧以等宽纯数字栏精准对齐打印 |
| 漏斗图 (Funnel Plot) | 散点 + 伪 95% 置信度倒三角边界线 | 散点 `INK`（alpha=0.6），对称边界 `GREY`（0.8pt 虚线） | 纵轴标准误（SE）必须倒序（0 在顶部，越向下 SE 越大） |
| 系数图 (Coefficient Plot) | 水平点估计 + 95% 误差线 + 垂直 0 基线 | 显著项 `BLUE`，不显著项 `GREY`，基线 `INK`（0.8pt 虚线） | 变量按效应量从大到小排序；显著性用实心/空心区分 |
| 毛毛虫图 (Caterpillar Plot) | 随机效应排序后的水平误差线点图 | 跨过零线 `GREY`，显著异于零 `BLUE` | 沿纵轴必须严格单调排序，展示群体异质性与极值单位 |
| 亚组分析图 (Subgroup Plot) | 分组森林图，带缩进类别层级 | 各组内研究 `INK`，组汇总 `SLATE`，总效应 `BLUE` | 亚组标题左对齐不带标记，数据行缩进两个空格 |
| 敏感性分析图 (Sensitivity) | 逐一剔除研究后的效应量变动折线/点图 | 原始总效应 `CLAY`（基线），剔除点 `BLUE` | 明确标注被剔除的研究名称，观察总体估计是否稳健 |

---

## 2. 本类专属风格塌陷点

1. **无效假说零线缺失或不显著**：在森林图或系数图中，无效假设基线（差值为 0，比值 RR/OR 为 1）画得像普通网格线甚至遗漏，导致读者无法一眼看清统计显著性；必须绘制明显的 `0.8pt` 虚线。
2. **漏斗图纵轴未倒置**：漏斗图的标准误轴从下往上递增，导致漏斗尖朝下，严重违反流行病学读图公约；纵轴顶部必须对应最小标准误（最大精度）。
3. **右侧数字表格未对齐**：研究名称、样本量、权重、OR (95% CI) 用比例字体混排，小数点错位扭曲；必须使用等宽对齐或拆分子子图对齐。
4. **效应量度量单位未取对数**：比值比（OR/RR）在自然尺度下左右不对称（0~1 压缩，1~$\infty$ 膨胀）；必须在对数尺度（Log scale）上对称排布置信区间。

---

## 3. 通用规范引用

- 色值与语义：严格遵守 `20_palette_typography.md`。
- 线宽与标记：无效基线 `0.8pt` 虚线，区间误差线 `1.0pt` 实线，汇总菱形填充 `BLUE`。
- 字号：文本行采用 9pt，数据数字必须整齐垂直对齐。

---

## 4. 核心代码骨架（医学 Meta 分析森林图，<=20 行）

```python
import academic_fig as afg
import numpy as np

afg.apply_theme()
fig, ax = afg.paper_fig("single", nrows=1)

studies = ["Smith et al. (2020)", "Zhang et al. (2021)", "Müller et al. (2023)", "Summary (RE Model)"]
y = np.arange(len(studies))[::-1]
mean = np.array([1.24, 0.85, 1.42, 1.18]); ci_lo = np.array([0.95, 0.62, 1.10, 1.02]); ci_hi = np.array([1.62, 1.15, 1.84, 1.36])

for i in range(len(studies)-1):
    ax.errorbar(mean[i], y[i], xerr=[[mean[i]-ci_lo[i]], [ci_hi[i]-mean[i]]], fmt='s', color=afg.palette.INK, ecolor=afg.palette.INK, elinewidth=1.0, capsize=2.5, markersize=5)

ax.plot([ci_lo[-1], mean[-1], ci_hi[-1], mean[-1], ci_lo[-1]], [y[-1], y[-1]+0.2, y[-1], y[-1]-0.2, y[-1]], color=afg.palette.BLUE, lw=1.2)
ax.axvline(1.0, color=afg.palette.CLAY, ls="--", lw=0.8)

ax.set_yticks(y); ax.set_yticklabels(studies); ax.set_xlim(0.4, 2.2)
afg.panel(ax, xlabel="比值比 (Odds Ratio, 95% CI)", title="多中心临床疗效 Meta 分析")
afg.footnote(fig, "垂直红棕虚线表示无效假设 OR=1.0；蓝色菱形为随机效应模型汇总值。")
afg.save(fig, "out/fig_cat_inference")
```

---

## 5. 自检要点

- [ ] 无效线（0 或 1）是否清晰标定且线型为虚线？
- [ ] 汇总菱形（Summary diamond）的宽度与中心是否精确对应 CI 与点估计？
- [ ] 纵坐标研究名称与文字是否左对齐无错乱？
