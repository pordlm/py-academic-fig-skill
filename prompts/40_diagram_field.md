# 场量与响应面图规范 (prompts/40_diagram_field.md)

> 适用：势能场分布、连续等高线、优化目标二维响应曲面
> 渲染器 API：`afg.diagrams.field(spec, *, kind=None, width=None, height=None, note=None, strict=True) -> ax`
> **自己建图并返回 `ax`**，不要传 `ax=`：`ax = d.field(spec, width="single")`，再 `afg.save(ax.figure, "out/fig01_…")`。

---

## 0. 何时用这一篇

用：表达连续二维势能场、人工势场、响应曲面分布与极值点定位。
不用：若为真实实验测量的大规模空间地理信息测绘改用 30_cat_spatial.md；若为纯高维数据散点降维投影改用 30_cat_dimred.md。
边界：背景连续云图必须选用学术顺序色板（`cmap_seq`/`cmap_div`，渲染器自动选），绝对禁止 Jet/Rainbow 等伪彩失真调色盘。

## 1. 成员图型表

- 展示势场引力与斥力合力场分布、局部极小值逃逸过程。
- 展示双变量调优时的损失曲面、响应面峰值与鞍点特性。
- 展示采样密度对场重构精度的影响（同一场，不同 `n_points`）。

## 2. 核心代码骨架

```
┌──────────────────────────────┬──┐
│  连续填色 + 细等值线（0.55pt） │色│  ← 色条与绘图区等高，标签 8.5pt
│  峰值角注（左上角，不贴点）    │条│
├──────────────────────────────┴──┤
│ 图注：来源 / 口径 / 示意声明 + 自动附「网格 n×m 点，Δx、Δy」│
└─────────────────────────────────┘
```

绘图区 `set_aspect` 保持 1:1；不画网格线、不画坐标框以外的装饰。

## 3. 必须做

- **`footnote` 必填**（或 `note=`）：写清来源 / 口径 / 示意声明；渲染器会自动在末尾追加「网格 n×m = N 点，Δx、Δy」——采样步长与点数是硬要求，不要自己再写一遍。
- **真实数据走 `grid`**：`"grid": {"x": [...], "y": [...], "z": [[…]]}`，`z` 形状必须是 `(len(y), len(x))`。
- **解析式场走 `field`**：`{"type": "gaussian_sum" | "radial" | "saddle" | "ripples" | "plane", …}`，需要极值标注时保留 `mark_extrema`（默认开）。
- **有正负号就声明 `diverging`**：跨零场（势能、残差）用发散色板并以 0 为中性色；纯强度场用顺序色板。
- `levels` 取 6–12，等值线数字（`clabel`）保留，字号由渲染器统一为 8.5pt。

## 4. 禁止做

- **不要自己手写 `ax.contourf(..., colors=[...])` 传一串离散色**：会打断连续色阶梯度，出现「等高线分层瓷砖」。要控制配色就改 `levels` 与 `diverging`。
- **不要把 z 值矩阵塞进 `field`**：`field` 只接受解析式 dict，数组会 `AttributeError`；数据一律走 `grid`。
- **不要传 `ax=`**：`field()` 不收 `ax`，传了就是 `TypeError`。
- **不要用 `jet` / `rainbow` / `hsv`**，也不要在场图上叠 `ax.grid()`。
- **不要给 3D 曲面加阴影、光照、投影网格**：默认 `elev=22, azim=-64` 已是「扁平轴测」视角，改了容易变成 PPT 立体块。
- **不要在图上用 legend 列色阶**：色阶只由色条表达。

## 5. 推荐 API 规范

```python
import academic_fig as afg
import academic_fig.diagrams as d
import numpy as np

afg.apply_theme()

# 构造连续场网格（示意：二维峰函数，真实数据同样放进 grid）
x = np.linspace(-3, 3, 60)
y = np.linspace(-3, 3, 60)
X, Y = np.meshgrid(x, y)
Z = (1 - X / 2 + X ** 5 + Y ** 3) * np.exp(-X ** 2 - Y ** 2)

spec = {
    "kind": "both",                     # contourf | contour | both | surface3d | scatter
    "grid": {"x": x.tolist(), "y": y.tolist(), "z": Z.tolist()},
    "levels": 10,
    "labels": {
        "title": "人工势场标量分布",
        "x": "横向空间位置 x / m",
        "y": "纵向空间位置 y / m",
        "z": "归一化势能 Φ",             # 色条标题（无则留空）
    },
    "footnote": "来源：本文仿真；口径：归一化势能，仅作示意。",
}

ax = d.field(spec, width="single")      # 自己建图、返回 ax，不传 ax=
afg.save(ax.figure, "out/fig01_potential_field")
```

### 降级备选（仅在极特殊定制需要逃生时）
仅当标准 `afg.diagrams.field` 无法满足异构多场嵌套叠加时，才退到直接调用 `ax.contourf`。手绘需调用 `afg.palette.cmap_seq()` / `cmap_div()` 取色，并执行 `afg.style_axes(ax)`。

## 6. 自检要素

- [ ] 是否首选 `afg.diagrams.field(spec)` 表达？
- [ ] 图注是否含来源 / 口径 + 采样步长与点数？
- [ ] 轴标签是否规范无中英混排方块（中文与公式不写进同一字符串）？
- [ ] 跨零场是否用发散色板、是否以 0 为中性色？
- [ ] 色条是否与绘图区等高、标签是否 8.5pt？