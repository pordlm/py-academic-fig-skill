# 分层框架图设计规范 (prompts/40_diagram_architecture.md)

> 适用：学术论文系统全景图、算法流水线、深度学习三层架构图
> 与代码的对应：`academic_fig.diagrams.architecture`, `academic_fig.style`, `academic_fig.layout`

---

## 0. 何时用这一篇

用：展示复杂软硬件系统架构、全流程算法流水线、深度模型多层网络拓扑等结构化全景（如系统全景图、三层算法流水线）。
不用：若表达动态交互、时间顺序流转或泳道协同关系改用 40_diagram_flow.md；若展示离散数据工序与物理质量转移改用 30_cat_flow.md 的桑基图。
边界：模块内文本严禁溢出外框边界；层间留白需严格对齐，禁止随意斜线穿插，连线统一采用带箭头的正交直角折线。

## 1. 成员图型表

- 当展示复杂软硬件系统架构、全流程算法流水线、深度模型端到端处理过程时。
- 当向审稿人清晰呈现“输入层 → 处理/核心方法层 → 输出/评估层”的结构化逻辑时。
- 整个框架建议分为 2~4 个大层，每层内包含 2~5 个子功能模块。
- **推荐优先方式**：直接使用声明式 spec 调用 `academic_fig.diagrams.architecture(spec)` 渲染。渲染器内置了自动分栏、层边框破口引线、重叠避让、反向闭环弧线与 `check_box_overflow` 自检。

---

## 2. 核心代码骨架

```text
 ┌─────────────────────────────────────────────────────────────┐
 │  输入层 (Input Layer)                [底框: WASH, INK 0.8pt] │
 │  ┌───────────────────────┐         ┌──────────────────────┐ │
 │  │ 原始多模态传感器数据  │         │ 外部先验知识库       │ │
 │  └───────────┬───────────┘         └───────────┬──────────┘ │
 └──────────────┼─────────────────────────────────┼────────────┘
                ▼ 0.9pt 细墨线箭头                 ▼
 ┌──────────────┼─────────────────────────────────┼────────────┐
 │  方法核心层 (Core Methodology)      [底框: WASH, INK 0.8pt] │
 │  ┌───────────▼───────────┐         ┌───────────▼──────────┐ │
 │  │ 特征对齐与投影模块    │───────► │ 核心自注意力主干     │ │
 │  │ [WASH_COOL, INK 0.8pt]│         │ [★ BLUE_T, BLUE 1pt] │ │
 │  └───────────────────────┘         └───────────┬──────────┘ │
 └────────────────────────────────────────────────┼────────────┘
                                                  ▼
 ┌────────────────────────────────────────────────┼────────────┐
 │  输出决策层 (Output & Actions)                               │
 │  ┌─────────────────────────────────────────────▼──────────┐ │
 │  │ 轨迹规划与最优控制指令 [WASH_COOL, INK 0.8pt]           │ │
 │  └────────────────────────────────────────────────────────┘ │
 └─────────────────────────────────────────────────────────────┘
```

---

## 3. 必须做与设计规范

1. **分层结构清晰分界**：垂直方向划分为 2~4 个层级（如输入层、方法层、输出层）。每层可配极浅底框（`WASH` 或 `WASH_COOL`），边框为 `INK` 细线 `0.8pt`。
2. **圆角矩形图元规范**：模块几何外框采用圆角矩形绘制，保证平滑整齐。
3. **等高对齐与规整留白**：同层内的兄弟模块等高对齐，层内与层间预留充分呼吸留白。
4. **主从填充与边框分级**：
   - 常规功能模块：填充 `WASH` 或 `WASH_COOL`，边框线宽 `0.8pt`，颜色为 `INK`。
   - 本文核心创新模块（至多 1~2 个）：填充 `BLUE_T`（`#E9EFF4`），边框加粗至 `1.0pt`，边框颜色为强调蓝 `BLUE`（`#2F5D8A`）。
5. **细线精工箭头与路由规划**：
   - 前向流转采用正交直角折线或直线，墨线细度 `0.9pt`。
   - **长横穿保护**：渲染器按列距算上限 `1.2 × 列距`（4 列约 1.86in、3 列约 2.48in）。某条 link 的水平位移超限时会抛
     `ValueError: architecture(): 连线「A→B」有一段水平位移 2.12in，超过上限 1.86in（1.2×列距）；请给该 link 加 route 点指定走法，或在 spec 里写 auto_cols: true …`
     —— 两种解法都在下面 §4：给该 link 补 `route` 点，或整体开 `auto_cols` 让渲染器按连线关系重排列位。
   - 反向闭环连接：设置 `kind="return"`，渲染器自动画回流支路（虚线，`(0,(4,2.5))`）。
6. **双层字号体系与文字安全**：
   - 模块主标题字号 `9.5pt`（居中，`INK`）。
   - 模块辅助说明字号 `8.5pt`（`INK_SOFT`）。
   - 必须通过 `checks.check_box_overflow()` 验证文字完全内切于几何框体内。

---

## 4. 声明式 Spec 字段说明

`academic_fig.diagrams.architecture(spec)` 接收字典或 JSON 路径，核心字段如下：

- `title` (str): 框架图顶部主标题。
- `layers` (list[dict]): 分层列表，从上到下排布。
  - `name` (str): 该层显示名称。
  - `note` (str, 可选): 该层副标题/口径说明。
  - `nodes` (list[dict]): 该层包含的模块节点。
    - `label` (str): 节点名称（主标题）。
    - `note` (str, 可选): 节点辅助说明。
    - `col` (int, 可选): 指定列位置（0-indexed）。若启用 `auto_cols` 则自动平铺分布。
    - `highlight` (bool, 可选): 是否高亮（强调蓝边框与浅蓝底色）。
- `links` (list[dict]): 模块间连线列表。
  - `from` (str): 起始节点 `label`。
  - `to` (str): 目标节点 `label`。
  - `kind` (str, 可选): `"forward"`（前向数据流，默认）或 `"return"`（反向反馈/闭环回路，虚线）。
  - `label` (str, 可选): 连线旁标注文字。**回流线（`kind="return"`）带 label 时若无处可放会触发压线检查**，没有把握就先不加，或改用图注说明。
  - `route` (list[[float, float]], 可选): **显式走法点，单位英寸**，形如 `[[3.2, 2.1], [3.2, 2.6]]`；渲染器把它接成「源框边 → 各点 → 目标框边」。只在长横穿被拦下、或版式特殊时使用。
- `highlight` (list[str], 可选): 全局声明需要高亮的核心节点 label 列表（等价于逐节点写 `highlight: true`）。
- `auto_cols` (bool, 可选, **默认 False**): 置 `true` 时，渲染器按连线关系重算层内列位，把互相连线的模块排到同列附近，消除被迫的长横穿。**跨层且目标列位差 > 1 列时优先开它**。
- `footnote` (str, 可选): 底部学术口径图注（函数参数 `note=` 可覆盖它）。

函数参数（不是 spec 键）：`architecture(spec, *, width="double", height=None, note=None, strict=True, debug=False, layer_border="ink")`。
`layer_border="none"` 可去掉层带描边（纯浅底分层），适合极简版式；默认 `"ink"` 保留细框。

---

## 5. 推荐代码骨架：声明式 Spec (<30 行)

```python
import academic_fig as afg

afg.apply_theme()

spec = {
    "title": "分层决策框架",
    "layers": [
        {
            "name": "输入层",
            "note": "观测与先验",
            "nodes": [
                {"label": "多源观测", "note": "状态 / 图像 / 日志"},
                {"label": "先验知识", "note": "约束与规则"}
            ]
        },
        {
            "name": "方法层",
            "note": "本文贡献",
            "nodes": [
                {"label": "特征对齐", "note": "跨模态编码"},
                {"label": "自适应决策网络", "note": "在线权重调整", "highlight": True},
                {"label": "安全约束层", "note": "可行性投影"}
            ]
        },
        {
            "name": "输出层",
            "nodes": [
                {"label": "控制指令", "note": "轨迹与动作"}
            ]
        }
    ],
    "links": [
        {"from": "多源观测", "to": "特征对齐"},
        {"from": "先验知识", "to": "安全约束层"},
        {"from": "特征对齐", "to": "自适应决策网络"},
        {"from": "自适应决策网络", "to": "安全约束层"},
        {"from": "安全约束层", "to": "控制指令"},
        {"from": "控制指令", "to": "自适应决策网络", "kind": "return", "label": "闭环校正"}
    ],
    "highlight": ["自适应决策网络"],
    "footnote": "来源：本文方法框架；口径：示意结构，模块大小不代表计算量或参数量。"
}

ax = afg.diagrams.architecture(spec, width="double")
afg.save(ax.figure, "out/fig_diagram_architecture")
```

---

## 6. 降级备选 / 逃生通道（纯 matplotlib 手写代码骨架）

当架构拓扑极其特殊、非标准分层无法用 spec 声明时，使用此降级备选方案手动绘制：

```python
import academic_fig as afg
import matplotlib.patches as patches

afg.apply_theme()
fig, ax = afg.paper_fig("double", height=3.2, nrows=1)

def draw_block(ax, xy, w, h, title, desc, is_core=False):
    fc = afg.palette.BLUE_T if is_core else afg.palette.WASH
    ec = afg.palette.BLUE if is_core else afg.palette.INK
    lw = 1.0 if is_core else 0.8
    # 降级备选：手动使用 FancyBboxPatch 绘制圆角模块
    box = patches.FancyBboxPatch(xy, w, h, boxstyle="round,pad=0.02", fc=fc, ec=ec, lw=lw)
    ax.add_patch(box)
    ax.text(xy[0] + w/2, xy[1] + h*0.62, title, ha="center", va="center", fontsize=9.5, color=afg.palette.INK)
    ax.text(xy[0] + w/2, xy[1] + h*0.30, desc, ha="center", va="center", fontsize=8.5, color=afg.palette.INK_SOFT)

draw_block(ax, (0.05, 0.55), 0.22, 0.35, "输入传感器数据", "点云与图像观测", False)
draw_block(ax, (0.39, 0.55), 0.22, 0.35, "多模态特征融合", "交叉注意力对齐", False)
draw_block(ax, (0.73, 0.55), 0.22, 0.35, "自适应决策网络", "本文核心贡献 (Ours)", True)

for x_start in [0.27, 0.61]:
    ax.annotate("", xy=(x_start + 0.12, 0.725), xytext=(x_start, 0.725),
                arrowprops=dict(arrowstyle="-|>", lw=0.9, color=afg.palette.INK, mutation_scale=8))

ax.set_xlim(0, 1.0); ax.set_ylim(0.4, 1.0); ax.axis("off")
afg.panel(ax, title="系统整体分层处理架构")
afg.footnote(fig, "架构说明：蓝色高亮模块为本文提出的自适应决策网络；各处理阶段保持时间对齐与信息单向流转。")
afg.save(fig, "out/fig_diagram_architecture_manual")
```

---

## 7. 自检点

- [ ] 是否优先采用 `academic_fig.diagrams.architecture(spec)` 声明式渲染？
- [ ] 模块间距是否保证了充分的呼吸留白与层间对齐？
- [ ] 核心模块（高亮强调蓝）是否唯一且明确？
- [ ] 闭环反馈引线是否指定了 `kind="return"` 或平滑弧线？
- [ ] 模块内部文字（主标题 9.5pt/说明 8.5pt）是否完全在边界以内无溢出？

> 与代码的对应：`academic_fig.diagrams.architecture`, `academic_fig.checks.check_box_overflow`

