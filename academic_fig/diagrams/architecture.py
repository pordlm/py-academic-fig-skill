# -*- coding: utf-8 -*-
"""分层框架图（架构图）：纯数据规格 → 白纸墨线的三层框图。

坐标体系见 :mod:`academic_fig.diagrams._canvas`：1 数据单位 = 1 英寸。
本模块只做「排」和「画」，不做任何计算——所有内容都来自 ``spec``。

spec 结构（全部字段都可 JSON 序列化）::

    {
      "title": "系统整体分层架构",
      "layers": [
        {"name": "输入层", "note": "原始观测",
         "nodes": [{"label": "多源数据", "note": "CSV / 日志"},
                   {"label": "外部知识库", "note": "先验约束"}]},
        {"name": "方法层",
         "nodes": [{"label": "特征对齐", "note": "交叉注意力"},
                   {"label": "自适应决策网络", "note": "本文贡献"}]},
        {"name": "输出层",
         "nodes": [{"label": "决策指令", "note": "轨迹与控制"}]}
      ],
      "links": [{"from": "多源数据", "to": "特征对齐"},
                {"from": "特征对齐", "to": "自适应决策网络"},
                {"from": "自适应决策网络", "to": "决策指令"},
                {"from": "决策指令", "to": "特征对齐", "kind": "return",
                 "label": "闭环校正"}],
      "highlight": ["自适应决策网络"],
      "footnote": "来源：…；口径：示意，非真实值。"
    }

约束（ARCH §3「示意图专项」，全部由英寸坐标系直接保证）
-----------------------------------------------------
* 圆角矩形 ``FancyBboxPatch``，``pad=0.02``；
* 同层模块**等高**（全图统一高度，由最长文字决定）；
* 层间/模块间间距 ``>= 0.25in``（:data:`~._canvas.MIN_GAP`，超窄时直接报错）；
* 关键模块 ``BLUE_T`` 填充 + ``BLUE`` 1.0pt 边框，其余 ``INK`` 0.8pt；
* 箭头 0.9pt ``-|>`` ``mutation_scale=8``，回流走最外侧虚线；
* 模块名 9.5pt、说明 8.5pt，文字不溢出框（:func:`check_box_overflow` 复核）。
"""
from __future__ import annotations

from ..palette import BLUE, BLUE_T, GREY, INK, INK_SOFT, PAPER, WASH, WASH_COOL
from ._canvas import (
    BORDER_BREAK as _BORDER_BREAK,
    BORDER_LW,
    MIN_GAP,
    MODULE_FS,
    NOTE_FS,
    TITLE_FS,
    Diagram,
    TextLineCollision,
    TextOverflowError,
    arrow,
    border_gap,
    check_box_overflow,
    check_text_hits,
    label,
    line,
    load_spec,
    register_box,
    register_link,
    rounded_box,
    seg_hits_rect,
    wrap_to_width,
)
from ._guard import check_spec_keys, ensure_theme

__all__ = ["architecture", "check_box_overflow", "check_text_hits", "TextOverflowError"]

# 连线常数
RETURN_LANE = 0.30      # 回流车道相对列中心的偏移（in）：与前向线并行但不贴着
RETURN_LS = (0, (4, 2.5))  # 回流整条虚线（只此一种线型，不再出现半实半虚）
LABEL_GAP = 0.10         # 标注离线的距离（in）≈ 7.2pt，远大于 2pt 下限
# 穿框白口半宽由 0.9pt 轴宽推出来（见 _canvas.BORDER_BREAK）：总宽 ≈10.4px@300dpi。
BORDER_BREAK = _BORDER_BREAK
# 单段水平腿上限（in）的**兜底值**：只在拿不到列距时使用（如外部直接调 _check_runs）。
# 正常渲染路径一律用 ``d._max_run = 1.2 * col_w`` 覆盖它——列距随层内模块数变
# （4 列 1.55in → 1.86in；3 列 2.07in → 2.48in），写死绝对值会把合法的单列换位判成超限。
# 判据的物理含义是「最多横移 1.2 个列距」，不是某个固定英寸数。
MAX_RUN = 1.85
CROSS_GAP = 0.06         # 两线交叉处让位的白口宽度（in）

# 版面常数（英寸）——层间距与横向间距均 >= MIN_GAP
PAD_X = 0.24
PAD_TOP = 0.14
PAD_BOTTOM = 0.16
LAYER_PAD_X = 0.16
LAYER_PAD_Y = 0.09
HEADER_H = 0.26
NODE_GAP = 0.28          # 同层模块横向间距（>= 0.25in）
LAYER_GAP = 0.34         # 层间垂直间距（>= 0.25in）
NODE_PAD_X = 0.13        # 模块内左右留白
NODE_PAD_Y = 0.09        # 模块内上下留白
NODE_MIN_H = 0.44
NODE_MAX_W = 3.10
LABEL_NOTE_GAP = 0.035


def _node_key(node: dict, idx: int) -> str:
    return str(node.get("id") or node.get("label") or f"node{idx}")


def _columns(n: int, n_max: int) -> list[float]:
    """把 n 个模块摊在 n_max 个等宽列上：两端对齐 + 整体居中。

    列号允许半格。2 个模块放进 3 列就是 0 和 2（与下一层的首尾列对齐，
    连线是直的）；单个模块放进 3 列是 1.0、放进 2 列是 0.5（正中间），
    这样「上宽下窄」的框架图不会左倾。
    """
    if n <= 0:
        return []
    if n == 1:
        return [(n_max - 1) / 2.0]
    step = (n_max - 1) / float(n - 1)
    return [i * step for i in range(n)]


def architecture(spec, *, width="double", height=None, note=None, strict=True,
                 debug=False, layer_border="ink"):
    """画一张分层框架图，返回 ``ax``（``ax.figure`` 可直接交给 ``afg.save``）。

    Parameters
    ----------
    spec : dict | str | pathlib.Path
        规格字典，或指向 JSON 规格文件的路径。除 ``layers`` / ``links`` /
        ``highlight`` / ``footnote`` 外，还有两个可选的**路由**键：

        - ``"route": [[x, y], …]``（写在单条 link 上，单位英寸）：显式走法，渲染器
          接成「源框边 → route 各点 → 目标框边」，用于布局上注定要绕远的那条线。
        - ``"auto_cols": true``（写在顶层，默认 **False**）：按连线关系重排层内列位
          （邻居列位重心排序 + 三轮夹取），把「跨 3 列」压成「跨 1 列」。默认关闭——
          规格里显式写的 ``col`` 优先，渲染器不擅自改用户的排版。

        单段水平腿上限为 ``1.2 × 列距``（:data:`MAX_RUN` 只是拿不到列距时的兜底值）；
        超限且没给 route 时 ``strict=True`` 直接抛错，不默默画一条长横穿。
    width : {"single", "double"} or float
        画布宽度（inch），默认双栏 7.0in。
    height : float, optional
        画布高度；缺省按内容算。给得比内容需要的矮会直接报错（不留压字空间）。
    note : str, optional
        覆盖 ``spec["footnote"]`` 的图注。
    strict : bool
        文字溢出框时是否抛 :class:`TextOverflowError`（默认抛）。
    debug : bool
        溢出时给越界文字套 CLAY 虚线框，便于定位。
    layer_border : {"ink", "none"}
        层带描边。``"ink"``（默认）是 WASH 填充 + INK 0.8pt 描边，穿线处开
        :data:`BORDER_BREAK` 宽的白口；``"none"`` 只填充不描边（Nature/Cell 常见
        的分层做法），没有框可断，穿线处也不画白口。

    Returns
    -------
    matplotlib.axes.Axes
    """
    sp = load_spec(spec)
    ensure_theme()
    check_spec_keys(sp, __name__, strict=strict, extra=())
    layers = sp.get("layers") or []
    if not layers:
        raise ValueError("architecture(): spec['layers'] 不能为空；至少要有一层")
    band_ink = str(layer_border).lower() not in ("none", "off", "false", "0", "")
    if str(layer_border).lower() not in ("ink", "none", "off", "false", "0", ""):
        raise ValueError(
            f"architecture(): layer_border={layer_border!r} 不受支持；只能是 'ink' 或 'none'")
    highlight = {str(s) for s in (sp.get("highlight") or [])}
    if len(layers) > 1 and LAYER_GAP < MIN_GAP:                        # pragma: no cover
        raise ValueError("architecture(): LAYER_GAP 小于 ARCH §3 要求的 0.25in")

    # ---------------------------------------------------------------- 量字
    d = Diagram(width)
    m = d.measure
    w = d.w
    content_w = w - 2 * PAD_X
    inner_w = content_w - 2 * LAYER_PAD_X
    n_max = max(1, max(len(lay.get("nodes") or []) for lay in layers))
    col_w = inner_w / n_max
    node_w = min(NODE_MAX_W, col_w - NODE_GAP) if n_max > 1 else min(NODE_MAX_W, inner_w)
    if node_w <= 0.6:
        raise ValueError(
            f"architecture(): {n_max} 列放不下 {w:.2f}in 画布（单列仅 {col_w:.2f}in）；"
            "请减少每层模块数，或改用 width='double'")
    text_w = node_w - 2 * NODE_PAD_X
    # 长横穿上限随列距走：写死英寸会在 4 列（列距 1.55in）与 2 列（2.07in）下误判
    d._max_run = 1.2 * col_w

    # ---------------------------------------------------------------- 自动列位
    # 规格里没写 col 的模块，按「邻居列位重心」重排：把互相连接的模块拉到同一侧，
    # 从根上消掉长距离横穿（盲测里「线横跨半个画布」就是列位没对齐造成的）。
    if bool(sp.get("auto_cols")):
        pos = _auto_columns(layers, sp.get("links") or [], n_max)
        for li, lay in enumerate(layers):
            for ni, nd in enumerate(lay["nodes"]):
                if nd.get("col") is None:
                    nd["col"] = pos[_node_key(nd, ni)]

    # 逐节点折行 + 量高度
    for lay in layers:
        nodes = lay.get("nodes") or []
        if not nodes:
            raise ValueError(f"architecture(): 层「{lay.get('name', '?')}」没有 nodes")
        for nd in nodes:
            nd["_label"] = wrap_to_width(m, nd.get("label", ""), MODULE_FS, text_w)
            nd["_note"] = (wrap_to_width(m, nd["note"], NOTE_FS, text_w)
                           if nd.get("note") else [])
            h_need = (len(nd["_label"]) * m.line_height(MODULE_FS)
                      + (LABEL_NOTE_GAP + len(nd["_note"]) * m.line_height(NOTE_FS)
                         if nd["_note"] else 0.0))
            nd["_text_h"] = h_need
    node_h = max(NODE_MIN_H, max(nd["_text_h"] for lay in layers
                                 for nd in lay["nodes"]) + 2 * NODE_PAD_Y)

    # ---------------------------------------------------------------- 版面
    layer_h = HEADER_H + node_h + 2 * LAYER_PAD_Y
    n_layers = len(layers)
    need_h = (PAD_TOP + n_layers * layer_h + (n_layers - 1) * LAYER_GAP
              + PAD_BOTTOM)
    if sp.get("title"):
        need_h += 0.30
    h = float(height) if height is not None else need_h
    if h < need_h - 1e-6:
        raise ValueError(
            f"architecture(): height={h:.2f}in 装不下内容（至少需要 {need_h:.2f}in）；"
            "请加高画布或减少层数")
    extra_gap = (h - need_h) / (n_layers - 1) if n_layers > 1 else 0.0
    gap = LAYER_GAP + max(0.0, extra_gap)
    d.size(h)
    d._layer_border = "ink" if band_ink else "none"

    top = h - PAD_TOP
    if sp.get("title"):
        d.ax.text(w / 2.0, h - 0.05, str(sp["title"]), ha="center", va="top",
                  fontsize=TITLE_FS, color=INK)
        top -= 0.30

    boxes: dict[str, dict] = {}
    order: list[str] = []
    d._bands = []
    d._deferred = []
    d._intentional = set()     # 刻意压在自己线上的标注（白底兜底），复核时豁免
    for li, lay in enumerate(layers):
        y_top = top - li * (layer_h + gap)
        y0 = y_top - layer_h
        rounded_box(d.ax, PAD_X, y0, content_w, layer_h, fc=WASH,
                    ec=INK if band_ink else "none",
                    lw=BORDER_LW if band_ink else 0.0,
                    radius=0.05, zorder=1)
        _register_band(d.ax, PAD_X, y0, content_w, layer_h)
        d._bands.append((PAD_X, y0, content_w, layer_h))
        label(d.ax, PAD_X + 0.10, y_top - HEADER_H / 2.0 - 0.01, lay.get("name", ""),
              fs=MODULE_FS, color=INK, ha="left")
        if lay.get("note"):
            label(d.ax, PAD_X + content_w - 0.10, y_top - HEADER_H / 2.0 - 0.01,
                  lay["note"], fs=NOTE_FS, color=GREY, ha="right")
        row_top = y_top - HEADER_H - LAYER_PAD_Y
        row_y = row_top - node_h
        nodes = lay["nodes"]
        cols = _columns(len(nodes), n_max)
        for nd, col in zip(nodes, cols):
            if nd.get("col") is not None:
                col = float(nd["col"])
            cx = PAD_X + LAYER_PAD_X + (col + 0.5) * col_w
            x0 = cx - node_w / 2.0
            key = _node_key(nd, len(order))
            if key in boxes:
                raise ValueError(f"architecture(): 模块名重复「{key}」；请用 id 区分")
            core = bool(nd.get("highlight")) or key in highlight or \
                str(nd.get("label", "")) in highlight
            fc = BLUE_T if core else WASH_COOL
            ec = BLUE if core else INK
            lw = 1.0 if core else 0.8
            rounded_box(d.ax, x0, row_y, node_w, node_h, fc=fc, ec=ec, lw=lw,
                        radius=0.055, zorder=3)
            # 文字：整块垂直居中，逐行单行 Text（行高自己算，量得准）
            total = nd["_text_h"]
            y = row_y + node_h / 2.0 + total / 2.0
            lh = m.line_height(MODULE_FS)
            for ln in nd["_label"]:
                art = d.ax.text(cx, y - lh / 2.0, ln, ha="center", va="center",
                                fontsize=MODULE_FS, color=INK, zorder=5)
                register_box(d.ax, art, x0, row_y, node_w, node_h)
                y -= lh
            if nd["_note"]:
                y -= LABEL_NOTE_GAP
                lh2 = m.line_height(NOTE_FS)
                for ln in nd["_note"]:
                    art = d.ax.text(cx, y - lh2 / 2.0, ln, ha="center", va="center",
                                    fontsize=NOTE_FS, color=INK_SOFT, zorder=5)
                    register_box(d.ax, art, x0, row_y, node_w, node_h)
                    y -= lh2
            boxes[key] = dict(x=x0, y=row_y, w=node_w, h=node_h, cx=cx,
                              cy=row_y + node_h / 2.0, layer=li,
                              lay_top=y_top, lay_bottom=y0)
            order.append(key)

    # ---------------------------------------------------------------- 连线
    # 多条线汇入同一模块时，入点沿目标框顶边错开，否则几条线会叠成一根
    incoming: dict[str, int] = {}
    for link in sp.get("links") or []:
        if str(link.get("kind", "forward")) == "return":
            continue
        key = str(link.get("to", ""))
        incoming[key] = incoming.get(key, 0) + 1
    seen_in: dict[str, int] = {}

    _z = [6.0]

    def _next_z() -> float:
        _z[0] += 0.03
        return _z[0]

    def _kind_of(link) -> str:
        a, b = boxes[str(link.get("from", ""))], boxes[str(link.get("to", ""))]
        if str(link.get("kind", "forward")) == "return" or b["layer"] < a["layer"]:
            return "return"
        return "side" if a["layer"] == b["layer"] else "layer"

    # 前向线先画、回流线后画：回流线是「后笔」，在交点处给前向线开白口（下面那条
    # 断开、上面那条连续）——这就是印刷上的跳线；同时回流车道选侧时能看见所有前向线。
    links_all = list(sp.get("links") or [])
    ordered = ([lk for lk in links_all if _kind_of(lk) != "return"]
               + [lk for lk in links_all if _kind_of(lk) == "return"])

    for link in ordered:
        a_key, b_key = str(link.get("from", "")), str(link.get("to", ""))
        if a_key not in boxes or b_key not in boxes:
            raise ValueError(
                f"architecture(): 连线引用了不存在的模块「{a_key}」→「{b_key}」")
        a, b = boxes[a_key], boxes[b_key]
        kind = _kind_of(link)
        lbl = link.get("label")
        route = link.get("route")
        z = _next_z()
        if kind == "return":
            _return_link(d, a, b, lbl, route=route, zorder=z)
        elif kind == "side":
            _side_link(d, a, b, lbl, route=route, strict=strict, zorder=z,
                       what=f"{a_key}→{b_key}")
        else:
            n_in = incoming.get(b_key, 1)
            k = seen_in.get(b_key, 0)
            seen_in[b_key] = k + 1
            dx = (k - (n_in - 1) / 2.0) * 0.40 if n_in > 1 else 0.0
            _layer_link(d, a, b, lbl, dx_entry=dx, route=route, strict=strict,
                        zorder=z, what=f"{a_key}→{b_key}")

    for _place in d._deferred:               # 回流标注：等所有连线登记完再落位
        _place()

    note_text = note if note is not None else sp.get("footnote")
    d.footnote(note_text)
    try:
        check_box_overflow(d.ax, strict=strict, debug=debug)
        check_text_hits(d.ax, strict=strict, debug=debug,
                        ignore=sorted(d._intentional) or None)
    except (TextOverflowError, TextLineCollision):
        raise
    return d.ax


# --------------------------------------------------------------------------- 连线
def _register_band(ax, x: float, y: float, w: float, h: float):
    """把层带四条边登记成碰撞源：文字压到带边框会在复核里报出来。"""
    for seg in ([(x, y), (x + w, y)], [(x, y + h), (x + w, y + h)],
                [(x, y), (x, y + h)], [(x + w, y), (x + w, y + h)]):
        register_link(ax, seg, lw=BORDER_LW)


def _cut(d: Diagram, x: float, y: float):
    """在层带边框上开一个白口；``layer_border="none"`` 时没有框可断，直接跳过。"""
    if getattr(d, "_layer_border", "ink") == "ink":
        border_gap(d.ax, x, y, half=BORDER_BREAK)


def _cut_path(d: Diagram, pts):
    """整条路径与层带边框的交点全部开白口（竖腿穿框处，逐层算，不靠调用方数）。"""
    for p0, p1 in zip(pts[:-1], pts[1:]):
        if abs(p1[0] - p0[0]) > 1e-6:          # 只有竖腿会穿横边框
            continue
        x = p0[0]
        lo, hi = sorted((p0[1], p1[1]))
        for bx, by, bw, bh in getattr(d, "_bands", []):
            if not (bx - 1e-6 <= x <= bx + bw + 1e-6):
                continue
            for row in (by, by + bh):
                if lo + 1e-6 < row < hi - 1e-6:
                    _cut(d, x, row)


def _auto_columns(layers, links, n_max: int, *, rounds: int = 3) -> dict:
    """按邻居列位重心给模块分列（``spec["auto_cols"]`` 打开时用）。

    每一轮：每个模块取「与之相连的**其它层**模块列位的平均」作为期望列，按期望
    排序后依次放置，相邻两个至少隔 1 列（模块宽 + 间距的物理下限），整体夹回
    ``[0, n_max-1]``。三轮足够收敛（层数通常 3–4）。

    Returns
    -------
    dict
        ``{模块 key: 列号}``（列号可为半格）。
    """
    idx: dict[str, int] = {}
    pos: dict[str, float] = {}
    for li, lay in enumerate(layers):
        cols = _columns(len(lay["nodes"]), n_max)
        for ni, nd in enumerate(lay["nodes"]):
            k = _node_key(nd, ni)
            idx[k] = li
            pos[k] = (float(nd["col"]) if nd.get("col") is not None else float(cols[ni]))
    for _ in range(max(1, rounds)):
        for li, lay in enumerate(layers):
            keys = [_node_key(nd, i) for i, nd in enumerate(lay["nodes"])]
            des: list[float] = []
            for k in keys:
                vals = []
                for lk in links:
                    a, b = str(lk.get("from", "")), str(lk.get("to", ""))
                    if a == k and b in pos and idx.get(b, li) != li:
                        vals.append(pos[b])
                    elif b == k and a in pos and idx.get(a, li) != li:
                        vals.append(pos[a])
                des.append(sum(vals) / len(vals) if vals else pos[k])
            order = sorted(range(len(keys)), key=lambda i: des[i])
            p = [0.0] * len(keys)
            prev = -1e9
            for i in order:                     # 保序 + 最小 1 列
                p[i] = max(des[i], prev + 1.0)
                prev = p[i]
            over = p[order[-1]] - (n_max - 1)
            if over > 0:                        # 右溢出：整体左移
                p = [v - over for v in p]
            low = min(p)
            if low < 0:                         # 左溢出：整体右移
                p = [min(float(n_max - 1), v - low) for v in p]
            for i, k in enumerate(keys):
                pos[k] = p[i]
    return pos


def _check_runs(pts, *, strict: bool, what: str, limit: float = MAX_RUN):
    """长横穿检查：单段水平腿超过 ``limit`` 就报出来（strict 时抛，否则警告）。"""
    bad = [(p0, p1) for p0, p1 in zip(pts[:-1], pts[1:])
           if abs(p1[0] - p0[0]) > limit + 1e-9]
    if not bad:
        return
    p0, p1 = max(bad, key=lambda s: abs(s[1][0] - s[0][0]))
    run = abs(p1[0] - p0[0])
    msg = (f"architecture(): 连线「{what}」有一段水平位移 {run:.2f}in，超过上限 "
           f"{limit:.2f}in（1.2×列距）；请给该 link 加 route 点指定走法，"
           "或在 spec 里写 auto_cols: true 让渲染器按连线关系重排层内列位")
    if strict:
        raise ValueError(msg)
    print("warning: " + msg)


def _cross_point(p0, p1, q0, q1):
    """两条线段的**真交点**（端点相接、共线重叠都不算），无交点返回 ``None``。"""
    def ori(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    d1, d2 = ori(q0, q1, p0), ori(q0, q1, p1)
    d3, d4 = ori(p0, p1, q0), ori(p0, p1, q1)
    if abs(d1) < 1e-12 or abs(d2) < 1e-12 or abs(d3) < 1e-12 or abs(d4) < 1e-12:
        return None
    if (d1 > 0) == (d2 > 0) or (d3 > 0) == (d4 > 0):
        return None
    t = d1 / (d1 - d2)
    return (p0[0] + t * (p1[0] - p0[0]), p0[1] + t * (p1[1] - p0[1]))


def _yield_crossings(d: Diagram, pts, *, zorder: float):
    """后画的线在上：在它与**已画线**的每个交点处，给下面那条开 :data:`CROSS_GAP` 白口。

    白口画成一小段垂直于**下面那条线**的白线，线宽 = ``CROSS_GAP``（沿下线的方向
    正好吃掉 0.06in），长度 = 下线的线宽 + 抗锯齿余量。zorder 夹在下线和新线之间，
    所以新线连续、下线断开——这就是印刷上「跳线」的等价做法。
    """
    drawn = d.ax.__dict__.get("_afg_drawn") or []
    if not drawn:
        return
    half = 0.02
    for q0, q1 in zip(pts[:-1], pts[1:]):
        for p0, p1, _z in drawn:
            hit = _cross_point(q0, q1, p0, p1)
            if hit is None:
                continue
            x, y = hit
            if abs(p1[1] - p0[1]) < 1e-9:       # 下线水平 → 竖向白口
                d.ax.plot([x, x], [y - half, y + half], color=PAPER,
                          lw=CROSS_GAP * 72.0, solid_capstyle="butt",
                          zorder=zorder)
            else:                               # 下线竖直 → 横向白口
                d.ax.plot([x - half, x + half], [y, y], color=PAPER,
                          lw=CROSS_GAP * 72.0, solid_capstyle="butt",
                          zorder=zorder)


def _draw(d: Diagram, pts, *, ls: str = "-", zorder: float = 6.0):
    """画一条连线：先给旧线让位 → 开穿框白口 → 画线 → 登记（供后面的线让位）。"""
    _yield_crossings(d, pts, zorder=zorder - 0.002)
    register_link(d.ax, pts, lw=0.9)
    _cut_path(d, pts)
    arrow(d.ax, pts, color=INK, lw=0.9, ls=ls, zorder=zorder)
    d.ax.__dict__.setdefault("_afg_drawn", []).extend(
        [(p0, p1, zorder) for p0, p1 in zip(pts[:-1], pts[1:])])


def _route_pts(a: dict, b: dict, route, y_start: float, y_end: float, bx: float):
    """把 ``link["route"]`` 的中间点接成完整路径：源框边 → 各 route 点 → 目标框边。"""
    mid = [(float(p[0]), float(p[1])) for p in route]
    return [(a["cx"], y_start)] + mid + [(bx, y_end)]


def _route_label(pts):
    """给带 route 的线找标注落点：取最长一段的中点，返回 ``(x, y)``。"""
    seg = max(zip(pts[:-1], pts[1:]), key=lambda s: abs(s[1][0] - s[0][0])
              + abs(s[1][1] - s[0][1]))
    return ((seg[0][0] + seg[1][0]) / 2.0, (seg[0][1] + seg[1][1]) / 2.0)


def _layer_link(d: Diagram, a: dict, b: dict, lbl, dx_entry: float = 0.0,
                route=None, strict: bool = True, zorder: float = 6.0, what: str = ""):
    """跨层前向：同列直落，异列走「下—横—下」正交折线。

    ``dx_entry`` 让汇入同一模块的几条线在目标框顶边错开落点。横向行程落在
    **层间空档**（层带上下边框之间，0.34in）里，不会压在任何一条框线上。
    ``route`` 给定时改走显式点（规格里的 ``[[x, y], …]``，单位英寸），用于
    布局本身注定要跨远距离的场合；没有 route 而横穿超过 :data:`MAX_RUN` 时，
    ``strict=True`` 会抛 :class:`ValueError`——不默默画一条难读的线。
    """
    y_a = a["y"]                      # 源框底边
    y_b = b["y"] + b["h"]             # 目标框顶边
    bx = b["cx"] + dx_entry
    mid = None
    if route:
        pts = _route_pts(a, b, route, y_a, y_b, bx)
        mid = _route_label(pts)
    elif abs(a["cx"] - bx) < 1e-3:
        pts = [(a["cx"], y_a), (bx, y_b)]
    else:
        y_mid = (a["lay_bottom"] + b["lay_top"]) / 2.0     # 层间空档正中
        pts = [(a["cx"], y_a), (a["cx"], y_mid), (bx, y_mid), (bx, y_b)]
        mid = ((a["cx"] + bx) / 2.0, y_mid)
    _check_runs(pts, strict=strict, what=what or "?→?",
                limit=getattr(d, "_max_run", MAX_RUN))
    _draw(d, pts, zorder=zorder)
    if lbl:
        if mid is None:                                   # 直落：标注贴线右侧
            label(d.ax, a["cx"] + LABEL_GAP, (y_a + y_b) / 2.0, str(lbl),
                  fs=NOTE_FS, color=INK_SOFT, ha="left")
        else:                                             # 折线：标注压在横线上（白底兜住）
            label(d.ax, mid[0], mid[1], str(lbl), fs=NOTE_FS, color=INK_SOFT,
                  bbox=True)


def _side_link(d: Diagram, a: dict, b: dict, lbl, *, route=None,
               strict: bool = True, zorder: float = 6.0, what: str = ""):
    """同层横向：右出左进；目标在左时绕框顶与层带标题之间的空档走。"""
    if route:
        pts = [(a["cx"], a["cy"])] + [(float(p[0]), float(p[1])) for p in route] \
            + [(b["cx"], b["cy"])]
    elif b["cx"] > a["cx"]:
        x0, x1 = a["x"] + a["w"], b["x"]
        y = a["cy"]
        pts = [(x0, y), (x1, y)]
    else:
        # 框顶到层带标题之间有一条 0.09in 的空档：绕这里不会压到标题，也不用出带
        y_route = max(a["y"] + a["h"], b["y"] + b["h"]) + 0.05
        x0, x1 = a["cx"], b["cx"]
        pts = [(x0, a["y"] + a["h"]), (x0, y_route), (x1, y_route), (x1, b["y"] + b["h"])]
    _check_runs(pts, strict=strict, what=what or "?→?",
                limit=getattr(d, "_max_run", MAX_RUN))
    _draw(d, pts, zorder=zorder)
    if lbl:
        lx, ly = _route_label(pts) if route else ((pts[0][0] + pts[-1][0]) / 2.0, pts[0][1])
        label(d.ax, lx, ly + 0.06, str(lbl), fs=NOTE_FS, color=INK_SOFT, bbox=True)


def _free_label_y(d: Diagram, x: float, text: str, fs: float, lean: float,
                  y_lo: float, y_hi: float, *, gap: float = LABEL_GAP):
    """在竖直空档 ``[y_lo, y_hi]`` 里给「贴线标注」找一个不压线的 y。

    层间空档只有 :data:`LAYER_GAP` 高，前向线的横向腿也走这条走廊；标注若固定放
    在空档中心就会骑在横线上。这里按实测字宽/行高搭出标注矩形，从空档顶部每
    0.02in 向下试位，取第一个不与已登记线段（含层带边框）相交的位置。

    Returns
    -------
    float | None
        可用位置；空档塞不下（或全被线段占住）时返回 ``None``，由调用方换一侧。
    """
    links = d.ax.__dict__.get("_afg_links") or []
    w = d.measure.width(text, fs)
    h = d.measure.line_height(fs)
    pad = 0.02                     # ≈1.4pt，给 check_text_hits 的 1pt 余量留空间
    x0 = x + gap if lean > 0 else x - gap - w
    top = y_hi - h / 2.0 - pad
    bottom = y_lo + h / 2.0 + pad
    if top < bottom:
        return None
    y = top
    while y >= bottom:
        rect = (x0, y - h / 2.0, x0 + w, y + h / 2.0)
        if not any(seg_hits_rect(p0, p1, rect) for p0, p1, _ in links):
            return y
        y -= 0.02
    return None


def _stub(d: Diagram, p0, p1, *, ln: float = 0.07):
    """在虚线起点补一小段实线。

    matplotlib 的虚线相位从路径起点算起，落到起点上时常是「空档」，看上去线没
    接到框上；补 0.07in 实线（≈5pt，比 4pt 虚线段略长）保证接得住。
    """
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    dist = (dx * dx + dy * dy) ** 0.5
    if dist <= 1e-9:
        return None
    t = min(ln / dist, 1.0)
    return line(d.ax, [p0, (p0[0] + dx * t, p0[1] + dy * t)],
                color=INK, lw=0.9, zorder=6)


def _place_return_label(d: Diagram, lbl: str, x_a: float, x_b: float,
                        lean: float, span, lbl_y: float):
    """回流线标注落位（延迟到全部连线登记之后执行，避开后画的前向线）。

    折线情形自己按「以 x 为中心」的矩形试位——:func:`_free_label_y` 是按左/右对齐
    算框的，两者混用会把标注放到没校验过的位置（fig01 的「闭环校正」就是这样压到
    前向线横腿上的）。
    """
    h = d.measure.line_height(NOTE_FS)
    w = d.measure.width(lbl, NOTE_FS)
    links = d.ax.__dict__.get("_afg_links") or []
    if abs(x_a - x_b) < 1e-3:                     # 标注贴车道外侧，不压线
        # 层间空档只有 0.34in：前向线的横腿 + 竖腿常把车道两侧都占掉。由近及远
        # 试若干横向偏移，取第一个能放下字的位置（最远 0.5in，仍在车道旁边）。
        for side in (lean, -lean):
            for off in (LABEL_GAP, LABEL_GAP + 0.08, LABEL_GAP + 0.16,
                        LABEL_GAP + 0.24, LABEL_GAP + 0.32, LABEL_GAP + 0.40):
                x_edge = x_a + side * off
                x0 = x_edge if side > 0 else x_edge - w
                y = _search_y(x0, w, h, span, links)
                if y is not None:
                    label(d.ax, x_edge, y, lbl, fs=NOTE_FS, color=INK_SOFT,
                          ha="left" if side > 0 else "right", va="center")
                    return
        # 空档里实在放不下（前向横腿 + 竖腿两头占死）：把字压在**自己这条**虚线上，
        # 垫 0.03in 白底——虚线在字下断一小段，这是论文里给竖排反馈线加标注的常规做法。
        y_mid = (min(span) + max(span)) / 2.0
        label(d.ax, x_a + lean * 0.12, y_mid, lbl, fs=NOTE_FS, color=INK_SOFT,
              ha="left" if lean > 0 else "right", va="center", bbox=True)
        d._intentional.add(lbl)
        return
    xc = (x_a + x_b) / 2.0
    y = _search_y(xc - w / 2.0, w, h, span, links)
    if y is not None:
        label(d.ax, xc, y, lbl, fs=NOTE_FS, color=INK_SOFT, ha="center",
              va="center")
        return
    label(d.ax, xc, (min(span) + max(span)) / 2.0, lbl, fs=NOTE_FS,
          color=INK_SOFT, ha="center", va="center", bbox=True)
    d._intentional.add(lbl)


def _search_y(x0: float, w: float, h: float, span, links):
    """在竖直空档 ``span`` 里自上而下找第一个不压线的标注中心 y（找不到返回 None）。"""
    lo, hi = min(span) + h / 2.0 + 0.02, max(span) - h / 2.0 - 0.02
    y = hi
    while y >= lo:
        rect = (x0, y - h / 2.0, x0 + w, y + h / 2.0)
        if not any(seg_hits_rect(p0, p1, rect) for p0, p1, _ in links):
            return y
        y -= 0.02
    return None


def _return_link(d: Diagram, a: dict, b: dict, lbl, *, route=None, zorder: float = 6.0):
    """回流/反馈：**整条**虚线 + 专用侧向车道 + 标注离线 ≥2pt。

    车道相对列中心偏 :data:`RETURN_LANE`（0.16in）：回流线与同列前向线并行而不是
    重合。重合时后画的线会盖住先画的，看上去就成了「半实半虚」的一根线——这正是
    之前 fig01 的假象。整条支路只用一个线型 :data:`RETURN_LS`，拐角半径也统一走
    :data:`CORNER_R`。
    """
    up = b["cy"] > a["cy"]
    lean = 1.0 if a["cx"] <= d.w / 2.0 else -1.0
    if route:                                          # 显式走法：规格说了算
        start = (a["cx"], a["y"] + a["h"]) if up else (a["cx"], a["y"])
        end = (b["cx"], b["y"]) if up else (b["cx"], b["y"] + b["h"])
        pts = [start] + [(float(p[0]), float(p[1])) for p in route] + [end]
        _draw(d, pts, ls=RETURN_LS, zorder=zorder)
        _stub(d, pts[0], pts[1])
        if lbl:
            lx, ly = _route_label(pts)
            label(d.ax, lx, ly + LABEL_GAP * 0.5, str(lbl), fs=NOTE_FS,
                  color=INK_SOFT, bbox=True)
        return
    if abs(a["layer"] - b["layer"]) == 1:              # 相邻层：层间空档折线
        span = ((a["lay_top"], b["lay_bottom"]) if up
                else (a["lay_bottom"], b["lay_top"]))
        # 车道走哪一侧：先试朝画布中线的一侧；若那个空档被前向线的横向腿占住
        # （标注塞不进去），就换另一侧——回流线一变道，也不会再横穿前向线。
        lbl_y = None
        if lbl:
            for side in (lean, -lean):
                yy = _free_label_y(d, a["cx"] + side * RETURN_LANE, str(lbl),
                                   NOTE_FS, side, *span)
                if yy is not None:
                    lean, lbl_y = side, yy
                    break
            if lbl_y is None:                          # 两侧都塞不下：退回原位
                lbl_y = (span[0] + span[1]) / 2.0
        x_a, x_b = a["cx"] + lean * RETURN_LANE, b["cx"] + lean * RETURN_LANE
        if up:
            y_gap = (a["lay_top"] + b["lay_bottom"]) / 2.0
            start = (x_a, a["y"] + a["h"])
            end = (x_b, b["y"])
        else:
            y_gap = (a["lay_bottom"] + b["lay_top"]) / 2.0
            start = (x_a, a["y"])
            end = (x_b, b["y"] + b["h"])
        if abs(x_a - x_b) < 1e-3:
            pts = [start, end]
        else:
            pts = [start, (x_a, y_gap), (x_b, y_gap), end]
        _draw(d, pts, ls=RETURN_LS, zorder=zorder)
        _stub(d, pts[0], pts[1])
        if lbl:
            # 回流先画，标注要等所有连线都登记完再落位，否则会压到后画的前向线
            d._deferred.append(lambda: _place_return_label(
                d, str(lbl), x_a, x_b, lean, span, lbl_y))
        return
    # 跨多层：绕画布最外侧，横线落在层带之外的空白里
    x_a, x_b = a["cx"] + lean * RETURN_LANE, b["cx"] + lean * RETURN_LANE
    x_out = (d.w - 0.07) if lean > 0 else 0.07
    if up:
        y_exit, y_entry = a["lay_top"] + 0.12, b["lay_bottom"] - 0.12
        pts = [(x_a, a["y"] + a["h"]), (x_a, y_exit), (x_out, y_exit),
               (x_out, y_entry), (x_b, y_entry), (x_b, b["y"])]
    else:
        y_exit, y_entry = a["lay_bottom"] - 0.12, b["lay_top"] + 0.12
        pts = [(x_a, a["y"]), (x_a, y_exit), (x_out, y_exit),
               (x_out, y_entry), (x_b, y_entry), (x_b, b["y"] + b["h"])]
    _draw(d, pts, ls=RETURN_LS, zorder=zorder)
    _stub(d, pts[0], pts[1])
    if lbl:
        d._deferred.append(lambda: label(
            d.ax, x_out + lean * LABEL_GAP, (y_exit + y_entry) / 2.0, str(lbl),
            fs=NOTE_FS, color=INK_SOFT,
            rotation=90 if abs(y_exit - y_entry) > 0.5 else 0,
            ha="left" if lean > 0 else "right"))
