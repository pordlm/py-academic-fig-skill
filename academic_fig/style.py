# -*- coding: utf-8 -*-
"""style.py —— 统一论文风格（rcParams）与可复用图元。

风格定位：**白纸 + 墨线 + 低饱和强调色**，像框架图，不像数据看板。
本模块只改视觉，不动数据；所有颜色默认取自 :mod:`academic_fig.palette` 的语义色，
不允许在画图代码里写死色值。

用法：:

    import academic_fig as afg
    afg.apply_theme()
    fig, ax = afg.paper_fig("single")
    afg.axes(ax, box=True)
    ax.plot(x, y, color=afg.palette.BLUE, lw=1.0, marker="o", ms=5)
    afg.legend(ax)                       # 自动挑一个不压数据的角落
    afg.threshold(ax, 0.9, "自设目标")     # 判定线（图注须注明「自设」）
"""
from __future__ import annotations

import warnings
from typing import Sequence

import numpy as np

from . import palette as _pal
from . import typography as _typo

#: 当前生效的配色方案名（apply_theme 写入；图元默认色仍以 palette 语义色为准）
_ACTIVE: dict[str, object] = {"name": "paper-calm", "cjk": True, "font_size": 10.0}

#: 本进程是否已经跑过 apply_theme（示意图入口用它判断“渲染器不自带主题”）
_THEMED: bool = False

#: 自动兜底时是否已经警告过（每个进程只提示一次，别在循环里刷屏）
_THEME_WARNED: bool = False

#: 本进程的主题是**哪个入口**替用户兜底套上的（``None`` = 用户自己 ``apply_theme()``）。
#: 只用于诊断（``save()`` 返回值的 ``auto_theme``），不参与任何渲染判断。
_AUTO_THEMED_BY: str | None = None

#: 判「图例压住数据」时把图例框外扩的像素数（marker 半径 + 无框边缘的视觉余量）
_LEGEND_HIT_PAD: float = 5.0


def is_themed() -> bool:
    """返回当前进程是否已调用过 :func:`apply_theme`。

    示意图渲染器（``academic_fig.diagrams.*``）只画几何、不带主题，
    因此它们会在入口处检查这个标记：没跑过主题就发一次警告并自动补齐。
    数据图渲染器（``academic_fig.plots.*``）虽会自行设置画布底色，但字号、
    刻度、图例等 rcParams 仍来自主题，同理建议先 ``apply_theme()``。
    """
    return _THEMED


def _mark_themed() -> None:
    global _THEMED
    _THEMED = True


def auto_themed() -> bool:
    """本进程的主题是不是**库替用户兜底**套上的（``apply_theme()`` 显式调用过则为 False）。

    只服务诊断：``save()`` 把它写进返回值的 ``auto_theme``，让用户一眼看出
    「字体/字号跟我设的不一样」是兜底造成的，而不是自己写错了。
    """
    return _AUTO_THEMED_BY is not None


def auto_themed_by() -> str | None:
    """兜底是哪个入口触发的（``"paper_fig()"`` / ``"save()"`` / ``"示意图渲染器"``）；显式套过则为 ``None``。"""
    return _AUTO_THEMED_BY


#: 自动兜底提示的统一措辞（``who`` 会被替换成具体入口名）
_THEME_HINT = ("{who}: 还没有调用 apply_theme()，已自动套用 paper-calm；"
               "若要自定义字体/字号，请先显式调用 apply_theme(...)。")


def _ensure_theme(who: str = "academic_fig", *, stacklevel: int = 3) -> bool:
    """内部统一入口：没跑过 :func:`apply_theme` 就套上默认主题，**每个进程只提示一次**。

    这是「漏一行 ``apply_theme()`` 不该换来满屏豆腐块」的唯一兜底点：
    ``paper_fig()`` / ``save()`` / ``diagrams`` 的渲染入口都走这里，别再各写一套。

    判定只认模块级标记 ``_THEMED``（不嗅 ``rcParams``）：用户用别的方式改过
    ``font.family`` 也算“没套主题”，我们仍补一次；反过来，用户**显式**调用过
    ``apply_theme("journal-cns")`` 之后 ``_THEMED`` 已为真，这里绝不覆盖他的选择。

    Parameters
    ----------
    who : str
        触发点名字（写进提示语，如 ``"paper_fig()"``）。
    stacklevel : int
        告警回溯层数，让提示指向用户自己的调用行。

    Returns
    -------
    bool
        True 表示用户已经显式套过主题；False 表示本次是兜底代劳的。
    """
    global _THEME_WARNED, _AUTO_THEMED_BY

    if _THEMED:
        return True
    if not _THEME_WARNED:
        _THEME_WARNED = True
        warnings.warn(_THEME_HINT.format(who=who), UserWarning, stacklevel=stacklevel)
    apply_theme()
    # ``apply_theme()`` 会把 _AUTO_THEMED_BY 清成 None（它无法区分自己是被兜底调用
    # 还是用户直接调用），所以兜底标记在它返回之后再落，别写反了顺序。
    _AUTO_THEMED_BY = who
    return False


def active_palette() -> dict:
    """当前生效的配色方案（``paper-calm`` 或 ``journal-cns``）。"""
    return _pal.get_palette(str(_ACTIVE["name"]))


def ink() -> str:
    """当前方案的主墨色。"""
    return active_palette()["ink"]


def grey() -> str:
    """当前方案的次级灰。"""
    return active_palette()["grey"]


def paper() -> str:
    """当前方案的底色。"""
    return active_palette()["paper"]


def accent(i: int = 0) -> str:
    """当前方案的第 i 个强调色（循环取用）。"""
    accents = list(active_palette()["accents"])
    return accents[i % len(accents)]


def apply_theme(palette: str = "paper-calm", cjk: bool = True, font_size: float = 10) -> None:
    """套用论文统一风格（幂等；可重复调用）。

    Parameters
    ----------
    palette : str
        配色方案名，``"paper-calm"``（默认，简单高级）或 ``"journal-cns"``（CNS 期刊风格）。
        **实测范围**：切换方案会改墨色/灰阶/底色等框架色，并写入 ``axes.prop_cycle``，
        所以裸 ``ax.plot(...)`` / ``ax.bar(...)`` 的循环色也跟着变；但
        ``academic_fig.plots.*`` 里的**语义色**（GOOD/BAD/基线/高亮）与色阶
        （``cmap_seq/div/disc``）始终取 ``palette.py`` 的 paper-calm 常量，
        不会跟着方案走 —— 这是已知限制（见 README「已知限制」）。
    cjk : bool
        是否把中文字体加入字体栈（英文论文可关）。
    font_size : float
        正文字号（默认 10pt），其余字号按 ``typography.TEXT_SIZES`` 比例派生。

    Raises
    ------
    KeyError
        配色方案名不存在时。
    """
    import matplotlib as mpl

    global _AUTO_THEMED_BY

    # 走到这里说明主题是**用户要的**（兜底路径会在本函数返回后再把标记写回去）
    _AUTO_THEMED_BY = None

    p = _pal.get_palette(palette)  # 未知方案 → 明确 KeyError
    _ACTIVE.update(name=palette, cjk=bool(cjk), font_size=float(font_size))

    _typo.ensure_registered()
    stack = _typo.font_stack(cjk=cjk)
    body = float(font_size)
    scale = body / 10.0
    ink_color = p["ink"]
    grey_color = p["grey"]

    mpl.rcParams.update({
        # ---- 画布 / 背景
        "figure.facecolor": p["paper"],
        "axes.facecolor": p["paper"],
        "savefig.facecolor": p["paper"],
        "figure.dpi": 150,
        "figure.constrained_layout.use": False,

        # ---- 字体（Windows 路径优先，粗体单独走黑体）
        "font.family": stack,
        "font.serif": stack,
        "font.sans-serif": stack,
        "font.size": body,
        "font.weight": "normal",
        "axes.titlesize": _typo.TEXT_SIZES["title"] * scale,
        "axes.titleweight": "normal",
        "axes.labelsize": _typo.TEXT_SIZES["label"] * scale,
        "xtick.labelsize": _typo.TEXT_SIZES["tick"] * scale,
        "ytick.labelsize": _typo.TEXT_SIZES["tick"] * scale,
        "legend.fontsize": _typo.TEXT_SIZES["legend"] * scale,
        "figure.titlesize": _typo.TEXT_SIZES["title"] * scale,
        "text.usetex": False,
        "axes.unicode_minus": False,
        "mathtext.fontset": "stix",

        # ---- 轴线 / 刻度
        "axes.linewidth": 0.8,
        "axes.edgecolor": ink_color,
        "axes.labelcolor": ink_color,
        "axes.titlecolor": ink_color,
        "axes.grid": False,
        "axes.axisbelow": True,
        "axes.labelpad": 3.0,
        "axes.titlepad": 6.0,
        "text.color": ink_color,
        "xtick.color": ink_color,
        "ytick.color": ink_color,
        "xtick.direction": "in",
        "ytick.direction": "in",
        "xtick.major.width": 0.8,
        "ytick.major.width": 0.8,
        "xtick.major.size": 3.5,
        "ytick.major.size": 3.5,
        "xtick.minor.width": 0.6,
        "ytick.minor.width": 0.6,
        "xtick.minor.size": 2.0,
        "ytick.minor.size": 2.0,
        "xtick.top": False,
        "ytick.right": False,

        # ---- 线条 / 图例
        "lines.linewidth": 1.0,
        "lines.markersize": 5.0,
        "lines.solid_capstyle": "round",
        "patch.linewidth": 0.8,
        # 裸 ax.plot / ax.bar 的循环色也用色板（否则落到 matplotlib 默认 C0 #1F77B4，
        # 会被自家 check 判 color error）；换 palette 时这一项跟着变
        "axes.prop_cycle": mpl.cycler(color=[str(c) for c in p["categorical"]]),
        "grid.color": grey_color,
        "grid.linewidth": 0.6,
        "legend.edgecolor": grey_color,
        "legend.frameon": False,
        "legend.labelspacing": 0.35,
        "legend.handlelength": 1.6,
        "legend.borderaxespad": 0.4,
        "legend.borderpad": 0.2,
        "legend.columnspacing": 1.2,

        # ---- 导出
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.02,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "svg.fonttype": "none",
    })
    _mark_themed()


def axes(ax, box: bool = True, equal: bool = False):
    """统一坐标轴：白底、无网格、四边细框（0.8pt 墨色）、刻度朝内 3.5pt。

    **幂等**：对同一坐标轴重复调用不会叠加效果，所以 ``apply_theme()`` 之后
    任何手写 matplotlib 代码都可以在最后一律调一次 ``afg.style_axes(ax)`` 收口。

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        目标坐标轴。
    box : bool
        ``True``（默认，符合 ``docs/ARCH.md`` §3 的「0.8pt 四边框」）四边都有细框；
        ``False`` 只留左/下（部分示意图更轻，但数据图请保持四边）。
    equal : bool
        ``True`` 时强制等比例（空间图/几何图必须），并用 ``set_box_aspect(1)`` 保证不变形。

    Returns
    -------
    matplotlib.axes.Axes
        传入的 ``ax``。
    """
    ax.set_facecolor(paper())
    ax.grid(False)
    for name, spine in ax.spines.items():
        spine.set_visible(True if box else name in ("left", "bottom"))
        spine.set_linewidth(0.8)
        spine.set_color(ink())
        spine.set_zorder(4)
    ax.tick_params(axis="both", which="major", direction="in", width=0.8,
                   length=3.5, color=ink(), labelcolor=ink(),
                   labelsize=_typo.TEXT_SIZES["tick"])
    ax.tick_params(axis="both", which="minor", direction="in", width=0.6,
                   length=2.0, color=ink(), labelcolor=ink())
    ax.xaxis.label.set_size(_typo.TEXT_SIZES["label"])
    ax.yaxis.label.set_size(_typo.TEXT_SIZES["label"])
    ax.title.set_size(_typo.TEXT_SIZES["title"])
    ax.title.set_fontweight("normal")
    import matplotlib as _mpl
    _mpl.rcParams["axes.unicode_minus"] = False
    if equal:
        square(ax)
    return ax


def square(ax):
    """空间图：等比例坐标轴 + 正方形绘图区（几何/覆盖/可达性图必用）。"""
    ax.set_aspect("equal", adjustable="box")
    ax.set_box_aspect(1)
    return ax


# ---------------------------------------------------------------- 图元
def refline(ax, y: float | None = None, x: float | None = None, *,
            color: str | None = None, lw: float = 0.9, ls=(0, (4, 3)),
            label: str | None = None, zorder: float = 1.2):
    """参考线（水平/垂直）：细虚线，语义为「参考结构 / 基线」，不是拟合结果。

    ``y`` 与 ``x`` 至少给一个；都给时画两条。图注要说明这条线是什么（基线/参考结构）。
    """
    if y is None and x is None:
        raise ValueError("refline(): y 与 x 至少给一个")
    color = color or _pal.GREY
    artists = []
    if y is not None:
        artists.append(ax.axhline(float(y), color=color, lw=lw, ls=ls, zorder=zorder,
                                  label=label))
    if x is not None:
        artists.append(ax.axvline(float(x), color=color, lw=lw, ls=ls, zorder=zorder,
                                  label=None if y is not None else label))
    return artists[0] if len(artists) == 1 else artists


def reference_circle(ax, radius: float, xy: tuple[float, float] = (0.0, 0.0), *,
                     label: str | None = None, lw: float = 0.9,
                     color: str | None = None, ls=(0, (4, 3))):
    """参考圆：细虚线、不填充（目标区域/探测半径之类的「参考结构」）。"""
    if radius <= 0:
        raise ValueError(f"reference_circle(): radius 必须为正（收到 {radius!r}）")
    theta = np.linspace(0.0, 2.0 * np.pi, 720)
    line, = ax.plot(xy[0] + radius * np.cos(theta), xy[1] + radius * np.sin(theta),
                    color=color or _pal.GREY, lw=lw, ls=ls, zorder=1, label=label)
    return line


def _renderer(fig):
    """拿一个可用的 renderer（Agg 直接取；其它后端先 draw 一次）。"""
    canvas = fig.canvas
    getter = getattr(canvas, "get_renderer", None)
    if callable(getter):
        try:
            return getter()
        except Exception:
            pass
    try:
        canvas.draw()
    except Exception:
        return None
    return getattr(canvas, "renderer", None)


def _artist_points(ax) -> list[tuple[float, float]]:
    """收集坐标轴里所有「可能被图例压住」的数据点（散点、线、柱顶）。"""
    pts: list[tuple[float, float]] = []
    for coll in ax.collections:
        try:
            offs = coll.get_offsets()
        except Exception:
            continue
        if offs is None or len(offs) == 0:
            continue
        arr = np.asarray(offs, dtype=float)[:, :2]
        pts.extend(map(tuple, arr[np.isfinite(arr).all(axis=1)].tolist()))
    for line in ax.lines:
        try:
            xy = np.asarray(line.get_xydata(), dtype=float)
        except Exception:
            continue
        if xy.ndim != 2 or len(xy) == 0:
            continue
        step = max(1, len(xy) // 80)
        xy = xy[::step, :2]
        pts.extend(map(tuple, xy[np.isfinite(xy).all(axis=1)].tolist()))
    for patch in ax.patches:
        try:
            bbox = patch.get_bbox()
        except Exception:
            continue
        x0, y0, x1, y1 = bbox.x0, bbox.y0, bbox.x1, bbox.y1
        if all(np.isfinite([x0, y0, x1, y1])):
            pts.extend([(x0, y0), ((x0 + x1) / 2.0, y1), (x1, y1)])
    return pts


def _legend_score(ax, legend, renderer) -> tuple[int, float]:
    """图例得分：压住的点数越少越好，其次占绘图区面积越小越好。

    除数据点外，也把 ``ax.texts`` 里已有的标注算作「会被压住的东西」——
    散点图的 R²/n 这类注释往往正好落在空角，图例若也挑那里就会叠字。

    判定时把图例框外扩 :data:`_LEGEND_HIT_PAD` 像素：无框图例的边缘是透明的，
    marker 半径本身有 3–4px，贴着框边不算「没压住」。
    """
    bbox = legend.get_window_extent(renderer)
    x0, y0 = bbox.x0 - _LEGEND_HIT_PAD, bbox.y0 - _LEGEND_HIT_PAD
    x1, y1 = bbox.x1 + _LEGEND_HIT_PAD, bbox.y1 + _LEGEND_HIT_PAD
    pts = _artist_points(ax)
    inside = 0
    if pts:
        disp = ax.transData.transform(np.asarray(pts, dtype=float))
        inside = int(np.sum(
            (disp[:, 0] >= x0) & (disp[:, 0] <= x1)
            & (disp[:, 1] >= y0) & (disp[:, 1] <= y1)
        ))
    for txt in getattr(ax, "texts", []):
        if not txt.get_visible() or not txt.get_text():
            continue
        try:
            tb = txt.get_window_extent(renderer)
        except Exception:
            continue
        # 与文字框相交即算冲突：文字被压比点被压更难看
        if tb.x1 > x0 and tb.x0 < x1 and tb.y1 > y0 and tb.y0 < y1:
            inside += 3
    ax_bbox = ax.get_window_extent(renderer)
    area = float(bbox.width * bbox.height) / max(1.0, float(ax_bbox.width * ax_bbox.height))
    return inside, area


def legend(ax, loc: str = "auto", *, handles=None, labels=None, ncol: int = 1,
           fontsize: float | None = 9, title: str | None = None, handlelength: float = 1.6,
           labelspacing: float = 0.35, markerscale: float = 1.0,
           frameon: bool = False, **kwargs):
    """无框图例，并自动挑一个不压住数据点的角落。

    ``loc="auto"``（默认）时对四个角落分别试排，按「压住的点数 → 占绘图区面积」择优；
    显式给 ``loc`` 则完全按 matplotlib 语义执行。

    Parameters
    ----------
    handles, labels : sequence, optional
        显式给图例条目（柱状图用 ``Patch`` 代理时必须给），否则从轴上的
        带 label artist 自动收集。

    Returns
    -------
    matplotlib.legend.Legend | None
        没有可画的条目时返回 ``None``。**不会静默覆盖已有图例**：
        自动收集时若轴上已有图例，相同条目直接返回原图例（幂等），
        新条目合并进去（例如分组柱图已经有「方案A/方案B」，你再补一条参考线说明）。
    """
    if handles is None:
        handles, labels = ax.get_legend_handles_labels()
        existing = ax.get_legend()
        if existing is not None:
            # ``Legend`` 没有 ``get_legend_handles_labels()``（那是 ``Axes`` 的方法）；
            # 直接读图例自己的 handles 与文字，否则「合并且不覆盖」这条承诺一调就崩。
            old_handles = list(getattr(existing, "legend_handles", None)
                               or getattr(existing, "legendHandles", None) or [])
            old_labels = [t.get_text() for t in existing.get_texts()]
            known = set(old_labels)
            extra = [(h, l) for h, l in zip(handles, labels)
                     if l and not str(l).startswith("_") and l not in known]
            if not extra:
                return existing          # 已有图例覆盖同样条目：原样返回，不重画
            handles = list(old_handles) + [e[0] for e in extra]
            labels = list(old_labels) + [e[1] for e in extra]
            existing.remove()
    if labels is None:
        labels = [h.get_label() for h in handles]
    handles = list(handles)
    labels = list(labels)
    if not handles:
        return None
    cfg = dict(ncol=ncol, frameon=bool(frameon), fontsize=fontsize,
               handlelength=handlelength, labelspacing=labelspacing,
               markerscale=markerscale, **kwargs)
    if title:
        cfg["title"] = title
    if loc not in ("auto", "best"):
        return ax.legend(handles, labels, loc=loc, **cfg)

    fig = ax.figure
    # 先让 autoscale 落定再测位置：``fill_between``/``errorbar`` 这类集合要到 draw
    # 才把范围算进 viewLim，若此时测，图例是按「更窄的范围」挑的角落；draw 之后
    # 数据往外一撑，图例就正好压在端点 marker 上（样张面板 (b) 就是这么翻车的）。
    #
    # 但这里**绝不能** ``ax.relim()``：它的语义是「按 artist 重算 dataLim」，对
    # scatter/PathCollection + 回归线这类组合会把 dataLim 收缩（实测 y 从
    # (−1.29, 1.17) 缩到 (−1.04, 0.93)），随后 ``autoscale_view()`` 就把视窗缩进
    # 数据里——交付图 relation/fig01_scatter 曾有 18/32 个点画到框外。
    # draw() 一次即可：matplotlib 自己的 autoscale 会把集合算进来，不需要我们插手。
    try:
        fig.canvas.draw()
    except Exception:                              # 自定义画布（无 renderer）跳过
        pass
    renderer = _renderer(fig)
    if renderer is None:
        return ax.legend(handles, labels, loc="best", **cfg)

    def _measure(leg) -> tuple[float, float]:
        ext = leg.get_window_extent(renderer)
        return float(ext.width), float(ext.height)

    def _best_corner(use: dict) -> tuple[tuple[int, float], str]:
        best: tuple[tuple[int, float], str] | None = None
        for candidate in ("upper right", "upper left", "lower left", "lower right"):
            leg = ax.legend(handles, labels, loc=candidate, **use)
            score = _legend_score(ax, leg, renderer)
            leg.remove()
            if best is None or score < best[0]:
                best = (score, candidate)
            if score[0] == 0:
                break
        assert best is not None
        return best

    best = _best_corner(cfg)
    if best[0][0] > 0 and ax.get_yscale() == "linear":
        # 四角都被数据压着：在画框内抬出一条刚好够图例的留白带（下界不动），
        # 图例仍留在图内，不侵占页边距，也不会留下大块空白。
        lo, hi = ax.get_ylim()
        span = hi - lo
        if span > 0:
            probe = ax.legend(handles, labels, loc=best[1], **cfg)
            _w_px, leg_h_px = _measure(probe)
            probe.remove()
            ax_box = ax.get_window_extent(renderer)
            ax_w_in = ax_box.width / fig.dpi
            ax_h_px = float(ax_box.height) or 1.0
            # 单栏窄图里三行以上的竖排图例太占高：先试两列，压掉一半行数
            if leg_h_px / ax_h_px > 0.18 and len(handles) >= 3 and ax_w_in < 4.2:
                two = dict(cfg)
                two["ncol"] = 2
                two["handlelength"] = min(two.get("handlelength", 1.6), 1.2)
                two["columnspacing"] = 1.1
                probe2 = ax.legend(handles, labels, loc=best[1], **two)
                w2, h2 = _measure(probe2)
                probe2.remove()
                if w2 / (ax_w_in * fig.dpi) < 0.62 and h2 < leg_h_px:
                    cfg = two
                    leg_h_px = h2
            # 留白带最多占 30%：再多就说明这块画布塞不下这个图例，
            # 与其把数据压成一条，不如让下面"出框"那段接手。
            need = min(leg_h_px / ax_h_px * span * 1.10, 0.30 * span)
            ax.set_ylim(lo, hi + need)
            renderer = _renderer(fig) or renderer
            best = _best_corner(cfg)
    if best[0][0] > 0:
        # 仍然挤不下（数据铺满全图）：宁可出框，也不压数据点。
        # 挂在画框上方、右对齐，并把 panel 标题抬到图例之上，避免叠字。
        outside = dict(cfg)
        outside["ncol"] = cfg.get("ncol", 1) if cfg.get("ncol", 1) > 1 else min(len(handles), 3)
        outside["handlelength"] = min(outside.get("handlelength", 1.6), 1.15)
        outside["handletextpad"] = 0.5
        outside["columnspacing"] = 1.0
        outside["borderaxespad"] = 0.0
        leg = ax.legend(handles, labels, loc="lower right",
                        bbox_to_anchor=(1.0, 1.012), **outside)
        title_left = ax.get_title(loc="left")
        title_txt = title_left or ax.get_title()
        if title_txt:
            ext = leg.get_window_extent(renderer)
            new_pad = 6.0 + ext.height / fig.dpi * 72.0 + 3.0
            ax.set_title(title_txt, fontsize=ax.title.get_fontsize(),
                         fontweight=ax.title.get_fontweight(),
                         loc="left" if title_left else "center",
                         pad=new_pad)
        return leg
    return ax.legend(handles, labels, loc=best[1], **cfg)


def threshold(ax, y: float, label: str | None = None, *, x: float | None = None,
              color: str | None = None, lw: float = 0.9,
              fontsize: float | None = None, ls=(0, (4, 3))):
    """判定线 / 阈值线：默认砖红虚线 + 右端标注。

    这是**自设目标**，不是官方指标；图注必须写明「判定线为自设目标」。
    ``x`` 给定时改画垂直线。
    """
    color = color or _pal.TARGET
    line = refline(ax, y=None if x is not None else float(y),
                   x=x, color=color, lw=lw, ls=ls, zorder=1.5)
    if label:
        size = fontsize if fontsize is not None else _typo.TEXT_SIZES["footnote"]
        if x is None:
            ax.annotate(label, xy=(1.0, float(y)), xycoords=("axes fraction", "data"),
                        xytext=(-3, 3), textcoords="offset points",
                        ha="right", va="bottom", fontsize=size, color=color)
        else:
            ax.annotate(label, xy=(float(x), 1.0), xycoords=("data", "axes fraction"),
                        xytext=(4, -2), textcoords="offset points",
                        ha="left", va="top", rotation=90, fontsize=size, color=color)
    return line


def annotate_point(ax, x: float, y: float, text: str | None = None, *,
                   xytext: tuple[float, float] = (10, 8), arrow: bool = False,
                   color: str | None = None, fontsize: float = None,
                   ha: str = "left", va: str = "bottom", mark: bool = False,
                   marker: str = "o", ms: float = 4.5):
    """只给「关键点」加标注（不要每个点都标数值）。

    ``mark=True`` 时同时画一个空心点强调目标点。
    """
    color = color or _pal.INK
    if mark:
        ax.scatter([x], [y], s=ms ** 2, facecolors="none", edgecolors=color,
                   linewidths=0.9, marker=marker, zorder=6)
    if not text:
        return None
    props = None
    if arrow:
        props = dict(arrowstyle="-", lw=0.7, color=_pal.GREY, shrinkA=0, shrinkB=2)
    return ax.annotate(text, xy=(float(x), float(y)), xytext=xytext,
                       textcoords="offset points", fontsize=fontsize or _typo.TEXT_SIZES["footnote"],
                       color=color, ha=ha, va=va, arrowprops=props, zorder=7)


def shade_region(ax, xmin: float | None = None, xmax: float | None = None,
                 ymin: float | None = None, ymax: float | None = None, *,
                 color: str | None = None, alpha: float = 0.10,
                 label: str | None = None, zorder: float = 0.4):
    """极浅色强调区（可行域 / 判定区 / 置信区），不做渐变、不加阴影。

    用 ``palette.tint()`` 把强调色压成与白底混合的浅色，而不是靠 alpha 叠灰。
    """
    if all(v is None for v in (xmin, xmax)) and all(v is None for v in (ymin, ymax)):
        raise ValueError("shade_region(): 至少给 xmin/xmax 或 ymin/ymax")
    base = color or _pal.BLUE
    face = _pal.tint(base, alpha)
    patch = None
    if any(v is not None for v in (xmin, xmax)):
        lo = 0.0 if xmin is None else float(xmin)
        hi = 1.0 if xmax is None else float(xmax)
        if hi <= lo:
            raise ValueError(f"shade_region(): xmax({hi}) 必须大于 xmin({lo})")
        patch = ax.axvspan(lo, hi, facecolor=face, edgecolor="none",
                           label=label, zorder=zorder)
    if any(v is not None for v in (ymin, ymax)):
        lo = 0.0 if ymin is None else float(ymin)
        hi = 1.0 if ymax is None else float(ymax)
        if hi <= lo:
            raise ValueError(f"shade_region(): ymax({hi}) 必须大于 ymin({lo})")
        patch = ax.axhspan(lo, hi, facecolor=face, edgecolor="none",
                           label=label if patch is None else None, zorder=zorder)
    return patch


# B 包旧名兼容（拷脚本即用）
plot_reference_circle = reference_circle
style_axes = axes


__all__ = [
    "accent",
    "active_palette",
    "annotate_point",
    "apply_theme",
    "axes",
    "grey",
    "ink",
    "is_themed",
    "legend",
    "paper",
    "plot_reference_circle",
    "reference_circle",
    "refline",
    "shade_region",
    "square",
    "style_axes",
    "threshold",
]