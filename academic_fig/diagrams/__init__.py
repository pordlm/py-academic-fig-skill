# -*- coding: utf-8 -*-
"""示意图渲染器：分层框架图 / 流程泳道 / 场量响应面 / 几何覆盖 / 门限权衡。

和数据图（:mod:`academic_fig.plots`）不同，示意图**没有数据**，只有版面：
谁能放哪、间距多大、字会不会溢出框。所以这一层全部由纯数据规格（dict / JSON）
驱动，画布做成「1 数据单位 = 1 英寸」（见 :mod:`._canvas`），
ARCH §3 的硬约束（间距 ≥0.25in、圆角 0.02、字号 9.5/8.5pt）就变成了可校验的量。

五个入口
--------
========================  ==============================================
:func:`architecture`     三层框架图（输入 / 方法 / 输出），关键模块 BLUE_T
:func:`flow`             流程图 / 泳道图，判定菱形 + 回流 + 旁支
:func:`field`            场量与响应面：contour / contourf / 3D 曲面 / 散点场
:func:`geometry`         几何 / 覆盖 / 可达性：等比坐标 + 比例尺
:func:`gate`             门限 / 帕累托 / 多次运行包络
========================  ==============================================

所有入口签名一致：``f(spec, *, width=…, height=…, note=…, strict=…, debug=…) -> ax``，
``spec`` 既可以是 dict，也可以是 JSON 文件路径。拿到 ``ax`` 后交给
:func:`academic_fig.save` 即可::

    import academic_fig as afg
    ax = afg.diagrams.architecture("examples/data/diagrams/arch_layers.json")
    afg.save(ax.figure, "examples/out/diagrams/fig01_arch_layers")

规格示例与可运行脚本见 ``examples/render_diagrams.py``。
"""
from __future__ import annotations

import inspect

from ._canvas import (
    MIN_GAP,
    TextOverflowError,
    check_box_overflow,
    load_spec,
    resolve_color,
)
from .architecture import architecture
from .field import field, sample_field
from .flow import flow
from .gate import gate, pareto_front
from .geometry import geometry


__all__ = [
    "architecture", "flow", "field", "geometry", "gate",
    "DIAGRAMS", "RENDERERS", "CATEGORIES",
    "check_box_overflow", "load_spec", "resolve_color",
    "sample_field", "pareto_front", "TextOverflowError", "MIN_GAP",
]

CATEGORIES = {
    "framework": "框架与结构",
    "process": "流程与时序",
    "field": "场量与响应面",
    "geometry": "几何与覆盖",
    "tradeoff": "门限与权衡",
}

DIAGRAMS = {
    "architecture": {
        "func": architecture,
        "category": "framework",
        "desc": "分层框架图：三层（输入/方法/输出）、模块等高、关键模块 BLUE_T 强调、"
                "回流走外侧虚线",
        "sig": "architecture(spec, *, width='double', height=None, note=None, "
               "strict=True, debug=False)",
        "spec_keys": ("title", "layers", "links", "highlight", "footnote"),
    },
    "flow": {
        "func": flow,
        "category": "process",
        "desc": "流程/泳道图：顺序步骤、判定菱形、回流、旁支注释；纵向主线或横向泳道",
        "sig": "flow(spec, *, width='double', height=None, note=None, strict=True, "
               "debug=False, title=None)",
        "spec_keys": ("title", "direction", "lanes", "nodes", "edges", "footnote"),
    },
    "field": {
        "func": field,
        "category": "field",
        "desc": "场量与响应面：contourf/contour/3D 曲面/散点场，声明式场公式，"
                "图注自动标采样步长与点数",
        "sig": "field(spec, *, kind=None, width=None, height=None, note=None, "
               "strict=True)",
        "spec_keys": ("title", "kind", "x", "y", "field", "labels", "levels",
                      "footnote"),
    },
    "geometry": {
        "func": geometry,
        "category": "geometry",
        "desc": "几何/覆盖/可达性：等比坐标、极浅覆盖填充、空心测点、实心关键点、"
                "比例尺与物理单位",
        "sig": "geometry(spec, *, width=None, height=None, note=None, strict=True, "
               "title=None, legend=True)",
        "spec_keys": ("title", "x", "y", "regions", "circles", "lines", "stations",
                      "keypoints", "arrows", "annotations", "scale_bar", "footnote"),
    },
    "gate": {
        "func": gate,
        "category": "tradeoff",
        "desc": "门限/帕累托/多次运行包络：阈值线 CLAY 点划线（图注自动声明"
                "「自设目标，非官方指标」）、非支配解高亮、理想方向箭头",
        "sig": "gate(spec, *, kind=None, width=None, height=None, note=None, "
               "strict=True, title=None)",
        "spec_keys": ("title", "kind", "x", "y", "points", "cloud", "pareto",
                      "thresholds", "runs", "ideal", "footnote"),
    },
}

RENDERERS = {name: meta["func"] for name, meta in DIAGRAMS.items()}

#: 签名由 ``inspect.signature`` 现场生成（acceptance #6）：
#: 手写常量在函数加参数后必然过期，``cli list`` 与文档就会说假话。
def _sig_text(__name: str, __fn) -> str:  # noqa: N802 - 局部辅助函数
    """去掉类型注解的现场签名：CLI 里要能一行读完。"""
    try:
        __sig = inspect.signature(__fn)
    except (TypeError, ValueError):  # pragma: no cover - 纯 C 函数没有签名
        return __name
    __params = [__p.replace(annotation=inspect.Parameter.empty)
                for __p in __sig.parameters.values()]
    __sig = __sig.replace(parameters=__params,
                          return_annotation=inspect.Signature.empty)
    return f"{__name}{__sig}"


for _reg_name, _reg_meta in DIAGRAMS.items():
    _reg_fn = RENDERERS.get(_reg_name)
    if _reg_fn is not None:
        _reg_meta["sig"] = _sig_text(_reg_name, _reg_fn)
