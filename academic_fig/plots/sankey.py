# -*- coding: utf-8 -*-
"""sankey —— 桑基图（两阶段流向/构成分解；纯 matplotlib Path 手绘，不引第三方）。

**这张图要让读者看到什么**：总量从左侧来源经右侧去向如何分流，
哪条流的占比最大，以及是否存在「一进多出」的集中结构。

塌陷点提醒
1. 流数量超过 ~8 条 → 带状互相遮挡，先合并长尾为「其它」；
2. 不带数值/百分比 → 读者无法估流量，至少标首尾总量；
3. 两列节点不用同一高度基准 → 视觉上会「凭空多出/少掉」物质。
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np
import matplotlib.patheffects as _pe
from matplotlib.patches import PathPatch, Rectangle
from matplotlib.path import Path

from .. import palette as _pal
from .. import typography as _typo
from . import base as _base

#: 节点条宽度（占画布横向比例）
_NODE_W = 0.055
#: 节点之间留的间隙（占总量比例）
_GAP = 0.018


def _ribbon(x0: float, x1: float, y0a: float, y0b: float, y1a: float, y1b: float) -> Path:
    """构造一条三次贝塞尔带状路径（左端口 y0a–y0b，右端口 y1a–y1b）。"""
    xm = (x0 + x1) / 2.0
    verts = [
        (x0, y0a), (xm, y0a), (xm, y1a), (x1, y1a),
        (x1, y1b), (xm, y1b), (xm, y0b), (x0, y0b), (x0, y0a),
    ]
    codes = [Path.MOVETO, Path.CURVE4, Path.CURVE4, Path.CURVE4,
             Path.LINETO, Path.CURVE4, Path.CURVE4, Path.CURVE4, Path.CLOSEPOLY]
    return Path(verts, codes)


def sankey(ax=None, links: Any | None = None, *, data: Any | None = None,
           nodes: Sequence[str] | None = None, source_label: str | None = None,
           target_label: str | None = None, value_fmt: str = "{:.0f}",
           show_values: bool = True, node_color: str | None = None):
    """画桑基图（来源 → 去向）。

    Parameters
    ----------
    ax : matplotlib.axes.Axes, optional
        目标坐标轴；``None`` 时新建（会自动关闭坐标轴边框，桑基图不需要）。
    links : sequence of (src, dst, value) | Mapping[str, Mapping[str, float]], optional
        流量数据；也可用 ``data={"links": …}``。值必须非负，至少一条 > 0。
    data : Mapping, optional
        ``{"links": …, "nodes": …}``（给了就覆盖同名参数）。
    nodes : sequence of str, optional
        节点顺序（缺省按 links 出现顺序：先来源后去向）。
    source_label, target_label : str, optional
        左右两列的列名（如「来源」「去向」）。
    show_values : bool
        是否在流的中点标数值（默认开；流多时可关）。
    node_color : str, optional
        节点条颜色，默认墨色。

    Returns
    -------
    matplotlib.axes.Axes
        画好图的坐标轴。
    """
    ax = _base.ensure_ax(ax, box=False)
    if data is not None:
        links = _base.pick(data, "links", "flows", default=links)
        nodes = _base.pick(data, "nodes", default=nodes)
    if links is None:
        raise ValueError("sankey(): 缺少 links（(source, target, value) 列表）")

    pairs: list[tuple[str, str, float]] = []
    if isinstance(links, Mapping):
        for src, targets in links.items():
            if not isinstance(targets, Mapping):
                raise ValueError("sankey(): links 为映射时，值必须是 {去向: 数值}")
            for dst, val in targets.items():
                pairs.append((str(src), str(dst), float(val)))
    else:
        for item in links:
            if len(item) != 3:
                raise ValueError(f"sankey(): 每条流需要 (source, target, value)，收到 {item!r}")
            pairs.append((str(item[0]), str(item[1]), float(item[2])))
    if not pairs:
        raise ValueError("sankey(): links 为空")
    if any(v < 0 for _, _, v in pairs):
        raise ValueError("sankey(): 流量不能为负；分流请拆成正向流")
    if sum(v for _, _, v in pairs) <= 0:
        raise ValueError("sankey(): 所有流量都为 0")
    loops = sorted({s for s, d, _ in pairs if s == d})
    if loops:
        raise ValueError(f"sankey(): 不支持自环（source == target）：{loops[:3]}；请拆成中间节点")

    src_tot: dict[str, float] = {}
    dst_tot: dict[str, float] = {}
    for s, d, v in pairs:
        src_tot[s] = src_tot.get(s, 0.0) + v
        dst_tot[d] = dst_tot.get(d, 0.0) + v
    if nodes is None:
        left = list(src_tot)
        right = list(dst_tot)
    else:
        wanted = [str(n) for n in nodes]
        left = [n for n in wanted if n in src_tot]
        right = [n for n in wanted if n in dst_tot]
        left += [n for n in src_tot if n not in left]
        right += [n for n in dst_tot if n not in right]

    total = max(sum(src_tot.values()), sum(dst_tot.values()))
    gap = _GAP * total
    height = total + gap * max(len(left), len(right))
    color_node = node_color or _pal.GREY

    def _layout(names: list[str], totals: dict[str, float], x: float):
        y = height
        pos = {}
        for name in names:
            h = totals.get(name, 0.0)
            pos[name] = (y - h, y)  # (bottom, top)
            y -= h + gap
        return pos

    left_pos = _layout(left, src_tot, 0.0)
    right_pos = _layout(right, dst_tot, 1.0)

    for name, (b, t) in left_pos.items():
        ax.add_patch(Rectangle((0.0, b), _NODE_W, t - b, facecolor=color_node,
                               edgecolor="none", zorder=4))
        ax.annotate(f"{name}  {value_fmt.format(t - b)}", xy=(0.0, (b + t) / 2.0),
                    xytext=(-6, 0), textcoords="offset points", ha="right", va="center",
                    fontsize=_typo.TEXT_SIZES["tick"], color=_pal.INK)
    for name, (b, t) in right_pos.items():
        ax.add_patch(Rectangle((1.0 - _NODE_W, b), _NODE_W, t - b, facecolor=color_node,
                               edgecolor="none", zorder=4))
        ax.annotate(f"{name}  {value_fmt.format(t - b)}", xy=(1.0, (b + t) / 2.0),
                    xytext=(6, 0), textcoords="offset points", ha="left", va="center",
                    fontsize=_typo.TEXT_SIZES["tick"], color=_pal.INK)

    # 每条流按「目标节点内顺序」分配纵向位置，避免交叉重叠
    cursor_l = {k: v[1] for k, v in left_pos.items()}
    cursor_r = {k: v[1] for k, v in right_pos.items()}
    for i, (s, d, v) in enumerate(pairs):
        y0b = cursor_l[s] - v
        y1b = cursor_r[d] - v
        path = _ribbon(_NODE_W, 1.0 - _NODE_W, cursor_l[s], y0b, cursor_r[d], y1b)
        color = _pal.tint(_pal.CATEGORICAL[i % len(_pal.CATEGORICAL)], 0.38)
        ax.add_patch(PathPatch(path, facecolor=color, edgecolor="none", zorder=2))
        # 数值放在带子的真实中线上（左端中心与右端中心的均值）；
        # 带子太薄就别标了，数字会溢出到相邻带上
        if show_values and v > 0 and v >= 0.02 * total:
            y_mid = (cursor_l[s] + y0b + cursor_r[d] + y1b) / 4.0
            ax.annotate(value_fmt.format(v), xy=(0.5, y_mid),
                        ha="center", va="center", fontsize=_typo.TEXT_SIZES["footnote"],
                        color=_pal.INK_SOFT, zorder=6,
                        path_effects=[_pe.withStroke(linewidth=2.4,
                                                     foreground=_pal.PAPER)])
        cursor_l[s] = y0b
        cursor_r[d] = y1b

    ax.set_xlim(-0.34, 1.34)
    ax.set_ylim(-0.06 * height, height * 1.02)
    ax.set_axis_off()
    if source_label:
        ax.annotate(source_label, xy=(0.0, height * 1.01), ha="center", va="bottom",
                    fontsize=_typo.TEXT_SIZES["label"], color=_pal.INK)
    if target_label:
        ax.annotate(target_label, xy=(1.0, height * 1.01), ha="center", va="bottom",
                    fontsize=_typo.TEXT_SIZES["label"], color=_pal.INK)
    return ax


__all__ = ["sankey"]