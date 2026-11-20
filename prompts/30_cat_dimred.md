# 降维与聚类类图表规范 (prompts/30_cat_dimred.md)

> 适用：《图表词典》第7类：高维数据降维、聚类与流形学习
> 与代码的对应：`academic_fig.plots.pca`, `academic_fig.plots.radar`, `academic_fig.style`, `academic_fig.layout`

---

## 0. 何时用这一篇

用：高维特征或隐空间向低维（2D/3D/极坐标）投影聚类结构、主成分方差解释贡献或多维度综合能力雷达（如 PCA、t-SNE、UMAP、多指标雷达图）。
不用：若特征两两之间计算相关系数并逐一呈现改用 30_cat_relation.md 的相关矩阵热图；若展示两连续变量之间的因果回归改用 30_cat_relation.md。
边界：雷达图维度必须控制在 3~8 个之间，严禁跨圈涂覆深重填充；PCA 得分图坐标轴必须以百分比注明所解释的方差贡献率（PC1 与 PC2）。

## 1. 成员图型清单

| 图型 | Matplotlib / 推荐 API | 颜色角色 | 唯一必须注意的点 |
|---|---|---|---|
| PCA 得分图 (Score Plot) | `academic_fig.plots.pca` / `ax.scatter()` | 分组用低饱和主色（`BLUE`, `CLAY`, `MOSS`） | 坐标轴标签必须百分比标注方差解释率（如 `PC1 (42.5%)`） |
| PCA 载荷图 (Loading Plot) | 原点射出箭头向量 `ax.quiver()` / `annotate()` | 变量箭头 `INK`（1.0pt），标签微偏移 | 向量长度对应特征贡献权重，密集特征仅标注贡献最大者 |
| PCA 双标图 (Biplot) | 得分散点 + 载荷向量双层叠加 | 散点浅色（alpha=0.3），载荷向量深色 `INK` | 采用归一化双坐标系，确保散点与向量比例协调可见 |
| 碎石图 (Scree Plot) | 主成分方差解释率柱状图 + 累计折线 | 单方差柱 `WASH` + `INK`，累计折线 `BLUE` | 明确标注“肘部（Elbow）”截断位置及累计解释率阈值 |
| t-SNE / UMAP 投影图 | `ax.scatter(x, y, s=10, alpha=0.6)` | 类别色板 `BLUE`, `CLAY`, `MOSS`, `OCHRE`, `PLUM` | 轴无物理量纲，须隐藏具体刻度值仅保留轴线与原点 |
| 平行坐标图 (Parallel Coord) | 多维折线穿行 `ax.plot([0..p], row)` | 重点类别 `BLUE`（1.2pt），其余 `GREY`（alpha=0.15） | 各特征维度必须做统一极差（Min-Max）或 Z-score 标准化 |
| 雷达图 / 蜘蛛网图 (Radar) | 极坐标系 `plt.subplot(polar=True)` | 多边形轮廓 `BLUE`/`CLAY`（1.2pt），填充 alpha=0.15 | 维度限制在 5~8 个；网格环线设为 `0.6pt` 极细淡灰 |
| 层次聚类树状图 (Dendrogram) | `scipy.cluster.hierarchy.dendrogram` | 聚类支系默认 `INK`，目标簇使用低饱和强调色 | 必须在图注说明距离度量（如欧氏距离）与链接方式 |

---

## 2. 本类专属风格塌陷点

1. **PCA 轴未标注方差解释率**：只写 `PC1` 和 `PC2`，读者完全不知道这两个成分代表了 80% 还是 8% 的信息；必须在括号内写明方差百分比。
2. **t-SNE/UMAP 留存无意义刻度**：对没有绝对物理距离尺度的流形投影保留具体的 `-20, -10, 0, 10` 刻度，误导读者以为数值有距离意义；应清空数值刻度。
3. **高维平行坐标形成大黑刷**：数百条样本折线完全不透明地穿过坐标轴，交织成一堵黑色高墙；必须大幅压低非重点样本的不透明度（`alpha <= 0.15`）。
4. **雷达图多边形重叠遮挡**：多组数据填充了强饱和颜色，导致重叠区变成脏乱的混色；填充透明度必须 `<= 0.2`，或仅保留轮廓线。

---

## 3. 通用规范引用

- 色值与语义：严格遵守 `20_palette_typography.md`。
- 线宽与标记：主成分向量与雷达轮廓 `1.2pt`，散点大小 `s=12~18`。
- 坐标轴细框：常规图四边封闭；极坐标图环线采用极细淡灰。

---

## 4. 核心代码骨架（双主成分得分与置信椭圆图，<=20 行）

```python
import academic_fig as afg
import numpy as np

afg.apply_theme()
fig, ax = afg.paper_fig("single", nrows=1)

np.random.seed(42)
c1 = np.random.multivariate_normal([-1.5, 0], [[1, 0.3], [0.3, 0.8]], 60)
c2 = np.random.multivariate_normal([1.8, 0.5], [[1.2, -0.4], [-0.4, 0.9]], 60)

ax.scatter(c1[:, 0], c1[:, 1], color=afg.palette.SLATE, s=18, alpha=0.6, label="Control Group")
ax.scatter(c2[:, 0], c2[:, 1], color=afg.palette.BLUE, s=18, alpha=0.6, label="Treated Group")

ax.legend(frameon=False, fontsize=9, loc="upper right")
afg.panel(ax, xlabel="第一主成分 PC1 (54.2%)", ylabel="第二主成分 PC2 (21.8%)", title="样本主成分分析投影得分")
afg.footnote(fig, "数据经标准 Z-score 归一化；累计方差贡献率达 76.0%。")
afg.save(fig, "out/fig_cat_dimred")
```

---

## 5. 自检要点

- [ ] PCA 轴标签是否标注了确切的方差解释率百分比？
- [ ] 聚类散点与轮廓线是否使用低饱和分类色板清晰区分？
- [ ] 雷达图与平行坐标图的填充透明度是否适中无遮挡？
