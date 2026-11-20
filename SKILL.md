---
name: academic-figures
description: 生成中文论文插图（数据图 / 框架图 / 场量图 / 流程图）统一的「简单高级框架风」：白底墨线、低饱和强调色、细框刻度朝内、PNG+PDF 双出。用于画论文图表、复现或改造已有插图、把数据变成可投稿的图、按期刊规格排版多面板图。当用户提到论文配图、论文插图、figure、图表美化、框架图、技术路线图、消融实验图、热力图、雷达图、桑基图、ROC、混淆矩阵、响应面、覆盖图时使用。
whenToUse: 用户要画、改、统一风格化论文/报告的统计图或示意图；需要 matplotlib 出图并交付 PNG(300dpi)+PDF(矢量)；需要中文标注且不能出现方框乱码；需要多面板、期刊尺寸、图注与自检。
metadata:
  version: "0.2.2"
  palette: paper-calm
  entry: academic_fig
---

# 论文插图 skill（简单高级 · 框架风）

把「论文里要一张图」变成**可复现的代码 + 符合风格的产物**：白纸、墨线、克制的低饱和强调色、
充足留白，像框架图，不像数据看板，也不像海报。

---

## 0. 三条铁律（违反任何一条，图就废了）

1. **颜色只用 `academic_fig/palette.py` 里的值。** 不用 matplotlib 默认色、不用 `jet/rainbow/tab10`、
   不用 Excel/seaborn 默认色。一个颜色在全篇只表达一个含义。
2. **信息不能只靠颜色承载。** 颜色之外必须有 marker 形状 / 线型虚实 / 直接标注之一，保证灰度打印仍可读。
3. **不编数据、不改计算。** 图注必须写数据来源与口径；示意量标「示意，非真实值」；判定线标「自设目标，非官方指标」。

---

## 1. 先判断：这是哪一类图

先看**大类**（12 个数据图大类 + 5 个示意图入口），再看具体图型。提示词按大类组织，一篇管一类。

| 用户说的是什么 | 大类 | 入口（`academic_fig`） | 先读的提示词 |
|---|---|---|---|
| 比大小、多组对比、占比构成、瀑布/帕累托 | compare | `plots.bar` / `grouped_bar` / `stacked_bar` / `lollipop` | `prompts/30_cat_compare.md` |
| 误差曲线、收敛、趋势、面积、阶梯 | trend | `plots.line` / `plots.area` | `prompts/30_cat_trend.md` |
| 分布形状、箱线、提琴、直方、误差棒 | distribution | `plots.violin` / `box` / `hist` | `prompts/30_cat_dist.md` |
| 散点、相关、回归、密度、等高线 | relation | `plots.scatter` / `plots.corr` | `prompts/30_cat_relation.md` |
| 森林图、漏斗图、效应量、系数 | inference | `plots.forest` | `prompts/30_cat_inference.md` |
| ROC、PR、混淆矩阵、学习曲线、特征重要性 | ml | `plots.roc` / `pr` / `confusion` | `prompts/30_cat_ml.md` |
| 降维、聚类、PCA、t-SNE、雷达、平行坐标 | dimred | `plots.pca` / `plots.radar` | `prompts/30_cat_dimred.md` |
| 生存曲线、KM、风险人数、Swimmer | clinical | `plots.km` | `prompts/30_cat_clinical.md` |
| 火山、热图、聚类热图、Venn、富集 | omics | `plots.volcano` / `plots.heatmap` | `prompts/30_cat_omics.md` |
| 流程图、框架图、桑基、网络、DAG | flow | `diagrams.architecture` / `flow` / `plots.sankey` | `prompts/30_cat_flow.md` |
| 地图、空间分布、场量、3D 曲面、quiver | spatial | `diagrams.field` / `geometry` | `prompts/30_cat_spatial.md` |
| 谱图、XRD、I–V、Nyquist、Bode、应力应变 | physics | 通用原语手写（见下节） | `prompts/30_cat_physics.md` |
| **本类未覆盖的图型**（如三元图、Circos、UMAP、Nomogram） | 任意 | 通用原语手写（见本节末），不硬套渲染器 | 该大类提示词 |

示意图另有 5 个专用入口，参数是**纯 dict / JSON 规格**（不用手摆坐标）：

| 图 | 入口 | 提示词 |
|---|---|---|
| 分层方法框架、模块关系 | `diagrams.architecture(spec)` | `prompts/40_diagram_architecture.md` |
| 流程、判定、分支、回流 | `diagrams.flow(spec)` | `prompts/40_diagram_flow.md` |
| 响应面、等高线、场量 | `diagrams.field(spec, kind=…)` | `prompts/40_diagram_field.md` |
| 覆盖范围、可达性、几何 | `diagrams.geometry(spec)` | `prompts/40_diagram_geometry.md` |
| 阈值扫描、帕累托、鲁棒性 | `diagrams.gate(spec, kind=…)` | `prompts/40_diagram_gate.md` |
| **本节未覆盖的示意图**（泳道时序、状态机、鱼骨图） | 任意 | 通用原语手写或换 `diagrams.flow` + 自定义 `route` | `prompts/40_diagram_flow.md` |

五类的 **spec 字段表**（键名、示例值类型、默认值）由代码自动生成：`references/diagram-spec-fields.md`
（改渲染器后跑 `python scripts/diagram_fields.py --write` 同步，`--check` 可验一致性）。
**spec 里写错键名会直接抛 `ValueError` 并给拼写建议**——不再静默画空图。

**词典里还有约 180 种图没有专用函数**（谱图、三元图、Circos、UMAP、Nomogram…）。这不是不支持，正确做法是用通用原语手写 matplotlib：

```python
afg.apply_theme(); fig, ax = afg.paper_fig("single")
ax.plot(x, y, color=afg.palette.BLUE, lw=1.0)   # 任何原生 matplotlib 调用
afg.style_axes(ax)                              # 套：白底/细框/刻度朝内/字号
afg.save(fig, "out/fig_x")                      # → PNG300 + PDF
```

**不要为了用上渲染器而硬套**——渲染器只覆盖常见 21 种，通用原语能覆盖全部。

判断不了就先问（见 `prompts/10_intake.md`），**不要先画再改**。

---

## 2. 标准工作流（5 步，不要跳步）

**Step 1 — 收口需求。** 至少确认：数据从哪来（文件/变量/表）、x/y 是什么与量纲、单栏还是双栏、
有没有基线对比、是否需要灰度可读、目标期刊。缺一项就在回复里问，别猜。

**Step 2 — 定骨架。** 先用一句话写清「这张图要让读者看到什么结论」，再列面板数与每面板的图类型。
一张图只讲一件事；多面板超过 4 个就考虑拆图。

**Step 3 — 写代码。** 固定模板：

```python
import matplotlib
matplotlib.use("Agg")                      # 必须在 pyplot 之前
import matplotlib.pyplot as plt
import academic_fig as afg

afg.apply_theme()                          # 白底、细框、刻度朝内、字体回退
fig, ax = afg.paper_fig("double", nrows=1, ncols=2)   # 3.35in 单栏 / 7.0in 双栏

ax[0].plot(epoch, err, color=afg.palette.BLUE, lw=1.0, marker="o", ms=5, label="Ours")
ax[0].plot(epoch, base, color=afg.palette.GREY, lw=1.0, ls=(0, (4, 2)), label="Baseline")
ax[0].legend(loc="best")
afg.panel(ax[0], label="(a)", title="收敛性", xlabel="迭代次数", ylabel="误差 / m")

afg.footnote(fig, "数据来源：run_018.csv（n=18）；虚线为基线复现值。")
afg.save(fig, "out/fig_convergence")       # → out/fig_convergence.png (300dpi) + .pdf
```

> `apply_theme()` 仍是**推荐的第一步**（它决定配色方案、字号与字体栈）。漏了也不会
> 得到满屏方框：`paper_fig()` / `save()` / 示意图入口都会自动补 `paper-calm` 并
> **提示一次**；`save()` 还会把补主题之前建好的文字一并改到中文字体栈上。想自定义
> 配色/字号，就必须自己先调 `apply_theme(...)`——显式调用永远优先，不会被兜底覆盖。

> `save()` 返回的是 `{'png': Path, 'pdf': Path, 'auto_theme': bool, 'font_retrofit': int}`：
> 后两个是诊断键（主题是不是库替你兜的、本次改了几处文字字体）。只想拿路径就过一层
> `afg.figure_paths(result)`——别直接迭代 `.items()`，会撞上 `True.name`。

**Step 4 — 跑自检。** 一条命令：

```bash
python -m academic_fig.cli check --dir out --strict
```

不通过就按提示改，不要靠肉眼赌。检查项：宽高比与绝对栏宽、PNG dpi、PDF 是否齐、配色、命名；**该目录里有生成脚本时**还会静态查字形缺失、中文 `$...$` 混排，以及「脚本自己把 `font.family` 换成无中文字体」（`font-family`，字体探针查不出这一种）。纯图目录（只有 png/pdf）只能验前五项：此时结论行是 `△ 未发现问题（字形/混排：未检查）`——`△` 读作「只验了一部分」，别把没查读成查过；要验字形就把生成脚本放进该目录（或 `--script` 指定），那时才打 `✓`。

**Step 5 — 交付。** 给用户：PNG（预览）+ PDF（投稿）+ 生成脚本 + 一句图注。图注必须含来源与口径。

---

## 3. 风格参数（唯一真源是代码，这里只是速查）

| 项 | 值 |
|---|---|
| 画布 | 白底 `#FFFFFF`；框图填充可用暖纸白 `#F6F4F0` |
| 墨/灰 | `INK #1A1A1A`、`INK_SOFT #33383D`、`GREY #6E6E6E`、`GREY_LIGHT #C9CCD1` |
| 强调 | `BLUE #2F5D8A`、`CLAY #A4442F`、`MOSS #3F6B52`、`OCHRE #B08443`、`SLATE #5B6B7C`、`PLUM #6E5068` |
| 语义 | GOOD=BLUE、BAD=CLAY、BASE=GREY、TARGET=CLAY、HIGHLIGHT=OCHRE、MUTED=GREY_LIGHT |
| 字号 | 正文 10 / 子图标题 11（不加粗）/ 轴标签 10 / 刻度·图例 9 / 图注 8.5 |
| 线 | 轴框 0.8pt、曲线 1.0–1.15pt、marker 5pt、刻度朝内 3.5pt |

线宽只允许两处例外，其余一律 ≤1.15pt：**核密度/提琴轮廓 1.6pt**（要压过填充色才看得清）、
**比例尺 1.2pt**（`diagrams.geometry`）。看到 2pt 以上的线先当 bug 处理。
| 尺寸 | 单栏 3.35in、双栏 7.0in；宽高比 0.6–2.6 |
| 导出 | PNG 300dpi + PDF（`pdf.fonttype=42`，文字可编辑）；需要时 SVG（`svg.fonttype='none'`） |

### 3.1 配色三句（比色值更重要，盲测里最容易靠猜的就是这条）

1. **主方法/处理组只用 `BLUE`**；对照与基线退到 `GREY`（或 `SLATE`）；第三组才动 `CLAY`。一图只有一个"主角"，其余降级。
2. **顺序即语义**：`CATEGORICAL = [BLUE, CLAY, MOSS, OCHRE, SLATE, PLUM]` 按序取，超过 6 类改用小倍数面板或线型区分，**不要循环取色**。
3. **颜色之外必须有第二编码**（marker 形状 / 线型虚实 / 直接标注），保证灰度打印仍可读。

全文见 `references/palette-role.md`（含每色的"建议固定语义"表），比本页更细。

### 3.2 多面板的宽度怎么定（别再猜）

- **一张图里并排多个面板**：用 `paper_fig("double", ncols=n)`，由布局器分栏；不要用 `paper_fig("single")` 硬塞两个面板。
- **一栏一个独立文件**（例如双栏版面左右各一张图、分别出 PDF）：用 `paper_fig("single")` = 3.35in，这是双栏刊半栏图的标准宽（`references/journal-specs.md` 有 mm 换算表）。
- 默认 `wspace=0.32`、`hspace=0.42`；图注一栏放不下时先缩图注行数，别缩面板。
- **横向多面板（1 行 n 列）先别写 `height`**，布局器的默认值就是合规的：

  ```python
  fig, axes = afg.paper_fig("double", ncols=4)    # 实测 7.00×3.13in，宽高比 2.24
  ```

  只有想调比例时才显式给 `height`，**下限是 `画布宽 / 2.35 ≈ 2.98in`**（双栏）。更矮的值
  （例如 `height=1.85` → 宽高比 3.78）会被 `paper_fig` 自动抬到 3.14in 并发 `UserWarning`：
  图能出，但你要的"细长条"不会出现——所以别照着面板高去反推画布高。
  安全区间：**双栏 3.0–3.5in、单栏 1.6–2.1in**。面板自身高仍按 `面板宽 × 0.68` 推算
  （双栏 4 列 → 1.40in 面板宽 → 0.95in 面板高），余下的 0.55in 留给刻度与轴标签。
  列数 ≥ 4 的横排图，**真正的约束是画布宽高比，不是面板高**。

- **正方形图（热力图、混淆矩阵、PCA、雷达）在双栏版面上别直接铺满 7.0in**：正方形内容 7.0×7.0in
  会占掉半页，读者一眼看到的全是格子。两种正确写法：

  ```python
  fig, ax = afg.paper_fig("single", height=3.35)   # ① 半栏正方形，最常用
  fig, ax = afg.paper_fig("double", ncols=2, subplot_kw={"aspect": "equal"})
                                                   # ② 双栏两张方图并排（高度由面板宽自动推）
  ```

  只画一张又必须占双栏时，给 `height=4.2` 并把 colorbar 放右侧，让内容区仍接近正方形；
  单张方图不要用 `ncols=1` 的 double 画布硬拉，会得到 7.0×4.7in 的扁图。

**框架图专项**：只有矩形（圆角 0.02）+ 细箭头（0.9pt `-|>`）；三层（输入/方法/输出）；层内等高对齐、
间距 ≥0.25in；只有关键模块用 `BLUE_T` 填充 + `BLUE` 1.0pt 边框，其余 `INK` 0.8pt；
模块名 9.5pt、说明 8.5pt；文字不得溢出框。禁止阴影、3D、渐变、emoji、拟物图标。

---

## 4. 中文排版的两个致命坑

1. **中文与 mathtext 不能同串。** `"误差 $R$ / m"` 会让整段中文变方框。
   改写：用 Unicode（`R`、`ρ(g)`、`源⁻¹`），精确公式放图注或单独一行。
   `typography.text_safety()` 会静态查出来。
2. **字体要按系统回退。** Windows 优先 `C:\Windows\Fonts\`（`times.ttf`、`simsun.ttc`）；
   宋体没有粗体字面，粗体一律走 `simhei.ttf`。`apply_theme()` 已处理，别自己写 `font.family`。

---

## 5. 反 AI 味清单（高频 10 条，全文见 `prompts/50_negative.md`）

1. 默认蓝橙红 → 换 palette 语义色
2. 大面积网格 → 删掉，或 `alpha≤0.15` 点线
3. 每个点标数值 → 只标极值/关键点
4. 均值线+阈值线+判定线全画 → 只留最有解释力的一条
5. 图例带框、太大 → `frameon=False`、9pt、`labelspacing=0.35`
6. 标题加粗加大 → 11pt、normal
7. 分组颜色过多 → ≤6 类，其余合并或直接标注
8. 阴影/渐变/大面积色块 → 白底，强调区最多极浅填充
9. 一图塞多个结论 → 一张图一个结论
10. 为「好看」加装饰 → 先删后加

---

## 6. 出图前自检（8 条，全过再交付）

- [ ] `does not have a glyph` 计数为 0（`cli check` 在目录含生成脚本时报；纯图目录结论行是 `△ …：未检查`＝没验，不是通过）
- [ ] 脚本没有把 `font.family` / `font.sans-serif` 换成无中文字形的字体栈（`cli check` 报 `font-family`）
- [ ] 无网格、白底、四边细框、刻度朝内
- [ ] 图例无框且没压住任何数据点/标注
- [ ] 没有给每个点标数值
- [ ] 删掉颜色后类别仍可区分（marker/线型/标注）
- [ ] 空间图 equal aspect
- [ ] 宽高比 0.6–2.6，图注没把画布撑变形
- [ ] 图注写明数据来源与口径；示意量/判定线已声明

---

## 7. 目录与命令

```
academic_fig/      # 框架本体：palette / style / layout / export / checks / cli / plots / diagrams
prompts/           # 提示词库（index.md 是入口，index.json 给机器读的 大类→文件→API 映射）
references/        # 期刊规格、中文排版、坑清单、路由表、配色角色、R 等价写法
examples/          # 可运行示例（render_plots / render_diagrams / render_showcase）
assets/            # style_preview.png（双栏 6 面板样张，约 460 KB，单张上限 600 KB）+ atlas/ 精选图
scripts/install_skill.py   # 安装到 <项目>/.dsh/skills/academic-figures
scripts/check_docs.py      # 文档↔代码零漂移核对（CI 可用）
```

```bash
python -m academic_fig.cli list                        # 21 种数据图 + 5 个示意图入口，含签名
python -m academic_fig.cli init --example bar           # 生成可运行起步脚本
python -m academic_fig.cli check --dir out --strict    # 自检（CI 可用，退出码即结论）
python scripts/install_skill.py --dry-run              # 看安装计划，不落盘
python scripts/install_skill.py --target <dir> --copy  # 真装（幂等，可重复执行）
python scripts/check_docs.py --verbose                 # 文档与代码是否一致
```

**想先看效果**：`assets/style_preview.png` 是同一套风格下的双栏 6 面板样张，
`assets/atlas/` 按图类各放一张——先看这两处，再决定要不要读提示词。

---

## 8. 边界（明确不做）

- 不重算、不修正用户的数据与统计结论；只负责「怎么画」。
- 不生成照片/插画/海报（那属于图像生成模型），也不做 3D 建模渲染。
- 不打包 R 代码：`references/r-cheatsheet.md` 只给等价写法索引。
- 不把预渲染 PNG 当资产贴进新图（不可溯源）；所有图都必须由脚本可复现。
