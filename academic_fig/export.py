# -*- coding: utf-8 -*-
"""export.py —— 统一导出：PNG + PDF（可加 SVG），写盘后立刻自检尺寸与 DPI。

口径（``docs/ARCH.md`` §3）：

* 位图 ``PNG``：``dpi=300``（投稿最低要求），白底不透明。
* 矢量 ``PDF``：``pdf.fonttype=42``（TrueType 嵌入，文字可选中、可被期刊系统接受）。
* 可编辑 ``SVG``：``svg.fonttype='none'``（保留 ``<text>``，AI/Inkscape 里能改字）。
* 命名：``figNN_name.png`` / ``figNN_name.pdf``；``NN`` 是两位以上序号。

写盘后还会做一次「事后体检」（尺寸、宽高比、PNG dpi、文件是否非空），
不达标只 ``warnings.warn`` 并写进返回值的 ``report`` 里，不打断批量出图；
需要硬失败请用 :func:`academic_fig.checks.check_dir`。
"""
from __future__ import annotations

import contextlib
import os
import re
import sys
import warnings
from pathlib import Path
from typing import Iterable, Sequence

import matplotlib as mpl
import numpy as np

from . import palette as _pal
from . import style as _style
from . import typography as _typo
from .layout import DOUBLE as DOUBLE_IN
from .layout import SINGLE as SINGLE_IN

#: 允许的最小 DPI
MIN_DPI: int = 300
#: 宽高比允许区间（宽/高）
ASPECT_RANGE: tuple[float, float] = (0.6, 2.6)
#: 单张图最长边上限（inch×dpi），防止 bbox_inches='tight' 把图撑爆
MAX_PIXELS: int = 20000
#: 默认格式
DEFAULT_FORMATS: tuple[str, ...] = ("png", "pdf")
#: 支持的所有格式
SUPPORTED_FORMATS: tuple[str, ...] = ("png", "pdf", "svg")
#: 合法院刊宽度（inch）：单栏 / 双栏。README 与 SKILL.md 只许引用这两档。
WIDTH_TARGETS: tuple[float, float] = (SINGLE_IN, DOUBLE_IN)
#: 宽度容差（inch）；与 ``checks.WIDTH_TOL_IN`` 同一个口径
WIDTH_TOL_IN: float = 0.15

#: 文件名规范：fig01_xxx（``fig`` + 1–3 位序号 + 可选后缀）。
#: **只在这里定义一次**——``checks.NAME_RE`` 直接 import 本常量（R-09：两套正则曾不一致）。
NAME_RE = re.compile(r"^fig\d{1,3}(?:[_-][\w\-]+)?$", re.IGNORECASE)

#: 四边统一留白（inch）。0.04in = 300dpi 下 12px，高于 8px 的硬下限；
#: 之所以不用 ``bbox_inches='tight'``，见 :func:`_ink_bbox_inches` 的说明。
#: **不要随手加大**：留白算进页面宽度，栏宽是 3.35/7.0in 的硬指标，0.10in 会把
#: 单栏图顶到 3.56in、超出 ±0.15in 容差（R-04 的实测来历）。
PAD_IN: float = 0.04
#: 四边留白硬下限（px @300dpi）：低于它就算「贴边裁切」
MIN_MARGIN_PX: int = 8
#: 留白补正的目标余量（px）：实测贴边时补到 ``MIN_MARGIN_PX + MARGIN_FIX_PX``，
#: 避免「补完刚好 8px、再抖一次又掉到 7px」
MARGIN_FIX_PX: int = 4


def stem_ok(base: str | Path) -> bool:
    """文件名是否符合 ``figNN_name`` 规范（不允许 ``figNN_`` 之后为空）。"""
    return bool(NAME_RE.match(Path(str(base)).stem))


def _prepare_paths(base: str | Path) -> Path:
    path = Path(str(base))
    if path.suffix.lower().lstrip(".") in SUPPORTED_FORMATS:
        path = path.with_suffix("")  # 允许传 fig01_x.png，自动剥掉扩展名
    if not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _retrofit_default_fonts(fig, prev_family: Sequence[str]) -> int:
    """把「补主题之前创建」的 ``Text`` 从旧默认字体栈改到当前栈上。

    为什么需要它：matplotlib 的 ``Text`` 在**构造时**就把
    ``rcParams["font.family"]`` 抄进自己的 ``FontProperties``（实测 3.9：
    创建时 ``_family == ['sans-serif']``，之后改 rcParams 也不影响这个对象）。
    所以 ``save()`` 里补主题只能救之后的 artist —— 用户先 ``plt.subplots()``
    再 ``set_xlabel("相对误差")`` 的那些文字仍是 DejaVu Sans，中文照样是豆腐块
    （实测 98 条 ``missing from font(s)``）。

    只改「族名与补主题前的默认栈**完全一致**」的 Text：用户显式指定过的字体
    （Arial、Times New Roman 之类）一个字都不动。改动是**永久**的，这是故意的：
    同一个 fig 第二次 ``save()`` 时 ``_ensure_theme()`` 已经返回 True，
    不会再补一次；若不落地，第二次导出的图会重新变成豆腐块。

    Returns
    -------
    int
        实际改写的 Text 个数。
    """
    from matplotlib.text import Text

    stack = list(mpl.rcParams["font.family"])
    if not stack or list(stack) == list(prev_family):
        return 0
    changed = 0
    for txt in fig.findobj(Text):
        try:
            if list(txt.get_fontproperties().get_family()) == list(prev_family):
                txt.set_fontfamily(stack)
                changed += 1
        except Exception:        # 第三方 artist 的自定义 Text 子类，跳过
            continue
    return changed


@contextlib.contextmanager
def _quiet_c_stderr():
    """在 with 块内屏蔽 **C 层** stderr（Python ``warnings`` 管不到的那种）。

    用途只有一处：PDF 后端的 ttconv 会直接往 fd 2 写
    ``MERG NOT subset; don't know how to subset; dropped``。
    这条消息产生于 C 代码，``warnings.filterwarnings`` 拦不住，只能暂时把
    fd 2 指向空设备。窗口极窄（只有 ``savefig`` 那一行），且异常照常抛出，
    不会吞掉真正的错误。
    """
    try:
        fd = sys.stderr.fileno()
    except (AttributeError, OSError, ValueError):      # 无真实 fd（IDE/notebook）
        yield
        return
    sys.stderr.flush()
    saved = os.dup(fd)
    try:
        with open(os.devnull, "w") as devnull:
            os.dup2(devnull.fileno(), fd)
            yield
    finally:
        sys.stderr.flush()
        os.dup2(saved, fd)
        os.close(saved)


def _figure_inches(fig) -> tuple[float, float]:
    try:
        bbox = fig.get_tightbbox(fig.canvas.get_renderer())
        return float(bbox.width), float(bbox.height)
    except Exception:
        return float(fig.get_figwidth()), float(fig.get_figheight())


def _axes_ink_inches(ax, renderer):
    """``axison=False`` 的轴返回**真实墨迹**框（inch 之前的 display 单位），否则 ``None``。

    示意图（桑基、架构图、场量图）常用 ``set_axis_off()``，此时
    ``ax.get_window_extent()`` 仍然是整块画布：桑基图右侧实测有 0.38in 空白被当成
    「墨迹」，裁出来的图右边比左边宽 100px（盲测记为 L7/R105）。这里改成只并可见的
    脊线 + 图元（线/补丁/集合/图像），并夹在轴框内；注释文字与标题由调用方另行登记。
    """
    if getattr(ax, "axison", True):
        return None
    from matplotlib.transforms import Bbox

    try:
        frame = ax.get_window_extent(renderer)
    except Exception:                                   # pragma: no cover
        return None
    boxes = []
    # 不登记脊线：``axison=False`` 时 matplotlib 的 Axes.draw 会整块跳过脊线，
    # 但 Spine.get_visible() 仍返回 True —— 拿它当墨迹会给桑基图右边白送 0.38in
    # （底脊线 bbox 量到 6.83in，实际一像素都没画）。图元自绘的边框走 patches，不受影响。
    for attr in ("lines", "patches", "collections", "images"):
        for artist in getattr(ax, attr, ()):
            try:
                if not artist.get_visible():
                    continue
                bb = artist.get_window_extent(renderer)
            except Exception:                           # pragma: no cover
                continue
            if bb.width > 0 and bb.height > 0:
                boxes.append(bb)
    if not boxes:
        return None
    # 只求并集、**不**夹回轴框：示意图常把标签/箭头放到轴外（样张面板 (f) 的
    # tightbbox 到 7.58in，比画布还宽）；夹回轴框会把溢出图元裁成半个字，
    # 表现出来就是「右边 0px 留白」。
    x0 = min(b.x0 for b in boxes)
    y0 = min(b.y0 for b in boxes)
    x1 = max(b.x1 for b in boxes)
    y1 = max(b.y1 for b in boxes)
    if x1 <= x0 or y1 <= y0:
        return None
    return Bbox.from_extents(float(x0), float(y0), float(x1), float(y1))


def _axes_text_children(ax):
    """轴自己拥有的 ``Text``（含 ``ax.texts`` 漏掉的、用 ``add_artist`` 挂上的）。

    为什么不用 ``ax.texts``：matplotlib 3.9 里它不等于 ``ax.get_children()`` 的
    Text 子集——样张面板 (f) 的面板标题就是这么漏掉的，标题右端到 7.58in 却算不进
    包围盒，裁出来右边 0px 留白、字被切一半。
    ``getattr(child, "axes", None) is not ax`` 用来滤掉空图 axes 的幽灵刻度 Text。
    """
    from matplotlib.text import Text

    seen, out = set(), []
    candidates = list(ax.get_children()) + [
        ax.title, ax.xaxis.label, ax.yaxis.label,
        ax.xaxis.get_offset_text(), ax.yaxis.get_offset_text(),
    ]
    for child in candidates:
        if not isinstance(child, Text) or id(child) in seen:
            continue
        if getattr(child, "axes", None) is not ax:
            continue
        seen.add(id(child))
        out.append(child)
    return out


def _ink_bbox_inches(fig, renderer, pad_in: float, dpi: int):
    """所有可见图元的并集包围盒（inch），向外对齐到 1/dpi 的整数倍。

    为什么不用 ``bbox_inches='tight'``
    ----------------------------------
    matplotlib 的 tight bbox 对**旋转文字**（纵轴标签）估得偏小，300dpi 下能差出
    20–30px：实测样张左侧只剩 1px、``fig05`` 上边只剩 1px，等于贴边裁切。
    这里改成「自底向上」求并集——figure 的 tightbbox + 每个 axes 的窗口框 +
    每个非空可见 ``Text``（含旋转标签、面板编号、图注）+ 每个图例，任何一项被
    tight 漏掉都不影响结果。

    Parameters
    ----------
    fig : matplotlib.figure.Figure
    renderer : 渲染器（必须已 draw 过一次）
    pad_in : float
        四边留白（inch）。
    dpi : int
        输出分辨率；用于把边界向外取整到整像素，保证 PNG 尺寸是可解释的整数。

    Returns
    -------
    matplotlib.transforms.Bbox
        以 inch 为单位、可直接交给 ``savefig(bbox_inches=...)`` 的包围盒。
        PNG 像素尺寸公式：``px = dpi × (W_ink + 2×pad_in)``（W_ink 已向外取整）。
    """
    from matplotlib.transforms import Bbox

    inv = fig.dpi_scale_trans.inverted()
    boxes = []

    def add(bbox) -> None:
        if bbox is None:
            return
        try:
            if bbox.width <= 0 or bbox.height <= 0:
                return
            if not np.isfinite([bbox.x0, bbox.y0, bbox.x1, bbox.y1]).all():
                return
        except Exception:  # pragma: no cover - 防御性
            return
        boxes.append(bbox)

    def add_text(text_artist) -> None:
        """登记一个 Text；空串/不可见/非本图的一律跳过。"""
        try:
            if text_artist is None or not text_artist.get_visible():
                return
            if not str(text_artist.get_text()).strip():
                return
            if text_artist.get_figure() is not fig:
                return
            add(text_artist.get_window_extent(renderer).transformed(inv))
        except Exception:  # pragma: no cover
            return

    # 刻意**不**登记 fig.get_tightbbox()：它就是「所有 axes 的 tightbbox 并集」，
    # 对 axison=False 的示意图等于把整块空轴框算成墨迹（桑基图右侧多出 0.38in，
    # 裁完 L31/R131）。下面逐项登记已经覆盖了它包含的一切（轴框/刻度/标题/图例/
    # fig.texts），且能对关闭了轴的图按真实图元收边。

    # 注意：**不要**用 fig.findobj(Text)，也**不要**直接量刻度/轴标签/标题的
    # get_window_extent —— 两者都会给出失效坐标：
    #   * fig.findobj(Text) 连带返回 30 个「幽灵 Text」（空图 axes 的默认刻度等，
    #     get_figure() 指向本图但 transform 早已过期，bbox 形如 (-32.5, 28.8, -9, 46.8)
    #     或 (0,0,1,1)），把并集撑大 0.7in 以上；
    #   * 刻度标签的坐标由每帧 draw 写入，单独调 get_window_extent 会拿到上一帧位置
    #     （实测 x 偏 0.6in），而 Axes.get_tightbbox() 内部走 _update_ticks，是准的。
    # 所以：轴内文字一律交给 ax.get_tightbbox()，这里只补它不管的用户文字与图例。
    for ax in fig.get_axes():
        ink = _axes_ink_inches(ax, renderer)
        if ink is None:
            try:
                add(ax.get_window_extent(renderer).transformed(inv))   # 轴框 + 脊线
            except Exception:  # pragma: no cover
                pass
            try:
                add(ax.get_tightbbox(renderer).transformed(inv))       # 刻度/轴标签/标题
            except Exception:  # pragma: no cover
                pass
        else:
            # 轴关闭（示意图）：轴框当墨迹会白撑 0.3–0.4in，只认真实图元
            add(ink.transformed(inv))
        for artist in _axes_text_children(ax):                     # 注释 / 面板编号
            add_text(artist)
        legend = ax.get_legend()
        if legend is not None:
            try:
                if legend.get_visible():
                    add(legend.get_window_extent(renderer).transformed(inv))
            except Exception:  # pragma: no cover
                pass
    for artist in fig.texts:                                       # 图注 / 整幅标题
        add_text(artist)
    for legend in fig.legends:
        try:
            if legend.get_visible():
                add(legend.get_window_extent(renderer).transformed(inv))
        except Exception:  # pragma: no cover
            pass

    if not boxes:
        return Bbox.from_bounds(0.0, 0.0, float(fig.get_figwidth()),
                                float(fig.get_figheight()))
    union = Bbox.union(boxes)
    x0 = np.floor((union.x0 - pad_in) * dpi) / dpi      # 向外取整 → 留白只多不少
    y0 = np.floor((union.y0 - pad_in) * dpi) / dpi
    x1 = np.ceil((union.x1 + pad_in) * dpi) / dpi
    y1 = np.ceil((union.y1 + pad_in) * dpi) / dpi
    return Bbox.from_extents(float(x0), float(y0), float(x1), float(y1))


def _png_dpi(path: Path) -> float | None:
    """直接从 PNG 头里读 pHYs（不依赖 PIL）。"""
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    idx = 8
    while idx + 8 <= len(raw):
        length = int.from_bytes(raw[idx:idx + 4], "big")
        ctype = raw[idx + 4:idx + 8]
        if ctype == b"pHYs" and idx + 8 + 9 <= len(raw):
            ppu_x = int.from_bytes(raw[idx + 8:idx + 12], "big")
            unit = raw[idx + 16]
            if unit == 1:  # 米
                return round(ppu_x * 0.0254, 2)
            return None
        idx += 12 + length
    return None


_MEDIABOX_RE = re.compile(
    rb"/MediaBox\s*\[\s*(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s*\]")


def _pdf_size_pt(path: Path) -> tuple[float, float] | None:
    """读 PDF 第一页的 MediaBox（pt）。找不到返回 ``None``。"""
    try:
        head = path.read_bytes()[:16384]
    except OSError:
        return None
    m = _MEDIABOX_RE.search(head)
    if not m:
        return None
    x0, y0, x1, y1 = (float(v) for v in m.groups())
    return abs(x1 - x0), abs(y1 - y0)


def _validate_written(paths: dict[str, Path], dpi: int, fig) -> list[str]:
    """写盘后的体检；返回问题清单（只 warning）。

    体检项：文件非空、PNG dpi、宽高比、四边留白（≥ :data:`MIN_MARGIN_PX`）、
    PNG 与 PDF 的页面尺寸是否一致（同一 bbox 导出，差异应当 ≤0.005in）。
    """
    problems: list[str] = []
    for fmt, path in paths.items():
        if not path.exists() or path.stat().st_size == 0:
            problems.append(f"{path.name}: 文件为空或不存在")
            continue
        if fmt == "png":
            actual = _png_dpi(path)
            if actual is None:
                problems.append(f"{path.name}: 读不出 dpi 元数据")
            elif actual + 1 < MIN_DPI:
                problems.append(f"{path.name}: dpi={actual} < {MIN_DPI}")
    png_wh: tuple[int, int] | None = None
    try:
        from matplotlib.image import imread
        if "png" in paths and paths["png"].exists():
            img = imread(paths["png"])
            h, w = img.shape[:2]
            png_wh = (int(w), int(h))
            ratio = w / max(1, h)
            lo, hi = ASPECT_RANGE
            if not lo <= ratio <= hi:
                problems.append(f"{paths['png'].name}: 宽高比 {ratio:.2f} 超出 {lo}–{hi}")
            if dpi:
                width_in = w / float(dpi)
                nearest = min(WIDTH_TARGETS, key=lambda t: abs(width_in - t))
                if abs(width_in - nearest) > WIDTH_TOL_IN:
                    problems.append(
                        f"{paths['png'].name}: 宽度 {width_in:.2f}in 不是单栏 {SINGLE_IN}in "
                        f"也不是双栏 {DOUBLE_IN}in（±{WIDTH_TOL_IN}in）——按栏宽插图会被缩放")
            if max(w, h) > MAX_PIXELS:
                problems.append(f"{paths['png'].name}: 边长 {max(w, h)}px 过大，图注可能没折行")
            from .checks import png_margins      # 延迟导入：避免模块级循环
            margins = png_margins(paths["png"])
            if margins:
                worst = min(margins["left"], margins["right"],
                            margins["top"], margins["bottom"])
                if worst < MIN_MARGIN_PX:
                    problems.append(
                        f"{paths['png'].name}: 四边最小留白 {worst}px < {MIN_MARGIN_PX}px"
                        f"（左 {margins['left']} 右 {margins['right']} "
                        f"上 {margins['top']} 下 {margins['bottom']}）——疑似贴边裁切")
    except Exception:
        pass
    if png_wh and "pdf" in paths and paths["pdf"].exists():
        size = _pdf_size_pt(paths["pdf"])
        if size:
            w_in, h_in = png_wh[0] / dpi, png_wh[1] / dpi
            dw = abs(w_in - size[0] / 72.0)
            dh = abs(h_in - size[1] / 72.0)
            if max(dw, dh) > 0.005:
                problems.append(
                    f"{paths['pdf'].name}: PNG 与 PDF 页面尺寸不一致"
                    f"（宽差 {dw:.3f}in、高差 {dh:.3f}in；应由同一 bbox 导出）")
    return problems


def _width_target(fig, spec) -> float | None:
    """把 ``target_width``（``"auto"``/``"single"``/``"double"``/数字/``None``）解析成 inch。

    ``"auto"``（默认）= 取离当前画布宽度最近的那一档：3.35 上下取单栏、7.0 上下取双栏。
    这样 ``paper_fig("single")`` 出来的图即使被图注撑到 3.5in，也会被回裁到 3.35in；
    而用户自己写 ``plt.figure(figsize=(5,3))`` 的画布仍按最近档处理（不会变成 3.35 的怪比例）。
    """
    if spec is None:
        return None
    if isinstance(spec, str):
        key = spec.strip().lower()
        if key in ("auto", ""):
            w = float(fig.get_figwidth())
            return min(WIDTH_TARGETS, key=lambda t: abs(w - t))
        if key in ("single", "single-column", "single_column"):
            return SINGLE_IN
        if key in ("double", "two-column", "two_column", "double-column"):
            return DOUBLE_IN
        try:
            return float(key)
        except ValueError:
            raise ValueError(
                f"save(): target_width={spec!r} 无法解析；用 'auto' / 'single' / 'double' / 数字")
    target = float(spec)
    if target <= 0:
        raise ValueError(f"save(): target_width 必须为正数（收到 {target}）")
    return target


def _measure_width(fig, w: float, h: float, pad_in: float, dpi: int):
    """把画布设成 ``w×h`` 英寸，返回 ``(墨迹宽 in, renderer, bbox)``。"""
    fig.set_size_inches(w, h)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    bbox = _ink_bbox_inches(fig, renderer, pad_in, dpi)
    return float(bbox.width), renderer, bbox


def _fit_to_width(fig, renderer, bbox, target_w: float, pad_in: float, dpi: int,
                  *, iters: int = 6):
    """把**页面宽度**（含左右留白）缩放到 ``target_w``（±1px），返回 ``(bbox, renderer)``。

    为什么不能直接裁 bbox
    --------------------
    裁掉的是内容（字被切一半）。要让内容适应栏宽，只能改画布尺寸。

    为什么不能「按比例迭代」
    ----------------------
    字号是绝对 pt：画布缩一半，刻度标签/轴标题/图注的**物理宽度不变**，只有轴框按比例缩。
    于是 ``content_w = a·fig_w + b``（``a`` ≈ 轴框占比，``b`` ≈ 文字固定边距）。
    按 ``target/渲染宽`` 迭代会成比例地越过目标，有的图收敛不了（实测出现 4.01in、
    2.84in 两种残差方向相反的失败）。这里改用**割线法**：量两点解出 ``(a, b)``，
    直接解 ``w* = (content_target-b)/a``，再量一次修正。

    为什么不追「不响应」的方向
    ------------------------
    图注是**在 resize 之前**按当时的画布折好的（固定宽度），图例也可能挂在轴外；
    这类元素不随 ``set_size_inches`` 变化，此时继续缩画布只会把图缩成邮票而宽度不变。
    所以探测出响应斜率 ``|a| < 0.25`` 就直接收手，回退到最接近目标的那次布局。

    注意 ``pad_in`` 是**从页面宽里扣掉**的：拟合目标是 ``target_w - 2×pad_in``，
    留白最后再补上，这样 3.35in 是「页面宽」而不是「内容宽 + 随便多少白」。
    """
    from matplotlib.transforms import Bbox

    if bbox is None:
        return bbox, renderer
    w_cur, h_cur = (float(v) for v in fig.get_size_inches())
    content_target = float(target_w) - 2.0 * float(pad_in)

    # 统一用「不含留白」的墨迹宽度做判据
    def _content_at(w: float):
        _, r, _ = _measure_width(fig, w, h_cur, 0.0, dpi)
        return float(_ink_bbox_inches(fig, r, 0.0, dpi).width)

    best_w = w_cur
    best_err = abs(_content_at(w_cur) - content_target)
    lo, hi = 0.55 * w_cur, 2.4 * w_cur
    prev: tuple[float, float] | None = None
    rigid = False                      # 内容宽与画布无关（示意图的英寸版式）
    for _ in range(max(1, iters)):
        if best_err <= 1.0 / dpi:
            break
        width_p = _content_at(best_w)
        if prev is None:
            probe = min(max(best_w * (content_target / max(width_p, 1e-6)), lo), hi)
            if abs(probe - best_w) < 1e-3:
                probe = min(max(best_w * 1.08, lo), hi)
        else:
            probe = min(max(best_w + 0.12, lo), hi)
        w_p, width_p = best_w, width_p
        width_q = _content_at(probe)
        a = (width_q - width_p) / (probe - w_p) if abs(probe - w_p) > 1e-9 else 0.0
        if abs(a) < 0.25:
            # 内容宽度与画布无关（图注/图例固定宽、示意图按英寸铺版）——
            # 缩画布**不会**让内容变窄，只会把它裁掉，所以必须收手。
            rigid = True
            _measure_width(fig, best_w, h_cur, 0.0, dpi)
            break
        b = width_p - a * w_p
        w_next = min(max((content_target - b) / a, lo), hi)
        got = _content_at(w_next)
        err = abs(got - content_target)
        if err < best_err:
            best_w, best_err = w_next, err
        if abs(w_next - probe) < 1e-3:
            break

    # 收尾：停在最优宽度，重新量一次「不含留白」的墨迹宽度
    w_fin = best_w
    width_fin, renderer, _raw = _measure_width(fig, w_fin, h_cur, 0.0, dpi)
    min_pad = MIN_MARGIN_PX / float(dpi)
    # 硬下限再加 5px 余量：matplotlib 的 tight bbox 对**旋转文字**（竖排 y 轴标签）
    # 会估小一点，实测并集左缘比真实墨迹右移 6–8px，照 8px 布留白会掉到 6px。
    pad_floor = max(min_pad, 16.0 / float(dpi))

    # 硬约束：内容必须在「页面宽 - 2×留白」之内，否则四边会被挤成 0px。
    # 割线法偶尔停在偏大的一侧（图注固定宽时目标无解），这里再按经验斜率 0.8 逼几步。
    for _ in range(4 if not rigid else 0):
        room = float(target_w) - 2.0 * pad_floor
        if width_fin <= room + 1e-3:
            break
        w_fin = max(lo, w_fin - (width_fin - room) / 0.8)
        width_fin, renderer, _raw = _measure_width(fig, w_fin, h_cur, 0.0, dpi)

    pad_use = (float(target_w) - width_fin) / 2.0
    pad_use = max(min(pad_use, 0.12), pad_floor)           # 留白 13px…0.12in
    bbox = _ink_bbox_inches(fig, renderer, pad_use, dpi)
    if float(bbox.width) > float(target_w) + 1e-9:
        # 留白已到下限还超宽：只压外框到目标（内容已被保证在 room 之内，不会切字）
        bbox = Bbox.from_extents(float(bbox.x0), float(bbox.y0),
                                 float(bbox.x0) + float(target_w), float(bbox.y1))
    return bbox, renderer


#: 让 PDF/SVG 逐字节可复现的元数据覆盖。
#:
#: matplotlib 默认往 PDF 里写 ``CreationDate``（= 当前时间）、往 SVG 里写 ``Date``，
#: 于是**同一张图两次渲染的 sha256 不同**——``scripts/write_build.py --check``
#: 因此永远绑不住「当前字节」，冷启动一次 build 串就失效（t25 实测：
#: ``assets/style_preview.pdf`` 两次 78E6DDC0… / C74E3F1D…）。
#: 置 ``None`` = 让后端**省略**该键（matplotlib 官方支持的写法），文件从此只由内容决定。
REPRO_METADATA: dict[str, dict[str, None]] = {
    "pdf": {"CreationDate": None, "ModDate": None},
    "svg": {"Date": None},
}


def _deterministic_kwargs(fmt: str, base_kwargs: dict) -> dict:
    """给某个格式补上确定性元数据（PDF 去创建/修改时间，SVG 去日期）。"""
    meta = REPRO_METADATA.get(fmt)
    if not meta:
        return base_kwargs
    kwargs = dict(base_kwargs)
    merged = {**(kwargs.get("metadata") or {}), **meta}
    kwargs["metadata"] = merged
    return kwargs


def _repair_margins(fig, bbox, saved: dict[str, Path], dpi: int, write_kwargs: dict,
                    *, rounds: int = 2):
    """写盘后按**实测**留白补包围盒，缺口补上再重写（返回修好的 bbox）。

    为什么需要：``_ink_bbox_inches`` 算的是「已知图元的并集」，而 matplotlib 的
    ``tight bbox`` 对**旋转/竖排文字**会估小 6–8px；示意图里还有 ``add_artist``
    挂上去、测量时机偏早的图元。实测 ``flow_vertical`` 期望左右各 30px、实际右侧
    只有 1px。与其把这些边角料都猜进去，不如**写完量一次真实像素**，哪边不够
    就往哪边扩，扩完重写（同一 bbox 给 PNG/PDF，尺寸依旧一致）。
    """
    from matplotlib.transforms import Bbox

    if bbox is None or isinstance(bbox, str) or "png" not in saved:
        return bbox

    from .checks import png_margins               # 局部导入：checks 反向依赖 export

    cur = bbox
    for _ in range(max(0, int(rounds))):
        box = png_margins(saved["png"])
        if not box:
            break
        grow = {}
        for side in ("left", "right", "top", "bottom"):
            short = (MIN_MARGIN_PX + MARGIN_FIX_PX) - float(box.get(side, MIN_MARGIN_PX))
            if short > 0:
                grow[side] = short / float(dpi)
        if not grow:
            break
        cur = Bbox.from_extents(
            float(cur.x0) - grow.get("left", 0.0),
            float(cur.y0) - grow.get("bottom", 0.0),
            float(cur.x1) + grow.get("right", 0.0),
            float(cur.y1) + grow.get("top", 0.0),
        )
        kwargs = dict(write_kwargs)
        kwargs["bbox_inches"] = cur
        for fmt, out in saved.items():
            fmt_kwargs = _deterministic_kwargs(fmt, kwargs)
            if fmt == "pdf":
                with _quiet_c_stderr():
                    fig.savefig(out, format=fmt, **fmt_kwargs)
            else:
                fig.savefig(out, format=fmt, **fmt_kwargs)
    return cur


def save(fig, base: str | Path, formats: Sequence[str] = DEFAULT_FORMATS,
         dpi: int = 300, tight: bool = True, *, bbox_inches: str | None = None,
         target_width: float | str | None = "auto",
         transparent: bool = False, validate: bool = True,
         check_name: bool = True,
         report: dict | None = None) -> dict[str, Path | bool | int]:
    """保存一幅图到 ``base``（自动补扩展名），返回 ``{格式: 路径}``。

    **主题兜底**：进到这里时若还没调用过 ``apply_theme()``，会先补 ``paper-calm``
    并提示一次（每进程一次）。对「用户自己 ``plt.subplots()`` 再画」的情形还会
    多走一步：把补主题**之前**创建、仍抄着旧默认字体栈的 ``Text`` 改到当前字体栈
    上——``Text`` 在构造时就把 ``rcParams["font.family"]`` 固化了，光改 rcParams
    救不了它们，中文会继续是豆腐块。显式调用过 ``apply_theme(...)`` 时一个字不动。

    Parameters
    ----------
    fig : matplotlib.figure.Figure
        要保存的图。
    base : str | Path
        输出主名，如 ``examples/out/fig01_bar``；带 ``.png`` / ``.pdf`` / ``.svg``
        时会自动剥掉，统一按 ``formats`` 出全。
    formats : sequence of str
        ``"png"`` / ``"pdf"`` / ``"svg"`` 的任意组合，默认 PNG+PDF。
    dpi : int
        位图分辨率，不得低于 300。
    tight : bool
        ``True`` 时按内容紧裁（图注已折行，不会撑宽）。
    target_width : {"auto", "single", "double"} | float | None
        把输出宽度收到栏宽（默认 ``"auto"``：离画布最近的一档，3.35 或 7.0in）。
        这是「单栏 3.35 / 双栏 7.0」承诺的唯一执行点——``bbox_inches='tight'``
        会按内容外扩（实测单栏图涨到 4.17in），按栏宽插入时整图被缩放、
        10pt 字就变成 8.4pt。传 ``None`` 关掉（不推荐）。
    transparent : bool
        默认不透明（期刊要求白底）。
    validate : bool
        写盘后是否做体检（尺寸/宽度/宽高比/DPI/留白/PNG-PDF 一致），问题以
        ``warnings`` 给出。
    check_name : bool
        是否检查 ``base`` 是否符合 ``figNN_name``。默认 ``True``；封面/样张/拼版
        这类**不是正文插图**的资产（如 ``assets/arch_border_ab``）可传 ``False``
        关掉这条警告，``checks.check_dir`` 侧另有 ``COVER_STEMS`` 把命名降级为 info。
    report : dict, optional
        传入一个 dict 会在其中填入 ``problems`` / ``width_in`` / ``height_in``。

    Returns
    -------
    dict[str, Path | bool | int]
        形如 ``{"png": Path(...), "pdf": Path(...), "auto_theme": True, "font_retrofit": 3}``。
        格式键（``png`` / ``pdf`` / ``svg``）的值**恒为** ``Path``；另有两条诊断键：

        - ``"auto_theme"``：这张图的主题是不是**库替你兜底**套上的（``True`` = 你没调
          ``apply_theme()``，``paper_fig()`` / ``save()`` 替你套了 ``paper-calm`` 并提示过一次；
          显式调过 ``apply_theme(...)`` 则为 ``False``）。
        - ``"font_retrofit"``：**本次调用**被改写到当前字体栈的 ``Text`` 个数，``0`` 表示一个没动
          （你自己套过主题，或主题在写字之前就套好了）。

        只关心路径时用 :func:`figure_paths` 过滤，别直接迭代 ``.items()``。

    Raises
    ------
    ValueError
        ``formats`` 含不支持格式、``dpi`` < 300，或 ``target_width`` 无法解析。
    """
    fmts = [str(f).lower().lstrip(".") for f in formats]
    if not fmts:
        raise ValueError("save(): formats 不能为空")
    bad = [f for f in fmts if f not in SUPPORTED_FORMATS]
    if bad:
        raise ValueError(f"save(): 不支持的格式 {bad}；只能从 {list(SUPPORTED_FORMATS)} 里选")
    if int(dpi) < MIN_DPI:
        raise ValueError(f"save(): dpi={dpi} 低于投稿最低要求 {MIN_DPI}")

    # 兜住「用户自己 plt.subplots() 直接画、从没调过 apply_theme()」的场景：
    # 字体栈里没有中文字形 → PNG 满屏豆腐块。只提示一次，显式主题优先。
    _prev_family = list(mpl.rcParams["font.family"])
    # 本次 save 是否**亲手**兜的底（决定要不要回头改已经建好的 Text）
    _applied_now = not _style._ensure_theme("save()")
    # 对外报的 auto_theme 是「这张图的主题是不是库替你套的」，包含 paper_fig() 早先
    # 兜的那一次——那才是用户真正想知道的（字体/字号为什么跟自己的设置不一样）。
    _auto_theme = _style.auto_themed()
    # 代劳兜底时必须回头修已经建好的 Text（它们在构造时就把旧字体栈抄走了）
    _retrofit = _retrofit_default_fonts(fig, _prev_family) if _applied_now else 0

    path_base = _prepare_paths(base)
    if check_name and not stem_ok(path_base):
        warnings.warn(
            f"save(): 文件名 {path_base.name!r} 不符合 figNN_name 规范"
            f"（例：fig03_radius_sweep），后续整理会很痛苦",
            stacklevel=2,
        )

    # 字体嵌入口径在这幅图上再钉一次（rcParams 可能被外部脚本改过）
    # R2-11：``_fit_to_width`` 必须把画布改成拟合后的宽度才能写出目标栏宽，这让
    # ``save()`` 带了副作用（figsize 7.0 → 7.77）。副作用本身是**出图所必需**的，
    # 但不能漏给调用方：保存完恢复原尺寸，用户手里的 fig 仍是他建的那一幅，
    # 于是「同一 fig 连存两次」「存完继续画/加图注」都不会错位。
    _orig_size = tuple(float(v) for v in fig.get_size_inches())
    with mpl.rc_context({"pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none"}):
        # PDF 后端会往 stderr 打 `MERG NOT subset; don't know how to subset; dropped`
        # （只在中文字体 ttc 子集化时出现）。这是 matplotlib 的**安全降级**：合并失败
        # 的子集直接丢弃、改用已嵌入的完整子集，pdffonts 仍显示
        # `CID TrueType / Identity-H / emb=yes sub=yes uni=yes`，pdftotext 能选出中文。
        # 真正会毁掉可编辑性的是 pdf.fonttype=3，本框架钉死 42 —— 不要为了消这条
        # 噪音去动 fonttype。该消息由 C 层直接写 fd 2，只能临时屏蔽 stderr。
        warnings.filterwarnings("ignore", message="MERG NOT subset")
        # 先 draw 一次拿到 renderer，再算**唯一**的导出 bbox：
        # PNG/PDF/SVG 三种后端共用同一个包围盒，尺寸差只剩浮点误差（≤0.001in）。
        try:
            fig.canvas.draw()
            renderer = fig.canvas.get_renderer()
        except Exception:  # pragma: no cover - 无 GUI 后端时退化为原逻辑
            renderer = None
        if bbox_inches is not None:
            export_bbox = bbox_inches
        elif tight and renderer is not None:
            export_bbox = _ink_bbox_inches(fig, renderer, PAD_IN, int(dpi))
        else:
            export_bbox = None

        # ---- 收口到栏宽（R-04）：tight bbox 会按内容外扩，单栏图实测能涨到 4.17in
        width_target = None
        if renderer is not None:
            width_target = _width_target(fig, target_width)
        if (export_bbox is not None and not isinstance(export_bbox, str)
                and width_target is not None):
            export_bbox, renderer = _fit_to_width(
                fig, renderer, export_bbox, float(width_target), PAD_IN, int(dpi))

        saved: dict[str, Path] = {}
        kwargs = dict(dpi=int(dpi), facecolor=_pal.PAPER, transparent=bool(transparent),
                      bbox_inches=export_bbox,
                      pad_inches=0.0 if export_bbox is not None else
                      mpl.rcParams["savefig.pad_inches"])
        for fmt in fmts:
            out = path_base.with_suffix("." + fmt)
            fmt_kwargs = _deterministic_kwargs(fmt, kwargs)
            if fmt == "pdf":
                with _quiet_c_stderr():        # ttconv 的 subset 警告只在 PDF 出现
                    fig.savefig(out, format=fmt, **fmt_kwargs)
            else:
                fig.savefig(out, format=fmt, **fmt_kwargs)
            saved[fmt] = out

        # 留白兜底：写完量真实像素，哪边不够补哪边（见 _repair_margins 文档）
        if export_bbox is not None and not isinstance(export_bbox, str):
            export_bbox = _repair_margins(fig, export_bbox, saved, int(dpi), kwargs)

    # R2-11：把画布还给调用方（拟合只服务于这一次写盘）
    if tuple(float(v) for v in fig.get_size_inches()) != _orig_size:
        fig.set_size_inches(*_orig_size)

    if report is not None:
        if export_bbox is not None and not isinstance(export_bbox, str):
            w_in, h_in = float(export_bbox.width), float(export_bbox.height)
        else:
            w_in, h_in = _figure_inches(fig)
        report["width_in"] = round(w_in, 3)
        report["height_in"] = round(h_in, 3)
        report["pad_in"] = PAD_IN if export_bbox is not None else 0.0
        report["target_width"] = width_target
        report["paths"] = {k: str(v) for k, v in saved.items()}
        # 本次是否代劳补了主题、顺手改写了几个 Text（0 表示用户自己套过主题）
        report["auto_theme"] = bool(_auto_theme)
        report["font_retrofit"] = int(_retrofit)

    if validate:
        problems = _validate_written(saved, int(dpi), fig)
        if report is not None:
            report["problems"] = problems
        for msg in problems:
            warnings.warn(f"save(): {msg}", stacklevel=2)

    # t30：诊断字段必须真在返回值里（t29 只在 docs/report 里说了，代码没加，
    # 用户按文档读 ``r["auto_theme"]`` 会 KeyError）。格式键仍是 Path，类型不变；
    # 只关心路径的调用方走 figure_paths()。
    result: dict[str, Path | bool | int] = dict(saved)
    result["auto_theme"] = bool(_auto_theme)
    result["font_retrofit"] = int(_retrofit)
    return result


def save_all(fig, base: str | Path, dpi: int = 300,
             **kwargs) -> dict[str, Path | bool | int]:
    """一次出 PNG + PDF + SVG（需要矢量可编辑稿时用）。

    返回值的键与 :func:`save` 相同：``{"png": Path, "pdf": Path, "svg": Path,
    "auto_theme": bool, "font_retrofit": int}``。
    """
    return save(fig, base, formats=("png", "pdf", "svg"), dpi=dpi, **kwargs)


def figure_paths(result: dict[str, Path | bool | int]) -> dict[str, Path]:
    """从 :func:`save` / :func:`save_all` 的返回值里挑出**只有格式键**的子集。

    ``save()`` 的返回值除了 ``png`` / ``pdf`` 还带两条诊断键（``auto_theme``、
    ``font_retrofit``，值是 bool/int）。要按路径遍历（拼清单、取 ``.name``、
    算 ``.stat()``）时先过这一层，免得撞上 ``True.name``::

        paths = afg.figure_paths(afg.save(fig, "fig01_name"))
        for fmt, p in paths.items():
            print(fmt, p.stat().st_size)
    """
    return {k: v for k, v in result.items() if isinstance(v, Path)}


# B 包旧名兼容
save_paper_figure = save


__all__ = [
    "ASPECT_RANGE",
    "DEFAULT_FORMATS",
    "DOUBLE_IN",
    "MAX_PIXELS",
    "MIN_DPI",
    "MIN_MARGIN_PX",
    "NAME_RE",
    "PAD_IN",
    "SINGLE_IN",
    "SUPPORTED_FORMATS",
    "WIDTH_TARGETS",
    "WIDTH_TOL_IN",
    "figure_paths",
    "save",
    "save_all",
    "save_paper_figure",
    "stem_ok",
]