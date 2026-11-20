# -*- coding: utf-8 -*-
"""checks —— 论文插图的静态/产物自检（合并 C 包 5 个 check_* 的逻辑，但**返回结构**）。

设计原则：**只返回结构化 :class:`Issue`，不 print**。CLI / 测试 / 编辑器插件各自决定
怎么展示；库代码里 print 是最难复用的副作用。

覆盖的检查
----------
============  ==========================================================
code          含义
============  ==========================================================
``glyph``     字体缺字形（中文/数学符号渲染成方框，matplotlib 会发 warning）
``font-family`` 脚本自己把 ``font.family``/``font.sans-serif`` 换成无中文字形的字体栈
``math-mix``  中文与 ``$...$`` 混排（Word 粘贴后最常见的塌陷）
``size``      PNG/PDF 输出尺寸或宽高比越界（0.6–2.6，超宽/超窄都不适合期刊）
``width``     输出宽度既不是单栏 3.35in 也不是双栏 7.0in（±0.15in）——按栏宽插图会被缩放
``dpi``       PNG 有效 dpi < 300
``pdf``       同名 PDF 缺失（期刊几乎都要矢量图）
``svg``       SVG 存在但字形被转成路径（``svg.fonttype`` 不是 ``none``）
``color``     出现 palette 之外的色相（含 tab10/jet/rainbow 这类默认色）
``fontsize``  脚本里的字号不在允许集合（``typography.ALLOWED_SIZES``）
``theme``     脚本没有调用 ``apply_theme`` / ``set_paper_style``
``grid``      脚本开启了网格（本风格禁网格）
``savefig``   ``savefig`` 没带 ``dpi=300``
``naming``    文件名不符合 ``figNN_name`` 规范
``overflow``  示意图里文字越出所在框（:func:`check_box_overflow`，默认抛错）
``hit``       示意图里文字压在连线/边框上（:func:`check_text_hits`）
============  ==========================================================

两类检查的粒度不同，返回结构相同：

* :func:`check_dir` / :func:`check_script` / :func:`check_text` 看**文件与文本**；
* :func:`check_box_overflow` / :func:`check_text_hits` 看**已画好的图元**，
  依赖 :func:`register_box` / :func:`register_link` 事先登记的几何，
  跑之前会 ``canvas.draw()`` 一次拿真实 bbox（示意图画布 1 单位 = 1 英寸）。

用法::

    issues = check_dir("examples/out")
    for issue in issues:
        print(issue)                    # "[ERROR] dpi  fig01.png: …"
    if has_errors(issues):
        ...
"""
from __future__ import annotations

import logging
import re
import struct
import sys
import warnings
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np

from . import palette as _pal
from . import typography as _typo
from .export import NAME_RE                    # 命名规范只留一处定义（见 export.NAME_RE）
from .layout import DOUBLE as DOUBLE_IN
from .layout import SINGLE as SINGLE_IN

#: 期刊常见允许范围（与 ``docs/ARCH.md`` §3 一致）
ASPECT_RANGE = (0.6, 2.6)
MIN_DPI = 300
#: 合法宽度只能是这两档（inch）；按栏宽插图时超出会被缩放，10pt 字号就变成 8.4pt
WIDTH_TARGETS = (SINGLE_IN, DOUBLE_IN)
#: 宽度容差（inch）：±0.15in ≈ ±4.5%，够容下「图注末字江白」又不能放过 4.17in
WIDTH_TOL_IN = 0.15
#: C 包 check_colors.py 的禁用色图/色板（默认色 = AI 味最重的地方）
FORBIDDEN_STYLES = (
    "tab10", "tab20", "tab20b", "tab20c", "jet", "rainbow", "hsv", "gist_rainbow",
    "nipy_spectral", "Set1", "Set2", "Set3", "Paired", "Accent", "Dark2", "Pastel1",
    "Pastel2", "seaborn", "colorblind", "viridis", "plasma", "magma", "inferno",
)
#: 封面 / 样张 / 参考图：不是论文插图，不适用 ``figNN_`` 命名（``check_dir`` 只报 info）
COVER_STEMS = ("style_preview", "cover", "atlas", "arch_border_ab")
#: 最近色距阈值（0–255 RGB 欧氏距离）：> 此值即判为「palette 之外的颜色」。
#: 28/255 ≈ 0.11——足够容下抗锯齿与 PNG 量化误差，又拦得住 matplotlib 默认色
#: （C0 ``#1F77B4`` 距最近的 ``palette.BLUE`` 已有 52/255）。
COLOR_TOL = 28.0
#: 饱和度低于此值视作中性灰（墨线/灰阶/白底都合法）
SAT_FLOOR = 0.12
#: 配色检查的像素采样上限（超过就先等距降采样，避免大图拖慢 CLI）
COLOR_MAX_PIXELS = 400_000
#: 单张图最多报告几种越界颜色（按像素数从多到少）
COLOR_TOP_N = 5
#: 越界色块的最小像素数：低于此值的「错色」多半是两色叠加的抗锯齿噪点
#: （例如深色字压在浅底上混合出的中间色），不报，免得淹没真问题
COLOR_MIN_PIXELS = 400
#: 越界色块的最小占比（彩色像素）：与 :data:`COLOR_MIN_PIXELS` 取「或」
COLOR_MIN_FRACTION = 0.005

_SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}
_CODES = {
    "glyph", "font-family", "math-mix", "size", "width", "dpi", "pdf", "svg", "color",
    "fontsize", "theme", "grid", "savefig", "naming", "empty",
    "overflow", "hit",
}


@dataclass
class Issue:
    """一条自检结论（结构化，可直接 JSON 化）。

    Attributes
    ----------
    code : str
        检查类别（见模块 docstring 表），便于按类过滤/抑制。
    severity : {"error", "warning", "info"}
        ``error`` 表示必须修（期刊/风格硬要求），``warning`` 建议修。
    file : str
        相关文件名（``""`` 表示与具体文件无关，如字体环境）。
    message : str
        问题描述（中文，含关键数字）。
    fix_hint : str
        具体怎么修（一句话，可执行）。
    """

    code: str
    severity: str
    file: str
    message: str
    fix_hint: str
    detail: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.code not in _CODES:
            raise ValueError(f"Issue: 未知 code {self.code!r}（可选：{sorted(_CODES)}）")
        if self.severity not in _SEVERITY_ORDER:
            raise ValueError(f"Issue: severity 只能是 error/warning/info（收到 {self.severity!r}）")

    def __str__(self) -> str:
        head = f"[{self.severity.upper()}] {self.code:<9} {self.file or '-':<24}"
        return f"{head} {self.message}\n{head.replace('[', ' ').replace(']', ' ')} -> {self.fix_hint}"

    def to_dict(self) -> dict[str, Any]:
        """转成可直接 ``json.dumps`` 的字典。"""
        return {
            "code": self.code,
            "severity": self.severity,
            "file": self.file,
            "message": self.message,
            "fix_hint": self.fix_hint,
            "detail": self.detail,
        }


# ------------------------------------------------------------------ 汇总工具
def has_errors(issues: Iterable[Issue]) -> bool:
    """是否存在 ``error`` 级问题（CLI ``--strict`` 用它决定退出码）。"""
    return any(i.severity == "error" for i in issues)


def sort_issues(issues: Iterable[Issue]) -> list[Issue]:
    """按严重度 → 文件名 → code 排序（报告读起来稳定）。"""
    return sorted(issues, key=lambda i: (_SEVERITY_ORDER[i.severity], i.file, i.code))


def format_report(issues: Iterable[Issue], *,
                  skipped: Iterable[str] | None = None) -> str:
    """把问题列表排成人类可读报告（CLI 直接打印它）。

    ``skipped`` 是「本次没做」的检查项（例如纯图目录没有生成脚本 → 图片内部字形没有
    逐一核对）。**没检查 ≠ 检查通过**：有跳过项时，即便 0 条 issue，结论行也不打
    ``✓``（那读作「验过了、没问题」），而是 ``△ 未发现问题（<跳过项>：未检查）``——
    ``△`` 专门表示「只验了一部分」。全项都验过才用 ``✓``。
    """
    ordered = sort_issues(issues)
    skip = [str(s) for s in (skipped or ()) if s]
    suffix = f"（{'；'.join(skip)}：未检查）" if skip else ""
    if not ordered:
        return ("△ 未发现问题" if skip else "✓ 未发现问题") + suffix
    n_err = sum(1 for i in ordered if i.severity == "error")
    n_warn = sum(1 for i in ordered if i.severity == "warning")
    lines = [str(i) for i in ordered]
    tail = f"\n合计 {len(ordered)} 条：error {n_err} / warning {n_warn}"
    if suffix:
        tail += "\n未检查：" + "；".join(skip)
    lines.append(tail)
    return "\n".join(lines)


# ------------------------------------------------------------------ PNG/PDF 解析
def _png_info(path: Path) -> dict[str, Any]:
    """读 PNG 头：尺寸与有效 dpi（pHYs 块，缺省时按 72）。"""
    info: dict[str, Any] = {"width": None, "height": None, "dpi": None}
    with path.open("rb") as fh:
        if fh.read(8) != b"\x89PNG\r\n\x1a\n":
            return info
        while True:
            head = fh.read(8)
            if len(head) < 8:
                break
            length, ctype = struct.unpack(">I4s", head)
            if ctype == b"IHDR":
                w, h = struct.unpack(">II", fh.read(8))
                info["width"], info["height"] = int(w), int(h)
                fh.seek(length - 8, 1)      # 块内剩余字段
                fh.seek(4, 1)               # CRC
            elif ctype == b"pHYs":
                px, py, unit = struct.unpack(">IIB", fh.read(9))
                if unit == 1:  # 米
                    info["dpi"] = round((px + py) / 2.0 * 0.0254, 1)
                else:
                    info["dpi"] = round((px + py) / 2.0, 1)
                fh.seek(length - 9, 1)
                fh.seek(4, 1)               # CRC
            elif ctype in (b"IDAT", b"IEND"):
                break
            else:
                fh.seek(length + 4, 1)
    return info


def _pdf_info(path: Path) -> dict[str, Any]:
    """读 PDF 首页 MediaBox：宽度/高度（pt），用于宽高比检查。"""
    info: dict[str, Any] = {"width_pt": None, "height_pt": None, "ok": False}
    raw = path.read_bytes()
    if not raw.startswith(b"%PDF"):
        return info
    info["ok"] = True
    m = re.search(rb"/MediaBox\s*\[\s*([\d.\-]+)\s+([\d.\-]+)\s+([\d.\-]+)\s+([\d.\-]+)\s*\]", raw)
    if m:
        x0, y0, x1, y1 = (float(v) for v in m.groups())
        info["width_pt"] = abs(x1 - x0)
        info["height_pt"] = abs(y1 - y0)
    return info


def _hex_to_rgb(color: str) -> tuple[float, float, float]:
    c = color.lstrip("#")
    return tuple(int(c[i:i + 2], 16) / 255.0 for i in (0, 2, 4))  # type: ignore[return-value]


def _palette_colors() -> set[str]:
    """收集 palette 里所有公开色值（含各档 tint），用于色彩合规比对。"""
    names = [n for n in dir(_pal) if n.isupper() and not n.startswith("_")]
    colors: set[str] = set()
    for name in names:
        val = getattr(_pal, name)
        if isinstance(val, str) and val.startswith("#"):
            colors.add(val.upper())
        elif isinstance(val, (list, tuple)):
            for item in val:
                if isinstance(item, str) and item.startswith("#"):
                    colors.add(item.upper())
    base = {c for c in colors}
    for c in base:
        for alpha in (0.10, 0.13, 0.2, 0.26, 0.38, 0.55):
            colors.add(_rgb_to_hex(_pal.tint(c, alpha)))
    return colors


def _rgb_to_hex(rgb) -> str:
    """(0–1  float RGB 三元组) → ``#RRGGBB``。"""
    r, g, b = (int(round(float(v) * 255.0)) for v in rgb[:3])
    return f"#{r:02X}{g:02X}{b:02X}"


def _hue_sat(rgb: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """向量化 HSV 的 H（度）与 S（0–1）。"""
    r, g, b = rgb[:, 0], rgb[:, 1], rgb[:, 2]
    mx = rgb.max(axis=1)
    mn = rgb.min(axis=1)
    diff = mx - mn
    sat = np.where(mx > 0, diff / np.clip(mx, 1e-9, None), 0.0)
    hue = np.zeros_like(mx)
    mask = diff > 1e-9
    im = np.argmax(rgb, axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        hue = np.where(mask & (im == 0), ((g - b) / np.clip(diff, 1e-9, None)) % 6.0, hue)
        hue = np.where(mask & (im == 1), (b - r) / np.clip(diff, 1e-9, None) + 2.0, hue)
        hue = np.where(mask & (im == 2), (r - g) / np.clip(diff, 1e-9, None) + 4.0, hue)
    hue = (hue * 60.0) % 360.0
    return hue, sat


@lru_cache(maxsize=1)
def _allowed_colors() -> tuple[np.ndarray, tuple[str, ...], tuple[str, ...]]:
    """palette 允许色集合（0–255 RGB）+ 每个色的显示名 + 建议改用的 palette 表达式。

    集合构成（顺序即「报告的优先级」）：

    1. 语义基色：``INK/INK_SOFT/GREY/GREY_LIGHT/BLUE/CLAY/MOSS/OCHRE/SLATE/PLUM``；
    2. 浅底：``*_T``（六色各一档）、``WASH``、``WASH_COOL``；
    3. ``tint(c, α)``——α = 0.05…0.95 每 0.05 一档：抗锯齿就是「色 + 白」的线性混合，
       把整条混合线收进允许集，才不会把 1.5pt 细线的边缘判成外来色；
    4. ``cmap_seq/cmap_seq_r/cmap_div/cmap_disc`` 的 33 个等距停靠色。

    阈值判定用 RGB 欧氏距离（见 :data:`COLOR_TOL`），**不看色相**：色相环上
    「离得近」和「看起来是同一个色」不是一回事，旧版就是被这条坑掉的。

    Returns
    -------
    rgbs : (N, 3) float ndarray
        允许色（0–255）。
    names : tuple of str
        每个允许色的显示名（报告里说「距最近允许色是谁」）。
    suggests : tuple of str
        每个允许色对应的「改用哪个 palette 表达式」——tint 档会回溯到基色，
        所以提示永远是可抄的一行代码，而不是 ``tint(BLUE, 0.95)`` 这种怪档位。
    """
    entries: list[tuple[str, str, str]] = []      # (显示名, #RRGGBB, 建议表达式)
    core = ("INK", "INK_SOFT", "GREY", "GREY_LIGHT", "BLUE", "CLAY", "MOSS",
            "OCHRE", "SLATE", "PLUM", "WASH", "WASH_COOL")
    for name in core:
        val = getattr(_pal, name, None)
        if isinstance(val, str) and val.startswith("#"):
            entries.append((f"palette.{name}", val, f"palette.{name}"))
    for name in dir(_pal):
        if name.endswith("_T") and name.isupper():
            val = getattr(_pal, name)
            if isinstance(val, str) and val.startswith("#"):
                entries.append((f"palette.{name}", val, f"palette.{name}"))

    bases = list(entries)                        # 基色（tint 的建议回溯到这里）
    for disp, hexval, suggest in bases:
        for alpha in np.arange(0.05, 0.951, 0.05):
            entries.append((f"{disp} + 白 {alpha:.0%}",
                            _rgb_to_hex(_pal.tint(hexval, float(alpha))), suggest))

    for cmap_name, cmap in (
        ("cmap_seq()", _pal.cmap_seq()),
        ("cmap_seq_r()", _pal.cmap_seq_r()),
        ("cmap_div()", _pal.cmap_div()),
        ("cmap_disc(5)", _pal.cmap_disc(5)),
        ("cmap_disc(3)", _pal.cmap_disc(3)),
    ):
        for i, rgba in enumerate(cmap(np.linspace(0.0, 1.0, 33))):
            entries.append((f"{cmap_name} 第 {i + 1}/33 档", _rgb_to_hex(rgba), cmap_name))

    # 去重（同一个色只留第一次出现），并转成 0–255 浮点数组
    seen: dict[str, tuple[str, str]] = {}
    for disp, hexval, suggest in entries:
        seen.setdefault(hexval.upper(), (disp, suggest))
    names = tuple(v[0] for v in seen.values())
    suggests = tuple(v[1] for v in seen.values())
    rgbs = np.array([[*_hex_to_rgb(h)] for h in seen], dtype=float) * 255.0
    return rgbs, names, suggests


def _nearest_allowed(colors: np.ndarray, allowed: np.ndarray,
                     chunk: int = 4096) -> tuple[np.ndarray, np.ndarray]:
    """对每个颜色求最近允许色的下标与 RGB 欧氏距离（0–255 尺度，分块防爆内存）。"""
    best_idx = np.empty(colors.shape[0], dtype=np.int64)
    best_dist = np.empty(colors.shape[0], dtype=float)
    for start in range(0, colors.shape[0], chunk):
        block = colors[start:start + chunk]
        d2 = ((block[:, None, :] - allowed[None, :, :]) ** 2).sum(axis=2)
        idx = np.argmin(d2, axis=1)
        best_idx[start:start + chunk] = idx
        best_dist[start:start + chunk] = np.sqrt(d2[np.arange(block.shape[0]), idx])
    return best_idx, best_dist


@lru_cache(maxsize=1)
def _blend_bases() -> np.ndarray:
    """混合判定的基色：12 个语义基色 + 6 个 ``*_T`` 浅色 + 白（0–255）。"""
    bases: list[str] = []
    for name in ("INK", "INK_SOFT", "GREY", "GREY_LIGHT", "BLUE", "CLAY", "MOSS",
                 "OCHRE", "SLATE", "PLUM", "WASH", "WASH_COOL"):
        val = getattr(_pal, name, None)
        if isinstance(val, str) and val.startswith("#"):
            bases.append(val)
    for name in sorted(dir(_pal)):
        if name.endswith("_T") and name.isupper():
            val = getattr(_pal, name)
            if isinstance(val, str) and val.startswith("#"):
                bases.append(val)
    bases.append("#FFFFFF")
    return np.array([[*_hex_to_rgb(h)] for h in bases], dtype=float) * 255.0


def _explained_by_blend(colors: np.ndarray, bases: np.ndarray,
                        tol: float) -> np.ndarray:
    """判断每个颜色是否落在「两个基色的连线」上（容差 ``tol``）。

    为什么需要它
    ------------
    两条合法色的细线相交、半透明色块压在另一色块上、抗锯齿跨过两种色，
    都会产出**既不属于任何允许色、也不是错色**的中间色。实测 ``ml/fig02_pr.png``
    的 ``#935D59``（50px）就是 CLAY 折线与灰网格叠加的产物——按最近色距判会误报，
    但它显然不是「用了 tab10/jet」。判据改成：到最近允许色超限，**且**不能由
    两个基色的线性混合解释，才算越界。

    Returns
    -------
    ndarray of bool
        每个颜色是否可由混合解释。
    """
    ok = np.zeros(colors.shape[0], dtype=bool)
    if colors.shape[0] == 0 or bases.shape[0] < 2:
        return ok
    for i in range(bases.shape[0]):
        for j in range(i + 1, bases.shape[0]):
            a, b = bases[i], bases[j]
            v = b - a
            vv = float(v @ v)
            if vv <= 1e-12:
                continue
            t = np.clip(((colors - a) @ v) / vv, 0.0, 1.0)
            closest = a + t[:, None] * v
            d = np.sqrt(((colors - closest) ** 2).sum(axis=1))
            ok |= d <= tol
            if ok.all():
                return ok
    return ok


def _color_issues(path: Path, *, tol: float = COLOR_TOL,
                  top_n: int = COLOR_TOP_N) -> list[Issue]:
    """像素级配色检查：PNG 里只允许出现 palette 的色（含 tint 与色阶停靠色）。

    判定：颜色在 RGB 空间到「最近允许色」的欧氏距离 > ``tol``（默认 28/255）即越界。
    近白像素与低饱和像素（``SAT_FLOOR`` 以下，即墨线/灰阶/抗锯齿留白）直接跳过，
    避免把 0.8pt 细线的边缘判成外来色。

    Returns
    -------
    list[Issue]
        每种越界颜色一条 ``color`` / ``error``（最多 ``top_n`` 条，按像素数降序），
        自带「相距多少 / 最近允许色是谁 / 改用哪个语义色」的可执行建议。
    """
    try:
        from matplotlib.image import imread
    except Exception:  # pragma: no cover - matplotlib 必然存在
        return []
    try:
        img = imread(path)
    except Exception:
        return []
    if img.ndim != 3 or img.shape[2] < 3:
        return []
    rgb = img[..., :3].reshape(-1, 3)
    if rgb.dtype.kind in "ui":
        rgb = rgb.astype(np.float32) / np.iinfo(rgb.dtype).max
    else:
        rgb = rgb.astype(np.float32)
    # 大图先等距降采样（配色是统计量，不需要每个像素）
    if rgb.shape[0] > COLOR_MAX_PIXELS:
        step = int(np.ceil(rgb.shape[0] / COLOR_MAX_PIXELS))
        rgb = rgb[::step]
    under = rgb * 255.0
    # 近白（白底/留白）与低饱和（墨线/灰阶）不参与判定
    keep = ~(under.max(axis=1) >= 251.0)
    under = under[keep]
    if under.shape[0] == 0:
        return []
    _, sat = _hue_sat(under / 255.0)
    chromatic = sat > SAT_FLOOR
    if not chromatic.any():
        return []
    cols = under[chromatic]
    total = float(cols.shape[0])

    # 按精确 RGB 聚合并计数（同色像素合成一条）
    uniq, counts = np.unique(np.rint(cols).astype(np.int16), axis=0,
                             return_counts=True)
    allowed, names, suggests = _allowed_colors()
    if allowed.size == 0:
        return []
    idx, dist = _nearest_allowed(uniq.astype(float), allowed)
    bad = dist > tol
    if bad.any():
        # 叠加色豁免：两个合法色的混合（细线相交、半透明色块叠加、抗锯齿跨界）
        # 不是「用错色」，不该报 error；真正的错色（jet/tab10/默认 C0）离任何
        # 合法色连线都远，仍会被抓住。
        bad &= ~_explained_by_blend(uniq.astype(float), _blend_bases(), tol)
    if not bad.any():
        return []

    # 抗锯齿会让同一个「错色」散成几十个近邻色值（#000080/#000084/…）。
    # 这里按 8 级量化分桶聚合，每桶用「像素最多的那个精确色」代表，避免报告刷屏。
    buckets: dict[tuple[int, int, int], int] = {}
    for row in np.nonzero(bad)[0]:
        key = tuple(int(v) // 8 for v in uniq[row])
        buckets[key] = buckets.get(key, 0) + int(counts[row])
    # 只留「成片」的越界色：两色叠加/抗锯齿会产出少量中间色（几十 px），
    # 那不是配色错误而是渲染噪声；真正的错色（默认色图/默认色线）一定成片。
    buckets = {k: v for k, v in buckets.items()
               if v >= COLOR_MIN_PIXELS or v >= COLOR_MIN_FRACTION * total}
    if not buckets:
        return []
    order = sorted(buckets.items(), key=lambda kv: -kv[1])[:top_n]

    out: list[Issue] = []
    for key, n_px in order:
        # 桶内代表色 = 该桶里像素最多的精确色（报告要能对得上肉眼看到的那个色）
        members = [r for r in np.nonzero(bad)[0]
                   if tuple(int(v) // 8 for v in uniq[r]) == key]
        row = max(members, key=lambda r: counts[r])
        hex_bad = _rgb_to_hex(uniq[row] / 255.0)
        near = int(idx[row])
        frac = n_px / total
        out.append(Issue(
            code="color", severity="error", file=path.name,
            message=(f"颜色 {hex_bad} 越界（占彩色像素 {frac:.1%}，{n_px} px）："
                     f"距最近允许色 {names[near]}（{_rgb_to_hex(allowed[near] / 255.0)}）"
                     f"相差 {float(dist[row]):.0f}/255"),
            fix_hint=(f"改用 {suggests[near]}；色阶用 palette.cmap_seq()/cmap_div()/cmap_disc()，"
                      f"浅底用 palette.tint()，不要手写十六进制、不要用 tab10/jet/rainbow"),
            detail={"hex": hex_bad, "fraction": round(frac, 4),
                    "pixels": n_px,
                    "nearest": names[near],
                    "nearest_hex": _rgb_to_hex(allowed[near] / 255.0),
                    "distance": round(float(dist[row]), 1), "tol": tol},
        ))
    return out


#: 四边留白下限（px @300dpi）：8px ≈ 0.027in，低于此值在期刊排版里就是贴边
MIN_MARGIN_PX = 8


def png_margins(path: str | Path, *, white: float = 251.0) -> dict[str, int] | None:
    """量一张 PNG 的四边留白（非白像素外接框到画布边缘的距离，单位 px）。

    自检和 ``scripts/check_margins.py`` 用它验证「``save()`` 之后四边 ≥8px」：
    300dpi 下 8px 的物质长度只有 0.027in，肉眼看不出来，但裁图/排版时会把
    刻度标签或图注重叠到边框。

    Parameters
    ----------
    path : str | Path
        PNG 路径。
    white : float
        0–255 阈值：三个通道都 ≥ 该值的像素算「白」（默认 251，留出 JPEG 级误差）。

    Returns
    -------
    dict[str, int] | None
        ``{"left", "right", "top", "bottom", "width", "height"}``；读不了返回 ``None``。
        纯白图四边留白等于画布尺寸（不算异常）。
    """
    try:
        from matplotlib.image import imread
        img = imread(path)
    except Exception:
        return None
    if img.ndim == 2:
        rgb = np.repeat(img[..., None], 3, axis=2)
    elif img.ndim == 3 and img.shape[2] >= 3:
        rgb = img[..., :3]
    else:
        return None
    if rgb.dtype.kind in "ui":
        rgb = rgb.astype(np.float32) / np.iinfo(rgb.dtype).max
    rgb = rgb.astype(np.float32) * 255.0
    h, w = rgb.shape[:2]
    ink = rgb.min(axis=2) < white
    rows = np.nonzero(ink.any(axis=1))[0]
    cols = np.nonzero(ink.any(axis=0))[0]
    if rows.size == 0 or cols.size == 0:
        return {"left": w, "right": w, "top": h, "bottom": h, "width": w, "height": h}
    return {
        "left": int(cols[0]),
        "right": int(w - 1 - cols[-1]),
        "top": int(rows[0]),
        "bottom": int(h - 1 - rows[-1]),
        "width": int(w),
        "height": int(h),
    }


# ------------------------------------------------------------------ 字体 / 文本
def _font_fix_hint() -> str:
    """按平台给出可执行的「装字体」指引。

    R-02 之前这里只写 ``C:\\Windows\\Fonts``：Linux/macOS 用户拿到的是无法执行的建议。
    """
    import sys

    if sys.platform.startswith("win"):
        return ("确认 C:\\Windows\\Fonts 下的 simsun.ttc / simhei.ttf 存在且可读；"
                "缺字体时装思源宋体（Source Han Serif SC）后调用 "
                "academic_fig.typography.ensure_registered()")
    if sys.platform == "darwin":
        return ("macOS 自带 Songti SC / PingFang SC，框架会按**族名**逐字回退（Songti SC → "
                "STSong → PingFang SC → Heiti SC）；仍缺则 brew install --cask "
                "font-noto-serif-cjk-sc，或把 .ttc 放进 /Library/Fonts/，再调用 "
                "typography.ensure_registered() 重建缓存")
    return ("Debian/Ubuntu: sudo apt install fonts-noto-cjk（或 fonts-wqy-zenhei）；"
            "装完调用 academic_fig.typography.ensure_registered() 重建字体缓存")


#: matplotlib 报「缺字形」的几种原话，逐条都要认（R2-02）：
#: * ``Glyph 20013 (\N{CJK UNIFIED IDEOGRAPH-4E2D}) missing from font(s) ...`` —— ft2font 直排
#: * ``Font 'default' does not have a glyph for '\u0394' [U+0394], substituting with a dummy symbol``
#:   —— **mathtext 缺字**，``$\\Delta E$`` 里 STIX 没有该字时就这一条，旧过滤词全漏
#: * ``ParseFatalException`` / ``TypeError`` —— 公式语法错（``$a_{}$``、未闭合 ``$``），
#:   渲染成字面量或炸掉，同样属于「这张图的公式是坏的」
_GLYPH_MARKERS: tuple[str, ...] = (
    "missing from",
    "does not have a glyph",
    "substituting with a dummy symbol",
    "Glyph",
)

#: 公式语法错的信号；与缺字形分开统计，fix_hint 也不一样。
_MATH_ERROR_MARKERS: tuple[str, ...] = ("ParseFatalException", "ParseException",
                                        "Unknown symbol", "TypeError")


class _RecordCollector(logging.Handler):
    """把 ``logging`` 记录收集成字符串列表。

    mathtext 缺字形走的是 **logging**（``matplotlib.mathtext`` 的 ``_log.warning``），
    不是 ``warnings``：``Font 'default' does not have a glyph for '\\u0394' …
    substituting with a dummy symbol`` 只出现在 logging 记录里。只抓 warnings 的探针
    在「中文 + $...$ 混排」这类图上会静默返回 0 条（R2-02 的第二个洞）。
    """

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:  # noqa: D102
        try:
            self.messages.append(record.getMessage())
        except Exception:  # pragma: no cover - 消息格式化失败不该影响自检
            self.messages.append(str(record.msg))


#: 探针默认样串：**中文与公式必须分两次画**。matplotlib 3.9 里只要一条串含 ``$...$``，
#: 整串都会交给 mathtext 排版，汉字落到 STIX（无 CJK）→ 每条汉字报一次
#: ``substituting with a dummy symbol``。也就是说「中文 + $...$ 混排」这条**写法问题**会被
#: 渲染成假阳性，掩盖真正的缺字体诊断；写法本身由 :func:`check_text` 静态抓（math-mix）。
PROBE_CJK_TEXT: str = "中位数 置信区间 相对误差 核密度 覆盖率 灵敏度 αβ ≥ 95% −1.2×10⁻³"
PROBE_MATH_TEXT: str = r"$\Delta E_{rms}$  $\log_2 FC$  $\alpha\beta \pm 0.5$  $10^{-3}$"


def _render_probe_text(text: str, rc: dict, Figure, FigureCanvasAgg) -> tuple[list[str], list[str]]:
    """把一个样串画一遍，返回 ``(warnings 消息, logging 消息)``。"""
    import matplotlib

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        collector = _RecordCollector()
        mpl_log = logging.getLogger("matplotlib")
        old_level = mpl_log.level
        mpl_log.addHandler(collector)
        mpl_log.setLevel(logging.WARNING)          # 让 WARNING 级也进 handler
        try:
            with matplotlib.rc_context(rc):
                fig = Figure(figsize=(3.35, 1.0), dpi=120)
                FigureCanvasAgg(fig)               # ← 没有这一行，draw() 什么也不做
                ax = fig.add_subplot(111)
                ax.set_title(text, fontsize=9)
                ax.set_xlabel(text, fontsize=9)
                fig.canvas.draw()
        finally:
            mpl_log.removeHandler(collector)
            mpl_log.setLevel(old_level)
    warn_msgs = [str(w.message) for w in caught]
    return warn_msgs, collector.messages


def probe_glyphs(text: str | None = None,
                 *, families: Sequence[str] | None = None) -> list[Issue]:
    """真实渲染探针文本，抓「缺字形」与「公式写法坏」两类问题。

    Parameters
    ----------
    text : str, optional
        只画这一个样串（自测/排查用）。缺省时画两串：
        :data:`PROBE_CJK_TEXT`（纯中文 + 希腊/上下标）与 :data:`PROBE_MATH_TEXT`
        （纯 ``$...$`` 公式）。分开画是为了不把「中文混公式」这条**写法**问题
        误报成缺字体——那个由 :func:`check_text` 静态判（见 ``math-mix``）。
    families : sequence of str, optional
        指定字体栈（默认用 :func:`academic_fig.typography.font_stack`）。
        自测脚本用它注入一个不存在的字体来验证「探针真的能报错」。

    为什么必须用 :class:`~matplotlib.backends.backend_agg.FigureCanvasAgg`
    ---------------------------------------------------------------
    ``matplotlib.figure.Figure()`` 挂的是 ``FigureCanvasBase``，它的 ``draw()`` 是
    **空实现**（注释原话：``Draw it only if it is an instance of FigureCanvasAgg``），
    文字一个都不会被光栅化，缺字形的 warning 自然一条也不发。R-02 就是这里：
    探针恒返回 ``[]``，全乱码的图 ``check --strict`` 照样 exit 0。
    改成显式挂 Agg canvas 后，``draw()`` 走 ft2font 真实排字，缺字形会被 warning 抓到。

    为什么还要抓 logging（R2-02）
    ---------------------------
    mathtext 缺字报的是 ``Font 'default' does not have a glyph for '\\u0394' …
    substituting with a dummy symbol``，走的是 ``matplotlib.mathtext`` 的 **logging**，
    不是 ``warnings``；只抓 warnings 的探针在这条通道上静默返回 0 条。

    Returns
    -------
    list[Issue]
        缺字形返回 ``glyph`` 级 error；公式语法错返回 ``math-mix`` 级 error；
        字体环境正常时返回空列表。
    """
    issues: list[Issue] = []
    try:
        import matplotlib
        matplotlib.use("Agg", force=False)
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from matplotlib.figure import Figure
    except Exception as exc:  # pragma: no cover
        return [Issue(code="glyph", severity="warning", file="",
                      message=f"无法加载 matplotlib 做字形自检：{exc}",
                      fix_hint="确认 matplotlib 已安装且后端可用")]
    # 用**框架自己的字体栈**渲染，而不是调用时碰巧生效的 rcParams：
    # 裸 ``python -m academic_fig.cli check`` 从没跑过 apply_theme，matplotlib 默认
    # 字体是 DejaVu（无中文），照默认 rcParams 探针会把「图其实是好的」判成乱码。
    stack = list(families) if families else _typo.font_stack()
    rc = {"font.family": stack, "font.sans-serif": stack, "font.serif": stack,
          "axes.unicode_minus": False, "mathtext.fontset": "stix"}
    samples = [text] if text is not None else [PROBE_CJK_TEXT, PROBE_MATH_TEXT]
    msgs: list[str] = []
    raised: list[str] = []
    for sample in samples:
        try:
            warn_msgs, log_msgs = _render_probe_text(sample, rc, Figure, FigureCanvasAgg)
        except Exception as exc:
            # 公式语法错会让 draw() 直接抛 ParseFatalException，而不是发 warning：
            # 归到 math-mix（写法问题），不要混进「缺字体」。
            detail = str(exc).strip().splitlines()
            head = detail[0] if detail else repr(exc)
            if any(k in str(exc) for k in _MATH_ERROR_MARKERS) or "$" in sample:
                raised.append(head)
                continue
            return [Issue(code="glyph", severity="warning", file="",
                          message=f"字形自检渲染失败：{head}",
                          fix_hint="检查字体文件与后端")]
        msgs.extend(warn_msgs)
        msgs.extend(log_msgs)
    missing = [m for m in msgs if any(k in m for k in _GLYPH_MARKERS)]
    broken = [m for m in msgs if any(k in m for k in _MATH_ERROR_MARKERS)] + raised
    if missing:
        issues.append(Issue(
            code="glyph", severity="error", file="",
            message="字体缺字形：" + "; ".join(missing[:3]) + ("…" if len(missing) > 3 else ""),
            fix_hint=_font_fix_hint(),
            detail={"count": len(missing), "samples": missing[:5]},
        ))
    if broken:
        issues.append(Issue(
            code="math-mix", severity="error", file="",
            message="公式渲染报错：" + "; ".join(broken[:3]),
            fix_hint=(r"mathtext 只认精简子集：上下标用 $x_{i}$、分式用 $\frac{a}{b}$；"
                      r"不要写 \text{} 之类宏，也别在 $...$ 里塞中文"
                      r"（改写成「相对误差 $\Delta E$」这种公式与汉字分段的写法）"),
            detail={"count": len(broken), "samples": broken[:5]},
        ))
    return issues


def check_text(text: str, *, file: str = "", where: str = "") -> list[Issue]:
    """检查一段文本：中文与 ``$...$`` 混排（``math-mix``）。"""
    report = _typo.text_safety(text)
    if report["safe"]:
        return []
    loc = f"{file}:{where}" if where else (file or "-")
    return [Issue(
        code="math-mix", severity="error", file=loc,
        message="中英文与 $…$ 数学模式混排，渲染时会出现断字/方框（" + "；".join(report["issues"]) + "）",
        fix_hint=report["suggestion"],
        detail={"rewritten": report["rewritten"]},
    )]


# ------------------------------------------------- 图元级复核（框架图 / 示意图）
#: ``ax.__dict__`` 里存放「文字 → 应该待的框」清单的键（:func:`register_box` 写）
BOX_ATTR = "_afg_boxes"
#: ``ax.__dict__`` 里存放「已画的连线」清单的键（:func:`register_link` 写）
LINK_ATTR = "_afg_links"


class TextOverflowError(RuntimeError):
    """文字超出所在框：带着它出图就是错版，所以默认抛错。"""


class TextLineCollision(RuntimeError):
    """文字压在连线或边框上：示意图里最扎眼的错版，复核时默认报出来。"""


def register_box(ax, artist, x: float, y: float, w: float, h: float):
    """登记「这段字应该待在这个框里」，供 :func:`check_box_overflow` 复核。

    ``(x, y, w, h)`` 用**数据坐标**——示意图的画布是「1 数据单位 = 1 英寸」，
    所以传英寸即可（见 :mod:`academic_fig.diagrams._canvas`）。
    """
    reg = ax.__dict__.setdefault(BOX_ATTR, [])
    reg.append((artist, (float(x), float(y), float(w), float(h))))
    return artist


def register_link(ax, pts, *, lw: float = 0.9):
    """登记一条连线（折线）或一段边框，供 :func:`check_text_hits` 复核压线。"""
    reg = ax.__dict__.setdefault(LINK_ATTR, [])
    p = [(float(q[0]), float(q[1])) for q in pts]
    for i in range(len(p) - 1):
        reg.append((p[i], p[i + 1], float(lw)))
    return pts


def _extent_in_data(ax, artist, renderer) -> tuple[float, float, float, float]:
    """artist 的实测 bbox → 数据坐标 ``(x0, y0, w, h)``（宽高恒为正）。"""
    bb = artist.get_window_extent(renderer=renderer)
    inv = ax.transData.inverted()
    (x0, y0), (x1, y1) = inv.transform([[bb.x0, bb.y0], [bb.x1, bb.y1]])
    return min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0)


def _debug_rect(ax, x: float, y: float, w: float, h: float) -> None:
    """画一圈 CLAY 虚线框，标出出问题的那块地方（只在 ``debug=True`` 时调）。"""
    from matplotlib.patches import Rectangle

    ax.add_patch(Rectangle((x, y), w, h, fill=False, edgecolor=_pal.CLAY,
                           linewidth=0.7, linestyle=(0, (3, 2)), zorder=20))


def _artists_ready(ax, attr: str):
    """取登记表并 ensure 一次 renderer；没东西可查时返回 ``(None, None)``。"""
    reg = ax.__dict__.get(attr) or []
    if not reg:
        return reg, None
    try:
        ax.figure.canvas.draw()
    except Exception:                                        # pragma: no cover
        pass
    return reg, getattr(ax.figure.canvas, "renderer", None)


def check_box_overflow(ax, *, tol: float = 0.0, strict: bool = True,
                       debug: bool = False, only: Iterable[str] | None = None,
                       file: str = "") -> list[Issue]:
    """检查所有登记过的文字是否越出所在框（英寸判据）。

    判据：文字实测 bbox 的左右/上下越界量取最大值，超过 ``tol`` 即记一条
    ``overflow``。这里量的是**渲染后的真实 bbox**，所以「字多了一点、框窄了一点」
    这种肉眼要盯半天的错版能直接报出来。

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        画着示意图的轴（画布须是「1 数据单位 = 1 英寸」，否则 ``tol`` 没意义）。
    tol : float
        允许的越界容差（inch），默认 0：必须完全在框内。
    strict : bool
        发现问题时抛 :class:`TextOverflowError`；``False`` 时只返回清单。
    debug : bool
        给越界的文字套一圈 CLAY 虚线框，便于定位。
    only : sequence of str, optional
        只检查文字里包含这些子串的登记项。
    file : str
        报告里的文件名（``""`` 表示与具体文件无关）。

    Returns
    -------
    list[Issue]
        每项 code=``overflow``，``detail`` 带 ``text / over_x / over_y / box``。

    Raises
    ------
    TextOverflowError
        ``strict=True``（默认）且发现越界时。
    """
    reg, renderer = _artists_ready(ax, BOX_ATTR)
    if not reg or renderer is None:                          # pragma: no cover
        return []
    issues: list[Issue] = []
    for artist, (bx, by, bw, bh) in reg:
        get_text = getattr(artist, "get_text", None)
        txt = str(get_text()).strip() if callable(get_text) else ""
        if only and not any(str(k) in txt for k in only):
            continue
        x0, y0, w, h = _extent_in_data(ax, artist, renderer)
        over_x = max(bx - x0, (x0 + w) - (bx + bw))
        over_y = max(by - y0, (y0 + h) - (by + bh))
        worst = max(over_x, over_y)
        if worst <= float(tol) + 1e-9:
            continue
        if debug:
            _debug_rect(ax, bx, by, bw, bh)
        issues.append(Issue(
            code="overflow", severity="error", file=file,
            message=f"文字「{txt}」越出所在框 {worst:.3f}in"
                    f"（横向 {over_x:.3f} / 纵向 {over_y:.3f}）",
            fix_hint="缩短文字、降到说明字号（模块名 9.5pt / 说明 8.5pt）或加大框；"
                     "长文先用 wrap_to_width() 折行再画",
            detail={"text": txt, "over_x": round(over_x, 4), "over_y": round(over_y, 4),
                    "box": (float(bx), float(by), float(bw), float(bh))},
        ))
    if issues and strict:
        head = "；".join(
            f"「{i.detail['text']}」越界 {max(i.detail['over_x'], i.detail['over_y']):.3f}in"
            for i in issues[:4])
        raise TextOverflowError(f"文字溢出框：{head}（共 {len(issues)} 处）")
    return issues


def _seg_hits_rect(p0, p1, rect) -> bool:
    """Liang–Barsky 裁剪：线段与轴对齐矩形是否相交。"""
    x0, y0, x1, y1 = rect
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, p0[0] - x0), (dx, x1 - p0[0]),
                 (-dy, p0[1] - y0), (dy, y1 - p0[1])):
        if abs(p) < 1e-12:
            if q < 0:
                return False
            continue
        t = q / p
        if p < 0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
        if t0 > t1:
            return False
    return True


#: 公开别名：渲染器可以自己算「这段字会不会压线」（如自动选标注位置）
seg_hits_rect = _seg_hits_rect


def check_text_hits(ax, *, margin_pt: float = 1.0, strict: bool = False,
                    debug: bool = False, ignore: Iterable[str] | None = None,
                    file: str = "") -> list[Issue]:
    """复核「文字压线 / 压边框」。

    与 :func:`check_box_overflow`（文字是否越出所在框）互补：这里拿每条登记过的
    连线（:func:`register_link`）去撞文字的实测 bbox。判据：bbox 按
    ``线宽/2 + margin_pt`` 外扩后仍与线段相交 → 记为压线。

    Parameters
    ----------
    margin_pt : float
        视觉余量（pt），默认 1.0：线离字至少留 1pt，否则读起来像贴着线。
    strict : bool
        有问题时抛 :class:`TextLineCollision`（默认只返回清单）。
    debug : bool
        给压线的文字套一圈 CLAY 虚线框，便于定位。
    ignore : sequence of str, optional
        跳过包含这些子串的文字（如刻意贴线的引线标注）。
    file : str
        报告里的文件名。

    Returns
    -------
    list[Issue]
        每项 code=``hit``，``detail`` 带 ``text / seg``。
    """
    links, renderer = _artists_ready(ax, LINK_ATTR)
    if not links or renderer is None:                        # pragma: no cover
        return []
    hits: list[Issue] = []
    for art in ax.texts:
        txt = str(art.get_text()).strip()
        if not txt:
            continue
        if ignore and any(str(k) in txt for k in ignore):
            continue
        x0, y0, w, h = _extent_in_data(ax, art, renderer)
        for p0, p1, lw in links:
            m = (float(lw) / 2.0 + float(margin_pt)) / 72.0
            rect = (x0 - m, y0 - m, x0 + w + m, y0 + h + m)
            if not _seg_hits_rect(p0, p1, rect):
                continue
            if debug:
                _debug_rect(ax, x0, y0, w, h)
            hits.append(Issue(
                code="hit", severity="warning", file=file,
                message=f"文字「{txt}」压在线条/边框上（余量不足 {margin_pt}pt）",
                fix_hint="挪开这段字、给它让出通路（border_gap()），或缩短连线",
                detail={"text": txt, "seg": (tuple(p0), tuple(p1))},
            ))
            break
    if hits and strict:
        head = "；".join(f"「{i.detail['text']}」" for i in hits[:4])
        raise TextLineCollision(f"文字压线：{head}（共 {len(hits)} 处）")
    return hits


# ------------------------------------------------------------------ 脚本检查
_THEME_RE = re.compile(r"\b(apply_theme|set_paper_style)\s*\(")
_GRID_RE = re.compile(r"\.grid\s*\(\s*(True|.*?(axis|which)\s*=)")
_SAVEFIG_RE = re.compile(r"savefig\s*\((?P<args>[^)]*)\)", re.S)
_FONTSIZE_RE = re.compile(r"fontsize\s*=\s*([0-9]+(?:\.[0-9]+)?)")
_PLOT_SHOW_RE = re.compile(r"\bplt\.show\s*\(")
_STRING_RE = re.compile(r"""(?P<q>["'])(?P<text>(?:\\.|(?!\1).){2,400})\1""")
_CMAP_USE_RE = re.compile(r"cmap\s*=\s*['\"]?([A-Za-z0-9_]+)")
_HEX_RE = re.compile(r"#[0-9A-Fa-f]{6}\b")

# ---- 字体栈规则（R5-02 的第二形态假绿）------------------------------------
#: 能画中文的族名片段（小写比对）。判定用「有没有 CJK 字形」，不是「族名看起来
#: 像衬线字体」——``Times New Roman`` 只覆盖拉丁，单独设成 ``font.family`` 照样
#: 满屏空框，所以它**不在**这张表里；本框架的 ``font_stack()`` 之所以安全，是因为
#: 列表里同时有 ``SimSun``。
_CJK_FAMILY_MARKERS: tuple[str, ...] = (
    "simsun", "宋体", "simhei", "黑体", "microsoft yahei", "微软雅黑",
    "dengxian", "等线", "fangsong", "仿宋", "kaiti", "楷体", "nsimsun", "新宋体",
    "pingfang", "songti", "stheiti", "heiti", "hiragino",
    "noto serif cjk", "noto sans cjk", "source han", "wenquanyi", "wqy",
    "arial unicode ms",
)

#: ``rcParams["font.family"] = [...]`` / ``...['font.sans-serif'] = ...`` / ``update({...})``
_FONT_ASSIGN_RE = re.compile(
    r"""["'](?P<key>font\.(?:family|sans-serif|serif))["']\s*(?:\]\s*=|\}:?|:|=)\s*"""
    r"""(?P<val>\[[^\]]*\]|\([^)]*\)|["'][^"']*["'])""",
)


def _strip_python_comments(src: str) -> str:
    """去掉 ``#`` 行内注释（保守：只处理引号外的 ``#``），免得注释里的示例被当真。"""
    out: list[str] = []
    for line in src.splitlines():
        quote = ""
        cut = len(line)
        for i, ch in enumerate(line):
            if quote:
                if ch == quote:
                    quote = ""
            elif ch in "\"'":
                quote = ch
            elif ch == "#":
                cut = i
                break
        out.append(line[:cut])
    return "\n".join(out)


def _font_names(value: str) -> list[str]:
    """从赋值右侧取出字体族名（``["A", "B"]`` / ``'A'``；变量引用返回空表）。"""
    body = value.strip()
    if body[:1] == "(":
        body = "[" + body[1:-1] + "]"
    return [m.group(1).strip() for m in re.finditer(r"""["']([^"']+)["']""", body)]


def _is_cjk_family(name: str) -> bool:
    low = name.strip().lower()
    return any(marker in low for marker in _CJK_FAMILY_MARKERS)


def _font_stack_issues(src: str, fname: str) -> list[Issue]:
    """脚本自己换字体栈、且栈里没有中文字体 → ``font-family`` error。

    为什么需要：:func:`probe_glyphs` 测的是**本机字体栈**能不能画中文；脚本内部
    再写一行 ``rcParams["font.family"] = ["DejaVu Sans"]``，探针照样绿，图却满屏
    方框。两件事必须分开判：探针管环境，这条规则管脚本。

    支持的写法：``rcParams["font.family"] = ...``、``mpl.rcParams.update({...})``、
    ``plt.rcParams.update({"font.sans-serif": [...]})``（按出现顺序取最后一次赋值）。
    ``plt.rc("font", family=...)`` 这类关键字调用不在解析范围内（保守放过）。
    """
    src = _strip_python_comments(src)
    assigns: list[tuple[int, str, list[str]]] = []
    for m in _FONT_ASSIGN_RE.finditer(src):
        names = _font_names(m.group("val"))
        assigns.append((src[: m.start()].count("\n") + 1, m.group("key"), names))
    if not assigns:
        return []
    assigns.sort(key=lambda a: a[0])

    fam = [a for a in assigns if a[1] == "font.family"]
    sans = [a for a in assigns if a[1] == "font.sans-serif"]
    if fam:
        line, _, names = fam[-1]
        eff = list(names)
        # font.family 里写了通用族 "sans-serif"（或写成空表）时，真正的族名来自
        # font.sans-serif；只改 font.serif 不影响默认渲染，故不参与判定。
        if not eff or any(n.strip().lower() == "sans-serif" for n in eff):
            generic = [n for n in eff if n.strip().lower() != "sans-serif"]
            eff = generic + (sans[-1][2] if sans else [])
    elif sans:
        line, _, names = sans[-1]
        eff = list(names)
    else:
        return []                                  # 只改 font.serif：不影响当前渲染
    if not eff or any(_is_cjk_family(n) for n in eff):
        return []
    shown = ", ".join(repr(n) for n in eff[:4]) + ("…" if len(eff) > 4 else "")
    return [Issue(
        code="font-family", severity="error", file=f"{fname}:L{line}",
        message=(f"脚本把字体栈换成 [{shown}]，其中没有任何中文字体——"
                 f"中文会渲染成空心方框（stderr 里是 Glyph … missing from font(s)）"),
        fix_hint=("删掉这行（apply_theme() 已给出含 SimSun/SimHei 的中文栈），"
                  "或在列表里补 'SimSun'/'Noto Sans CJK SC'；"
                  "只靠字体探针查不出这一种（探针测的是本机栈）"),
        detail={"line": line, "families": eff},
    )]


def check_script(path: str | Path) -> list[Issue]:
    """静态检查一个绘图脚本是否符合本风格（不需要运行它）。

    覆盖：是否 ``apply_theme``、中文 + ``$…$`` 混排、禁用色图/外部色值、
    字号是否在允许集合、是否开网格、``savefig`` 是否带 ``dpi=300``，
    以及**脚本自己换字体栈后还有没有中文字体**（``font-family``，见
    :func:`_font_stack_issues`——字体探针查不出这一种）。
    """
    p = Path(path)
    if not p.exists():
        return [Issue(code="empty", severity="error", file=str(p),
                      message="脚本不存在", fix_hint="检查路径")]
    src = p.read_text(encoding="utf-8", errors="replace")
    issues: list[Issue] = []
    if not _THEME_RE.search(src):
        issues.append(Issue(
            code="theme", severity="error", file=p.name,
            message="脚本没有调用 apply_theme()/set_paper_style()，输出会是 matplotlib 默认风格",
            fix_hint="在 import matplotlib 之后立刻 academic_fig.apply_theme()",
        ))
    for m in _STRING_RE.finditer(src):
        text = m.group("text")
        if len(text) < 2:
            continue
        line = src[: m.start()].count("\n") + 1
        issues.extend(check_text(text, file=p.name, where=f"L{line}"))
    lowered = src.lower()
    for style in FORBIDDEN_STYLES:
        if re.search(rf"\b{re.escape(style.lower())}\b", lowered) and (
                "cmap" in lowered or "palette" in lowered or "color" in lowered):
            issues.append(Issue(
                code="color", severity="error", file=p.name,
                message=f"出现禁用色图/色板名 {style!r}（默认色 = AI 味最重的地方）",
                fix_hint="改用 academic_fig.palette 的 CATEGORICAL 或 cmap_seq/div/disc",
            ))
            break
    for m in _CMAP_USE_RE.finditer(src):
        name = m.group(1)
        if name.lower() in {s.lower() for s in FORBIDDEN_STYLES}:
            line = src[: m.start()].count("\n") + 1
            issues.append(Issue(
                code="color", severity="error", file=f"{p.name}:L{line}",
                message=f"cmap={name!r} 属于禁用色图",
                fix_hint="改用 academic_fig.palette.cmap_seq() / cmap_div() / cmap_disc()",
            ))
    for m in _FONTSIZE_RE.finditer(src):
        size = float(m.group(1))
        if size not in _typo.ALLOWED_SIZES:
            line = src[: m.start()].count("\n") + 1
            issues.append(Issue(
                code="fontsize", severity="warning", file=f"{p.name}:L{line}",
                message=f"fontsize={size:g} 不在允许集合 {list(_typo.ALLOWED_SIZES)} 内",
                fix_hint="用 typography.TEXT_SIZES（body=10/tick=9/legend=9/footnote=8.5）",
            ))
    if _GRID_RE.search(src):
        issues.append(Issue(
            code="grid", severity="warning", file=p.name,
            message="脚本里开启了网格（本风格禁网格，靠细边框和留白分隔）",
            fix_hint="删掉 ax.grid(...)；style_axes(ax) 已强制 grid(False)",
        ))
    for m in _SAVEFIG_RE.finditer(src):
        if "dpi" not in m.group("args"):
            line = src[: m.start()].count("\n") + 1
            issues.append(Issue(
                code="savefig", severity="warning", file=f"{p.name}:L{line}",
                message="savefig 没有显式 dpi=300，PNG 可能达不到期刊要求",
                fix_hint="用 academic_fig.save(fig, 'fig01_name')，它默认 dpi=300 并做体检",
            ))
    if _PLOT_SHOW_RE.search(src):
        issues.append(Issue(
            code="savefig", severity="warning", file=p.name,
            message="脚本调用了 plt.show()（批量出图应只 save）",
            fix_hint="删掉 plt.show()，或只在 __main__ 里按需 show",
        ))
    for m in _HEX_RE.finditer(src):
        hexv = m.group(0).upper()
        if hexv not in {c.upper() for c in _palette_colors()}:
            line = src[: m.start()].count("\n") + 1
            issues.append(Issue(
                code="color", severity="warning", file=f"{p.name}:L{line}",
                message=f"手写色值 {hexv} 不在 palette 中",
                fix_hint="改用 palette.INK / BLUE / tint(...) 等语义色",
            ))
    issues.extend(_font_stack_issues(src, p.name))
    return issues


# ------------------------------------------------------------------ 产物目录检查
def check_dir(path: str | Path, strict: bool = False, *,
              scripts: Sequence[str | Path] | None = None,
              glyph_probe: bool = True,
              stats: dict | None = None) -> list[Issue]:
    """检查一个出图目录：宽度/宽高比、dpi、PDF 是否齐、配色、命名、字形。

    Parameters
    ----------
    path : str | Path
        产物目录（含 ``*.png`` / ``*.pdf`` / ``*.svg``）。
    strict : bool
        严格模式：把「命名不规范」从 ``warning`` 升级为 ``error``
        （发布前应当全绿，所以 `fig_cat_compare` 这类名字必须改）。
    scripts : sequence of paths, optional
        额外要静态检查的脚本；缺省会扫目录下的 ``*.py``。
    glyph_probe : bool
        是否渲染一次中文样张来探测缺字形（约 0.3s）。
    stats : dict, optional
        传入一个 dict 会填入扫描计数（``png`` / ``pdf`` / ``svg`` / ``files``）、
        实际静态检查的脚本数 ``scripts``，以及**本次跳过没做**的检查项 ``skipped``
        （``list[str]``）。CLI 用它打印「已检查 N 张 / 哪些没查」——否则用户不知道
        到底扫没扫到东西，也容易把「没检查」误读成「检查通过」。

    Returns
    -------
    list[Issue]
        结构化问题列表（可能为空）；用 :func:`has_errors` 判退出码。
    """
    root = Path(path)
    issues: list[Issue] = []
    if not root.exists() or not root.is_dir():
        return [Issue(code="empty", severity="error", file=str(root),
                      message="目录不存在", fix_hint="先运行出图脚本，或检查 --dir 路径")]

    pngs = sorted(root.rglob("*.png"))
    pdfs = {p.with_suffix("").relative_to(root).as_posix().lower(): p for p in root.rglob("*.pdf")}
    svgs = sorted(root.rglob("*.svg"))
    if stats is not None:
        stats.update(png=len(pngs), pdf=len(pdfs), svg=len(svgs),
                     files=len(pngs) + len(pdfs) + len(svgs))
    if not pngs and not pdfs and not svgs:
        # 空目录不该算 error：新项目的 ``out/`` 就是空的，先出图再自检才对。
        issues.append(Issue(code="empty", severity="warning", file=str(root),
                            message="目录里还没有 png/pdf/svg 产物（已扫描 0 个文件）",
                            fix_hint="先运行 examples/render_plots.py 或自己的出图脚本"))

    for png in pngs:
        rel = png.relative_to(root).as_posix()
        info = _png_info(png)
        w, h, dpi = info["width"], info["height"], info["dpi"]
        if not w or not h:
            issues.append(Issue(code="size", severity="error", file=rel,
                                message="PNG 头无法解析（文件可能损坏）",
                                fix_hint="重新导出"))
            continue
        aspect = w / h
        if not ASPECT_RANGE[0] <= aspect <= ASPECT_RANGE[1]:
            issues.append(Issue(
                code="size", severity="error", file=rel,
                message=f"宽高比 {aspect:.2f} 超出 {ASPECT_RANGE[0]}–{ASPECT_RANGE[1]}"
                        f"（{w}×{h}px）",
                fix_hint="单栏 3.35in、双栏 7.0in；过高/过宽请拆面板或改横向",
                detail={"width": w, "height": h, "aspect": round(aspect, 3)},
            ))
        if w > 20000 or h > 20000:
            issues.append(Issue(code="size", severity="warning", file=rel,
                                message=f"图像边长过大（{w}×{h}px），期刊系统可能拒收",
                                fix_hint="把 dpi 降到 300 或缩窄画布"))
        # ---- 绝对宽度（R-04）：按栏宽插图会整体缩放，10pt 字号就变成 8.4pt
        if dpi:
            width_in = w / float(dpi)
            nearest = min(WIDTH_TARGETS, key=lambda t: abs(width_in - t))
            if abs(width_in - nearest) > WIDTH_TOL_IN:
                issues.append(Issue(
                    code="width", severity="error", file=rel,
                    message=(f"宽度 {width_in:.2f}in 既不是单栏 {SINGLE_IN}in 也不是双栏 "
                             f"{DOUBLE_IN}in（±{WIDTH_TOL_IN}in，{w}px @{dpi}dpi）——"
                             f"按栏宽插图会被缩放，字号随之失真"),
                    fix_hint=("用 paper_fig('single'|'double') 定画布，或 save(..., "
                              "target_width='single'|'double') 让它回裁到栏宽"),
                    detail={"width_in": round(width_in, 3), "targets": list(WIDTH_TARGETS)},
                ))
        if dpi is None or dpi < MIN_DPI - 1:
            issues.append(Issue(
                code="dpi", severity="error", file=rel,
                message=f"有效 dpi={dpi if dpi is not None else '未写入（默认 72）'}，要求 ≥{MIN_DPI}",
                fix_hint="savefig(..., dpi=300)，或直接用 academic_fig.save()",
                detail={"dpi": dpi},
            ))
        issues.extend(_color_issues(png))
        if not NAME_RE.match(png.stem):
            if png.stem.lower() in COVER_STEMS:
                issues.append(Issue(
                    code="naming", severity="info", file=rel,
                    message=f"{png.stem!r} 属封面/样张/拼版资产，不受 figNN 命名约束",
                    fix_hint="无需处理：论文插图才需要 figNN_ 前缀（README 首图即 style_preview）",
                ))
            else:
                issues.append(Issue(
                    code="naming",
                    severity="error" if strict else "warning",
                    file=rel,
                    message=f"文件名 {png.stem!r} 不符合 figNN_名称 规范",
                    fix_hint="改成 fig01_trend 这类前缀，便于正文引用与排序",
                ))
        key = png.with_suffix("").relative_to(root).as_posix().lower()
        if key not in pdfs:
            issues.append(Issue(
                code="pdf", severity="error", file=rel,
                message="缺少同名 PDF（期刊几乎都要求矢量图）",
                fix_hint="save(fig, stem, formats=('png','pdf')) 一次双出",
            ))

    for key, pdf in pdfs.items():
        rel = pdf.relative_to(root).as_posix()
        info = _pdf_info(pdf)
        if not info["ok"]:
            issues.append(Issue(code="pdf", severity="error", file=rel,
                                message="PDF 文件头无效（可能不是 PDF）",
                                fix_hint="重新导出；不要手动改扩展名"))
            continue
        if info["width_pt"] and info["height_pt"]:
            aspect = info["width_pt"] / info["height_pt"]
            if not ASPECT_RANGE[0] <= aspect <= ASPECT_RANGE[1]:
                issues.append(Issue(
                    code="size", severity="error", file=rel,
                    message=f"PDF 宽高比 {aspect:.2f} 超出 {ASPECT_RANGE[0]}–{ASPECT_RANGE[1]}",
                    fix_hint="调整 paper_fig 的 width/height 或面板数",
                ))
            pdf_w_in = info["width_pt"] / 72.0
            nearest = min(WIDTH_TARGETS, key=lambda t: abs(pdf_w_in - t))
            if abs(pdf_w_in - nearest) > WIDTH_TOL_IN:
                issues.append(Issue(
                    code="width", severity="error", file=rel,
                    message=(f"PDF 宽度 {pdf_w_in:.2f}in 既不是单栏 {SINGLE_IN}in 也不是双栏 "
                             f"{DOUBLE_IN}in（±{WIDTH_TOL_IN}in）"),
                    fix_hint="与 PNG 一起由 academic_fig.save() 导出，别单独 savefig",
                    detail={"width_in": round(pdf_w_in, 3)},
                ))

    for svg in svgs:
        rel = svg.relative_to(root).as_posix()
        head = svg.read_text(encoding="utf-8", errors="replace")[:4000]
        if "<text" not in head and "<tspan" not in head:
            issues.append(Issue(
                code="svg", severity="warning", file=rel,
                message="SVG 里没有 <text>（字形被转成路径），后续无法在 AI/Inkscape 里改字",
                fix_hint="设置 rcParams['svg.fonttype']='none'（apply_theme 已默认）",
            ))

    if glyph_probe:
        env_issues = probe_glyphs()
        issues.extend(env_issues)
        if env_issues:
            for issue in issues:
                if issue.code == "naming":
                    issue.fix_hint += "（另：先修字体，否则导出全是方框）"

    to_scan = list(scripts) if scripts is not None else sorted(root.rglob("*.py"))
    for script in to_scan:
        issues.extend(check_script(script))

    # 「没检查 ≠ 检查通过」：把本次**没做**的项如实记进 stats，CLI 会打印出来，
    # 并在结论行标注「未检查」。纯图目录（只有 png/pdf、没有生成脚本）就是这种
    # 情况：环境字体探针（probe_glyphs）只能证明「本机字体栈能画中文」，证明不了
    # 「这些图里的中文没被画成方框」——那要逐张 OCR 或回到生成脚本，两条都超出
    # 一个目录级检查的能力，所以只能如实上报，不能默默绿灯。
    if stats is not None:
        # 只在结论行里用的短标签；原因放 stats["skip_detail"]，免得结论行套括号套成
        # 「（字形/混排（目录内没有…）：未检查）」。
        skipped: list[str] = []
        detail: dict[str, str] = {}
        if not to_scan:
            skipped.append("字形/混排")
            detail["字形/混排"] = (
                "目录内没有生成脚本（.py），图片内部字形与中文+$混排未逐一核对；"
                "把生成脚本放进该目录，或用 --script 指定")
        if not glyph_probe:
            skipped.append("字形探针")
            detail["字形探针"] = "调用时传了 glyph_probe=False，缺字形未探测"
        stats["skipped"] = skipped
        stats["skip_detail"] = detail
        stats["scripts"] = len(to_scan)

    return sort_issues(issues)


__all__ = [
    "ASPECT_RANGE",
    "BOX_ATTR",
    "COLOR_TOL",
    "COLOR_TOP_N",
    "COVER_STEMS",
    "DOUBLE_IN",
    "FORBIDDEN_STYLES",
    "Issue",
    "LINK_ATTR",
    "MIN_DPI",
    "MIN_MARGIN_PX",
    "NAME_RE",
    "SINGLE_IN",
    "TextLineCollision",
    "TextOverflowError",
    "WIDTH_TARGETS",
    "WIDTH_TOL_IN",
    "check_box_overflow",
    "check_dir",
    "check_script",
    "check_text",
    "check_text_hits",
    "format_report",
    "has_errors",
    "png_margins",
    "probe_glyphs",
    "register_box",
    "register_link",
    "seg_hits_rect",
    "sort_issues",
]