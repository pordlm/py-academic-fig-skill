# 示意图 spec 字段表（自动生成，勿手改）

由 `scripts/diagram_fields.py` 从 `examples/data/diagrams/*.json` 与渲染器源码生成。
改动 spec 键或示例后重跑：`python scripts/diagram_fields.py --write`。

「来源」列：`示例` = 至少一个示例 JSON 在用（括号里给出示例值的类型）；
`源码` = 渲染器读得出来、但示例还没覆盖。未知键在 `strict=True`（默认）下直接抛
`ValueError`，不会再画出一张空图。

## 框架结构图（`architecture`）

架构图：分层、模块、跨层连线。

| 键 | 示例值类型 | 默认值 | 来源 |
| --- | --- | --- | --- |
| `auto_cols` | bool（arch_crossing.json） | `—` | 示例 |
| `debug` | — | `—` | 源码 |
| `footnote` | str（arch_crossing.json） | `—` | 示例 |
| `height` | — | `—` | 源码 |
| `highlight` | list（arch_crossing.json） | `—` | 示例 |
| `kind` | — | `—` | 源码 |
| `layer_border` | — | `—` | 源码 |
| `layers` | list（arch_crossing.json） | `—` | 示例 |
| `links` | list（arch_crossing.json） | `—` | 示例 |
| `note` | — | `—` | 源码 |
| `strict` | — | `—` | 源码 |
| `title` | str（arch_crossing.json） | `—` | 示例 |
| `width` | — | `—` | 源码 |

## 流程/时序图（`flow`）

流程、泳道、判断分支。

| 键 | 示例值类型 | 默认值 | 来源 |
| --- | --- | --- | --- |
| `debug` | — | `—` | 源码 |
| `direction` | str（flow_swimlane.json） | `"v"` | 示例 |
| `edges` | list（flow_swimlane.json） | `—` | 示例 |
| `footnote` | str（flow_swimlane.json） | `—` | 示例 |
| `height` | — | `—` | 源码 |
| `kind` | — | `—` | 源码 |
| `lanes` | list（flow_swimlane.json） | `—` | 示例 |
| `layer_border` | — | `—` | 源码 |
| `nodes` | list（flow_swimlane.json） | `—` | 示例 |
| `note` | — | `—` | 源码 |
| `steps` | — | `—` | 源码 |
| `strict` | — | `—` | 源码 |
| `title` | str（flow_swimlane.json） | `—` | 示例 |
| `width` | str（flow_vertical.json） | `—` | 示例 |

## 场量/响应面（`field`）

响应面、等高线、场分布。

| 键 | 示例值类型 | 默认值 | 来源 |
| --- | --- | --- | --- |
| `azim` | int（field_surface.json） | `-64.0` | 示例 |
| `box_aspect` | — | `—` | 源码 |
| `clabel` | — | `True` | 源码 |
| `colorbar` | — | `True` | 源码 |
| `debug` | — | `—` | 源码 |
| `diverging` | — | `—` | 源码 |
| `elev` | int（field_surface.json） | `22.0` | 示例 |
| `extrema_label` | — | `—` | 源码 |
| `field` | dict（field_gaussian.json） | `—` | 示例 |
| `footnote` | str（field_gaussian.json） | `—` | 示例 |
| `grid` | — | `—` | 源码 |
| `height` | — | `—` | 源码 |
| `kind` | str（field_gaussian.json） | `—` | 示例 |
| `labels` | dict（field_gaussian.json） | `—` | 示例 |
| `layer_border` | — | `—` | 源码 |
| `levels` | int（field_gaussian.json） | `LEVELS` | 示例 |
| `mark_extrema` | bool（field_gaussian.json） | `True` | 示例 |
| `marks` | — | `—` | 源码 |
| `n_points` | — | `90` | 源码 |
| `note` | — | `—` | 源码 |
| `point_size` | — | `14.0` | 源码 |
| `seed` | — | `0` | 源码 |
| `strict` | — | `—` | 源码 |
| `title` | str（field_gaussian.json） | `—` | 示例 |
| `width` | str（field_gaussian.json） | `"double"` | 示例 |
| `x` | dict（field_gaussian.json） | `—` | 示例 |
| `y` | dict（field_gaussian.json） | `—` | 示例 |

## 区域与覆盖（`geometry`）

区域、圆、基站、关键点、比例尺。

| 键 | 示例值类型 | 默认值 | 来源 |
| --- | --- | --- | --- |
| `annotations` | list（geometry_coverage.json） | `—` | 示例 |
| `arrows` | — | `—` | 源码 |
| `circles` | list（geometry_coverage.json） | `—` | 示例 |
| `debug` | — | `—` | 源码 |
| `footnote` | str（geometry_coverage.json） | `—` | 示例 |
| `height` | — | `—` | 源码 |
| `keypoints` | dict（geometry_coverage.json） | `—` | 示例 |
| `kind` | — | `—` | 源码 |
| `layer_border` | — | `—` | 源码 |
| `legend_loc` | str（geometry_coverage.json） | `"auto"` | 示例 |
| `legend_ncol` | int（geometry_coverage.json） | `1` | 示例 |
| `lines` | list（geometry_ring.json） | `—` | 示例 |
| `note` | — | `—` | 源码 |
| `regions` | list（geometry_coverage.json） | `—` | 示例 |
| `scale_bar` | dict（geometry_coverage.json） | `—` | 示例 |
| `stations` | dict（geometry_coverage.json） | `—` | 示例 |
| `strict` | — | `—` | 源码 |
| `ticks` | — | `True` | 源码 |
| `title` | str（geometry_coverage.json） | `—` | 示例 |
| `width` | — | `"single"` | 源码 |
| `x` | dict（geometry_coverage.json） | `—` | 示例 |
| `y` | dict（geometry_coverage.json） | `—` | 示例 |

## 门限与权衡（`gate`）

帕累托前沿、门限带、指标权衡。

| 键 | 示例值类型 | 默认值 | 来源 |
| --- | --- | --- | --- |
| `cloud` | dict（gate_pareto.json） | `—` | 示例 |
| `debug` | — | `—` | 源码 |
| `footnote` | str（gate_band.json） | `—` | 示例 |
| `height` | — | `—` | 源码 |
| `ideal` | dict（gate_pareto.json） | `—` | 示例 |
| `kind` | str（gate_band.json） | `—` | 示例 |
| `layer_border` | — | `—` | 源码 |
| `legend_loc` | str（gate_pareto.json） | `"auto"` | 示例 |
| `note` | — | `—` | 源码 |
| `pareto` | dict（gate_pareto.json） | `{}` | 示例 |
| `point_color` | — | `—` | 源码 |
| `points` | — | `—` | 源码 |
| `runs` | dict（gate_band.json） | `—` | 示例 |
| `shade_color` | — | `—` | 源码 |
| `strict` | — | `—` | 源码 |
| `thresholds` | list（gate_band.json） | `—` | 示例 |
| `title` | str（gate_band.json） | `—` | 示例 |
| `width` | str（gate_band.json） | `"single"` | 示例 |
| `x` | dict（gate_band.json） | `—` | 示例 |
| `y` | dict（gate_band.json） | `—` | 示例 |
