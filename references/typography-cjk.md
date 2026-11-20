# 中文排版与字体回退（typography-cjk）

中文插图出问题，九成不是"不会画"，而是**字体没落上**或**中文和数学混排**。
这篇讲清回退链、字号语义、以及"绝不出现方框"的写法。

---

## 1. 字体回退链（Windows 优先，其次 Linux/Noto）

`afg.typography` 里维护四组候选，按顺序探第一个存在的**文件**，再注册给 matplotlib：

| 角色 | 候选（按优先级） | 用途 |
|---|---|---|
| 正文西文 | `C:/Windows/Fonts/times.ttf` → `timesbd.ttf` → Linux `DejaVuSerif` → `NotoSerif` | 数字、英文、单位 |
| 正文中文 | `C:/Windows/Fonts/simsun.ttc` → `msyh.ttc` → Linux `NotoSansCJK-Regular.ttc` / `NotoSerifCJK` | 汉字 |
| 粗体 | `C:/Windows/Fonts/simhei.ttf`（黑体） | 标题、结论强调、需要"重"的地方 |
| 兜底 | `DejaVu Serif` | 前两类都缺失时避免直接崩 |

`apply_theme()` 会把整条链塞进 `rcParams["font.serif"]` / `["font.sans-serif"]`，并把
`font.family` 设成 `serif`；`axes.unicode_minus=False` 是把负号换成 ASCII `-`，
否则 SimSun 缺 U+2212，负号会变方框。

```python
afg.apply_theme()                       # 默认就做了上面这些
print(afg.typography.font_status())     # 看实测落到了哪个字体文件
```

**为什么粗体单独走 SimHei**：SimSun 没有真正的 bold 字面，matplotlib 会做"伪粗"
（描边加粗），在 300 dpi 下会糊；黑体本身笔画均匀，做标题更干净。
所以 `afg.typography.bold_font()` 返回黑体族，而不是给宋体加 `weight="bold"`。

**在别的机器上跑**（Mac / 服务器 / Docker）：候选里 `Noto*CJK` 那几条会接管；
如果全都没有，`font_status()` 会明确告诉你缺哪一类，而不是默默出方框。
CI 里建议加一条断言：

```python
st = afg.typography.font_status()
assert st["cjk"], f"缺中文字体：{st}"
```

## 2. 字号语义（与 journal-specs 一致，不重复定义）

```
title 11 · body/label 10 · tick/legend 9 · footnote 8.5 · 最小 8
```

三条纪律：

1. **不要给个别元素写 `fontsize=13`**——不在白名单里，`check --strict` 会 warning，
   而且和相邻面板不一致时肉眼立刻能看出来。
2. 面板标题用 `afg.panel(ax, title="…")`，不要 `ax.set_title(..., fontsize=14)`。
3. 图注一律走 `afg.footnote(fig, "…")`：它会折行、会在必要时把画布加高，
   保证不压刻度（自己 `fig.text(0.5, 0.01, …)` 几乎一定会压）。

## 3. 中文 + `$…$` 混排：这是本框架唯一"绝对禁止"的写法

matplotlib 的 mathtext 解析器只认 ASCII 数学字体；把汉字塞进 `$…$` 里，
它会**整段丢字**或画成方框。而中文论文里最常写的恰恰是「显著（$p<0.05$）」
这种半中半数的句子——所以规则是：

> **`$…$` 里只允许 ASCII（字母/数字/运算符），汉字与希腊字母放在外面。**

`afg.typography.text_safety()` 会静态查这件事，`check --strict` 里是 **error**：

```python
afg.typography.text_safety("显著（$p<0.05$）")          # safe=True
afg.typography.text_safety("$均值±标准差$")              # safe=False，给出改写建议
```

### 改写对照表（用 Unicode，不用 `$…$`）

| 想写 | 别写 | 写成 |
|---|---|---|
| α β γ δ ε θ λ μ σ τ φ χ ω | `$\alpha$` | `α β γ δ ε θ λ μ σ τ φ χ ω`（直接敲字符） |
| 上下标 | `$R^2$`、`$10^{-3}$` | `R²`、`10⁻³`（或 `10^-3`，视刊物要求） |
| 加减 / 大于等于 | `$\pm$`、`$\geq$` | `±`、`≥` |
| 乘号 | `$\times$` | `×` |
| 负号 | `$-$1.2` | `−1.2`（U+2212）或 `-1.2`（ASCII，最稳） |
| 统计量 | `$p<0.05$`、`$n=54$`、`$R^2=0.99$` | 原样保留（纯 ASCII，允许） |

`text_safety()` 返回 `rewritten` 字段，就是按上表替换后的版本，可直接用：

```python
info = afg.typography.text_safety("回归结果：$R^2$=0.99，$p<0.01$，均值$\\pm$SD")
print(info["safe"])       # False（含 "均值±SD" 这种中文+数学混排）
print(info["rewritten"])  # 已改写好的字符串
```

### 允许用 `$…$` 的场合

纯数学表达式对整句没有汉字，例如 `$y = ax + b$`、`$\mathrm{AUC}_{0.95}$`。
一旦句子里有汉字，就把它拆到 `$…$` 外面。

## 4. 标点、单位、括号（中文论文的细枝末节）

- **中英文之间留一个细空格**：`n = 54 例`、`300 dpi`、`pH 7.4`。
- **单位用正体**：`（a.u.）`、`（kPa）`、`（%）`；变量斜体只在公式里，图轴上不用斜体。
- **括号统一全角**：图注、轴标签用「（…）」；纯英文缩写可保留半角。
- **数字与范围**：`0.60–0.80` 用 en dash（–），不要用连字符 `-`（那是减号）。
- **百分号紧跟数字**：`85.2%`，`（%）` 写成轴标签后缀而不是每根柱都标。
- **图注结尾有句号**；一句话讲完来源，一句话讲口径：

  > 数据来源：本文实验（n=54，3 工位 × 18 点）；口径：柱与误差棒为均值 ± 1 SD。

## 5. 会遇到的坑（附处理）

| 症状 | 原因 | 处理 |
|---|---|---|
| 中文全变方框 | `font.family` 落到了 DejaVu | `afg.apply_theme()` 必须在建 fig 之前调 |
| 负号变方框 | SimSun 缺 U+2212 | 主题里已设 `axes.unicode_minus=False` |
| PDF 里字变轮廓/不可搜 | `pdf.fonttype=3` | 主题固定 42；不要临时改 rcParams |
| 导出时 stderr 刷 `MERG NOT subset` | SimSun/SimHei 的 MERG 表无法子集化 | **无害**，是 matplotlib 的 C 层直写 stderr，不影响字形 |
| 图注压住刻度 | 手写 `fig.text(y=0.01, …)` | 改用 `afg.footnote(fig, …)` |
| 某台机器上粗体变成描边 | 用宋体 + `weight="bold"` | 用 `afg.typography.bold_font()`（黑体） |

## 6. 一条自检命令

```bash
python -m academic_fig.cli check --dir examples/out --strict
```

`checks.py` 会做一次**真实渲染探针**（字形覆盖 + 中文/数学混排），
探针文本是「中位数 αβ ± ≥ 95% 置信区间 −1.2×10⁻³」——这一行能过，
说明中文字形、希腊字母、上下标、负号、乘号都齐了。