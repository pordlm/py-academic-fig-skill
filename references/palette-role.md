# 色板与语义角色（palette-role）

颜色不是装饰，是**词汇表**。一个颜色在一篇文章里只能有一个含义。
本框架把这件事收敛成 `academic_fig/palette.py` 里的一组常量，`checks.py` 会逐像素核对。

---

## 1. 三组色：墨、纸、强调

| 角色 | 常量 | 值 | 用在哪 |
|---|---|---|---|
| 墨 | `INK` | `#1A1A1A` | 轴框、文字、主数据线 |
| 次墨 | `INK_SOFT` | `#33383D` | 次要线条、箭头、抖动散点 |
| 灰 | `GREY` | `#6E6E6E` | 参考线、层名、辅助文字、0 值格 |
| 浅灰 | `GREY_LIGHT` | `#C9CCD1` | 不重要的网格/虚线、载荷箭头（`MUTED`） |
| 纸 | `PAPER` | `#FFFFFF` | 画布、柱内白填充、热力图格缝 |
| 暖底 | `WASH` | `#F6F4F0` | 框架图的层带背景 |
| 冷底 | `WASH_COOL` | `#F2F4F6` | 备用浅底（表格/泳道） |

**规则**：一图之内，纯墨 `INK` 只给"最重要的一条线/一层框"；其余降到 `INK_SOFT`/`GREY`。
这样即使全图只有一个强调色，视线也知道先看哪。

## 2. 六个强调色与它们的浅色调

| 序号 | 常量 | 值 | 浅色 `_T` | 语义（建议固定） |
|---|---|---|---|---|
| 1 | `BLUE` | `#2F5D8A` | `BLUE_T` `#E9EFF4` | 主方法 / 处理组 / 正类 |
| 2 | `CLAY` | `#A4442F` | `CLAY_T` `#F7EBE8` | 对照组 / 风险 / 负类 |
| 3 | `MOSS` | `#3F6B52` | `MOSS_T` `#EAF0EC` | 第三组 / 通过 / 上调 |
| 4 | `OCHRE` | `#B08443` | `OCHRE_T` `#F7F1E5` | 强调点 / 阈值 / 提示 |
| 5 | `SLATE` | `#5B6B7C` | `SLATE_T` `#EEF0F3` | 基线 / 参照 |
| 6 | `PLUM` | `#6E5068` | `PLUM_T` `#F2EDF1` | 第六组 / 辅助说明 |

`CATEGORICAL = [BLUE, CLAY, MOSS, OCHRE, SLATE, PLUM]` —— **按这个顺序取色，不要打乱**。
顺序本身就是语义：第 1 个是主角，第 2 个是对照，后面的依次降级。
超过 6 个序列时不要循环取色（第 7 条会和第 1 条撞），改用：
分组小倍数面板、线型/形状区分、或 `CATEGORICAL_EXTENDED`（14 色，仍不建议 > 8 条）。

`CATEGORICAL_TINTS` 是同序浅色，用于堆叠面积、置信带、背景区。

## 3. 语义色（表达"好/坏"，不表达"第几组"）

| 语义 | 常量 | 实际值 | 场景 |
|---|---|---|---|
| 更好 / 有效 | `GOOD` | = `BLUE` | 提升的柱、显著的组、AUC 更高的曲线 |
| 更差 / 风险 | `BAD` | = `CLAY` | 下降、失败、风险比 > 1 |
| 基线 | `BASE` | = `GREY` | 对照基线、随机基线 |
| 目标线 | `TARGET` | = `CLAY` | "自设目标，非官方指标"的那条线 |
| 强调 | `HIGHLIGHT` | = `OCHRE` | 只强调一个点/一根柱时的那个 |
| 弱化 | `MUTED` | = `GREY_LIGHT` | 背景点云、非重点系列 |

**注意**：语义色与分类色是同一批色值，但**用法不同**。
"第 1 组"用 `CATEGORICAL[0]`，"更好"用 `GOOD`——如果同一张图里两组都是"蓝色"，
读者会误以为它们同义。一张图里只允许一种逻辑生效。

## 4. 三套色阶（连续量必用）

| 函数 | 形状 | 什么时候用 |
|---|---|---|
| `palette.cmap_seq()` | 白 → 浅蓝 → 深蓝（单向量） | 表达"大小/密度/强度"，如热力图的绝对表达量 |
| `palette.cmap_seq_r()` | 反向 | 表达"越浅越重要"（少见，慎用） |
| `palette.cmap_div()` | 蓝 ← 白 → 砖红（双向量，中点为白） | **有意义的零点**：z-score、log2FC、差值、相关系数 |
| `palette.cmap_disc(n_bins)` | 离散 n 档 | 分级数据（如"低/中/高"三档），不要用连续色阶硬切 |

**选错色阶是最常见的"图看起来不对"**：把 `cmap_seq` 用在有正负的量上，
零值会显示成"中等蓝"，读者会误以为它比负值大。`corr`/`confusion`/`heatmap(div)` 内部已按
语义选好；自己画时按上表来。

## 5. 禁止清单（`check --strict` 会报）

| 禁止 | 原因 |
|---|---|
| `tab10` / `tab20` / `tab20b` / `tab20c` | 默认皮肤，色相无语义、饱和过高 |
| `jet` / `rainbow` / `hsv` / `viridis` / `plasma` / `magma` / `inferno` / `cividis` | 亮度非单调或与本文色板无关；`jet` 还会产生假边界 |
| seaborn 的 `deep/muted/pastel/bright/dark/colorblind` | 同上，且与白纸版式冲突 |
| `RColorBrewer` 的 `Set1/Set2/Set3/Paired/Accent/Pastel1/Pastel2` | 饱和度高，红绿配对色弱不可分 |
| 手写颜色（`color="red"`、随便一个 hex） | 除非是 `palette.py` 里已有的值 |
| 纯红 + 纯绿成对使用 | 红绿色盲不可分；需要"好/坏"时用 `GOOD`/`BAD`（蓝/砖红） |
| 同一色相多个明度当分类色（>3 档） | 读者分不清"第 2 档"和"第 3 档" |

`checks.py` 的判定方式：把 PNG 里饱和度 > 0.12 的像素取色相，
要求每个色相都能在 `palette.py` 的色值（含两两 50/50 混色、含抗锯齿）里找到 ±14° 内的匹配。
所以**只要老老实实用常量，就永远不会误报**。

## 6. 浅色的正确用法：`tint()`

```python
fill = afg.palette.tint(afg.palette.BLUE, 0.12)   # 12% 蓝，压在白色上
```

不要用 `alpha=0.12` 的透明色去叠——叠两层会变成另一个颜色，
而且在 PDF 里透明组有时会被拼平（flatten）导致色偏。`tint()` 返回的是**不透明的实色**，
打印和 PDF 都稳定。置信带、柱底浅填充、背景区带都该用它。

## 7. 一页速查

```python
import academic_fig as afg
p = afg.palette
p.CATEGORICAL[0]        # 主方法
p.GOOD / p.BAD          # 更好 / 更差
p.TARGET                # 自设目标线
p.tint(p.CLAY, 0.14)    # 浅填充
p.cmap_div()            # z-score / log2FC
p.cmap_seq()            # 密度 / 表达量
p.get_palette("journal-cns")   # 另一套（更冷的期刊风）
```

换配色方案只改一处：`afg.apply_theme(palette="journal-cns")`——但**它只改框架色**
（文字/脊线/网格/图例边）与 `axes.prop_cycle`（不指定颜色时折线依次取的那组）。
`plots.*` 里写死的语义色（`palette.GOOD/BAD/BASE/HIGHLIGHT`）与
`cmap_seq/div/disc` 恒取 paper-calm 常量，不随 `apply_theme` 变——这是当前已知限制，
已经在 README「已知限制」里写明。