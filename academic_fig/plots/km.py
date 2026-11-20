# -*- coding: utf-8 -*-
"""km —— Kaplan-Meier 生存曲线（阶梯线 + 删失刻度 + 可选风险人数表）。

**这张图要让读者看到什么**：两组生存曲线何时分开、分开后是否一直保持，
以及每组在每个时间点还剩多少人（风险人数决定尾部可信度）。

塌陷点提醒
1. 样本少（每组 < 10）却画到曲线末端 → 尾部是 1–2 人撑的，必须标风险人数；
2. 不标删失（censoring）→ 读者无法区分「随访结束」与「发生事件」；
3. 曲线交叉却只报中位生存期 → 中位数会掩盖交叉，图注要说清。
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np

from .. import palette as _pal
from .. import typography as _typo
from . import base as _base
from ._common import as_1d, check_len, style_ls


def kaplan_meier(time: Any, event: Any) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """计算 KM 生存曲线（纯 numpy）。

    Returns
    -------
    (times, survival, at_risk) : (ndarray, ndarray, ndarray)
        阶梯节点时间、对应生存率、每个事件时刻的风险人数。
    """
    t = as_1d(time, "time", caller="kaplan_meier").astype(float)
    e = as_1d(event, "event", caller="kaplan_meier")
    check_len("event", e, t.size, caller="kaplan_meier")
    if t.size == 0:
        raise ValueError("kaplan_meier(): time 为空")
    if np.any(t < 0):
        raise ValueError("kaplan_meier(): time 不能为负")
    ev = np.asarray([bool(v) for v in e], dtype=bool)
    order = np.argsort(t, kind="mergesort")
    t, ev = t[order], ev[order]

    uniq = np.unique(t)
    surv = [1.0]
    at_risk = []
    s = 1.0
    for u in uniq:
        n_risk = int(np.sum(t >= u))
        d = int(np.sum((t == u) & ev))
        at_risk.append(n_risk)
        if d > 0 and n_risk > 0:
            s *= 1.0 - d / n_risk
        surv.append(s)
    return np.r_[0.0, uniq], np.asarray(surv), np.asarray(at_risk, dtype=int)


def km(ax=None, time: Any | None = None, event: Any | None = None, *,
       data: Any | None = None, groups: Mapping[str, tuple] | None = None,
       xlabel: str | None = None, ylabel: str | None = None, censor_marks: bool = True,
       risk_table: bool = False, risk_times: Sequence[float] | None = None,
       legend: bool = True, ci: bool = False, max_time: float | None = None):
    """画 Kaplan-Meier 生存曲线。

    Parameters
    ----------
    ax : matplotlib.axes.Axes, optional
        目标坐标轴；``None`` 时新建。
    time, event : sequence, optional
        随访时间与事件指示（1=事件，0=删失），单组时使用。
    data : Mapping, optional
        ``{"time": …, "event": …}`` 或 ``{"groups": {名: (time, event)}}``。
    groups : Mapping[str, (time, event)], optional
        多组：组名 → (时间, 事件)。
    censor_marks : bool
        是否在删失时间点画竖刻度（论文里几乎必需）。
    risk_table : bool
        是否在底部列风险人数（每组每个时间点）。
    risk_times : sequence of float, optional
        风险人数表的时间点；缺省按时间范围取 5 个整点。
    ci : bool
        是否加 95% 置信带（Greenwood 方差，近似）。
    max_time : float, optional
        截断横轴（尾部样本太少时）。

    Returns
    -------
    matplotlib.axes.Axes
        画好图的坐标轴。
    """
    ax = _base.ensure_ax(ax)
    if data is not None:
        groups = _base.pick(data, "groups", default=groups)
        time = _base.pick(data, "time", default=time)
        event = _base.pick(data, "event", default=event)
    if groups is None:
        if time is None or event is None:
            raise ValueError("km(): 需要 (time, event) 或 groups={名: (time, event)}")
        groups = {"全部样本": (time, event)}
    if not isinstance(groups, Mapping) or not groups:
        raise ValueError("km(): groups 必须是非空映射 {组名: (time, event)}")

    curves = []
    t_max = 0.0
    for name, pair in groups.items():
        if len(pair) != 2:
            raise ValueError(f"km(): groups[{name!r}] 需要 (time, event) 两个序列")
        tt, ss, ar = kaplan_meier(pair[0], pair[1])
        if tt.size < 2:
            raise ValueError(f"km(): 组 {name!r} 没有有效随访时间")
        curves.append((str(name), tt, ss, ar, np.asarray(pair[0], dtype=float),
                       np.asarray([bool(v) for v in np.ravel(pair[1])])))
        t_max = max(t_max, float(tt.max()))

    if max_time is not None:
        t_max = min(t_max, float(max_time))
        if t_max <= 0:
            raise ValueError(f"km(): max_time 必须为正（收到 {max_time}）")

    for i, (name, tt, ss, ar, raw_t, raw_e) in enumerate(curves):
        color = _pal.CATEGORICAL[i % len(_pal.CATEGORICAL)]
        ax.step(tt, ss, where="post", color=color, lw=1.15, ls=style_ls(i),
                label=f"{name}（n={raw_t.size}）", zorder=3 + i * 0.1)
        if ci and tt.size > 2:
            # Greenwood 近似：方差累积（简化为按风险人数衰减）
            var = np.cumsum(1.0 / np.clip(ar, 1, None) ** 2)
            var = np.r_[0.0, var]
            se = ss * np.sqrt(np.clip(var, 0.0, None))
            ax.fill_between(tt, np.clip(ss - 1.96 * se, 0, 1), np.clip(ss + 1.96 * se, 0, 1),
                            step="post", color=_pal.tint(color, 0.13), edgecolor="none",
                            zorder=1.5)
        if censor_marks:
            cens_t = raw_t[~raw_e]
            cens_t = cens_t[cens_t <= t_max]
            if cens_t.size:
                # 在曲线上取删失时刻的生存率
                idx = np.searchsorted(tt, cens_t, side="right") - 1
                ax.plot(cens_t, ss[np.clip(idx, 0, ss.size - 1)], linestyle="none",
                        marker="|", ms=5.0, mew=0.9, color=color, zorder=4 + i * 0.1)

    ax.set_xlim(0.0, t_max * 1.02)
    ax.set_ylim(0.0, 1.02)
    ax.set_xlabel(xlabel or "随访时间", fontsize=_typo.TEXT_SIZES["label"])
    ax.set_ylabel(ylabel or "生存率", fontsize=_typo.TEXT_SIZES["label"])

    if risk_table:
        if risk_times is None:
            # 从 t_max 的一小段之后开始：t=0 那一列正好压在左边框/组名上
            ticks = np.unique(np.round(np.linspace(t_max * 0.15, t_max, 4)))
        else:
            ticks = np.asarray(risk_times, dtype=float)
            if ticks.ndim != 1 or ticks.size == 0:
                raise ValueError("km(): risk_times 需要非空的一维时间点序列")
        # 表格画在「刻度标签 + 轴标签」之下：先量出装饰占高，再按 inch 排行，
        # 这样表头/数字不会叠在 0/5/10 刻度上（也不用动 axes 的 position）。
        fig = ax.figure
        fig.canvas.draw()
        rend = fig.canvas.get_renderer()
        fw_in, fh_in = (float(v) for v in fig.get_size_inches())
        fig_dpi = float(fig.dpi)
        ax_px = ax.get_window_extent(rend)
        ax_y0_in = float(ax_px.y0) / fig_dpi
        deco_in = max(ax_y0_in - float(ax.get_tightbbox(rend).y0) / fig_dpi, 0.0)
        row_in = 0.20
        n_rows = len(curves) + 1  # 表头（时间点）+ 每条曲线
        need_below_in = deco_in + 0.10 + row_in * n_rows + 0.06
        if ax_y0_in < need_below_in:
            # 画布底部放不下风险人数表：先长高画布，再把所有 axes 按 inch 上移
            extra_in = need_below_in - ax_y0_in
            new_h_in = fh_in + extra_in
            fig.set_size_inches(fw_in, new_h_in, forward=True)
            for other in fig.axes:
                p = other.get_position()
                other.set_position([p.x0, (p.y0 * fh_in + extra_in) / new_h_in,
                                    p.width, p.height * fh_in / new_h_in])
            for txt in fig.texts:
                tx, ty = txt.get_position()
                txt.set_position((tx, (ty * fh_in + extra_in) / new_h_in))
            fh_in = new_h_in
            fig.canvas.draw()
            rend = fig.canvas.get_renderer()
            ax_y0_in = float(ax.get_window_extent(rend).y0) / fig_dpi
            deco_in = max(ax_y0_in - float(ax.get_tightbbox(rend).y0) / fig_dpi, 0.0)
        # 左列组名要占一条带：量出最宽的名字，不够就把绘图区右移（右边界不动），
        # 否则「标准化疗」会顶到画布外、还会和 t=0 那一列数字粘在一起。
        probe = fig.text(0.0, 0.0, "", fontsize=_typo.TEXT_SIZES["footnote"])
        label_w_px = 0.0
        for name, *_rest in curves:
            probe.set_text(str(name))
            label_w_px = max(label_w_px, float(probe.get_window_extent(rend).width))
        probe.set_text("风险人数")
        label_w_px = max(label_w_px, float(probe.get_window_extent(rend).width))
        probe.remove()
        need_x0 = (label_w_px / fig_dpi + 0.06) / max(fw_in, 1e-6)
        pos = ax.get_position()
        if pos.x0 < need_x0:
            new_w = max(pos.x1 - need_x0, 0.35)
            ax.set_position([need_x0, pos.y0, new_w, pos.height])
            fig.canvas.draw()
            rend = fig.canvas.get_renderer()
            ax_y0_in = float(ax.get_window_extent(rend).y0) / fig_dpi
            deco_in = max(ax_y0_in - float(ax.get_tightbbox(rend).y0) / fig_dpi, 0.0)
        y_head_in = ax_y0_in - deco_in - 0.10
        x_left = float(ax.get_position().x0) - 0.012

        def _x_of(tk: float) -> float:
            return float(ax.transData.transform((float(tk), 0.0))[0]) / (fw_in * fig_dpi)

        def _put(x: float, y_in: float, s: str, color: str, ha: str = "center") -> None:
            fig.text(x, max(y_in, 0.0) / max(fh_in, 1e-6), s, ha=ha, va="center",
                     fontsize=_typo.TEXT_SIZES["footnote"], color=color)

        _put(x_left, y_head_in, "风险人数", _pal.INK_SOFT, ha="right")
        for tk in ticks:
            _put(_x_of(tk), y_head_in, f"{tk:g}", _pal.INK_SOFT)
        for i, (name, _tt, _ss, _ar, raw_t, _raw_e) in enumerate(curves):
            y = y_head_in - row_in * (i + 1)
            counts = [int(np.sum(raw_t >= tk)) for tk in ticks]
            _put(x_left, y, str(name), _pal.INK_SOFT, ha="right")
            for tk, c in zip(ticks, counts):
                _put(_x_of(tk), y, f"{c:d}", _pal.CATEGORICAL[i % len(_pal.CATEGORICAL)])

    if legend:
        _base.legend(ax, loc="lower left")
    return ax


__all__ = ["km", "kaplan_meier"]