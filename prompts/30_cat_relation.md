# 关系与回归类图表规范 (prompts/30_cat_relation.md)

> 适用：《图表词典》第4类：相关性、多元关系与回归分析
> 与代码的对应：`academic_fig.style`, `academic_fig.layout`, `academic_fig.palette`

---

## 0. 何时用这一篇

用：分析两个或多个连续数值变量之间的相关性、线性/非线性依赖关系、聚类聚簇或残差分布（如准确率与参数量、速度与显存）。
不用：若自变量为严格有序的时序或训练轮次改用 30_cat_trend.md 的折线图；若仅需展示属性间的两两相关系数标量矩阵改用相关热力图，分类预测评估改用 30_cat_ml.md。
边界：散点数据重叠严重（严重 Overplotting）时必须降低 alpha 或改用 Hexbin/2D 直方；严禁在无函数因果依赖的多点散布中随意绘制高阶非线性拟合实线。

## 1. 成员图型清单

| 图型 | Matplotlib / 推荐 API | 颜色角色 | 唯一必须注意的点 |
|---|---|---|---|
| 散点图 (Scatter Plot) | `ax.scatter(x, y, s=15, alpha=0.6)` | 默认 `INK`（alpha=0.5），关键聚类用 `BLUE` / `CLAY` | 点数较多时必须设透明度 `alpha`，防止中心重叠成大黑块 |
| 线性与非线性回归 | `ax.scatter()` + `ax.plot(x, y_fit)` | 散点 `GREY`（alpha=0.4），拟合线 `CLAY`（1.5pt） | 必须在图注或角标给出 $R^2$ 与 $p$ 值，以及拟合方程式 |
| 气泡图 (Bubble Chart) | `ax.scatter(x, y, s=sizes, alpha=0.5)` | 类别色选用低饱和色板；气泡边框 `0.6pt` | 面积与数值成正比（`s ∝ r^2`），严禁半径与数值成正比 |
| 二维直方图 (2D Hist) | `ax.hist2d(x, y, bins=30, cmap=...)` | 连续色图 `afg.palette.cmap_seq()` | 附带精简水平/垂直 colorbar，并标明每个小格的频数单位 |
| 六边形蜂窝图 (Hexbin) | `ax.hexbin(x, y, gridsize=30, cmap=...)` | 密度色图 `afg.palette.cmap_seq()` | 点量超 5000 时代替散点图的首选，蜂窝边缘设微细描边 |
| 等高线密度图 (Contour) | `ax.contour(X, Y, Z, levels=6)` | 等高线 `INK`（0.8pt），填色用 `WASH_COOL` 渐变 | 等值线上内嵌数值标注时保持水平或沿切线清晰可见 |
| 相关性矩阵图 (Correlogram) | 矩阵热图或椭圆/圆盘大小编码相关系数 | 离散发散色图 `afg.palette.cmap_div()` | 必须只保留下三角或上三角矩阵，对角线及多余镜像全部省略 |
| 残差图 (Residual Plot) | `ax.scatter(y_pred, res)` + `ax.axhline(0)` | 残差散点 `SLATE`，零基准线 `CLAY`（0.8pt 虚线） | 检查残差是否在 0 轴上下对称均匀无趋势发散 |
| Q-Q 正态分位图 (Q-Q Plot) | 理论分位数 vs 样本分位数散点 + 45度基线 | 散点 `INK`，理论基线 `CLAY`（1.2pt 实线） | 轴范围等比例对称，重点关注两端尾部偏离程度 |

---

## 2. 本类专属风格塌陷点

1. **散点不透明形成漆黑墨块**：成千上万个不透明黑色点打在一起，重叠区完全丧失密度信息，像倒翻的墨水；必须设置 `alpha=0.3~0.5`，或换用 Hexbin 蜂窝图。
2. **气泡图尺寸按半径线性缩放**：把点大小 `s` 直接赋为变量值，导致面积按平方放大，严重夸大视觉差异；面积必须与物理量线性对应。
3. **相关矩阵全量冗余展示**：画一个方方正正的 $N \times N$ 矩阵，对角线全是无意义的 1.0，上下两半完全镜像重复；必须裁掉冗余上三角，仅留单侧三角。
4. **回归线外推过度而不声明**：在没有任何观测数据的极值区间画出长长的实线拟合线；外推部分必须使用虚线并标注外推警告。

---

## 3. 通用规范引用

- 色值与语义：严格遵守 `20_palette_typography.md`。
- 线宽规范：拟合回归线 `1.5pt`，残差零基线 `0.8pt` 虚线。
- 坐标轴细框：四边封闭，刻度朝内 `3.5pt`。

---

## 4. 核心代码骨架（回归散点与残差双联图，<=20 行）

```python
import academic_fig as afg
import numpy as np

afg.apply_theme()
fig, ax = afg.paper_fig("single", nrows=1)

np.random.seed(42)
x = np.linspace(1, 10, 50)
y = 2.4 * x + 5.0 + np.random.normal(0, 2.0, 50)
p = np.polyfit(x, y, 1); y_fit = np.polyval(p, x)

ax.scatter(x, y, color=afg.palette.INK, s=20, alpha=0.5, ec="none", label="Observed")
ax.plot(x, y_fit, color=afg.palette.CLAY, lw=1.5, label="Fit: $y=2.38x+5.12$")

ax.legend(frameon=False, fontsize=9, loc="upper left")
afg.panel(ax, xlabel="自变量特征 X", ylabel="响应测量值 Y", title="特征相关性与线性拟合")
afg.footnote(fig, "决定系数 R² = 0.88，p < 0.001；红棕实线为一阶最小二乘拟合。")
afg.save(fig, "out/fig_cat_relation")
```

---

## 5. 自检要点

- [ ] 密集散点是否配置了透明度或降采样？
- [ ] 回归统计指标（$R^2$、显著性 $p$）是否在图内或图注完整给出？
- [ ] 相关矩阵是否已剔除重复的镜像对称区？
