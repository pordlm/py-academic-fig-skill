# ARCH —— 论文插图 skill 架构与设计

> 本文档记录构建时定下的设计决策：目录结构、风格规范、公共 API、验收口径。
> 二次开发或改写实现时以此为准；本文与 `SKILL.md` 的对外约定冲突时，以 `SKILL.md` 为准。
> 三个参考源包（见 §1）不随本仓库分发。

---

## 1. 三个源包各自给什么

| 源 | 提供 | 处理 |
|---|---|---|
| A 图脚本 | 31 个真实项目脚本：`plot_style.py`（风格）、`fig_arch_layers.py`（双层框图）、`fig_flow_q3.py`（流程图）、`fig_geo_q1..q4*.py`（几何/场量/覆盖/门限）、`fig_cost.py`/`fig_runs_*.py`（成本条形）、`figdata.py`、`field_*.py`（算数据，与渲染分离） | **提炼为 API**：框图/流程图/场量图/几何图/门限图 → `academic_fig/diagrams/`；条形/成本对比 → `academic_fig/plots/`。脚本本身不进 skill（含作者机器私有路径与项目数据），只进 `examples/` 的“风格化复刻版” |
| B 风格模板 | `论文图表风格_复用提示词.md`（风格定义 + 反 AI 味清单 + 自检表）、`plot_style_template.py`（rcParams + 图元 + `footnote_wrapped`） | **主风格来源**。提示词 → `prompts/`（经重写扩写）；`plot_style_template.py` → `academic_fig/style.py` + `layout.py`（函数保留原名/同义名，见 §4） |
| C 大 skill | `SKILL.md`（工作流/路由/QA 协议）、`assets/figure-atlas`+`assets/figures`（29 类图 × 代码+PNG）、`references/`（期刊规格、排版、坑）、`scripts/`（QA：`check_dimensions/fontsize/colors/export/figure`、`compose`、eval） | **保留骨架**：SKILL.md 的工作流与图类路由、references 精选、`scripts/check_*.py` 合并为 `academic_fig/checks.py`；`assets` 只挑 8 张缩略图进 `assets/`（77MB 全量不进 bundle）；R 代码不进本 skill（只保留一份 `references/r-cheatsheet.md` 索引） |

**冲突裁决（已定，勿再讨论）**

1. **配色**：以 B 的“黑灰 + 2 强调色”为主，但把 A/C 的取值统一到 `academic_fig/palette.py`（冻结文件（改动需评审））。C 的 Nature/Cell 色板降级为可选方案 `journal-cns`。
2. **字体**：B 的候选路径是 WSL 路径（`/mnt/c/...`），Windows 上无效 → 改成 `C:\Windows\Fonts\...` 优先，再回退 WSL/Linux/Noto。粗体单独走 SimHei/Noto Sans CJK Bold（SimSun 无粗体字面）。
3. **中文 + mathtext**：沿用 B 的硬约束（同一字符串不放 `$...$`），但**升级为自动检查**：`checks.check_glyphs()` 直接扫 stderr 的 `does not have a glyph`，并在 `checks.text_safety()` 里静态检测“中文字符 + `$`”混排。
4. **`bbox_inches="tight"`**：沿用 B 的 `footnote_wrapped`（按渲染宽度折行），并把它提升为 `layout.footnote()` 的默认行为；`export.save()` 额外做一次“输出尺寸/宽高比”校验（0.6–2.6），越界给 warning。
5. **数据/渲染分离**（B §7）：保留为**推荐契约**，`examples/` 按 `data/` + `render_*.py` 组织。
6. **C 的 “native run PNG” 机制**（把预渲染 PNG 当资产贴进新图）：**不迁移**。它容易造成“图像来源不可溯源”，与本 skill 的“可复现脚本”冲突。只在 `references/` 留一段说明为什么不用。
7. **C 的 eval / A-B 框架**：不迁移脚本，只在 `references/` 留评分维度（自检 rubric 用）。

---

## 2. 目标目录结构

```
SKILL.md                     # frontmatter + 决策树 + 工作流（≤300 行，中文为主）
README.md                    # 维护者：安装、CLI、示例、与三源包差异
pyproject.toml               # 包名 academic-figures / 模块 academic_fig / 仅依赖 numpy+matplotlib
academic_fig/
  __init__.py                # 导出公共 API（见 §4）
  palette.py                 # ★冻结文件（改动需评审），只读
  typography.py              # 维护者：字体回退、中文/数学混排检查、字号表
  style.py                   # 维护者：apply_theme() + 图元（坐标轴/参考线/图例/标注）
  layout.py                  # 维护者：尺寸（单栏 3.35in / 双栏 7.0in）、grid、panel 标号、footnote 折行
  export.py                  # 维护者：PNG 300/600 + PDF + SVG，命名与校验
  checks.py                  # 维护者：合并 C 的 check_*（尺寸/字号/配色/glyph/图例遮挡/bbox）
  cli.py                     # 维护者：`python -m academic_fig.cli check|render|list|init`
  plots/                     # 维护者：bar, line, scatter, heatmap, violin, radar, sankey, pca, roc, confusion
  diagrams/                  # architecture(分层框架图), flow(流程/泳道), field(场量/等高/响应面),
                             #            geometry(几何/覆盖), gate(门限/帕累托/扫描)
prompts/                     # ★提示词库（写作规则见 prompts/index.md）
  index.md  index.json  00_system.md  10_intake.md  20_palette_typography.md
  30_plot_*.md (9 个)  40_diagram_*.md (5 个)  50_negative.md  60_rubric.md
references/                  # 维护者：journal-specs / typography-cjk / pitfalls / figure-routing / palette-role / r-cheatsheet
examples/
  data/*.csv|json            # 小的、可公开的演示数据（≤20KB）
  render_plots.py            # 跑全部数据图 → examples/out/
  render_diagrams.py         # 跑全部示意图 → examples/out/
  render_showcase.py         # 一图一页的“风格样张”，产出 assets/style_preview.png
assets/
  style_preview.png          # 由 render_showcase 生成（双栏 7.0in，6 面板）
  atlas/*.png                # 从 C 的 figure-atlas 精选 ≤8 张，长边压到 800px
scripts/
  install_skill.py           # 安装到 <root>/.dsh/skills/academic-figures（--copy / --junction / --dry-run）
```

**禁止**：把参考源包整体拷进 bundle；把上游 77MB 图集全量拷进来；引入 pandas 之外的第三方依赖（pandas 可选，缺失时示例退化为 numpy/csv）。

---

## 3. 风格规范（所有代码和提示词必须一致）

- 白底；无网格（或 `alpha<=0.15` 的点线）；四边细框 `0.8pt`；刻度朝内 `3.5pt`。
- 字号：`font.size=10`，子图标题 `11`（不加粗），轴标签 `10`，刻度/图例 `9`，图注 `8.5`（可用 `7.2` 折行版）。
- 线宽 `1.0`，marker `5pt`；图例 `frameon=False`，`labelspacing=0.35`。
- 单栏宽 `3.35in`，双栏宽 `7.0in`；宽高比 0.6–2.6（超出即改版式）。
- 导出：`PNG@300dpi`（预览）+ `PDF`（`pdf.fonttype=42`，文字可编辑）+ 可选 `SVG`（`svg.fonttype='none'`）。
- 颜色：只用 `palette.py`。语义固定（GOOD/BAD/TARGET/HIGHLIGHT/MUTED），同一篇论文里“一个颜色一个含义”。
- 冗余编码：颜色之外必须有 marker 形状 / 虚实 / 直接标注之一。
- 空间图（几何、覆盖、可达性）：`equal aspect` + `set_box_aspect(1)`。
- 图注在图下，说明**数据来源与口径**；示意量必须标“示意，非真实值”；判定线必须标“自设目标”。

**示意图（框架图）专项**（这是本 skill 的“高级感”核心）：
- 只用矩形（可 `FancyBboxPatch` 圆角 `0.02`）+ 细线箭头；禁止阴影、3D 立体、渐变、拟物图标、emoji。
- 三层结构：输入 → 方法（若干层/模块）→ 输出；层内模块等高对齐，间距 `>= 0.25in`。
- 模块填充用 `WASH`/`WASH_COOL` 或对应 `*_T` 浅色；只有“关键模块”用 `BLUE_T` + `BLUE` 边框 `1.0pt`，其余 `INK` 边框 `0.8pt`。
- 箭头 `0.9pt`，`arrowstyle='-|>'`，`mutation_scale=8`；不画粗箭头、不画曲线箭头（除表示回流）。
- 文字：模块名 `9.5pt`，说明 `8.5pt`；文字必须在框内（`checks.check_box_overflow()` 验证）。

---

## 4. 公共 API（`academic_fig/__init__.py` 必须导出）

```python
from academic_fig import (apply_theme, paper_fig, panel, footnote, save,
                          palette, figures)   # figures = plots/diagrams 注册表
apply_theme(palette="paper-calm", cjk=True, font_size=10) -> None
paper_fig(width="single"|"double"|float, height=float|None, ncols=1, nrows=1, ...) -> (fig, axes)
panel(ax, label="(a)", title=None, xlabel=None, ylabel=None, ...) -> ax
footnote(fig, text, ...) -> Text                      # 自动折行；返回 artist
save(fig, base_path, formats=("png","pdf"), dpi=300) -> dict[str, Path]
```

单图脚本模板（SKILL.md 与 prompts 都要引用）：

```python
import academic_fig as afg
afg.apply_theme()
fig, ax = afg.paper_fig("single", nrows=1)
ax.plot(x, y, color=afg.palette.BLUE, lw=1.0, marker="o", ms=5, label="Ours")
afg.panel(ax, xlabel="迭代次数", ylabel="误差 / m", title="收敛性")
afg.footnote(fig, "数据来源：run_018.csv；判定线为自设目标，非官方指标。")
afg.save(fig, "out/fig_convergence")
```

命名兼容（B 的老函数名保留为别名，避免拷脚本即崩）：
`set_paper_style→apply_theme`、`style_axes→panel(..., box=)`、`save_paper_figure→save`、
`square→layout.square`、`footnote_wrapped→footnote`、`panel_result/panel_note→layout.panel_note`。

---

## 5. 交付与验收（每个任务的 `acceptance` 都以此为准）

1. `python -m compileall -q academic_fig` 通过；`python -c "import academic_fig"` 通过。
2. `python -m academic_fig.cli check --dir examples/out --strict` 退出码 0：
   - 无 `does not have a glyph`；无中文 + `$` 混排；宽高比在 0.6–2.6；PNG ≥300dpi；PDF 存在且含字体嵌入标记。
3. `python examples/render_plots.py --out examples/out` 与 `render_diagrams.py` 均能一条命令跑完，产物 ≥10 张。
4. 每张示例图都配“图注字符串”，且图注写明来源/口径。
5. 文档-代码一致：`SKILL.md`、`README.md`、`prompts/20_palette_typography.md` 里出现的所有色值、字号、线宽、函数名，必须与 `palette.py`/`style.py`/`__init__.py` 逐字一致（`scripts/check_doc_sync.py` 可选，由集成负责人决定是否需要）。
6. 不出现作者机器上的私有绝对路径与内部项目名（`scripts/check_docs.py` 有对应护栏）。

---

## 6. 已验证的环境事实（别浪费时间重试）

- Python 3.12.0；matplotlib 3.9.0；numpy 2.2.6；pandas 2.2.3 可用。
- 字体：`C:\Windows\Fonts\times.ttf`、`simsun.ttc`、`simhei.ttf` 均存在（Windows 路径，不是 `/mnt/c/...`）。
- 安装到 DSH 的 skill 根 `<项目根>/.dsh/skills/`（目录名必须是 kebab-case，bundle 内必须有 `SKILL.md`，frontmatter 必填 `name`+`description`）。
- `.dsh\skills` 目前不存在，首次创建后 DSH 会自动发现（watcher 会探测不存在的根）。
- 无头渲染不依赖 GUI 后端：脚本里用 `matplotlib.use("Agg")`（在导入 pyplot 前）。