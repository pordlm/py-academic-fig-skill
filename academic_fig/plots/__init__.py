# -*- coding: utf-8 -*-
"""plots —— 一类图一个模块，签名统一 ``f(ax=None, *, data=..., ...) -> ax``。

约定（所有渲染器都遵守）：

1. **先校验、再画**：长度不一致 / 空数据 / 非有限值一律抛 ``ValueError``，
   错误信息要能直接读懂（带参数名、期望与实到）。
2. **签名统一**：``f(ax=None, …) -> matplotlib.axes.Axes``；传 ``ax`` 就画在它上面
   （面板复用），不传就按期刊单栏尺寸新建，``fig = ax.figure``。
3. **颜色只取 ``palette.py``**：不出现字面色值，也不用 ``tab10`` / ``jet`` / ``rainbow``。
4. **不画网格、不加阴影**，图例用 ``base.legend()``（无框 + 自动挑角落）。
5. **无 pandas / scipy / seaborn**：入参接受 list / numpy / pandas Series（鸭子类型），
   统计量（AUC、KDE、PCA、相关）都用 numpy 自己算。
6. **每个模块 docstring 都写清**「这张图要让读者看到什么」+ 3 条该类图的塌陷点。

按大类分组（``cli list`` 按这个顺序显示）：

* 比较与组成：bar / grouped_bar / stacked_bar / lollipop
* 趋势：line / area
* 分布：violin / box / hist
* 关系：scatter / corr
* 统计推断：forest
* 机器学习：roc / pr / confusion
* 降维：pca / radar
* 生存：km
* 组学：volcano / heatmap
* 流程：sankey
"""
from __future__ import annotations

import inspect

import functools

from matplotlib.axes import Axes as _Axes

from . import base
from .area import area
from .bar import bar
from .box import box
from .confusion import confusion
from .corr import corr, corrcoef
from .forest import forest
from .grouped_bar import grouped_bar
from .heatmap import heatmap
from .hist import hist, kde
from .km import kaplan_meier, km
from .line import line
from .lollipop import lollipop
from .pca import pca
from .pr import pr, pr_curve
from .radar import radar
from .roc import roc, roc_curve
from .sankey import sankey
from .scatter import scatter
from .stacked_bar import stacked_bar
from .violin import violin
from .volcano import volcano


def _flexible(fn):
    """允许省略 ``ax``：``f(labels, values)`` 等价于 ``f(None, labels, values)``。

    规则很窄——**第一个位置参数不是 ``Axes`` 且不是 ``None``** 时，才认为调用者
    省了 ``ax``，自动在前面补 ``None``（于是渲染器自己新建单栏画布）。
    这样 ``afg.plots.line(years, series)`` 与 ``afg.plots.line(ax, years, series)``
    两种写法都成立，README 与 ``cli list`` 里的签名才对得上。
    """

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if args and args[0] is not None and not isinstance(args[0], _Axes):
            args = (None,) + args
        return fn(*args, **kwargs)

    wrapper.__wrapped__ = fn  # type: ignore[attr-defined]
    return wrapper


#: 需要「ax 可省」的全部导出名（含别名 roc_curve / pr_curve / kde / kaplan_meier）
_FLEXIBLE_NAMES = (
    "area", "bar", "box", "confusion", "corr", "corrcoef", "forest", "grouped_bar",
    "heatmap", "hist", "kde", "km", "kaplan_meier", "line", "lollipop", "pca",
    "pr", "pr_curve", "radar", "roc", "roc_curve", "sankey", "scatter",
    "stacked_bar", "violin", "volcano",
)
for _name in _FLEXIBLE_NAMES:
    globals()[_name] = _flexible(globals()[_name])
del _name

#: 大类 → (中文名, 顺序)。CLI 的 ``list`` 与示例脚本都按它组织。
CATEGORIES: dict[str, str] = {
    "compare": "比较与组成",
    "trend": "趋势",
    "distribution": "分布",
    "relation": "关系",
    "inference": "统计推断",
    "ml": "机器学习",
    "dimred": "降维与多维",
    "survival": "生存分析",
    "omics": "组学",
    "flow": "流程与流向",
}

#: 图类型注册表（CLI ``list`` 与 ``init --example`` 都读这里）
REGISTRY: dict[str, dict[str, str]] = {
    "bar": {
        "func": "bar",
        "category": "compare",
        "desc": "单序列柱状图：类别对比，只强调 1–2 根关键柱（可加误差棒/显著性括号）",
        "sig": "bar(ax=None, labels, values, *, data=None, errors=None, highlight=None, brackets=None)",
    },
    "grouped_bar": {
        "func": "grouped_bar",
        "category": "compare",
        "desc": "分组柱状图：同一批类别下的多方案/多年度对比（颜色+纹理双编码）",
        "sig": "grouped_bar(ax=None, labels, groups, *, data=None, errors=None, hatch=True)",
    },
    "stacked_bar": {
        "func": "stacked_bar",
        "category": "compare",
        "desc": "堆叠柱状图：组成/占比随时间或类别变化（可归一化到 100%）",
        "sig": "stacked_bar(ax=None, labels, stacks, *, data=None, normalize=False)",
    },
    "lollipop": {
        "func": "lollipop",
        "category": "compare",
        "desc": "棒棒糖图：排序后的类别比较（类别多时比柱图更轻）",
        "sig": "lollipop(ax=None, labels, values, *, data=None, sort=True, highlight=None)",
    },
    "line": {
        "func": "line",
        "category": "trend",
        "desc": "多序列折线：趋势对比 + 置信带 + 阶梯/虚线基线",
        "sig": "line(ax=None, x, series, *, data=None, band=None, step=False, baseline=None)",
    },
    "area": {
        "func": "area",
        "category": "trend",
        "desc": "面积图：单序列趋势或堆叠组成随时间变化（可归一化）",
        "sig": "area(ax=None, x, series, *, data=None, stacked=False, normalize=False)",
    },
    "violin": {
        "func": "violin",
        "category": "distribution",
        "desc": "小提琴图：分布形状对比，内嵌中位数与四分位（可叠抖动散点）",
        "sig": "violin(ax=None, data, *, labels=None, show_points=False, show_median=True)",
    },
    "box": {
        "func": "box",
        "category": "distribution",
        "desc": "箱线图：中位数/四分位/离群点，组名下带样本量 n",
        "sig": "box(ax=None, data, *, labels=None, show_points=True, show_n=True)",
    },
    "hist": {
        "func": "hist",
        "category": "distribution",
        "desc": "直方图：分布形状 + KDE 叠加（可多组对比、带地毯图）",
        "sig": "hist(ax=None, data, *, labels=None, bins='auto', kde_overlay=True, density=True)",
    },
    "scatter": {
        "func": "scatter",
        "category": "relation",
        "desc": "散点图：主体分布 + 高亮分组 + 背景点云 + 可选回归线与 95% 带",
        "sig": "scatter(ax=None, x, y, *, data=None, groups=None, highlight=None, fit=False)",
    },
    "corr": {
        "func": "corr",
        "category": "relation",
        "desc": "相关矩阵热图：双色 cmap、可掩上三角、格内标系数与 n",
        "sig": "corr(ax=None, matrix, *, data=None, names=None, method='pearson', mask_upper=True)",
    },
    "forest": {
        "func": "forest",
        "category": "inference",
        "desc": "森林图：多研究效应量 + 95% CI + 无效线 + 合并效应菱形",
        "sig": "forest(ax=None, labels, estimates, *, lower, upper, pooled=None, null=0.0)",
    },
    "roc": {
        "func": "roc",
        "category": "ml",
        "desc": "ROC 曲线：多曲线 + AUC 写进图例，对角线为随机基线",
        "sig": "roc(ax=None, y_true, y_score, *, data=None, curves=None, positive=1)",
    },
    "pr": {
        "func": "pr",
        "category": "ml",
        "desc": "PR 曲线：精确率-召回率 + AP + 正类比例基线（不均衡数据优选）",
        "sig": "pr(ax=None, y_true, y_score, *, data=None, curves=None, positive=1)",
    },
    "confusion": {
        "func": "confusion",
        "category": "ml",
        "desc": "混淆矩阵：count 或按行归一化，单元格直接标数值",
        "sig": "confusion(ax=None, matrix, *, data=None, labels=None, normalize=False)",
    },
    "pca": {
        "func": "pca",
        "category": "dimred",
        "desc": "PCA 得分图：SVD 计算 + 95% 置信椭圆 + 可选双标图，轴标解释方差",
        "sig": "pca(ax=None, matrix, *, data=None, groups=None, ellipse=True, biplot=False)",
    },
    "radar": {
        "func": "radar",
        "category": "dimred",
        "desc": "雷达图：多维指标轮廓（3–8 个指标，轴序必须说明）",
        "sig": "radar(ax=None, labels, series, *, data=None, fill=False, rmax=None)",
    },
    "km": {
        "func": "km",
        "category": "survival",
        "desc": "Kaplan-Meier 生存曲线：阶梯线 + 删失刻度 + 可选风险人数表",
        "sig": "km(ax=None, time, event, *, data=None, groups=None, risk_table=False)",
    },
    "volcano": {
        "func": "volcano",
        "category": "omics",
        "desc": "火山图：log2FC × −log10 p，阈值线与 top 特征标注",
        "sig": "volcano(ax=None, log2fc, pvalue, *, data=None, names=None, fc_thresh=1.0)",
    },
    "heatmap": {
        "func": "heatmap",
        "category": "omics",
        "desc": "热力图：矩阵数值 + colorbar（seq / div / disc 三套色阶，可逐行 z-score）",
        "sig": "heatmap(ax=None, matrix, *, data=None, rows=None, cols=None, kind='seq', row_zscore=False)",
    },
    "sankey": {
        "func": "sankey",
        "category": "flow",
        "desc": "桑基图：两阶段流向/占比分解，纯 matplotlib patch 手绘",
        "sig": "sankey(ax=None, links, *, data=None, nodes=None, value_fmt='{:.0f}')",
    },
}

#: 所有渲染器（供 ``from academic_fig.plots import *`` 与自检使用）
RENDERERS = {
    "area": area,
    "bar": bar,
    "box": box,
    "confusion": confusion,
    "corr": corr,
    "forest": forest,
    "grouped_bar": grouped_bar,
    "heatmap": heatmap,
    "hist": hist,
    "km": km,
    "line": line,
    "lollipop": lollipop,
    "pca": pca,
    "pr": pr,
    "radar": radar,
    "roc": roc,
    "sankey": sankey,
    "scatter": scatter,
    "stacked_bar": stacked_bar,
    "violin": violin,
    "volcano": volcano,
}


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


for _reg_name, _reg_meta in REGISTRY.items():
    _reg_fn = RENDERERS.get(_reg_name)
    if _reg_fn is not None:
        _reg_meta["sig"] = _sig_text(_reg_name, _reg_fn)


__all__ = [
    "CATEGORIES",
    "REGISTRY",
    "RENDERERS",
    "area",
    "bar",
    "base",
    "box",
    "confusion",
    "corr",
    "corrcoef",
    "forest",
    "grouped_bar",
    "heatmap",
    "hist",
    "kaplan_meier",
    "kde",
    "km",
    "line",
    "lollipop",
    "pca",
    "pr",
    "pr_curve",
    "radar",
    "roc",
    "roc_curve",
    "sankey",
    "scatter",
    "stacked_bar",
    "violin",
    "volcano",
]