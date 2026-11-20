# 期刊规格与尺寸（journal-specs）

一页纸说清「出一张能投出去、不会被编辑部退回重排的图」需要的全部硬指标。
本框架把这些值做成了常量，改这里之前先读 §6。

---

## 1. 宽度：只允许两档

| 档位 | 常量 | 英寸 | 毫米 | 什么时候用 |
|---|---|---|---|---|
| 单栏 | `afg.SINGLE` = `3.35` | 3.35 in | 85 mm | 单列排版、正文里插一张小图、双栏刊的半栏图 |
| 双栏 | `afg.DOUBLE` = `7.0` | 7.0 in | 178 mm | 通栏大图、多面板（2×2 / 2×3）、流程图 |

```python
fig, ax = afg.paper_fig("single")        # 3.35 in 宽
fig, ax = afg.paper_fig("double")        # 7.0 in 宽
fig, ax = afg.paper_fig(3.0)             # 也可以直接给英寸，但请说明为什么不是上面两档
```

- **高度不要写死成"看着顺眼"**。不传 `height` 时按面板比例算（单面板约 2.0 in），
  多面板会随行数增长；需要精确控制时显式给 `height=`。
- 高度上限：正文插图一般 ≤ 9.0 in（247 mm），超过就该拆图或改成横排双栏。
- **宽高比**要落在 **0.6–2.6** 之间。低于 0.6 是竖长条（双栏里放不下），高于 2.6 是扁带
  （图例和刻度都会挤）。`afg.save()` 写盘时会体检并 warning，`afg.check_dir()` 会直接报 error。

## 2. 字号：只允许这 8 个值

`ALLOWED_SIZES = (7.2, 8.0, 8.5, 9.0, 9.5, 10.0, 11.0, 12.0)`，语义名在
`afg.typography.TEXT_SIZES`：

| 语义 | 值 | 用在哪 |
|---|---|---|
| `title` | 11.0 | 面板标题（`panel(title=…)`）；字重 normal，不加粗 |
| `body` | 10.0 | 轴标签（xlabel/ylabel） |
| `label` | 10.0 | 数据标注、图例标题 |
| `tick` | 9.0 | 刻度标签；`legend` 也是 9.0 |
| `footnote` | 8.5 | 图注（数据来源 + 口径） |
| `footnote_wrapped` | 7.2 | 长图注折行后的行距字号（内部用） |
| `diagram_module` | 9.5 | 框架图模块名 |

- 最小 5 pt 是硬底线（再小印出来是灰条），但**不要用 5–7 pt**：8 pt 已是下限。
- 缩放整图时不要逐个改 `fontsize=`，改 `afg.apply_theme(font_size=…)` 的基准。
- 中文期刊常见的「图表内文字 8 pt 宋体」= `footnote`/`tick` 档；正文图注用 8.5。

## 3. 分辨率与格式：PNG + PDF 双出

| 项 | 要求 | 本框架怎么保证 |
|---|---|---|
| PNG | ≥ 300 dpi，边长 ≤ 20000 px | `afg.save()` 默认 `dpi=300`，写盘后读 pHYs 复核 |
| PDF | 矢量、字体嵌入（Type 42 / TrueType） | `pdf.fonttype=42`，`save(fig, …, formats=("png","pdf"))` 默认双出 |
| SVG | 需要时可加，`fonttype='none'`（保留文本节点，便于后期改字） | `formats=("png","pdf","svg")` |
| 文件命名 | `figNN_名称`（如 `fig03_ablation`），便于正文引用与排序 | `afg.save(fig, "fig03_ablation")`；不合规只 warning |

命名的两个好处：正文里写「见图 3」能一眼对上文件名；补图重排时按名字排序不会乱。

## 4. 常见期刊对照（尺寸/字号习惯）

| 刊物类型 | 单栏 | 双栏 | 正文图字号 | 备注 |
|---|---|---|---|---|
| IEEE 汇刊 | 3.5 in（88.9 mm） | 7.16 in（181.8 mm） | 8 pt | 图题在图下方，`TABLE/FIGURE` 大写 |
| Elsevier（多数） | 90 mm | 190 mm | 8 pt | 允许 1.5 栏；矢量优先 |
| Springer LNCS/期刊 | 84 mm | 174 mm | 8–9 pt | 图注字号常与正文同级 |
| 中文核心（学报类） | 85 mm | 178 mm | 7.5–9 pt（宋体） | 图中文字常用宋体，不用黑体 |
| 学位论文（A4） | 半栏 80 mm | 通栏 150 mm | 9–10.5 pt | 允许彩色，但黑白打印要可读 |

本框架默认值取的是这几种的交集：**3.35 in / 7.0 in / 8.5–11 pt / 300 dpi**。
投特定期刊时用 `paper_fig(width=…)` 覆盖宽度即可，不必改主题。

## 5. 交付前自检（一条命令）

```bash
python -m academic_fig.cli check --dir examples/out --strict
```

它会逐张检查：宽高比、PNG dpi、同名 PDF 是否存在、配色是否越界、命名前缀、
以及脚本里有没有 `tab10/jet/rainbow`、字号是否越界、有没有中文与 `$…$` 混排。
有任一 error 就退出码 1（`--strict` 额外把「命名不规范」升成 error），可直接挂进 CI 或 pre-commit。

交付物清单（建议逐条勾）：

- [ ] PNG（300 dpi）+ PDF（矢量）成对存在，文件名 `figNN_*`
- [ ] 宽度是 3.35 或 7.0 in，宽高比 0.6–2.6
- [ ] 图注写了**数据来源 + 口径**（n、误差棒含义、是否归一化、是否示意）
- [ ] 灰度打印仍可读（颜色之外有 marker/线型/直接标注）
- [ ] 没有方框乱码（中文与 `$…$` 不混排；希腊字母用 Unicode）
- [ ] `check --strict` 无 error

## 6. 常量在哪、怎么改

| 常量 | 位置 | 说明 |
|---|---|---|
| `SINGLE` / `DOUBLE` / `WIDTHS` | `academic_fig/layout.py` | 导出到 `afg.SINGLE` 等 |
| 字号集合 `TEXT_SIZES` / `ALLOWED_SIZES` | `academic_fig/typography.py` | 改这里同时影响 `checks.py` 白名单 |
| `MIN_DPI` / `ASPECT_RANGE` | `academic_fig/export.py`、`checks.py` | 两处都要改，否则自检和导出会打架 |
| `pdf.fonttype` / `savefig.dpi` | `academic_fig/style.py` 的 `apply_theme()` | 只改这里，不要在脚本里临时 `rcParams` |

改完跑一次 `python -m academic_fig.cli check --dir examples/out --strict`，确认示例还全绿。
