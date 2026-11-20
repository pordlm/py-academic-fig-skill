# -*- coding: utf-8 -*-
"""流程 / 泳道图：纯数据规格 → 正交折线的中文流程图。

两种排布共用一套「网格」：每个节点落在 ``(row, col)`` 或 ``(lane, step)`` 格子里，
格子尺寸由格内最长文字决定，所以不会出现「框大小不一 / 箭头压字」。

spec 结构::

    {
      "title": "增量式重规划流程",
      "direction": "v",                      # "v" 纵向主线 / "h" 横向泳道
      "lanes": [{"name": "感知"}, {"name": "决策"}, {"name": "执行"}],
      "nodes": [
        {"id": "s1", "label": "开始", "kind": "start"},
        {"id": "s2", "label": "采集样本", "note": "n = 240"},
        {"id": "d1", "label": "残差是否超阈值", "kind": "decision"},
        {"id": "s3", "label": "局部重规划", "lane": 0, "step": 2, "accent": "CLAY"},
        {"id": "s4", "label": "输出轨迹", "kind": "end"}
      ],
      "edges": [
        {"from": "s1", "to": "s2"},
        {"from": "s2", "to": "d1"},
        {"from": "d1", "to": "s3", "label": "是"},
        {"from": "d1", "to": "s4", "label": "否"},
        {"from": "s4", "to": "s2", "kind": "return", "label": "闭环"}
      ],
      "footnote": "来源：…；口径：示意流程，非真实数据。"
    }

节点 ``kind``：``start``/``end``（胶囊）、``step``（圆角矩形，默认）、
``decision``（菱形）、``note``（无框旁注）。``accent`` 可取
``BLUE/CLAY/MOSS/OCHRE/SLATE/PLUM``，用对应浅底 + 1.0pt 同色边框强调关键一步。

排布规则（ARCH §3 / prompts/40_diagram_flow.md）
-----------------------------------------------
* 正交折线 0.9pt ``-|>`` ``mutation_scale=8``，拐角圆角 0.07in；
* 泳道底色 WASH / PAPER / WASH_COOL 交替，GREY_LIGHT 0.6pt 分隔；
* 判定菱形文字 8.5pt，分支标注 8.0pt，其余模块名 9.5pt；
* 回流线走整幅最外侧，绝不穿过中间节点；
* 行距 / 列距 >= 0.25in（:data:`~._canvas.MIN_GAP`）。
"""
from __future__ import annotations

import math

from matplotlib.patches import Rectangle

from ..palette import (
    BLUE,
    BLUE_T,
    CLAY,
    CLAY_T,
    GREY_LIGHT,
    INK,
    INK_SOFT,
    MOSS,
    MOSS_T,
    OCHRE,
    OCHRE_T,
    PAPER,
    PLUM,
    PLUM_T,
    SLATE,
    SLATE_T,
    WASH,
    WASH_COOL,
)
from ._canvas import (
    BRANCH_FS,
    MIN_GAP,
    MODULE_FS,
    NOTE_FS,
    Diagram,
    arrow,
    capsule,
    check_box_overflow,
    check_text_hits,
    diamond,
    label,
    load_spec,
    register_box,
    register_link,
    rounded_box,
    wrap_to_width,
)
from ._guard import check_spec_keys, ensure_theme

__all__ = ["flow", "check_box_overflow", "check_text_hits"]

PAD_X = 0.22
PAD_TOP = 0.14
PAD_BOTTOM = 0.18
V_GAP = 0.30          # 纵向行距（>= 0.25in）
H_GAP = 0.26          # 横向列距（>= 0.25in）
NODE_PAD_X = 0.15
NODE_PAD_Y = 0.10
NODE_MIN_H = 0.46
NODE_MIN_W = 0.86
NODE_MAX_TEXT_W = 1.70
LANE_PAD_Y = 0.13
LANE_LABEL_GAP = 0.14
CAPSULE_H = 0.42
DECISION_MIN_W = 1.28
DECISION_MIN_H = 0.72
LABEL_AT = 0.46        # 标注落在路径的这个比例处（避开箭头）

# accent 名 → (浅底, 主色)；只用 palette 里的量
ACCENTS = {
    "BLUE": (BLUE_T, BLUE), "CLAY": (CLAY_T, CLAY), "MOSS": (MOSS_T, MOSS),
    "OCHRE": (OCHRE_T, OCHRE), "SLATE": (SLATE_T, SLATE), "PLUM": (PLUM_T, PLUM),
}
LANE_FILLS = (WASH, PAPER, WASH_COOL)


# --------------------------------------------------------------------------- 节点
def _parse_nodes(sp: dict) -> list[dict]:
    raw = sp.get("nodes") or sp.get("steps") or []
    if not raw:
        raise ValueError("flow(): spec['nodes'] 不能为空")
    out, seen = [], set()
    for i, nd in enumerate(raw):
        node = dict(nd)
        node["id"] = str(node.get("id") or f"s{i + 1}")
        if node["id"] in seen:
            raise ValueError(f"flow(): 节点 id 重复「{node['id']}」")
        seen.add(node["id"])
        node["kind"] = str(node.get("kind", "step")).lower()
        if node["kind"] not in ("start", "end", "step", "decision", "note"):
            raise ValueError(
                f"flow(): 节点「{node['id']}」kind={node['kind']!r} 不支持；"
                "可选 start / end / step / decision / note")
        out.append(node)
    return out


def _measure_node(d: Diagram, nd: dict, max_text_w: float) -> None:
    fs = NOTE_FS if nd["kind"] == "decision" else MODULE_FS
    nd["_fs"] = fs
    nd["_label"] = wrap_to_width(d.measure, nd.get("label", ""), fs, max_text_w)
    nd["_note"] = (wrap_to_width(d.measure, nd["note"], NOTE_FS, max_text_w)
                   if nd.get("note") else [])
    tw = max([d.measure.width(s, fs) for s in nd["_label"]] or [0.0])
    th = len(nd["_label"]) * d.measure.line_height(fs)
    if nd["_note"]:
        tw = max(tw, max(d.measure.width(s, NOTE_FS) for s in nd["_note"]))
        th += 0.03 + len(nd["_note"]) * d.measure.line_height(NOTE_FS)
    nd["_tw"], nd["_th"] = tw, th
    if nd["kind"] == "decision":
        w = max(DECISION_MIN_W, tw * 1.90 + 0.10)
        h = max(DECISION_MIN_H, th * 2.20 + 0.10)
        while tw / w + th / h > 0.98:      # 菱形内接矩形判据：tw/w + th/h <= 1
            w *= 1.04
            h *= 1.04
        nd["_w"], nd["_h"] = w, h
    elif nd["kind"] == "note":
        nd["_w"], nd["_h"] = tw, max(th, 0.20)
    elif nd["kind"] in ("start", "end"):
        nd["_w"] = max(NODE_MIN_W, tw + 2 * NODE_PAD_X + 0.16)
        nd["_h"] = max(CAPSULE_H, th + 2 * (NODE_PAD_Y - 0.02))
    else:
        nd["_w"] = max(NODE_MIN_W, tw + 2 * NODE_PAD_X)
        nd["_h"] = max(NODE_MIN_H, th + 2 * NODE_PAD_Y)


def _node_colors(nd: dict):
    acc = nd.get("accent")
    if acc:
        key = str(acc).upper()
        if key not in ACCENTS:
            raise ValueError(
                f"flow(): 节点「{nd['id']}」accent={acc!r} 不在 {sorted(ACCENTS)}")
        fill, edge = ACCENTS[key]
        return fill, edge, 1.0
    if nd["kind"] in ("start", "end"):
        return WASH, INK, 0.8
    return WASH_COOL, INK, 0.8


def _draw_node(d: Diagram, nd: dict) -> None:
    ax = d.ax
    x, y, w, h = nd["x"], nd["y"], nd["w"], nd["h"]
    fill, edge, lw = _node_colors(nd)
    if nd["kind"] == "note":
        register_box(ax, label(ax, x + w / 2.0, y + h / 2.0, nd["label"], fs=NOTE_FS,
                               color=INK_SOFT), x, y, w, h)
        return
    if nd["kind"] == "decision":
        diamond(ax, x + w / 2.0, y + h / 2.0, w, h, fc=fill, ec=edge, lw=lw)
    elif nd["kind"] in ("start", "end"):
        capsule(ax, x, y, w, h, fc=fill, ec=edge, lw=lw)
    else:
        rounded_box(ax, x, y, w, h, fc=fill, ec=edge, lw=lw, radius=0.055)
    lh = d.measure.line_height(nd["_fs"])
    total = len(nd["_label"]) * lh
    if nd["_note"]:
        total += 0.03 + len(nd["_note"]) * d.measure.line_height(NOTE_FS)
    cy = y + h / 2.0 + total / 2.0
    for s in nd["_label"]:
        art = ax.text(x + w / 2.0, cy - lh / 2.0, s, ha="center", va="center",
                      fontsize=nd["_fs"], color=INK, zorder=6)
        register_box(ax, art, x, y, w, h)
        cy -= lh
    if nd["_note"]:
        cy -= 0.03
        lh2 = d.measure.line_height(NOTE_FS)
        for s in nd["_note"]:
            art = ax.text(x + w / 2.0, cy - lh2 / 2.0, s, ha="center", va="center",
                          fontsize=NOTE_FS, color=INK_SOFT, zorder=6)
            register_box(ax, art, x, y, w, h)
            cy -= lh2


# --------------------------------------------------------------------------- 路径工具
def _len(p0, p1) -> float:
    return math.hypot(p1[0] - p0[0], p1[1] - p0[1])


def _point_at(pts, frac: float):
    total = sum(_len(pts[i], pts[i + 1]) for i in range(len(pts) - 1)) or 1.0
    want = total * frac
    acc = 0.0
    for i in range(len(pts) - 1):
        seg = _len(pts[i], pts[i + 1])
        if acc + seg >= want or i == len(pts) - 2:
            t = 0.0 if seg == 0 else min(max((want - acc) / seg, 0.0), 1.0)
            return (pts[i][0] + (pts[i + 1][0] - pts[i][0]) * t,
                    pts[i][1] + (pts[i + 1][1] - pts[i][1]) * t)
        acc += seg
    return pts[-1]


def _label_spot(pts, width=None, height=None, label_h: float = 0.16):
    """标注放在最长线段中点旁：横线放上方（底对齐）、竖线放右侧（左对齐）。

    用 ``va="bottom"`` / ``ha="left"`` 把参考点放到文字**边缘**而不是中心，偏移
    0.055–0.07in ≈ 4–5pt 就是净空隙——标注是「贴线」而不是「压线」，因此不需要
    白底 halo（有 halo 反而会把虚线挖出一段断口）。:func:`check_text_hits` 据此复核。

    给出 ``width`` / ``height`` 时按画布夹取：靠右的竖线（回流车道）标注翻到线左侧
    **0.06in** 并转 90°——竖排的「下一轮」贴着虚线走，读者不会把它读成旁边那条
    实线肘部的标注；反过来 ``ha="left"`` 会顶出画布被裁成半个字。

    Returns
    -------
    tuple
        ``(x, y, ha, va, rotation)``。
    """
    best, best_len = (pts[0], pts[-1]), -1.0
    for i in range(len(pts) - 1):
        seg = _len(pts[i], pts[i + 1])
        if seg > best_len:
            best, best_len = (pts[i], pts[i + 1]), seg
    p0, p1 = best
    mx, my = (p0[0] + p1[0]) / 2.0, (p0[1] + p1[1]) / 2.0
    if abs(p1[0] - p0[0]) >= abs(p1[1] - p0[1]):
        y = my + 0.055
        if height is not None:
            y = min(y, height - 0.06)
        return mx, y, "center", "bottom", 0
    if width is not None and mx > width - 0.55:
        # 回流车道：竖排，文字右缘落在车道左侧 0.06in
        return mx - 0.06 - float(label_h) / 2.0, my, "center", "center", 90
    y = my
    return mx + 0.070, y, "left", "center", 0


# --------------------------------------------------------------------------- 纵向
def _row_heights(nodes: list[dict]) -> tuple[dict, dict]:
    rows, cols = {}, {}
    for i, nd in enumerate(nodes):
        nd["_row"] = int(nd.get("row", i))
        nd["_col"] = int(nd.get("col", 0))
    r0, c0 = min(nd["_row"] for nd in nodes), min(nd["_col"] for nd in nodes)
    for nd in nodes:
        nd["_row"] -= r0
        nd["_col"] -= c0
        rows[nd["_row"]] = max(rows.get(nd["_row"], 0.0), nd["_h"])
        cols[nd["_col"]] = max(cols.get(nd["_col"], NODE_MIN_W), nd["_w"])
    return rows, cols


def _layout_vertical(d: Diagram, nodes: list[dict], row_h: dict, col_w: dict,
                     top: float, gap: float) -> float:
    n_cols = len(col_w)
    total_w = sum(col_w.values()) + H_GAP * (n_cols - 1)
    avail = d.w - 2 * PAD_X
    if total_w > avail + 1e-9:
        raise ValueError(
            f"flow(): 横向需要 {total_w:.2f}in，画布可用 {avail:.2f}in；"
            "请减少分支列（col）或把长标签折短")
    x = (d.w - total_w) / 2.0
    centers = {}
    for c in sorted(col_w):
        centers[c] = x + col_w[c] / 2.0
        x += col_w[c] + H_GAP
    y, tops = top, {}
    for r in sorted(row_h):
        tops[r] = y
        y -= row_h[r] + (gap if r != max(row_h) else 0.0)
    for nd in nodes:
        r, c = nd["_row"], nd["_col"]
        if nd["kind"] == "decision":
            nd["w"], nd["h"] = col_w[c], row_h[r]
        else:
            nd["w"], nd["h"] = nd["_w"], nd["_h"]
        nd["cx"] = centers[c]
        nd["x"] = nd["cx"] - nd["w"] / 2.0
        nd["y"] = tops[r] - (row_h[r] - nd["h"]) / 2.0 - nd["h"]
        nd["cy"] = nd["y"] + nd["h"] / 2.0
    return y + gap


def _route_vertical(d: Diagram, a: dict, b: dict, dx_entry: float = 0.0) -> list:
    """纵向路由：y 轴朝上，``a`` 在上时向下走，``b`` 在上时贴边回流。

    ``dx_entry`` 让汇入同一节点的几条线在目标框顶边错开落点；为 0 时
    直落（用于「判定在上、动作在下」这种天然对齐的一对）。
    """
    if b["cy"] > a["cy"] + 0.02:                    # 目标在上：走侧边回流
        # 回流线贴着**整幅内容**的外沿走，避免横穿中间的节点与连线。
        right = getattr(d, "_v_right", None)
        if right is None:                           # 未预算内容外沿时退回节点侧
            right = a["x"] + a["w"] + 0.24 <= d.w - 0.10
            x_out = (max(a["x"] + a["w"], b["x"] + b["w"]) + 0.24 if right
                     else max(0.10, min(a["x"], b["x"]) - 0.24))
        else:
            x_out = right
        if x_out >= d.w / 2.0:
            return [(a["x"] + a["w"], a["cy"]), (x_out, a["cy"]),
                    (x_out, b["cy"]), (b["x"] + b["w"], b["cy"])]
        return [(a["x"], a["cy"]), (x_out, a["cy"]),
                (x_out, b["cy"]), (b["x"], b["cy"])]
    if abs(b["cy"] - a["cy"]) < 0.02:               # 同一行：横向旁支
        if b["cx"] > a["cx"]:
            return [(a["x"] + a["w"], a["cy"]), (b["x"], b["cy"])]
        return [(a["x"], a["cy"]), (b["x"] + b["w"], b["cy"])]
    x_entry = b["cx"] + dx_entry
    x_entry = min(max(x_entry, b["x"] + 0.12), b["x"] + b["w"] - 0.12)
    if abs(x_entry - a["cx"]) < 1e-6:               # 正下方
        return [(a["cx"], a["y"]), (x_entry, b["y"] + b["h"])]
    y_mid = a["y"] - max(0.12, (a["y"] - (b["y"] + b["h"])) / 2.0)
    return [(a["cx"], a["y"]), (a["cx"], y_mid), (x_entry, y_mid),
            (x_entry, b["y"] + b["h"])]


# --------------------------------------------------------------------------- 横向
def _lane_bands(nodes: list[dict], n_lanes: int, extra: float = 0.0) -> list[float]:
    bands = []
    for li in range(n_lanes):
        hs = [nd["_h"] for nd in nodes if nd["_lane"] == li]
        bands.append(max([NODE_MIN_H] + hs) + 2 * LANE_PAD_Y + extra)
    return bands


def _layout_horizontal(d: Diagram, nodes: list[dict], lanes: list[str],
                       lane_label_w: float, band_h: list[float],
                       top: float) -> tuple[float, list[float], list[float]]:
    n_steps = max(nd["_step"] for nd in nodes) + 1
    col_w = [NODE_MIN_W] * n_steps
    for nd in nodes:
        col_w[nd["_step"]] = max(col_w[nd["_step"]], nd["_w"])
    left = PAD_X + lane_label_w + LANE_LABEL_GAP
    total_w = sum(col_w) + H_GAP * (n_steps - 1)
    avail = d.w - left - PAD_X
    if total_w > avail + 1e-9:
        raise ValueError(
            f"flow(): 主线需要 {total_w:.2f}in，可用 {avail:.2f}in"
            f"（已扣泳道名 {lane_label_w:.2f}in）；请减少步骤或折短标签")
    x = left
    centers = []
    for c in range(n_steps):
        centers.append(x + col_w[c] / 2.0)
        x += col_w[c] + H_GAP
    y, band_top = top, []
    for li in range(len(band_h)):
        band_top.append(y)
        y -= band_h[li]
    for nd in nodes:
        li, c = nd["_lane"], nd["_step"]
        nd["w"], nd["h"] = nd["_w"], nd["_h"]
        nd["cx"] = centers[c]
        nd["cy"] = band_top[li] - band_h[li] / 2.0
        nd["x"] = nd["cx"] - nd["w"] / 2.0
        nd["y"] = nd["cy"] - nd["h"] / 2.0
    return y, band_h, band_top


def _side_point(nd: dict, toward) -> tuple:
    """取节点朝向 ``toward`` 的那条边（菱形取顶点，方框/胶囊取边中点）。"""
    dx = toward[0] - nd["cx"]
    dy = toward[1] - nd["cy"]
    if abs(dx) >= abs(dy):
        return (nd["x"] + nd["w"], nd["cy"]) if dx >= 0 else (nd["x"], nd["cy"])
    return (nd["cx"], nd["y"] + nd["h"]) if dy >= 0 else (nd["cx"], nd["y"])


def _route_horizontal(a: dict, b: dict, y_bottom: float) -> list:
    ex = _side_point(a, (b["cx"], b["cy"]))
    en = _side_point(b, (a["cx"], a["cy"]))
    if b["cx"] < a["cx"] - 0.02:                    # 回退：走整幅下方
        y_route = min(y_bottom - 0.12, a["y"] - 0.16)
        return [(a["cx"], a["y"]), (a["cx"], y_route), (b["cx"], y_route),
                (b["cx"], b["y"])]
    if abs(b["cy"] - a["cy"]) < 0.02:               # 同泳道直行
        return [ex, en]
    if abs(b["cx"] - a["cx"]) < 1e-6:               # 同列：直上直下
        return [ex, en]
    # 跨泳道：出边中点 → 竖着走一段 → 横过去 → 进目标边
    span = en[0] - ex[0]
    x_mid = ex[0] + (max(0.14, min(0.30, span / 2.0)) if span > 0
                     else min(-0.14, max(-0.30, span / 2.0)))
    return [ex, (x_mid, ex[1]), (x_mid, en[1]), en]


# --------------------------------------------------------------------------- 入口
def flow(spec, *, width="double", height=None, note=None, strict=True,
         debug=False, title=None):
    """画一张流程图 / 泳道图，返回 ``ax``。

    Parameters
    ----------
    spec : dict | str | pathlib.Path
        规格字典或 JSON 文件路径。
    width, height
        同 :func:`~academic_fig.diagrams.architecture.architecture`。
    note : str, optional
        覆盖 ``spec["footnote"]``。
    strict, debug : bool
        文字溢出框的处理方式（见 :func:`check_box_overflow`）。
    title : str, optional
        覆盖 ``spec["title"]``。

    Returns
    -------
    matplotlib.axes.Axes
    """
    sp = load_spec(spec)
    ensure_theme()
    check_spec_keys(sp, __name__, strict=strict, extra=())
    nodes = _parse_nodes(sp)
    direction = str(sp.get("direction", "v")).lower()
    if direction not in ("v", "h"):
        raise ValueError("flow(): direction 只能是 'v'（纵向）或 'h'（横向泳道）")
    lanes = [str(x.get("name", "")) if isinstance(x, dict) else str(x)
             for x in (sp.get("lanes") or [])]
    header = str(title if title is not None else (sp.get("title") or ""))
    w_spec = sp.get("width")
    d = Diagram(width if w_spec is None else w_spec)
    if V_GAP < MIN_GAP or H_GAP < MIN_GAP:                             # pragma: no cover
        raise ValueError("flow(): V_GAP / H_GAP 不能小于 0.25in")
    pad_top = PAD_TOP + (0.30 if header else 0.0)

    if direction == "v":
        max_text = min(NODE_MAX_TEXT_W, d.w - 2 * PAD_X - 2 * NODE_PAD_X)
        for nd in nodes:
            _measure_node(d, nd, max_text)
        row_h, col_w = _row_heights(nodes)
        need = pad_top + sum(row_h.values()) + V_GAP * (len(row_h) - 1) + PAD_BOTTOM
        h = float(height) if height is not None else need
        if h < need - 1e-6:
            raise ValueError(f"flow(): height={h:.2f}in 装不下（至少 {need:.2f}in）")
        d.size(h)
        extra = max(0.0, h - need)
        gap = V_GAP + (extra / (len(row_h) - 1) if len(row_h) > 1 else 0.0)
        content_bottom = _layout_vertical(d, nodes, row_h, col_w, h - pad_top, gap)
        if header:
            d.title(header)
    else:
        if not lanes:
            lanes = [""]
        lane_label_w = max([d.measure.width(s, MODULE_FS) for s in lanes] + [0.0]) + 0.06
        max_text = min(NODE_MAX_TEXT_W, d.w - 2 * PAD_X - lane_label_w
                       - LANE_LABEL_GAP - 2 * NODE_PAD_X)
        for nd in nodes:
            _measure_node(d, nd, max_text)
        counters = [0] * len(lanes)
        for nd in nodes:
            lane = int(nd.get("lane", 0))
            if lane < 0 or lane >= len(lanes):
                raise ValueError(
                    f"flow(): 节点「{nd['id']}」lane={lane} 越界"
                    f"（共 {len(lanes)} 条泳道）")
            nd["_lane"] = lane
            if nd.get("step") is None:
                nd["_step"] = counters[lane]
                counters[lane] += 1
            else:
                nd["_step"] = int(nd["step"])
        band_h = _lane_bands(nodes, len(lanes))
        need = pad_top + sum(band_h) + PAD_BOTTOM
        h = float(height) if height is not None else need
        if h < need - 1e-6:
            raise ValueError(f"flow(): height={h:.2f}in 装不下（至少 {need:.2f}in）")
        d.size(h)
        band_h = _lane_bands(nodes, len(lanes),
                            extra=max(0.0, h - need) / len(lanes))
        content_bottom, band_h, band_top = _layout_horizontal(
            d, nodes, lanes, lane_label_w, band_h, h - pad_top)
        for li, name in enumerate(lanes):          # 泳道底：交替底色 + 细线
            y0 = band_top[li] - band_h[li]
            d.ax.add_patch(Rectangle((PAD_X, y0), d.w - 2 * PAD_X, band_h[li],
                                     facecolor=LANE_FILLS[li % len(LANE_FILLS)],
                                     edgecolor="none", zorder=0))
            d.ax.plot([PAD_X, d.w - PAD_X], [y0, y0], color=GREY_LIGHT, lw=0.6,
                      zorder=1)
            if name:
                label(d.ax, PAD_X + 0.06, band_top[li] - band_h[li] / 2.0, name,
                      fs=MODULE_FS, color=INK_SOFT, ha="left")
        if header:
            d.title(header)

    for nd in nodes:
        _draw_node(d, nd)
    by_id = {nd["id"]: nd for nd in nodes}
    y_bottom = min(nd["y"] for nd in nodes)
    if direction == "v":                            # 回流线走整幅内容的外沿
        x_hi = max(nd["x"] + nd["w"] for nd in nodes)
        x_lo = min(nd["x"] for nd in nodes)
        if x_hi + 0.24 <= d.w - 0.10:
            d._v_right = x_hi + 0.24
        elif x_lo - 0.24 >= 0.10:
            d._v_right = x_lo - 0.24
        else:
            d._v_right = d.w - 0.06
    for edge in sp.get("edges") or []:
        a = by_id.get(str(edge.get("from")))
        b = by_id.get(str(edge.get("to")))
        if a is None or b is None:
            raise ValueError(
                f"flow(): 边引用了不存在的节点 {edge.get('from')!r} → "
                f"{edge.get('to')!r}")
        kind = str(edge.get("kind", "normal"))
        if direction == "v":
            # 斜向汇入的边在目标框顶边错开 0.30in；正上正下的保持直落
            dx = 0.0 if abs(a["cx"] - b["cx"]) < 1e-6 else (
                0.30 if a["cx"] > b["cx"] else -0.30)
            pts = _route_vertical(d, a, b, dx_entry=dx)
        else:
            pts = _route_horizontal(a, b, y_bottom)
        register_link(d.ax, pts, lw=0.9)
        arrow(d.ax, pts, color=INK, lw=0.9,
              ls=(0, (4, 2.5)) if kind == "return" else "-")
        if edge.get("label"):
            x, y, ha, va, rot = _label_spot(
                pts, d.w, d.h, label_h=d.measure.line_height(BRANCH_FS))
            label(d.ax, x, y, str(edge["label"]), fs=BRANCH_FS, color=INK_SOFT,
                  ha=ha, va=va, bbox=False, rotation=rot)

    note_text = note if note is not None else sp.get("footnote")
    d.footnote(note_text)
    check_box_overflow(d.ax, strict=strict, debug=debug)
    check_text_hits(d.ax, strict=strict, debug=debug)
    return d.ax
