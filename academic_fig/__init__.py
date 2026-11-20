# -*- coding: utf-8 -*-
"""academic_fig —— 中文论文插图框架（白纸 + 墨线 + 低饱和强调色）。

最短可用路径（5 行）::

    import matplotlib
    matplotlib.use("Agg")
    import academic_fig as afg

    afg.apply_theme()                                   # 1) 全局风格
    fig, ax = afg.paper_fig("single")                   # 2) 期刊尺寸画布
    afg.panel(ax, "(a)", title="不同处理的响应", ylabel="响应值")
    afg.plots.bar(ax, ["对照", "A", "B"], [42, 55, 62], highlight=[2])
    afg.footnote(fig, "数据来源：…；口径：n=30，误差棒为 1 SD。")
    afg.save(fig, "fig01_response")                     # → fig01_response.png/.pdf

设计约束（贯穿所有模块）：

* **不覆盖数据**：任何图元只在空白处加东西；图例自动挑不压点的角落。
* **只在 palette 里取色**：不出现字面色值，禁用 tab10 / jet / rainbow。
* **无网格、无阴影、无 3D 效果**；坐标轴四边 0.8pt 墨框、刻度朝内。
* **可选依赖只有 numpy / matplotlib**；pandas 可缺（示例退化到 csv/numpy）。
"""
from __future__ import annotations

from . import checks, export, layout, palette, plots, style, typography
from .checks import Issue, check_dir, check_script, check_text, has_errors
from .export import figure_paths, save, save_all
from .layout import (
    DOUBLE,
    SINGLE,
    WIDTHS,
    footnote,
    grid_axes,
    panel,
    panel_note,
    paper_fig,
)
from .style import (
    annotate_point,
    apply_theme,
    axes,
    ink,
    legend,
    reference_circle,
    refline,
    shade_region,
    square,
    threshold,
)

# ------------------------------------------------------------------ 旧名别名
# 迁移自两个源包（B 包 plot_style_template / A 包 plot_style），保证老脚本不改也能跑。
set_paper_style = apply_theme          # B/A 包的入口名
style_axes = axes                      # B/A 包的坐标轴收口
save_paper_figure = save               # B/A 包的导出口
footnote_wrapped = footnote            # B 包的自动折行脚注（已换成缓存 renderer 的快速实现）
panel_result = panel_note              # B 包的面板备注
plot_reference_circle = reference_circle  # A 包旧名

# ------------------------------------------------------------------ 可选子包
# diagrams/ 是正式组成部分，但允许单独缺省（例如只取了绘图部分的精简安装）。
try:
    from . import diagrams  # type: ignore[attr-defined]
except ImportError:  # 只吞「模块不存在」；模块内部写错（NameError 等）必须照常抛
    diagrams = None  # type: ignore[assignment]

__version__ = "0.2.2"


def _compute_build() -> str:
    """生成 build 串：``0.2.2+YYYYMMDD-HHMM``。

    复评时「哪个版本被戳过」必须可判：同一分钟内多文件在改写，靠版本号常量看不出来，
    所以把**最近一次写入 BUILD.json 的时间戳**编进 build 串。

    优先读仓库根的 ``BUILD.json``（``scripts/write_build.py`` 生成，覆盖包内 .py +
    交付面全部文件），这样 ``academic_fig.__build__`` 与 BUILD.json 的 ``build``
    逐字一致；没装脚本或文件缺失时退化为「包内 ``*.py`` 最新 mtime」。
    """
    import datetime as _dt
    import json as _json
    import pathlib as _path

    pkg = _path.Path(__file__).resolve().parent
    stamp_file = pkg.parent / "BUILD.json"
    try:
        data = _json.loads(stamp_file.read_text(encoding="utf-8"))
        build = data.get("build")
        if isinstance(build, str) and build.startswith(__version__ + "+"):
            return build
    except (OSError, ValueError):
        pass

    newest = 0.0
    for path in pkg.rglob("*.py"):
        try:
            newest = max(newest, path.stat().st_mtime)
        except OSError:
            continue
    stamp = _dt.datetime.fromtimestamp(newest) if newest else _dt.datetime.now()
    return f"{__version__}+{stamp.strftime('%Y%m%d-%H%M')}"


__build__ = _compute_build()

__all__ = [
    # ---- 核心 API（docs/ARCH.md §4）----
    "apply_theme",
    "paper_fig",
    "panel",
    "footnote",
    "save",
    "palette",
    "plots",
    # ---- 子模块 ----
    "checks",
    "export",
    "layout",
    "style",
    "typography",
    # ---- 图元 ----
    "axes",
    "legend",
    "refline",
    "reference_circle",
    "threshold",
    "annotate_point",
    "shade_region",
    "square",
    "grid_axes",
    "panel_note",
    "save_all",
    "figure_paths",
    "ink",
    # ---- 旧名别名 ----
    "set_paper_style",
    "style_axes",
    "save_paper_figure",
    "footnote_wrapped",
    "panel_result",
    "plot_reference_circle",
    # ---- 尺寸常量 ----
    "SINGLE",
    "DOUBLE",
    "WIDTHS",
    # ---- 自检 ----
    "Issue",
    "check_dir",
    "check_script",
    "check_text",
    "has_errors",
    # ---- 版本 ----
    "__version__",
    "__build__",
]
