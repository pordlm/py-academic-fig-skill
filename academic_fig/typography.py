# -*- coding: utf-8 -*-
"""typography.py —— 字体回退、字号表与「中文 + ``$...$``」静态检查。

设计约束（见 ``docs/ARCH.md`` §3）：

* **Windows 原生路径优先**：``C:\\Windows\\Fonts\\times.ttf`` / ``simsun.ttc`` / ``simhei.ttf``，
  再回退到 WSL 的 ``/mnt/c/Windows/Fonts/...``、Linux/Noto 与 DejaVu。
* **宋体没有粗体字面**：粗体单独走黑体（SimHei）或 Noto Sans CJK Bold，
  用 :func:`bold_family` / :func:`bold_font` 取，别指望 ``fontweight="bold"`` 把宋体加粗。
* **中文与 mathtext 不能同串**：matplotlib 会让 mathtext 接管整段字符串，中文退化成方框。
  :func:`text_safety` 做静态检测，并把 ``$\\rho$``、``$^{-1}$`` 之类改写成 Unicode。

本模块只在被调用时注册字体（``import academic_fig`` 不触发字体缓存构建）。
"""
from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Sequence

# ---------------------------------------------------------------- 候选字体路径
_WIN = Path(r"C:\Windows\Fonts")

_LATIN_CANDIDATES: tuple[Path, ...] = (
    _WIN / "times.ttf",
    _WIN / "timesbd.ttf",
    _WIN / "timesi.ttf",
    Path("/mnt/c/Windows/Fonts/times.ttf"),
    Path("/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"),
    # macOS：系统自带 Times 系（Times.ttc 在 Supplemental 里，路径随系统版本变动，
    # 因此这里主要靠 family 名回退，文件路径只作尽力而为）
    Path("/System/Library/Fonts/Supplemental/Times New Roman.ttf"),
    Path("/Library/Fonts/Times New Roman.ttf"),
)

_CJK_CANDIDATES: tuple[Path, ...] = (
    _WIN / "simsun.ttc",          # 宋体：中文正文
    _WIN / "simhei.ttf",          # 黑体：粗体 / 强提示
    _WIN / "msyh.ttc",            # 微软雅黑：兜底
    Path("/mnt/c/Windows/Fonts/simsun.ttc"),
    # macOS：PingFang 是 .ttc 且不含宋体字面，宋体优先 Songti SC
    Path("/System/Library/Fonts/Supplemental/Songti.ttc"),
    Path("/System/Library/Fonts/PingFang.ttc"),
    Path("/System/Library/Fonts/Supplemental/STHeiti Light.ttc"),
    Path("/System/Library/Fonts/STHeiti Light.ttc"),
    Path("/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    Path("/usr/share/fonts/truetype/arphic/uming.ttc"),
)

_BOLD_CANDIDATES: tuple[Path, ...] = (
    _WIN / "simhei.ttf",          # SimSun 无粗体字面 → 粗体一律走黑体
    _WIN / "msyhbd.ttc",
    Path("/mnt/c/Windows/Fonts/simhei.ttf"),
    # macOS：黑体（PingFang / STHeiti）——宋体没有粗体字面，别把 Songti 放进粗体档
    Path("/System/Library/Fonts/STHeiti Medium.ttc"),
    Path("/System/Library/Fonts/PingFang.ttc"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
)

#: 按 **family 名**回退（不依赖具体文件路径）：macOS 上字体文件路径随系统版本漂移，
#: 而 ``font.family`` 是按名字解析的，所以名字这一层才是 mac 的真正保险。
_FAMILY_FALLBACK: dict[str, tuple[str, ...]] = {
    "cjk": ("SimSun", "宋体", "Songti SC", "STSong", "PingFang SC", "Noto Serif CJK SC",
            "Source Han Serif SC", "Noto Sans CJK SC", "WenQuanYi Zen Hei", "DejaVu Serif"),
    "bold": ("SimHei", "黑体", "PingFang SC", "Heiti SC", "STHeiti", "Noto Sans CJK SC",
             "Source Han Sans SC", "WenQuanYi Zen Hei", "DejaVu Sans"),
    "latin": ("Times New Roman", "Liberation Serif", "Nimbus Roman", "DejaVu Serif"),
}

#: 字号表（与 ``docs/ARCH.md`` §3、``SKILL.md`` §3 逐字一致）
TEXT_SIZES: dict[str, float] = {
    "body": 10.0,          # font.size
    "title": 11.0,         # 子图标题（不加粗）
    "label": 10.0,         # 轴标签
    "tick": 9.0,           # 刻度
    "legend": 9.0,         # 图例
    "footnote": 8.5,       # 图注
    "footnote_wrapped": 7.2,  # 需要折行时的图注
    "diagram_module": 9.5,    # 框架图模块名
    "diagram_branch": 8.0,    # 框架图分支标注（「是」/「否」）
    "diagram_title": 12.0,    # 示意图整幅标题（不加粗，封顶 12pt）
}

#: checks.py 用的「允许字号集合（pt）」。
#: 不变式：``set(TEXT_SIZES.values()) == set(ALLOWED_SIZES)``（``scripts/check_docs.py`` 断言）。
#: 新增档位必须两边同时登记，否则自检等于放水。
ALLOWED_SIZES: tuple[float, ...] = (
    7.2, 8.0, 8.5, 9.0, 9.5, 10.0, 11.0, 12.0,
)

#: 低于该字号在任何印刷尺寸下都不可读
MIN_SIZE: float = 5.0

_REGISTERED: dict[str, object] | None = None


# ---------------------------------------------------------------- 注册与查询
def _register(paths: Sequence[Path]) -> list[tuple[str, str]]:
    """注册候选字体文件，返回 ``[(字体族名, 文件路径), ...]``（顺序即优先级）。"""
    from matplotlib import font_manager as fm

    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    for p in paths:
        try:
            if not p.exists():
                continue
            fm.fontManager.addfont(str(p))
            name = fm.FontProperties(fname=str(p)).get_name()
        except Exception:  # 字体损坏 / 权限问题：静默跳过，继续回退
            continue
        if name and name not in seen:
            seen.add(name)
            found.append((name, str(p)))
    return found


def ensure_registered() -> dict[str, object]:
    """一次性注册字体；返回 ``{"latin": [...], "cjk": [...], "bold": [...]}``。"""
    global _REGISTERED
    if _REGISTERED is not None:
        return _REGISTERED
    _REGISTERED = {
        "latin": _register(_LATIN_CANDIDATES),
        "cjk": _register(_CJK_CANDIDATES),
        "bold": _register(_BOLD_CANDIDATES),
    }
    return _REGISTERED


@lru_cache(maxsize=1)
def _available_families() -> frozenset[str]:
    """matplotlib 当前**认得到的**族名集合（小写）。

    为什么需要它：``font.family`` 里只要出现一个不存在的族名，matplotlib 每次排字都会往
    stderr 打一行 ``findfont: Font family '…' not found.``——把跨平台兜底名全塞进去会让
    每张图刷几十行噪音（自检脚本按 stderr 判失败，安装器输出也会被淹）。所以先问
    fontManager 有哪些族，再挑兜底名，**只保留真能用的**。
    """
    from matplotlib import font_manager as fm

    ensure_registered()
    names: set[str] = set()
    try:
        for entry in fm.fontManager.ttflist:
            names.add(entry.name.lower())
        for entry in getattr(fm.fontManager, "afmlist", []):
            names.add(entry.name.lower())
    except Exception:  # pragma: no cover - fontManager 结构变化时退化为不兜底
        return frozenset()
    return frozenset(names)


def _family_or_none(name: str) -> str | None:
    """族名可用就返回原名，否则 ``None``（避免 findfont 噪音）。"""
    return name if name.lower() in _available_families() else None


def latin_family() -> str:
    """西文字体族名（Times New Roman 优先；找不到退 DejaVu Serif）。"""
    reg = ensure_registered()
    found = reg["latin"]  # type: ignore[assignment]
    return found[0][0] if found else "DejaVu Serif"


def cjk_family() -> str:
    """中文字体族名（SimSun 优先；找不到退 DejaVu Sans）。"""
    reg = ensure_registered()
    found = reg["cjk"]  # type: ignore[assignment]
    return found[0][0] if found else "DejaVu Sans"


def bold_family() -> str:
    """粗体专用族名（SimHei，因为宋体没有粗体字面）。"""
    reg = ensure_registered()
    found = reg["bold"]  # type: ignore[assignment]
    return found[0][0] if found else "DejaVu Sans"


def font_stack(cjk: bool = True) -> list[str]:
    """rcParams 用的字体栈：西文 → 中文 → 粗体 → 平台族名兜底 → DejaVu。

    matplotlib ≥3.6 支持逐字回退（``font.family`` 是一串族名，缺字形时按顺序试下一个），
    所以这里给的是**一条链**而不是单个字体。链尾追加 :data:`_FAMILY_FALLBACK`，
    是为了 macOS：那里的字体文件路径随系统版本漂移（PingFang/Songti 在 ``/System/Library``
    或 ``Supplemental`` 下），按文件名注册经常一个都命中，但按**族名**解析一定成功。
    """
    stack = [latin_family()]
    if cjk:
        stack.append(cjk_family())
        stack.append(bold_family())
        stack.extend(_FAMILY_FALLBACK["bold"])
        stack.extend(_FAMILY_FALLBACK["cjk"])
    stack.extend(_FAMILY_FALLBACK["latin"])
    stack.append("DejaVu Serif")
    out: list[str] = []
    for name in stack:
        # 兜底名要与 fontManager 对照：不存在的族名不写进 font.family（否则 stderr 噪音）
        resolved = name if name in (latin_family(), cjk_family(), bold_family(), "DejaVu Serif") \
            else _family_or_none(name)
        if resolved and resolved not in out:
            out.append(resolved)
    return out


def bold_font(size: float | None = None):
    """返回 ``FontProperties``：显式指定黑体，用于中文粗体标题。"""
    from matplotlib.font_manager import FontProperties

    kwargs = {"family": bold_family(), "weight": "bold"}
    if size is not None:
        kwargs["size"] = size
    return FontProperties(**kwargs)


def font_status() -> dict[str, object]:
    """诊断用：实际命中的字体文件、缺失的候选、字号表。"""
    reg = ensure_registered()
    missing = [
        str(p)
        for group in (_LATIN_CANDIDATES, _CJK_CANDIDATES, _BOLD_CANDIDATES)
        for p in group
        if not p.exists()
    ]
    return {
        "latin": list(reg["latin"]),
        "cjk": list(reg["cjk"]),
        "bold": list(reg["bold"]),
        "stack": font_stack(),
        "missing_candidates": missing,
        "sizes": dict(TEXT_SIZES),
        "allowed_sizes": list(ALLOWED_SIZES),
    }


# ---------------------------------------------------------------- 字形覆盖
@lru_cache(maxsize=64)
def _charmap(font_path: str) -> frozenset[int]:
    from matplotlib.ft2font import FT2Font

    return frozenset(FT2Font(font_path).get_charmap())


def _font_paths(families: Iterable[str] | None = None) -> list[str]:
    from matplotlib import font_manager as fm

    names = list(families) if families is not None else font_stack()
    paths: list[str] = []
    for name in names:
        try:
            path = fm.findfont(fm.FontProperties(family=name), fallback_to_default=False)
        except Exception:
            continue
        if path and path not in paths and os.path.exists(path):
            paths.append(path)
    return paths


def missing_glyphs(text: str, families: Iterable[str] | None = None) -> list[str]:
    """返回字体栈里所有候选字体都缺字形的字符（去重、保持出现顺序）。

    这是**静态**检查：只看字符是否被某个候选字体覆盖，不等价于渲染（matplotlib 有逐字回退）。
    用来提前发现「用了一个连 SimSun 都没有的符号」这类问题。
    """
    if not text:
        return []
    paths = _font_paths(families)
    if not paths:
        return []
    covered: set[int] = set()
    for p in paths:
        covered |= _charmap(p)
    out: list[str] = []
    for ch in text:
        if ch.isspace():
            continue
        if ord(ch) not in covered and ch not in out:
            out.append(ch)
    return out


# ---------------------------------------------------------------- 中文 / mathtext
CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\u3000-\u303f\uff00-\uffef]")
MATH_RE = re.compile(r"(?<!\\)\$([^$]+)\$")

_GREEK = {
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "epsilon": "ε",
    "varepsilon": "ε", "zeta": "ζ", "eta": "η", "theta": "θ", "vartheta": "ϑ",
    "iota": "ι", "kappa": "κ", "lambda": "λ", "mu": "μ", "nu": "ν",
    "xi": "ξ", "pi": "π", "rho": "ρ", "sigma": "σ", "tau": "τ",
    "upsilon": "υ", "phi": "φ", "varphi": "φ", "chi": "χ", "psi": "ψ",
    "omega": "ω", "Gamma": "Γ", "Delta": "Δ", "Theta": "Θ", "Lambda": "Λ",
    "Xi": "Ξ", "Pi": "Π", "Sigma": "Σ", "Phi": "Φ", "Psi": "Ψ", "Omega": "Ω",
}

_SYMBOLS = {
    "times": "×", "cdot": "·", "div": "÷", "pm": "±", "mp": "∓",
    "leq": "≤", "le": "≤", "geq": "≥", "ge": "≥", "neq": "≠", "approx": "≈",
    "sim": "∼", "propto": "∝", "infty": "∞", "partial": "∂", "nabla": "∇",
    "rightarrow": "→", "to": "→", "leftarrow": "←", "Rightarrow": "⇒",
    "leftrightarrow": "↔", "sum": "Σ", "prod": "Π", "int": "∫",
    "in": "∈", "notin": "∉", "subset": "⊂", "cup": "∪", "cap": "∩",
    "angle": "∠", "perp": "⊥", "parallel": "∥", "degree": "°",
    "prime": "′", "ldots": "…", "cdots": "⋯", "sqrt": "√", "min": "min",
    "max": "max", "log": "log", "exp": "exp", "sin": "sin", "cos": "cos",
    "tan": "tan", "det": "det", "arg": "arg", "mathrm": "", "text": "",
}

_SUP = {
    "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴", "5": "⁵", "6": "⁶",
    "7": "⁷", "8": "⁸", "9": "⁹", "-": "⁻", "+": "⁺", "n": "ⁿ", "i": "ⁱ",
    "T": "ᵀ", "a": "ᵃ", "b": "ᵇ", "c": "ᶜ", "d": "ᵈ", "e": "ᵉ", "k": "ᵏ",
    "m": "ᵐ", "p": "ᵖ", "t": "ᵗ", "x": "ˣ", "y": "ʸ", "z": "ᶻ",
}
_SUB = {
    "0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄", "5": "₅", "6": "₆",
    "7": "₇", "8": "₈", "9": "₉", "i": "ᵢ", "j": "ⱼ", "k": "ₖ", "n": "ₙ",
    "t": "ₜ", "x": "ₓ", "a": "ₐ", "e": "ₑ", "o": "ₒ", "p": "ₚ", "s": "ₛ",
    "u": "ᵤ", "v": "ᵥ", "+": "₊", "-": "₋",
}


def _sup(match: re.Match[str]) -> str:
    body = match.group(1)
    if len(body) > 4:  # 长上标没有对应的 Unicode，保留括号提示人工改写
        return "^(" + body + ")"
    return "".join(_SUP.get(ch, ch) for ch in body)


def _sub(match: re.Match[str]) -> str:
    body = match.group(1)
    if len(body) > 4:
        return "_(" + body + ")"
    return "".join(_SUB.get(ch, ch) for ch in body)


def _unicode_math(expr: str) -> str:
    """把一小段 mathtext 尽量改成 Unicode 文本（不保证 100% 无损）。"""
    s = expr.strip()
    s = re.sub(r"\\(?:mathrm|text|mathit|mathbf|operatorname)\{([^{}]*)\}", r"\1", s)
    s = re.sub(r"\^\{([^{}]*)\}", _sup, s)
    s = re.sub(r"\^(\w)", lambda m: _SUP.get(m.group(1), m.group(1)), s)
    s = re.sub(r"_\{([^{}]*)\}", _sub, s)
    s = re.sub(r"_(\w)", lambda m: _SUB.get(m.group(1), m.group(1)), s)
    for cmd in sorted(_SYMBOLS, key=len, reverse=True):
        s = s.replace("\\" + cmd, _SYMBOLS[cmd])
    s = s.replace("\\,", " ").replace("\\;", " ").replace("\\ ", " ")
    s = s.replace("\\left", "").replace("\\right", "")
    s = s.replace("{", "").replace("}", "")
    s = s.replace("\\", "")
    return re.sub(r"\s+", " ", s).strip()


def unicode_math(expr: str) -> str:
    """公开别名：把 ``\\rho^{-1}`` 这类 mathtext 片段改写成 Unicode。"""
    return _unicode_math(expr)


def has_cjk(text: str) -> bool:
    """文本里是否含中日韩文字或全角标点。"""
    return bool(CJK_RE.search(text or ""))


def has_mathtext(text: str) -> bool:
    """文本里是否含 ``$...$`` mathtext 片段。"""
    return bool(MATH_RE.search(text or ""))


def text_safety(text: str) -> dict[str, object]:
    """静态检查一段文本是否违反「中文 + ``$...$`` 不能同串」的硬约束。

    Parameters
    ----------
    text : str
        要检查的字符串（通常是坐标轴标签、标题、图注）。

    Returns
    -------
    dict
        ``{"safe": bool, "has_cjk": bool, "has_mathtext": bool,
        "issues": list[str], "suggestion": str, "rewritten": str}``。
        ``rewritten`` 是尽力改写后的文本；``suggestion`` 可直接贴进改图提示。
    """
    text = text or ""
    cjk = has_cjk(text)
    math = has_mathtext(text)
    rewritten = MATH_RE.sub(lambda m: _unicode_math(m.group(1)), text) if math else text
    issues: list[str] = []
    suggestion = ""

    if cjk and math:
        issues.append(
            "同一字符串里同时出现中文与 $...$ mathtext：matplotlib 会让 mathtext 接管整段，中文会变成方框"
        )
        suggestion = f"改写为：{rewritten}（用 Unicode 希腊字母/上下标）；精确公式放到图注或单独一行"
        missing = missing_glyphs(rewritten)
        if missing:
            suggestion += f"；注意字体栈缺字：{'、'.join(missing)}，请换成更基础的字符"

    missing_all = missing_glyphs(text)
    if missing_all:
        issues.append(f"字体栈（Times/SimSun/SimHei/DejaVu）缺这些字符的字形：{'、'.join(missing_all)}")
        if not suggestion:
            suggestion = "换用常见字符，或安装带该字形的中文字体（SimSun/SimHei/Noto CJK）"

    return {
        "safe": not issues,
        "has_cjk": cjk,
        "has_mathtext": math,
        "issues": issues,
        "suggestion": suggestion,
        "rewritten": rewritten,
    }


def check_text(text: str) -> list[str]:
    """只返回问题列表（空列表 = 通过），供 checks.py / CLI 打印。"""
    return list(text_safety(text)["issues"])  # type: ignore[arg-type]


__all__ = [
    "ALLOWED_SIZES",
    "MIN_SIZE",
    "TEXT_SIZES",
    "bold_family",
    "bold_font",
    "cjk_family",
    "ensure_registered",
    "font_stack",
    "font_status",
    "has_cjk",
    "has_mathtext",
    "latin_family",
    "missing_glyphs",
    "text_safety",
    "check_text",
    "unicode_math",
]