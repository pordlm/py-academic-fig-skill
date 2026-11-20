# 几何与覆盖图设计规范 (prompts/40_diagram_geometry.md)

> 适用：传感器视场覆盖、多智能体空间几何拓扑、机器人障碍物可行域
> 渲染器 API：`afg.diagrams.geometry(spec, *, width=None, height=None, note=None, strict=True, title=None, legend=True) -> ax`
> **自己建图并返回 `ax`**，不要传 `ax=`：`ax = d.geometry(spec, width="single")`，再 `afg.save(ax.figure, "out/fig01_…")`。

---

## 0. 何时用这一篇

用：展示二维平面内几何约束、感知扇区/圆形覆盖、通信拓扑与凸包边界、可达域与禁入区。
不用：若为地理地图上的站点数据测绘改用 30_cat_spatial.md；若为纯粹模块逻辑关系改用 40_diagram_architecture.md。
边界：覆盖区域必须用极浅填充（`alpha ≈ 0.10`），避免叠置覆盖导致底层拓扑线与参考虚线消失。

## 1. 成员图型表

- 传感器网络感知范围、重叠覆盖与盲区分析。
- 移动机器人局部导航中的几何避障约束、禁入区与可达扇区。
- 测站布设与关键点（最坏点 / 最优点）定位，配比例尺与单位标注。

## 2. 核心代码骨架

```
   y / m
   4 ┤        ╭────────╮          ← 安全边界（GREY 虚线，只留线不留填充）
   2 ┤     ╭──┤  ◇ A   │          ← 关键点：实心黑点 + 字母
   0 ┤  ○━━━┿━━○━━━━━━  │          ← 测站空心圆；覆盖圆 10% BLUE 填充
  -2 ┤     ╰──┴────────╯          ← 禁入区：CLAY 极浅填充 + 细边
     └──┬────┬────┬────┬── x / m
       -5   -2    1    4
                    ▭▭ 2 m         ← 比例尺（右下，独立，不压数据）
```

`set_aspect("equal")` 强制 1:1，横纵单位必须一致；图例放角落并允许 `legend_ncol` 分栏。

## 3. 必须做

- **圆用 `center` + `r`**：`{"center": [x, y], "r": 1.6, "color": "BLUE", "alpha": 0.10, "label": "基站 A 覆盖"}`。
- **测站与关键点用 `pts`**：`"stations": {"pts": [[x, y], …], "label": "测站"}`、`"keypoints": {"pts": [[x, y]], "labels": ["最坏点"], "label": "关键点"}`。
- **比例尺写全**：`"scale_bar": {"length": 1.0, "unit": "m", "position": "lower right"}`；坐标轴标「物理量 / 单位」。
- **参考结构用虚线**：安全边界、禁入区轮廓一律 `"ls": "dashed"` 并保持 `alpha` 只压填充（渲染器内部用 `to_rgba` 填色，边框始终实色）。
- **`footnote` 必填**：来源 / 口径 / 示意声明（几何示意必须声明「非真实测点」）。

## 4. 禁止做

- **比例尺不要手画**：别用 `ax.plot` 拼三段线，直接用 `scale_bar`；`position` 取 `"lower right" | "lower left" | "upper right" | "upper left"`。
- **不要把圆写成长宽两参数**：`r` 是半径；写 `w`/`h` 会被忽略并画出一个半径为 0 的点（静默出空图）。
- **不要给覆盖圆写 `alpha=0.3` 以上的重填充**：两个圆一叠就成深色斑块，底下的栅格/虚线全看不见。
- **不要关掉等比例**：`ax.set_aspect` 被改成默认时，圆会变椭圆、扇区角度失真。
- **不要传 `ax=`**：`geometry()` 不收 `ax`，传了就是 `TypeError`。
- **不要用 3D 立体块表示覆盖球**：二维投影 + 极浅填充已经足够，立体块属 N 类 AI 味。

## 5. 推荐 API 规范

```python
import academic_fig as afg
import academic_fig.diagrams as d

afg.apply_theme()

spec = {
    "circles": [
        {"center": [0.0, 0.0], "r": 1.6, "color": "BLUE", "alpha": 0.10,
         "label": "基站 A 覆盖"},
        {"center": [1.4, 0.9], "r": 1.2, "color": "CLAY", "alpha": 0.10,
         "label": "基站 B 覆盖"},
    ],
    "stations": {"pts": [[0.0, 0.0], [1.4, 0.9]], "label": "测站"},
    "keypoints": {"pts": [[0.7, 0.35]], "labels": ["最坏点"], "label": "关键点"},
    "scale_bar": {"length": 1.0, "unit": "m", "position": "lower right"},
    "footnote": "来源：本文布置方案；口径：示意几何，非真实测点。",
}

ax = d.geometry(spec, width="single")        # 自己建图、返回 ax，不传 ax=
afg.save(ax.figure, "out/fig01_coverage_geometry")
```

### 降级备选（仅在极特殊定制需要逃生时）
仅当标准 `afg.diagrams.geometry` 无法表达不规则复杂多边形或样条曲线时，退到手动调用 `patches.Polygon` / `patches.Wedge`。手绘必须使用 `afg.palette` 规范颜色、`facecolor=to_rgba(color, 0.10)`（alpha 只压填充），并 `ax.set_aspect("equal")`。

## 6. 自检要素

- [ ] 是否首选 `afg.diagrams.geometry(spec)` 表达？
- [ ] 覆盖填充是否 ≤0.10、叠置处是否仍看得清底层线与虚线？
- [ ] 横纵比例是否严格 1:1、比例尺与单位是否齐全？
- [ ] 测站（空心）与关键点（实心）是否视觉可分？
- [ ] 图注是否声明「示意几何，非真实测点」？
