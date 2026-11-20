# 生物信息与组学类图表规范 (prompts/30_cat_omics.md)

> 适用：《图表词典》第10类：生物信息学、高通量测序与系统生物学
> 与代码的对应：`academic_fig.plots.heatmap`, `academic_fig.style`, `academic_fig.layout`, `academic_fig.palette`

---

## 0. 何时用这一篇

用：高通量生物信息学与多组学特征筛选、差异表达分析与高维矩阵表达谱（如火山图筛选显著基因、双向聚类表达热图）。
不用：若仅呈现两三个标量基因在对照与处理组的均值变化改用 30_cat_compare.md 的柱图/带误差散点；若展示不同生化通路的层级流转改用 30_cat_flow.md。
边界：火山图必须以虚线明确标定折叠变化（Log2FC）与统计显著性（-Log10 P-value）门限；聚类热图必须指明是否做逐行 Z-score 归一化。

## 1. 成员图型清单

| 图型 | Matplotlib / 推荐 API | 颜色角色 | 唯一必须注意的点 |
|---|---|---|---|
| 火山图 (Volcano Plot) | `ax.scatter(log2FC, -log10P)` | 上调 `CLAY`，下调 `BLUE`，不显著 `GREY`（alpha=0.4） | 严格绘制 $|\log_2\text{FC}| \ge 1$ 与 $p \le 0.05$ 阈值虚线；Top 基因文字标注 |
| MA 图 (MA Plot) | `ax.scatter(A, M)` | 差异表达基因 `CLAY` / `BLUE`，其余背景 `GREY` | 横轴为表达均值，纵轴为倍数变化；必须标出 $M=0$ 中心基线 |
| 曼哈顿图 (Manhattan Plot) | 按染色体交替排布散点 | 染色体交替用 `SLATE` 与 `GREY`，全基因组显著点 `CLAY` | 必须标明全基因组显著门限（如 $p = 5 \times 10^{-8}$）水平线 |
| 组学 Q-Q 图 (Genomics Q-Q) | 观测 $-\log_{10}(p)$ vs 理论期望 | 常规点 `INK`（alpha=0.5），45 度线 `CLAY`（实线） | 图注给出基因组膨胀因子 $\lambda_{\text{GC}}$ 数值 |
| 聚类热图 (Clustered Heatmap) | `academic_fig.plots.heatmap` + 侧边树状图 | 发散色图 `afg.palette.cmap_div()` | 表达量行标准化（Z-score）；侧边聚类树线宽 `0.8pt` |
| 韦恩图 / UpSet 图 (Venn/UpSet) | 集合交集矩阵点线连接 + 交集规模柱状图 | 集合交集柱 `BLUE`，单集合底色 `WASH` | 集合数 $\ge 4$ 时一律禁止画错乱的椭圆 Venn，必须改用 UpSet 图 |
| 功能富集气泡图 (Enrichment) | 散点大小编码基因数，颜色编码 $p$ 值 | 颜色映射采用连续渐变色图 `cmap_seq()` | 气泡面积与基因数量线性对应；条目名称过长时限制字符截断 |

---

## 2. 本类专属风格塌陷点

1. **4 集合以上硬画大杂乱 Venn 图**：5 个集合交叉画成扭曲的花瓣，交集面积与数量完全无关，文字挤成团；4 集合及以上必须使用 UpSet 矩阵柱状图。
2. **火山图阈值基准线缺失**：散点漫天飞舞却不标定倍数变化（Fold Change）和显著性 $P$ 值的阈值线；必须画出纵向两条和横向一条的浅灰虚线。
3. **曼哈顿图染色体颜色过于斑斓**：给 23 对染色体每一对都指定一个鲜艳的高饱和颜色，像被打碎的调色盘；只允许使用深灰/浅灰或深蓝/浅蓝双色交替。
4. **热图标尺缺失 Z-score 声明**：读者无法得知热图上的数值是原始 Counts、TPM 还是行中心化后的相对量；必须在 colorbar 上方标清单位。

---

## 3. 通用规范引用

- 色值与语义：严格遵守 `20_palette_typography.md`。
- 线宽与标记：阈值虚线 `0.8pt`，散点 `s=10~18`，热图微网格 `0.5pt` 白色隔断。
- 坐标轴细框：四边封闭，刻度朝内 `3.5pt`。

---

## 4. 核心代码骨架（基因差异表达火山图，<=20 行）

```python
import academic_fig as afg
import numpy as np

afg.apply_theme()
fig, ax = afg.paper_fig("single", nrows=1)

np.random.seed(42)
lfc = np.random.normal(0, 1.5, 400); pval = np.random.uniform(0, 6, 400)
sig_up = (lfc >= 1.0) & (pval >= 1.3); sig_dn = (lfc <= -1.0) & (pval >= 1.3); nosig = ~sig_up & ~sig_dn

ax.scatter(lfc[nosig], pval[nosig], color=afg.palette.GREY, s=12, alpha=0.3, label="Not Significant")
ax.scatter(lfc[sig_up], pval[sig_up], color=afg.palette.CLAY, s=16, alpha=0.7, label="Up-regulated")
ax.scatter(lfc[sig_dn], pval[sig_dn], color=afg.palette.BLUE, s=16, alpha=0.7, label="Down-regulated")

ax.axhline(1.3, color=afg.palette.GREY, ls="--", lw=0.8)
ax.axvline(-1.0, color=afg.palette.GREY, ls="--", lw=0.8); ax.axvline(1.0, color=afg.palette.GREY, ls="--", lw=0.8)

ax.legend(frameon=False, fontsize=8.5, loc="upper right")
afg.panel(ax, xlabel="log₂FC（变化倍数）", ylabel="−log₁₀P（显著性）", title="差异表达基因火山图")
afg.footnote(fig, "阈值标准：P < 0.05 且 |log₂FC| ≥ 1.0；红棕为上调，蓝色为下调。")
afg.save(fig, "out/fig_cat_omics")
```

---

## 5. 自检要点

- [ ] 火山图与 MA 图的统计学门限水平/垂直虚线是否完整标定？
- [ ] 集合交集展示是否遵循“≥ 4 个集合强制采用 UpSet”规范？
- [ ] 基因表达矩阵是否有明确的 Z-score 或单位声明？
