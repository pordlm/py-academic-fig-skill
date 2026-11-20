# 配色与排版硬约束 (prompts/20_palette_typography.md)

> 适用：配置 matplotlib rcParams、选择图元色彩、定义文本字号与线宽
> 与代码的对应：`academic_fig.palette`, `academic_fig.style`, `academic_fig.typography`

---

## 1. 唯一色值表 (严格对照 palette.py，禁止自创与篡改)

```python
# 墨与纸
INK        = "#1A1A1A"     # 主墨：坐标轴框、主曲线、关键特征点、强调外边框
INK_SOFT   = "#33383D"     # 次墨：图表正文文字、次级重要曲线
GREY       = "#6E6E6E"     # 三级：参考线、辅助结构、基线对照组
GREY_LIGHT = "#C9CCD1"     # 四级：背景散点、极弱网格、非可行域
PAPER      = "#FFFFFF"     # 底色：纯白（画布及坐标轴默认底色）
WASH       = "#F6F4F0"     # 暖纸白：框图默认模块填充、浅色底层
WASH_COOL  = "#F2F4F6"     # 冷纸白：与 WASH 交替用于相邻对比模块

# 强调色（低饱和、小面积使用）
BLUE       = "#2F5D8A"     # 主张量 / 推荐解 / 达标 / 正向
CLAY       = "#A4442F"     # 违例 / 未达标 / 峰值 / 关键对比一
MOSS       = "#3F6B52"     # 保证量 / 已覆盖 / 稳健分支
OCHRE      = "#B08443"     # 次级强调 / 预警 / 对比基线
SLATE      = "#5B6B7C"     # 中性强调（替代蓝色）
PLUM       = "#6E5068"     # 第五类分类（极少量使用）

# 浅色底（框图填充、置信区间带、可行域）
BLUE_T     = "#E9EFF4"     # 核心推荐模块浅底、95% 置信区间填充
CLAY_T     = "#F7EBE8"     # 风险区域、危险违规范围填充
MOSS_T     = "#EAF0EC"     # 安全可达区域、达标范围浅底
OCHRE_T    = "#F7F1E5"     # 观察预警区域浅底
SLATE_T    = "#EEF0F3"     # 中性结构模块浅底
PLUM_T     = "#F2EDF1"     # 扩展分支浅底
```

---

## 2. 语义角色映射表

学术插图必须遵循色彩语义一贯性，禁止同一图表中反转色彩逻辑：

| 语义角色 | 绑定常量 | 具体色值 | 适用元素 |
|---|---|---|---|
| `GOOD` | `BLUE` | `#2F5D8A` | 本文方法（Ours）、满足约束条件、达标指标、收敛最优解 |
| `BAD` | `CLAY` | `#A4442F` | 越界违例点、误差峰值、未命中样本、消融退化组 |
| `BASE` | `GREY` | `#6E6E6E` | 对照组方法（Baseline）、传统经典算法、背景参考点 |
| `TARGET` | `CLAY` | `#A4442F` | 判定线、控制阈值界限（虚线绘制，图注必须注明自设） |
| `HIGHLIGHT` | `OCHRE` | `#B08443` | 单个需特别讨论的样本点、特异值列、消融重点关注行 |
| `MUTED` | `GREY_LIGHT`| `#C9CCD1` | 海量背景背景点、不活跃状态区域、未激活神经元 |

**三条配色硬规则（全文详见 `references/palette-role.md`）**：
1. **主次分明**：主方法/处理组只用 `BLUE`，对照与基线退到 `GREY`/`SLATE`，第三组才动 `CLAY`。
2. **定序取色禁循环**：分类色板 `CATEGORICAL = [BLUE, CLAY, MOSS, OCHRE, SLATE, PLUM]` 必须严格按序取用；超过 6 类改用小倍数面板（Small Multiples）或线型/标记区分，**严禁循环取色**。
3. **双重编码**：颜色之外必须有第二编码冗余（Marker 形状、线型虚实或直接文字引线标注），确保黑白与灰度打印完全可读。

---

## 3. 标准字号、线宽与版面规格

必须统一使用以下尺寸设定，确保最终印刷成稿时的可读性：

| 元素类别 | 标准规格 | 说明 |
|---|---|---|
| 单栏标准宽度 | `width="single"` = `3.35 in` (`85 mm`) | 双栏刊物的半栏标准宽，正文单图或独立 PDF 出图 |
| 双栏标准宽度 | `width="double"` = `7.0 in` (`178 mm`) | 通栏大图、架构图、多面板并排大图 |
| 多面板布局 | `paper_fig("double", ncols=n)` | 一张图内并排多面板；默认 `wspace=0.32`, `hspace=0.42`（尺寸换算见 `references/journal-specs.md`） |
| 全局基础字号 | `font.size = 10pt` | 正文与常规注释基础 |
| 子图标题 | `axes.titlesize = 11pt` | 严格使用 `fontweight="normal"`，不加粗 |
| 坐标轴标签 | `axes.labelsize = 10pt` | 标明物理量与单位，如 `时间 / s` |
| 刻度数值标签 | `xtick.labelsize = 9pt, ytick.labelsize = 9pt` | 坐标轴刻度数字 |
| 图例字号 | `legend.fontsize = 9pt` | 配合 `frameon=False` 紧凑排版 |
| 图注与数据来源 | `footnote = 8.5pt`（紧凑场景可降至 `7.2pt`） | 必须放置于画布下方，自动折行 |
| 框图模块主名 | `name = 9.5pt` | 架构图模块核心标题，居中 |
| 框图模块说明 | `desc = 8.5pt` | 架构图模块附属注释文字 |
| 坐标轴外框线宽 | `axes.linewidth = 0.8pt` | 四边黑色细框 |
| 数据曲线线宽 | `lines.linewidth = 1.0pt` | 主数据折线，次要线设为 `0.8pt` |
| 数据散点直径 | `markersize = 5pt` | 散点、数据标记点（`ms=5`） |
| 刻度线长度与方向 | `major.size = 3.5pt`, `direction = "in"` | 刻度线强制朝内 |

---

## 4. 色图 (Colormap) 选择准则

连续与离散矩阵图表必须直接调用 `academic_fig.palette` 提供的生成器，禁止调用 matplotlib 预置色图：

1. **单向连续量（无符号）**：
   - 适用：场量强度、概率密度、绝对误差、能量分布。
   - 调用：`afg.palette.cmap_seq()`（纸白 `#F7F5F1` → 青灰 `#6E9AA0` → 深蓝 `#16304A`，明度严格单调递减）。
   - 反向：表达“越小越好”或损失函数时，使用 `afg.palette.cmap_seq_r()`。
2. **双向发散量（有符号）**：
   - 适用：相对变化率（log2FC）、标准化偏差（Z-Score）、差分矩阵。
   - 调用：`afg.palette.cmap_div()`（深蓝 `#2F5D8A` 负向 ── 纯白 `#FFFFFF` 零点 ── 砖红 `#A4442F` 正向）。
3. **离散分级计数量**：
   - 适用：网格覆盖次数、重试次数、离散聚类阶数。
   - 调用：`afg.palette.cmap_disc(n_bins)`（基于墨蓝调阶梯，等距色彩分段）。

---

## 5. 严格禁用清单

遇到以下行为判定为不合格：
- **禁用色板**：严禁使用 `jet`、`rainbow`、`turbo`、`hsv`（明度非单调，严重扭曲数据）；严禁使用 matplotlib 默认 `tab10`、`tab20`（红蓝青绿饱和度过高）；严禁使用 Seaborn 默认调色盘及 Excel 默认三原色。
- **禁用修饰**：严禁渐变填充（除科学场量图外）、阴影滤镜（Drop Shadow）、拟物 3D 棱角效果、发光边缘。
- **禁用字体混合混乱**：严禁在同一段文字中任意混用不同衬线体；同一标签内严格禁止中文文字与 `$...$` 数学公式写进同一个字符串。

> 与代码的对应：`academic_fig.palette`, `academic_fig.typography`
