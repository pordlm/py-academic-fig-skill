# 门限与权衡图设计规范 (prompts/40_diagram_gate.md)

> 适用：多目标优化帕累托前沿 (Pareto Frontier)、门限扫描、性能与开销权衡
> 渲染器 API：`afg.diagrams.gate(spec, *, kind=None, width=None, height=None, note=None, strict=True, title=None) -> ax`
> **自己建图并返回 `ax`**，不要传 `ax=`：`ax = d.gate(spec, width="single")`，再 `afg.save(ax.figure, "out/fig01_…")`。

---

## 0. 何时用这一篇

用：表达双目标或多目标优化中的权衡曲线、门限淘汰边界、帕累托支配前沿面。
不用：若为单纯两组连续测量变量的相关性分析改用 30_cat_relation.md 的散点图；若为时间序列趋势对比改用 30_cat_trend.md。
边界：非支配解集合必须有明确的连线或阶梯前沿指示，且必须标出乌托邦理想点或最佳平衡拐点。

## 1. 成员图型表

- 算力开销 vs. 识别精度的极限收益分析。
- 灵敏度 vs. 特异度的门限选择与过滤界限。
- 多次随机种子的性能包络（`runs`）与门限扫描（`scan`）。

## 2. 核心代码骨架

```
覆盖率 / %
 100 ┤            ╭──●──●   帕累托前沿（BLUE 台阶线 + 空心描边点）
  95 ┤      ╭─●──╯         ← 理想点方向箭头「更优」
  85 ┤ ┈┈┈┈●┈┈┈┈┈┈┈┈┈┈┈    门限：CLAY 点划线 + 左端文字
  75 ┤  ·  ·  背景解（GREY_LIGHT 低透明）
     └──┬────┬────┬────┬── 平均时延 / ms
        10   20   30   40
```

图注末句固定出现「自设目标，非官方指标」（缺了渲染器会自动补）。

## 3. 必须做

- **阈值线必须带 `label`**：`{"axis": "x"|"y", "value": 30, "label": "时延上限 30 ms"}`，图注必须出现「自设目标，非官方指标」——写清是作者设定的目标而非官方/标准指标，避免读者误读为实测基准。
- **前沿与背景分离**：背景解用低对比点，前沿点着 `BLUE` 并加白描边（渲染器默认），不要两者同色。
- **`sense` 写对**：`{"sense": ["min", "max"]}` 表示「x 越小越好、y 越大越好」；写反了前沿会落到错误的一侧且不会报错——画完必须肉眼核对前沿在「右上角」还是「左下角」。
- **`footnote` 必填**：来源 / 口径 / 示意声明。
- 多次运行用 `runs`：`{"x": [...], "mid": [...], "lo": [...], "hi": [...], "label": "20 次运行"}`，包络 16% 透明填充 + 1.0pt 中位轨迹。

## 4. 禁止做

- **不要拿 `cloud` 冒充 `points`**：`cloud` 是解析式点云生成器（`{"n": 70, "x": {"min": 9, "max": 40}, "model": "log", "a": 62, "b": 10, "noise": 1.6}`），真实解集走 `"points": [[x, y], …]`；把点列塞进 `cloud` 会 `AttributeError`。
- **不要用 `shade` 把半张图刷成底色**：`shade: true` 只用于「安全区 / 触发区间」这类窄带；整片着色会压掉背景解。
- **不要把阈值线画成实线黑线**：那是数据，不是门限。门限固定 `CLAY` 点划线（0.8pt）。
- **不要传 `ax=`**：`gate()` 不收 `ax`，传了就是 `TypeError`。
- **不要在图上写「官方阈值」**：没有出处的数字一律标「自设目标」。
- **不要用 legend 代替标注**：门限文字必须贴在线端（渲染器已做），不要只靠图例。

## 5. 推荐 API 规范

```python
import academic_fig as afg
import academic_fig.diagrams as d

afg.apply_theme()

spec = {
    "kind": "pareto",                       # pareto | threshold | band | scan
    "x": {"label": "平均时延", "unit": "ms"},
    "y": {"label": "覆盖率", "unit": "%"},
    "points": [                             # 真实解集：[[x, y], …]
        [10, 80], [20, 85], [30, 88], [40, 91], [50, 92],
        [15, 75], [25, 82], [35, 85], [45, 89],
    ],
    "pareto": {"sense": ["min", "max"], "label": "帕累托前沿"},
    "thresholds": [
        {"axis": "x", "value": 30, "label": "时延上限 30 ms"},
        {"axis": "y", "value": 85, "label": "覆盖率下限 85%"},
    ],
    "ideal": {"dx": -1, "dy": 1, "text": "更优"},
    "footnote": "来源：本文实验；口径：示意数据，非实测。",
}

ax = d.gate(spec, width="single")           # 自己建图、返回 ax，不传 ax=
afg.save(ax.figure, "out/fig01_pareto_gate")
```

### 降级备选（仅在极特殊定制需要逃生时）
仅当标准 `afg.diagrams.gate` 无法表达复杂的非连续阶梯多维门限时，退回底层原生绘图。手绘时使用 `ax.scatter` / `ax.plot` 配合 `afg.palette.BLUE` 与 `afg.style_axes(ax)`，阈值线仍用 `afg.palette.CLAY` 点划线。

## 6. 自检要素

- [ ] 是否首选 `afg.diagrams.gate(spec)` 表达？
- [ ] 前沿是否在 `sense` 指定的最优角、且与背景解颜色可分？
- [ ] 每条阈值线是否都有文字标签 + 图注「自设目标，非官方指标」？
- [ ] 坐标轴是否按「物理量 / 单位」标注量纲？
- [ ] 多次运行包络是否只占 16% 填充、中位轨迹 1.0pt？
