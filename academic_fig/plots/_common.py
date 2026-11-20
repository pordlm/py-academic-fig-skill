# -*- coding: utf-8 -*-
"""plots._common —— 各图共用的入参校验与配色取用。

这些函数只做「把关」，不画东西；错误信息统一成
``ValueError: <函数名>(): <参数名> ...（收到 ...）``，方便直接贴进日志。
"""
from __future__ import annotations

from typing import Any, Iterable, Sequence

import numpy as np

from .. import palette as _pal
from .. import typography as _typo


def as_1d(values: Any, name: str, *, caller: str = "", allow_nan: bool = False,
          min_len: int = 1) -> np.ndarray:
    """转成一维 float 数组，并保证非空、长度达标、值有限。"""
    where = f"{caller}(): " if caller else ""
    arr = np.asarray(values, dtype=float)
    arr = np.ravel(arr)
    if arr.size == 0:
        raise ValueError(f"{where}{name} 为空；至少需要 {min_len} 个数值")
    if arr.size < min_len:
        raise ValueError(f"{where}{name} 至少需要 {min_len} 个数值（收到 {arr.size} 个）")
    if not allow_nan and not np.all(np.isfinite(arr)):
        bad = int(np.sum(~np.isfinite(arr)))
        raise ValueError(f"{where}{name} 含 {bad} 个 NaN/Inf；请先清洗数据"
                         f"（allow_nan=True 可放过 NaN）")
    return arr


def as_matrix(values: Any, name: str, *, caller: str = "", ndim: int = 2) -> np.ndarray:
    """转成二维 float 矩阵（非空、规则、值有限）。"""
    where = f"{caller}(): " if caller else ""
    arr = np.asarray(values, dtype=float)
    if arr.ndim != ndim:
        raise ValueError(f"{where}{name} 需要 {ndim} 维数组（收到 {arr.ndim} 维）")
    if arr.size == 0:
        raise ValueError(f"{where}{name} 为空")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{where}{name} 含 NaN/Inf；矩阵图不接受缺失值，请先补/删")
    return arr


def check_len(name: str, arr: Sequence, expected: int, *, caller: str = "") -> None:
    """长度必须与 ``expected`` 一致。"""
    where = f"{caller}(): " if caller else ""
    got = len(arr)
    if got != expected:
        raise ValueError(f"{where}{name} 长度 {got} 与数据长度 {expected} 不一致")


def as_labels(labels: Any, n: int, name: str = "labels", *, caller: str = "") -> list[str]:
    """类别标签：缺省时用 ``1..n``；给了就必须等长。"""
    if labels is None:
        return [str(i + 1) for i in range(n)]
    seq = list(labels)
    check_len(name, seq, n, caller=caller)
    return [str(x) for x in seq]


def as_bool_mask(mask: Any, n: int, name: str, *, caller: str = "") -> np.ndarray:
    """布尔掩码：接受等长 bool 序列或下标序列。"""
    where = f"{caller}(): " if caller else ""
    arr = np.asarray(mask)
    if arr.dtype == bool:
        if arr.size != n:
            raise ValueError(f"{where}{name} 布尔掩码长度 {arr.size} 与数据长度 {n} 不一致")
        return arr.astype(bool).ravel()
    idx = np.asarray(arr, dtype=int).ravel()
    if idx.size and (idx.min() < 0 or idx.max() >= n):
        raise ValueError(f"{where}{name} 下标越界：允许 0..{n - 1}，收到 {idx.min()}..{idx.max()}")
    out = np.zeros(n, dtype=bool)
    out[idx] = True
    return out


def as_series_map(series: Any, x_len: int, *, caller: str = "") -> dict[str, np.ndarray]:
    """把「多序列」入参统一成 ``{名字: 一维数组}``。

    接受：``dict[str, seq]``、``[(name, seq), ...]``、或二维数组（自动命名 S1..Sn）、
    或单个一维数组（自动命名 Series 1）。
    """
    where = f"{caller}(): " if caller else ""
    if isinstance(series, dict):
        items = list(series.items())
    elif isinstance(series, (list, tuple)) and series and isinstance(series[0], (list, tuple)) \
            and len(series[0]) == 2 and isinstance(series[0][0], str):
        items = [(str(k), v) for k, v in series]
    else:
        arr = np.asarray(series, dtype=float)
        if arr.ndim == 1:
            items = [("Series 1", arr)]
        elif arr.ndim == 2:
            # 判断是 (n_series, n_points) 还是 (n_points, n_series)：取行数更少的作为序列数
            if arr.shape[0] <= arr.shape[1]:
                items = [(f"S{i + 1}", arr[i]) for i in range(arr.shape[0])]
            else:
                items = [(f"S{i + 1}", arr[:, i]) for i in range(arr.shape[1])]
        else:
            raise ValueError(f"{where}series 维度不支持（收到 {arr.ndim} 维）")
    if not items:
        raise ValueError(f"{where}series 为空；至少给一条序列")

    out: dict[str, np.ndarray] = {}
    for name, vals in items:
        arr = as_1d(vals, f"series[{name!r}]", caller=caller)
        if arr.size != x_len:
            raise ValueError(
                f"{where}series[{name!r}] 有 {arr.size} 个点，与 x 的 {x_len} 个点不一致"
            )
        out[str(name)] = arr
    return out


def cat_color(i: int) -> str:
    """第 i 个类别色（循环取 ``palette.CATEGORICAL``）。"""
    return _pal.CATEGORICAL[i % len(_pal.CATEGORICAL)]


def cat_colors(n: int) -> list[str]:
    """n 个类别色（超过 6 个自动用扩展色板，仍不够则循环）。"""
    if n <= len(_pal.CATEGORICAL):
        return list(_pal.CATEGORICAL[:n])
    pool = list(_pal.CATEGORICAL_EXTENDED)
    return [pool[i % len(pool)] for i in range(n)]


def style_lw(i: int) -> float:
    """多序列的线宽也要有差异（粗/细交替），别只靠颜色。"""
    return 1.15 if i == 0 else 0.95


def style_ls(i: int) -> str:
    """多序列线型：实线、长虚、点划、短虚。"""
    return ("-", (0, (5, 2)), (0, (1.2, 1.6)), (0, (6, 2, 1.2, 2)))[i % 4]


def style_marker(i: int) -> str:
    """多序列标记：圆、方、三角、菱。"""
    return ("o", "s", "^", "D")[i % 4]


def set_labels(ax, *, xlabel: str | None = None, ylabel: str | None = None) -> None:
    """只写调用方显式给出的轴标签。

    渲染器不能把没传的标签写成空串——那会抹掉 ``layout.panel(ax, ylabel=...)``
    或用户自己 ``ax.set_ylabel(...)`` 已经设好的文字。
    """
    size = _typo.TEXT_SIZES["label"]
    if xlabel is not None:
        ax.set_xlabel(str(xlabel), fontsize=size)
    if ylabel is not None:
        ax.set_ylabel(str(ylabel), fontsize=size)


def auto_rotate_x(ax, *, rot: float = 30.0) -> bool:
    """列标签挤不下时自动旋转（按真实渲染宽度判断，不靠标签长度猜）。

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        目标坐标轴。
    rot : float
        旋转角度，默认 30°（期刊里最常用的斜排角度）。

    Returns
    -------
    bool
        发生旋转返回 True。

    Notes
    -----
    只在「最宽标签 > 每个刻度分到的槽宽」时动手；本来就放得下时不改版面。
    """
    try:
        fig = ax.figure
        fig.canvas.draw()
        rend = fig.canvas.get_renderer()
    except Exception:  # 非 Agg 后端或画布尚未建立
        return False
    ticks = [t for t in ax.get_xticklabels() if t.get_text()]
    if len(ticks) < 2:
        return False
    slot = ax.get_window_extent(rend).width / max(len(ticks), 1)
    widest = max(t.get_window_extent(rend).width for t in ticks)
    if widest <= slot * 0.96:
        return False
    for t in ticks:
        t.set_rotation(rot)
        t.set_ha("right")
        t.set_rotation_mode("anchor")
    return True
