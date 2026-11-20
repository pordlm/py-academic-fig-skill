# -*- coding: utf-8 -*-
"""示意图渲染器入口守卫：主题自检 + spec 未知键校验。

为什么单独成模块
----------------
五个渲染器（architecture / flow / field / geometry / gate）都要在入口做同两件事：

1. **主题自检**——示意图只画几何，不带主题（字号、刻度、脊线全来自 rcParams）。
   用户在裸 matplotlib 里直接调 ``digrams.architecture(spec)``，出来的是 DejaVu
   无衬线 + 灰底 + 外框，和「白纸墨线」完全两个东西。这里检测
   :func:`academic_fig.style.is_themed`：没跑过就发一次 ``UserWarning`` 并自动
   补 ``apply_theme()``（警告只发一次，免得批量渲染刷屏）。

2. **spec 未知键校验**——``sp.get("nodes")`` 这类读法遇到拼错的键
   （``module`` / ``step`` / ``label`` 放错层）不会报错，只会画出一张空图，
   排查代价极高。这里从**渲染器源码本身**扫出它认识的键（``sp.get("x")``、
   ``sp["x"]``），再和传入 spec 的顶层键对账：未知键在 ``strict=True`` 时抛
   :class:`ValueError` 并列出「你可能想写的是哪个键」，``strict=False`` 时只警告。
   键表按模块缓存，源码扫描只做一次。
"""
from __future__ import annotations

import re
import sys
import warnings

__all__ = ["COMMON_SPEC_KEYS", "check_spec_keys", "ensure_theme", "known_spec_keys"]

#: 所有示意图共用的顶层键（渲染器源码里不一定出现，但 spec 里合法）
COMMON_SPEC_KEYS = frozenset({
    "width", "height", "note", "footnote", "title", "kind", "strict", "debug",
    "layer_border",
})

#: 只认「从 sp（= load_spec 之后的顶层 dict）上读」的键；``node.get("label")`` 这种
#: 内层读法不算顶层键——否则键表会被 id/label/from/to 之类内层名淹没，
#: 校验也会变松（顶层写错成 ``nodes`` 之外的内层名就混过去了）。
_GET_RE = re.compile(r"""\bsp\.get\(\s*["']([A-Za-z_]\w*)["']""")
_IDX_RE = re.compile(r"""\bsp\[\s*["']([A-Za-z_]\w*)["']\s*\]""")
_ALIAS_RE = re.compile(r"""^\s*(\w+)\s*=\s*sp\s*$""", re.MULTILINE)
#: ``_axis(sp, "x")`` 这类「把键名当参数传」的读法：键名是调用点的字面量，
#: 光扫 ``sp.get(...)`` 会漏掉，字段表与未知键校验都会缺键。
_CALL_RE = re.compile(r"""\b[A-Za-z_]\w*\(\s*sp\s*,\s*["']([A-Za-z_]\w*)["']""")
_CACHE: dict[str, frozenset[str]] = {}
# 主题兜底的「只警告一次」标记在 academic_fig.style._THEME_WARNED（与数据图共用一处）


def known_spec_keys(module_name: str) -> frozenset[str]:
    """扫渲染器源码，返回它认识的 spec 顶层键（含 :data:`COMMON_SPEC_KEYS`）。"""
    if module_name in _CACHE:
        return _CACHE[module_name]
    mod = sys.modules.get(module_name)
    path = getattr(mod, "__file__", None)
    keys: set[str] = set(COMMON_SPEC_KEYS)
    if path:
        try:
            with open(path, encoding="utf-8") as fh:
                src = fh.read()
        except OSError:
            src = ""
        keys.update(_GET_RE.findall(src))
        keys.update(_IDX_RE.findall(src))
        keys.update(_CALL_RE.findall(src))
        # ``d = sp`` 这类别名也算顶层（渲染器里常见 ``sp = load_spec(spec)`` 后转手）
        for alias in _ALIAS_RE.findall(src):
            keys.update(re.findall(
                rf"""\b{re.escape(alias)}\.get\(\s*["']([A-Za-z_]\w*)["']""", src))
            keys.update(re.findall(
                rf"""\b{re.escape(alias)}\[\s*["']([A-Za-z_]\w*)["']\s*\]""", src))
    keys = {k for k in keys if not k.startswith("_")}
    _CACHE[module_name] = frozenset(keys)
    return _CACHE[module_name]


def _suggest(key: str, pool) -> str:
    """给未知键找最近的合法键（拼写提示，纯 difflib，无第三方依赖）。"""
    import difflib

    hit = difflib.get_close_matches(key, sorted(pool), n=1, cutoff=0.6)
    return f"；你可能想写的是 {hit[0]!r}" if hit else ""


def check_spec_keys(spec: dict, module_name: str, *, strict: bool = True,
                    extra=()) -> list[str]:
    """校验 spec 顶层键；返回未知键列表（strict 时直接抛 ValueError）。

    Parameters
    ----------
    spec : dict
        已经过 :func:`academic_fig.diagrams._canvas.load_spec` 的规格字典。
    module_name : str
        渲染器模块名（通常直接传 ``__name__``），用于按模块缓存键表。
    strict : bool
        True（默认）抛 :class:`ValueError`；False 只发 ``UserWarning``。
    extra : iterable of str
        本次调用额外接受的键（例如 ``kind=`` 这类关键字参数也可写进 spec）。

    Raises
    ------
    ValueError
        ``strict=True`` 且存在未知键时；消息里带可用键表与拼写建议。
    """
    if not isinstance(spec, dict):
        return []
    # ``extra`` 常写作 ``(kind,)``，而 kind 可能为 None：None 不是合法键名，剔掉
    known = set(known_spec_keys(module_name)) | {k for k in (extra or ()) if k}
    unknown = [k for k in spec if k not in known]
    if not unknown:
        return []
    detail = "、".join(f"{k!r}{_suggest(k, known)}" for k in sorted(unknown))
    tail = ("可用顶层键：" + "、".join(sorted(known - COMMON_SPEC_KEYS)) +
            "；公共键：" + "、".join(sorted(COMMON_SPEC_KEYS)))
    msg = (f"{module_name.rsplit('.', 1)[-1]}(): spec 里有未知键 {detail}。"
           f"{tail}。写错了键不会报错，只会画出一张空图——所以这里直接拦下。")
    if strict:
        raise ValueError(msg)
    warnings.warn(msg, UserWarning, stacklevel=3)
    return sorted(unknown)


def ensure_theme() -> bool:
    """示意图入口调用：没跑过 ``apply_theme()`` 就警告一次并自动补上。

    实现统一在 :func:`academic_fig.style._ensure_theme` —— 数据图（``paper_fig`` /
    ``save``）和示意图走**同一条**兜底逻辑，同一个进程里只提示一次。

    Returns
    -------
    bool
        True 表示用户已经显式应用过主题；False 表示本次是守卫代劳的。
    """
    from .. import style as _style

    # stacklevel=4：用户 → diagram() → ensure_theme() → _ensure_theme() → warn
    return _style._ensure_theme("示意图渲染器", stacklevel=4)