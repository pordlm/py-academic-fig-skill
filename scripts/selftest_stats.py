# -*- coding: utf-8 -*-
"""自证统计口径：KM 置信区间、PR 的 AP、相关矩阵的常量列、森林图的对数轴。

这些函数出错时**不报错、只给错数**——图照样能画出来，审稿时才发现结论有问题。
本脚本把「正确口径」钉成可执行的断言：

1. ``km(ci=True)`` 用真 Greenwood 方差 ``Σ d/(n(n−d))``（只有事件时点累加）
   与 log(-log S) 变换；尾部不得出现负生存率；``d == n`` 时 S=0 且 CI=[0,0]；
2. ``kaplan_meier`` 的事件编码必须是 0/1（CSV 里的 ``"0"`` 不能再被 ``bool()``
   当成事件），非法编码要报错；
3. ``pr_curve`` 的 AP = ``Σ(R_i − R_{i−1})·P_i``；``pr(curves=…)`` 能区分
   ``(recall, precision)`` 点集与 ``(y_true, y_score)``，点集缺 ``ap`` 时按积分算
   （不是 ``mean(precision)``），recall 非单调/越界要报错；
4. ``corrcoef`` 遇到常量列默认报错（不再用 1e-12 伪装成 0 相关），
   ``constant_policy="nan"`` 标 NaN；``corr`` 的 ``is_correlation_matrix`` 可显式指定；
5. ``roc_curve``/``pr_curve`` 的 ``y_score`` 走 ``as_1d``，NaN/Inf 要报错；
6. ``forest(log_scale=True)`` 的 lower/estimates/upper/pooled 必须全为正；
7. ``volcano`` 的 p=0 走 1e-300 兜底并给 warning（不再直接抛错）。

用法::

    python scripts/selftest_stats.py          # 全部通过 exit 0；任一断言失败 exit 1

只用 numpy + matplotlib（包本身已有的依赖）。
"""
from __future__ import annotations

import importlib
import math
import sys
import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from academic_fig import plots as afp  # noqa: E402

# plots/__init__ 把同名函数导出到包命名空间，会遮蔽模块：按模块路径取
km_mod = importlib.import_module("academic_fig.plots.km")
corr_mod = importlib.import_module("academic_fig.plots.corr")
pr_mod = importlib.import_module("academic_fig.plots.pr")
roc_mod = importlib.import_module("academic_fig.plots.roc")
forest_mod = importlib.import_module("academic_fig.plots.forest")
volcano_mod = importlib.import_module("academic_fig.plots.volcano")

FAILS: list[str] = []


def ok(msg: str) -> None:
    print(f"[ok] {msg}")


def expect(label: str, cond: bool, detail: str = "") -> None:
    if cond:
        ok(label + (f"  {detail}" if detail else ""))
    else:
        FAILS.append(label)
        print(f"[!!] {label}  {detail}", file=sys.stderr)


def expect_raises(label: str, fn, needle: str = "") -> None:
    try:
        fn()
    except Exception as exc:  # noqa: BLE001 - 自测就是要抓所有异常
        msg = str(exc)
        expect(label, needle in msg, f"→ {msg[:100]}")
    else:
        expect(label, False, "没有抛错")


def _km() -> None:
    # 10 例：事件在 2/4/6，删失 3/5/7/8/9/10/11
    t = np.array([2, 3, 4, 5, 6, 7, 8, 9, 10, 11], float)
    e = np.array([1, 0, 1, 0, 1, 0, 0, 0, 0, 0], int)
    times, surv, _at_risk, green = km_mod._km_core(t, e)
    expect("KM 生存率（删失时点不下降）",
           np.allclose(surv[:6], [1.0, 0.9, 0.9, 0.7875, 0.7875, 0.65625]),
           f"{surv[:6]}")
    expect("Greenwood 方差只加在事件时点",
           np.allclose(green[:6], [0.0, 1 / 90, 1 / 90, 1 / 90 + 1 / 56,
                                   1 / 90 + 1 / 56, 1 / 90 + 1 / 56 + 1 / 30]),
           f"{green[:6]}")

    lo, hi = km_mod._loglog_ci(surv, green)
    h = -math.log(0.9)
    a = 1.96 * math.sqrt(1 / 90) / h
    expect("CI 走 log(-log S) 变换",
           abs(lo[1] - 0.9 ** math.exp(a)) < 1e-12
           and abs(hi[1] - 0.9 ** math.exp(-a)) < 1e-12, f"{lo[1]:.6f}/{hi[1]:.6f}")
    expect("CI 不越出 [0, 1] 且包住点估计",
           bool(np.all(lo >= 0) and np.all(hi <= 1)
                and np.all(lo <= surv + 1e-12) and np.all(hi >= surv - 1e-12)))

    _t2, s2, _ar2, g2 = km_mod._km_core([1, 1, 1], [1, 1, 1])
    lo2, hi2 = km_mod._loglog_ci(s2, g2)
    expect("风险集全灭：S=0、CI=[0,0]", s2[-1] == 0 and lo2[-1] == 0 and hi2[-1] == 0)

    _t3, s3, _ar3, _g3 = km_mod._km_core(["2", "3", "4"], ["1", "0", "1"])
    _t4, s4, _ar4, _g4 = km_mod._km_core([2, 3, 4], [1, 0, 1])
    expect("CSV 字符串事件编码与数值一致", np.allclose(s3, s4), f"{s3}")
    expect_raises("事件编码 2 被拒", lambda: km_mod._km_core([1, 2], [1, 2]),
                  "不是合法的事件编码")
    expect_raises("字符串事件 '2' 被拒", lambda: km_mod._km_core([1, 2], ["1", "2"]),
                  "不是合法的事件编码")
    expect("kaplan_meier 公开签名仍返回三元组",
           len(km_mod.kaplan_meier([1, 2, 3], [1, 0, 1])) == 3)


def _pr_roc() -> None:
    yt = np.array([0, 0, 1, 1, 1, 0, 1, 0])
    ys = np.array([0.1, 0.4, 0.35, 0.8, 0.9, 0.2, 0.7, 0.3])
    rec, prec, ap = pr_mod.pr_curve(yt, ys)
    manual = 0.0
    prev = 0.0
    for r, p in zip(rec[1:], prec[1:]):
        manual += (r - prev) * p
        prev = r
    expect("AP = Σ(R_i−R_{i−1})·P_i", abs(ap - manual) < 1e-12, f"ap={ap:.6f}")
    expect("AP 不是 mean(precision)", abs(ap - float(np.mean(prec))) > 1e-9,
           f"ap={ap:.4f} vs mean={float(np.mean(prec)):.4f}")

    ax = pr_mod.pr(curves={"点集": (rec, prec), "原始": (yt, ys)})
    legend = [t.get_text() for t in ax.get_legend().get_texts()]
    expect("curves 同时接受点集与 (y_true, y_score)", ax is not None, f"{legend}")
    expect("点集缺 ap 时按积分算", any(f"AP={manual:.3f}" in s for s in legend), f"{legend}")

    expect_raises("recall 非单调被拒",
                  lambda: pr_mod.pr(curves={"X": (np.array([0.0, 0.5, 0.3]),
                                                    np.array([1.0, 0.8, 0.7]))}),
                  "单调不减")
    expect_raises("precision 越界被拒",
                  lambda: pr_mod.pr(curves={"X": (np.array([0.0, 0.5]),
                                                    np.array([1.0, 1.7]))}),
                  "必须在 [0, 1]")
    _r, _p, ap_str = pr_mod.pr_curve(np.array(["0", "1", "1", "0"]),
                                     np.array([0.2, 0.9, 0.7, 0.1]), positive="1")
    expect("PR 支持字符串正类标签", np.isfinite(ap_str) and ap_str > 0, f"ap={ap_str:.3f}")
    expect_raises("pr_curve 拒绝 NaN 分数",
                  lambda: pr_mod.pr_curve(yt, np.r_[ys[:-1], np.nan]), "NaN")
    expect_raises("roc_curve 拒绝 Inf 分数",
                  lambda: roc_mod.roc_curve(yt, np.r_[ys[:-1], np.inf]), "NaN")


def _corr() -> None:
    X = np.array([[1, 5, 3], [2, 5, 1], [3, 5, 4], [4, 5, 2], [5, 5, 6]], float)
    expect_raises("常量列默认报错", lambda: corr_mod.corrcoef(X), "标准差为 0")
    C, _n = corr_mod.corrcoef(X, constant_policy="nan")
    expect("constant_policy='nan' 标 NaN",
           bool(np.isnan(C[1]).all() and np.isnan(C[:, 1]).all()))
    expect("非恒定列对角仍为 1", np.allclose(np.diag(C)[[0, 2]], 1.0), f"{np.diag(C)}")

    M = np.array([[1.0, 0.5], [0.5, 1.0]])
    expect("is_correlation_matrix=True 可直传相关矩阵",
           corr_mod.corr(matrix=M, is_correlation_matrix=True) is not None)
    expect_raises("is_correlation_matrix=True 但内容不像时拒绝",
                  lambda: corr_mod.corr(matrix=np.array([[1.0, 2.0], [3.0, 1.0]]),
                                        is_correlation_matrix=True), "不像相关矩阵")
    sample = np.array([[1.0, 0.5], [2.0, 0.7], [3.0, 0.9], [4.0, 1.1], [5.0, 1.3]])
    expect("is_correlation_matrix=False 强制按样本矩阵算",
           corr_mod.corr(matrix=sample, is_correlation_matrix=False) is not None)


def _forest_volcano() -> None:
    expect_raises("forest(log_scale) 拒绝 lower<=0",
                  lambda: forest_mod.forest(labels=["a"], estimates=[1.5],
                                            lower=[0.0], upper=[2.0],
                                            null=1.0, log_scale=True), "必须全为正")
    expect_raises("forest(log_scale) 拒绝非正 pooled",
                  lambda: forest_mod.forest(labels=["a"], estimates=[1.5],
                                            lower=[0.8], upper=[2.0],
                                            null=1.0, log_scale=True,
                                            pooled=(1.2, 0.0, 2.0)), "pooled")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        volcano_mod.volcano(log2fc=[0.0, 2.0, -2.0], pvalue=[1.0, 0.0, 0.01])
    expect("volcano 的 p=0 走 1e-300 兜底并告警",
           any("1e-300" in str(w.message) for w in caught),
           f"{[str(w.message)[:40] for w in caught]}")
    expect_raises("volcano 仍拒绝 p>1",
                  lambda: volcano_mod.volcano(log2fc=[0.0, 2.0], pvalue=[1.2, 0.01]),
                  "落在 [0, 1]")


def main() -> int:
    afp  # 确认包可导入（plots 包在导入时注册了渲染器）
    _km()
    _pr_roc()
    _corr()
    _forest_volcano()
    print()
    if FAILS:
        print(f"[!!] {len(FAILS)} 项失败：{FAILS}", file=sys.stderr)
        return 1
    print("[ok] 统计口径自检全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
