# 流程与网络类图表规范 (prompts/30_cat_flow.md)

> 适用：《图表词典》第10类：流程、网络、层次与知识图谱
> 与代码的对应：`academic_fig.diagrams.flow`, `academic_fig.plots.sankey`, `academic_fig.style`, `academic_fig.layout`

---

## 0. 何时用这一篇

用：表达多阶段工序流转、类别间能量/流量转移、状态机跃迁或有向无环拓扑关系（如算法流程图、桑基图、数据处理流水线）。
不用：若强调复杂软硬件系统层级架构与模块划分改用 40_diagram_architecture.md；若仅比较各环节离散终态数量占比改用 30_cat_compare.md 的堆叠柱图。
边界：桑基图连接带流动方向必须保持单向一致，左右节点垂直对齐；流程图连接线必须走直角折线（Manhattan routing），绝对禁止凌乱倾斜线穿透节点。

## 1. 成员图型清单

| 图型 | Matplotlib / 推荐 API | 颜色角色 | 唯一必须注意的点 |
|---|---|---|---|
| 算法流程图 (Flowchart) | `academic_fig.diagrams.flow` / 矩形与判定菱形 | 普通节点 `PAPER`，核心算法 `BLUE_T`，线与框 `INK` | 箭头横平竖直走直角折线（Manhattan routing），禁斜穿 |
| 系统框架图 (Architecture) | 见 `40_diagram_architecture.md` 详述规范 | 底层 `WASH`，执行层 `WASH_COOL`，创新层 `BLUE_T` | 三层垂直等宽排布，同层模块等高对齐，字号统一 10pt |
| 技术路线图 (Roadmap) | 阶段大底框包裹小模块 + 阶段推进主轴 | 阶段背景 `WASH`，当前突破 `BLUE_T` | 自左向右单向推进，阶段连接使用粗箭头或带圆圈序号 |
| 有向无环图 (DAG) | 节点圆形/小方块 + 有向边 | 根节点 `SLATE`，叶节点 `BLUE`，连接线 `GREY` | 拓扑分层分级排布，边的交叉点数量尽量最小化 |
| 桑基图 (Sankey Diagram) | `academic_fig.plots.sankey` / 多边形流动条 | 流动条用节点对应淡强调色（alpha=0.35~0.5） | 节点流量输入与输出必须严格守恒；流带边缘不加粗边框 |
| 冲积图 (Alluvial Diagram) | 多列状态分流与合流 | 各状态流带采用低饱和半透明色系 | 状态列垂直对齐，流线使用光滑三次贝塞尔曲线连接 |
| 拓扑网络图 (Network Graph) | 节点散点 + 连线集合 `LineCollection` | 核心 Hub 节点 `BLUE`，外围节点 `GREY`，边线极淡灰 | 节点标签只标注度数（Degree）最高的前 5% 关键枢纽 |

---

## 2. 本类专属风格塌陷点

1. **五颜六色的高饱和方框**：每个流程框涂一个红黄蓝绿大亮色，把架构图变成积木玩具；严格使用白底（`PAPER`）或极淡灰底（`WASH`），仅创新模块施加淡蓝（`BLUE_T`）。
2. **斜穿乱七八糟的交叉箭头**：连线随意从圆角拉出斜线斜切过其他模块；必须横平竖直走直角拐弯（Orthogonal Routing）。
3. **文本溢出边框（Box Overflow）**：模块名字过长直接穿透矩形左右边缘；必须依据文本长度动态反算框体最小宽度，或强制折行。
4. **网络图头发团效应（Hairball）**：将成千上万个节点和边一次性全画出，重叠成毫无结构的黑色线团；必须过滤弱边，或聚合为社区子群。

---

## 3. 通用规范引用

- 色值与语义：严格遵守 `20_palette_typography.md`。
- 线宽规范：流程框边缘 `0.8pt`，连接线与直角箭头 `1.0pt`，边线 `GREY`。
- 坐标轴：流程架构类图表默认隐藏常规坐标轴与刻度（`ax.axis('off')`）。

---

## 4. 核心代码骨架（简洁数据流处理管道图，<=20 行）

```python
import academic_fig as afg
import matplotlib.patches as patches

afg.apply_theme()
fig, ax = afg.paper_fig("single", nrows=1)
ax.axis("off"); ax.set_xlim(0, 10); ax.set_ylim(0, 3)

nodes = [(0.5, "Raw Input\n(Data/Signal)", afg.palette.WASH),
         (3.8, "Feature Extractor\n(Backbone)", afg.palette.WASH_COOL),
         (7.2, "Adaptive Fusion\n(Ours)", afg.palette.BLUE_T)]

for x, label, bg in nodes:
    rect = patches.Rectangle((x, 0.8), 2.2, 1.4, fc=bg, ec=afg.palette.INK, lw=0.8)
    ax.add_patch(rect)
    ax.text(x + 1.1, 1.5, label, ha="center", va="center", fontsize=9, color=afg.palette.INK)

for x_start in [2.9, 6.2]:
    ax.annotate("", xy=(x_start + 0.8, 1.5), xytext=(x_start, 1.5),
                arrowprops=dict(arrowstyle="->", lw=1.0, color=afg.palette.INK))

afg.footnote(fig, "数据处理三阶段流水线；蓝色高亮为本文提出的自适应融合核心模块。")
afg.save(fig, "out/fig_cat_flow")
```

---

## 5. 自检要点

- [ ] 方框底色是否克制在白/浅灰/淡蓝范围内？
- [ ] 文字是否完全内切于方框几何边界无溢出？
- [ ] 箭头是否规整对齐，无任意斜切遮挡其他模块？
