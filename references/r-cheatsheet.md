# R / ggplot2 用户对照表（r-cheatsheet）

如果你平时用 R，把脑子里的 `ggplot2` 语法映射到本框架，基本一一对应——
只是"图层叠加"变成"函数参数"，"主题"变成一次 `apply_theme()`。

---

## 1. 主流程对照

| R / ggplot2 | 本框架 |
|---|---|
| `library(ggplot2)` | `import academic_fig as afg` |
| `theme_set(theme_bw())` | `afg.apply_theme()`（一次，放在建图之前） |
| `ggplot(df, aes(x, y)) + geom_point()` | `afg.plots.scatter(ax, x, y)` |
| `ggsave("fig1.pdf", w=3.35, h=2.4, dpi=300)` | `afg.save(fig, "fig01_x")`（PNG+PDF 双出） |
| `facet_wrap(~g, ncol=3)` | `fig, axes = afg.paper_fig("double", nrows=2, ncols=3)` + 逐面板调渲染器 |
| `labs(title=, x=, y=)` | `afg.panel(ax, title=, xlabel=, ylabel=)` |
| `annotate("text", …)` | `afg.annotate_point(ax, x, y, "…")` |
| `geom_hline(yintercept=)` | `afg.refline(ax, y=…)` |
| `theme(legend.position="bottom")` | `afg.legend(ax, loc="auto")`（自动避数据；要固定位置就 `loc="lower right"`） |
| `caption = "数据来源：…"` | `afg.footnote(fig, "数据来源：…；口径：…")` |

## 2. geom → 渲染器

| geom / 常见包 | 本框架 | 备注 |
|---|---|---|
| `geom_col()` / `geom_bar(stat="identity")` | `plots.bar` | 误差棒用 `errors=`，显著性用 `brackets=` |
| `geom_bar(stat="count")` | `plots.bar`（自己先 `np.bincount`） | 本框架不做统计汇总 |
| `position="dodge"` | `plots.grouped_bar` | 颜色 + 纹理双编码 |
| `position="stack"` / `position="fill"` | `plots.stacked_bar(normalize=True)` | `normalize` 即 `position="fill"` |
| `coord_flip()` | 任意图的 `horizontal=True`（`bar`/`lollipop`） | 不要真的翻转坐标轴 |
| `geom_line()` | `plots.line` | 多序列传 `dict` → 自动线型/marker |
| `geom_step()` | `plots.line(step="steps-post")` | 阶梯图别用折线硬画 |
| `geom_ribbon(aes(ymin, ymax))` | `plots.line(band={名称: (lo, hi)})` | 填充用 `palette.tint()`，不用透明 |
| `geom_area()` | `plots.area` | `stacked=True` / `normalize=True` |
| `geom_point()` | `plots.scatter` | `background=` 背景点云、`highlight=` 强调、`fit=True` 回归线 |
| `stat_smooth(method="lm")` | `plots.scatter(fit=True)` | 自带 R²/n 角标与 95% 带 |
| `geom_boxplot()` | `plots.box` | 组名自动带 `(n=…)` |
| `geom_violin()` | `plots.violin` | `show_points=True` 叠抖动散点 |
| `geom_histogram()` | `plots.hist` | `kde=True` 叠核密度 |
| `geom_tile()` / `pheatmap()` | `plots.heatmap` | `row_zscore=True` 逐行标准化，`kind="div"` 双色阶 |
| `ggcorrplot()` / `corrplot()` | `plots.corr` | 可掩上三角、格内标系数与 n |
| `ggsurvplot()`（survival） | `plots.km` | `risk_table=True` 出风险人数表 |
| `ggalluvial()` / `geom_sankey()` | `plots.sankey` | 纯 matplotlib，不引第三方 |
| `pROC::ggroc()` | `plots.roc` | `curves={名称: (y_true, y_score)}`，AUC 写图例 |
| `PRROC` | `plots.pr` | 不均衡数据优先用这个 |
| `caret::confusionMatrix` 的图 | `plots.confusion` | `normalize="row"` 看召回 |
| `factoextra::fviz_pca_ind()` | `plots.pca` | `biplot=True` 出载荷箭头 |
| `fmsb::radarchart()` | `plots.radar` | 指标 3–8 个，轴序要写进图注 |
| `forestplot` / `metafor::forest()` | `plots.forest` | 合并效应菱形自动画 |
| `EnhancedVolcano` | `plots.volcano` | 只标 top N 基因名 |
| `scale_fill_brewer()` | `afg.palette.cmap_seq/div/disc` | 不用 Brewer 配色 |
| `scale_color_manual(values=…)` | `afg.palette.CATEGORICAL[i]` | 顺序即语义，不要自己配 |

## 3. 三个思维差异（最容易踩）

1. **没有"图层 + 数据框"的魔法**。R 里 `aes(x=col)` 会自动去数据框找列；
   这里要显式传数组（`df["col"].values`）。好处是数据从哪来一眼可见，图注更容易写对。
2. **主题是全局的、一次性的**。`apply_theme()` 设 `rcParams`，之后所有图继承；
   不要在单个图上写 `theme(...)` 式的临时覆盖——那正是"每张图都不一样"的来源。
3. **导出是一等公民**。R 里常先出屏幕再看 `ggsave`；这里 `afg.save()` 同时写
   PNG(300dpi)+PDF，并**写盘后体检**（dpi/宽高比/命名），不合规当场 warning。

## 4. 迁移一段 R 代码的例子

R：

```r
p <- ggplot(df, aes(x = dose, y = response, fill = group)) +
  geom_col(position = position_dodge(0.8), width = 0.7) +
  geom_errorbar(aes(ymin = m - sd, ymax = m + sd), width = 0.12,
                position = position_dodge(0.8)) +
  scale_fill_brewer(palette = "Set2") +
  labs(x = "剂量", y = "响应值（a.u.）") +
  theme_bw()
ggsave("fig2.png", p, width = 3.35, height = 2.4, dpi = 300)
```

本框架：

```python
import matplotlib; matplotlib.use("Agg")
import academic_fig as afg

afg.apply_theme()
fig, ax = afg.paper_fig("single", height=2.4)
afg.plots.grouped_bar(ax, ["对照", "低剂量", "高剂量"],
                      {"方案 A": [41, 49, 60], "方案 B": [38, 44, 52]},
                      errors={"方案 A": [1.6, 2.3, 2.4], "方案 B": [1.4, 1.9, 2.1]},
                      ylabel="响应值（a.u.）", xlabel="剂量")
afg.footnote(fig, "数据来源：示例数据；口径：柱为均值，误差棒为 ± 1 SD（n=12）。")
afg.save(fig, "fig02_dose_response")
```

差别：`fill=group` 变成了"第二个位置参数传 dict"；Brewer 配色不用了；
`theme_bw()` 被 `apply_theme()` 取代；图注必须自己写（这是硬要求，不是可选）。

## 5. 还留在 R 里的部分

本框架只管**出图**，不做统计：混合效应模型、生存分析拟合、多重比较校正、
富集分析都在 R/Python 里算完，把结果（均值、CI、p 值、log2FC）当数组传进来。
这样图与计算解耦：换模型不用重画，改配色不用重算。