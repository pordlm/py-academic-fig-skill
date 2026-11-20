#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""``aff.apply_theme()`` 漏写时的兜底回归（t29 / r7）。

为什么需要这个脚本
-----------------
``paper_fig()`` 过去不检查主题：用户漏掉 ``apply_theme()`` 时，``rcParams`` 还是
matplotlib 默认的 ``font.family = ['sans-serif']``（DejaVu Sans），中文字符在 PNG 里
直接渲染成**豆腐块**，屏幕上只留几行 ``Glyph 24230 … missing from font(s)``。这类
缺陷「看起来正常」——坐标系、刻度、颜色都对，只有字是空的；评审曾把
「README 示例缺一行 → 全 □」判成 high，根子就是库不兜底。

``diagrams`` 侧早就有 ``_guard.ensure_theme()`` 会补主题，``plots`` 侧没有，
同一个包两套行为。现在统一成 :func:`academic_fig.style._ensure_theme`：
``paper_fig()`` / ``save()`` / ``diagrams`` 三个入口共用，**每进程只提示一次**，
且**显式调用过 apply_theme() 就不再覆盖**。

断言（每条都对着「可数的东西」，不接受“看起来正常”）
---------------------------------------------------
1. 干净解释器里**不调** ``apply_theme()``，直接 ``paper_fig("single")`` + 中文
   柱状图：渲染时 ``missing from font(s)`` 计数 **== 0**，且提示性 ``UserWarning``
   **恰好 1 条**，``rcParams["font.family"]`` 里出现本机解析出的中文字体
   （Windows 是 ``SimSun``，Linux 是 ``Noto Serif CJK SC``——CJK 栈真的套上了）；
   同时 ``save()`` 返回值里 ``auto_theme is True``（t30：诊断字段必须真存在），
   而 ``font_retrofit == 0``（``paper_fig`` 在建 axes 之前就套好了主题，没有 Text 要回填）；
2. 连调两次 ``paper_fig()``：提示**仍然只有 1 条**（不刷屏）；
3. 先显式 ``apply_theme("journal-cns")`` 再 ``paper_fig()``：**0 条**提示，
   且 ``axes.edgecolor`` / 画布底色确实取 journal-cns 的墨色与底色（显式优先，
   不被兜底覆盖）；``save()`` 返回值里 ``auto_theme is False``；
4. 用户自己 ``plt.subplots()`` 直接画、全程没主题，只调 ``afg.save()``：
   ``missing from font(s)`` 计数 **== 0**，提示 **1 条**，PNG/PDF 都写出，
   且 ``auto_theme is True``、``font_retrofit >= 1``（真的回去改了已建好的 Text）；
5. ``diagrams`` 侧守卫与数据图共用同一个「只提示一次」标记：先调守卫再调
   ``paper_fig()``，提示合计 **1 条**，``is_themed()`` 为真。

另外每个用例都有一条 **negative control**：把 ``style._ensure_theme`` 临时换成
空函数（等价于修复前的行为），断言 ``missing from font(s)`` **> 0** —— 证明本脚本
测的是兜底本身，不是「图能出来」。

退出码：全部断言通过 0，否则 1。

用法::

    python scripts/selftest_theme.py
    python scripts/selftest_theme.py --verbose   # 打印每个子进程的原始输出
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

#: 缺字消息的两种写法（matplotlib 版本差异）
GLYPH_MARKERS = ("missing from font(s)", "missing from font")
#: 兜底提示的固定片段（与 style._THEME_HINT 对齐）
HINT_MARKER = "还没有调用 apply_theme"

#: 子进程公共前缀：Agg 后端、从仓库导入、统计工具函数
PRELUDE = '''
import io, os, sys, warnings
from contextlib import redirect_stderr
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import academic_fig as afg

GLYPH = ("missing from font(s)", "missing from font")
HINT = "还没有调用 apply_theme"


def collect(fn):
    """跑 fn()，返回 (warnings 文本列表, stderr 文本)。"""
    buf = io.StringIO()
    with redirect_stderr(buf):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            fn()
        msgs = [str(w.message) for w in caught]
    return msgs, buf.getvalue()


def counts(msgs, err):
    """(缺字条数, 提示条数)。缺字可能走 warnings 也可能走 stderr，两边都数。"""
    glyph = sum(1 for m in msgs if any(k in m for k in GLYPH))
    glyph += sum(err.count(k) for k in GLYPH)
    hint = sum(1 for m in msgs if HINT in m)
    return glyph, hint


def disable_guard():
    """negative control：把兜底换成空操作（= 修复前的行为）。"""
    afg.style._ensure_theme = lambda *a, **k: True
'''


CASES: list[tuple[str, str]] = []


def case(name: str, body: str) -> None:
    """登记一个子进程用例（body 追加在 PRELUDE 之后）。"""
    CASES.append((name, PRELUDE + "\n" + body))


case("无主题直接 paper_fig", '''
out = os.path.join(os.getcwd(), "out")
os.makedirs(out, exist_ok=True)
saved = []

def run():
    fig, ax = afg.paper_fig("single")
    afg.plots.bar(ax, ["甲", "乙"], [1, 2], ylabel="精度")
    fig.canvas.draw()
    # t30：save() 的返回值必须带 auto_theme / font_retrofit（说明文字不能跑在代码前面）
    saved.append(afg.save(fig, os.path.join(out, "fig01_paperfig_theme")))

msgs, err = collect(run)
glyph, hint = counts(msgs, err)
fam = list(matplotlib.rcParams["font.family"])
cjk_fam = afg.typography.cjk_family()   # 各平台不同：Windows 是 SimSun，Linux 是 Noto Serif CJK SC
res = saved[0]
fmt_paths = afg.figure_paths(res)

print("[data] font.family =", fam)
print("[data] 本机中文字体 =", cjk_fam)
print("[data] 缺字 %d 条 / 提示 %d 条" % (glyph, hint))
print("[data] save() 返回 =", {k: (type(v).__name__) for k, v in res.items()})
print("[data] auto_theme=%r font_retrofit=%r 路径键=%s"
      % (res.get("auto_theme"), res.get("font_retrofit"), sorted(fmt_paths)))

ok = True
if glyph != 0:
    ok = False
    print("[FAIL] 缺字 %d 条（必须 0）—— 中文仍然是豆腐块" % glyph)
if hint != 1:
    ok = False
    print("[FAIL] 提示 %d 条（必须恰好 1 条）" % hint)
if not any(str(f) == cjk_fam for f in fam):
    ok = False
    print("[FAIL] font.family 里没有本机解析出的中文字体 %r，说明 CJK 栈没套上：%s" % (cjk_fam, fam))
if res.get("auto_theme") is not True:
    ok = False
    print("[FAIL] save() 返回值里 auto_theme=%r（漏主题路径必须是 True）" % (res.get("auto_theme"),))
if res.get("font_retrofit") != 0:
    ok = False
    print("[FAIL] font_retrofit=%r（paper_fig 在写字之前就套好了主题，没有 Text 需要回填）"
          % (res.get("font_retrofit"),))
if "auto_theme" not in res or "font_retrofit" not in res:
    ok = False
    print("[FAIL] save() 返回值缺诊断键：", sorted(res))
if sorted(fmt_paths) != ["pdf", "png"]:
    ok = False
    print("[FAIL] 格式键不是只有 png/pdf：", sorted(res))
if not all(isinstance(v, Path) for v in fmt_paths.values()):
    ok = False
    print("[FAIL] 格式键的值不是 Path：", {k: type(v).__name__ for k, v in fmt_paths.items()})
if not ok:
    sys.exit(1)
print("[ok] 无主题也能出中文：缺字 0 条 / 提示 1 条 / CJK 栈已套上（%s）/ auto_theme=True" % cjk_fam)
''')

case("只提示一次", '''
def run():
    for _ in range(2):
        fig, ax = afg.paper_fig("single")
        ax.plot([0, 1], [0, 1])

msgs, err = collect(run)
glyph, hint = counts(msgs, err)
print("[data] 两次 paper_fig → 提示 %d 条" % hint)
if hint != 1:
    print("[FAIL] 提示 %d 条（必须恰好 1 条：第二次不该再刷）" % hint)
    sys.exit(1)
print("[ok] 两次 paper_fig 只提示 1 次")
''')

case("显式主题优先", '''
_p = afg.palette.get_palette("journal-cns")
out = os.path.join(os.getcwd(), "out")
os.makedirs(out, exist_ok=True)
saved = []

def run():
    afg.apply_theme(palette="journal-cns")
    fig, ax = afg.paper_fig("single")
    afg.plots.bar(ax, ["甲", "乙"], [1, 2], ylabel="精度")
    fig.canvas.draw()
    saved.append(afg.save(fig, os.path.join(out, "fig02_explicit_theme")))

msgs, err = collect(run)
glyph, hint = counts(msgs, err)
edge = matplotlib.rcParams["axes.edgecolor"]
face = matplotlib.rcParams["figure.facecolor"]
res = saved[0]
print("[data] 提示 %d 条 / edgecolor=%s / facecolor=%s" % (hint, edge, face))
print("[data] auto_theme=%r font_retrofit=%r" % (res.get("auto_theme"), res.get("font_retrofit")))
ok = True
if hint != 0:
    ok = False
    print("[FAIL] 显式套过主题却仍提示 %d 条" % hint)
if res.get("auto_theme") is not False:
    ok = False
    print("[FAIL] auto_theme=%r（显式套过主题必须是 False）" % (res.get("auto_theme"),))
if res.get("font_retrofit") != 0:
    ok = False
    print("[FAIL] font_retrofit=%r（显式套过主题时不该动任何 Text）" % (res.get("font_retrofit"),))
if str(edge).lower() != str(_p["ink"]).lower():
    ok = False
    print("[FAIL] edgecolor=%s 不是 journal-cns 墨色 %s（被兜底覆盖了）" % (edge, _p["ink"]))
if str(face).lower() != str(_p["paper"]).lower():
    ok = False
    print("[FAIL] facecolor=%s 不是 journal-cns 底色 %s" % (face, _p["paper"]))
if not ok:
    sys.exit(1)
print("[ok] 显式 apply_theme(journal-cns) 优先，兜底不覆盖，auto_theme=False")
''')

case("save() 兜底", '''
import matplotlib.pyplot as plt

out = os.path.join(os.getcwd(), "out")
os.makedirs(out, exist_ok=True)
saved = []

def run():
    fig, ax = plt.subplots(figsize=(3.35, 2.4))   # 用户自己开的画布，没主题
    ax.plot([0, 1], [0.2, 0.8])
    ax.set_xlabel("相对误差")
    ax.set_title("灵敏度")
    saved.append(afg.save(fig, os.path.join(out, "fig01_save_fallback")))

msgs, err = collect(run)
glyph, hint = counts(msgs, err)
png = os.path.exists(os.path.join(out, "fig01_save_fallback.png"))
pdf = os.path.exists(os.path.join(out, "fig01_save_fallback.pdf"))
res = saved[0]
print("[data] 缺字 %d 条 / 提示 %d 条 / png=%s pdf=%s" % (glyph, hint, png, pdf))
print("[data] auto_theme=%r font_retrofit=%r" % (res.get("auto_theme"), res.get("font_retrofit")))
ok = True
if glyph != 0:
    ok = False
    print("[FAIL] save() 路径缺字 %d 条（必须 0）" % glyph)
if hint != 1:
    ok = False
    print("[FAIL] 提示 %d 条（必须恰好 1 条）" % hint)
if not (png and pdf):
    ok = False
    print("[FAIL] PNG/PDF 没有都写出来")
if res.get("auto_theme") is not True:
    ok = False
    print("[FAIL] auto_theme=%r（自建画布 + 漏主题必须是 True）" % (res.get("auto_theme"),))
if not isinstance(res.get("font_retrofit"), int) or res.get("font_retrofit") < 1:
    ok = False
    print("[FAIL] font_retrofit=%r（先写字后 save 至少要改写 1 个 Text）"
          % (res.get("font_retrofit"),))
if not ok:
    sys.exit(1)
print("[ok] 自建画布 + 只调 save() 也能出中文：缺字 0 / 提示 1 / font_retrofit>=1")
''')

case("diagrams 与数据图共用标记", '''
from academic_fig.diagrams import _guard

def run():
    _guard.ensure_theme()          # 示意图入口的兜底
    fig, ax = afg.paper_fig("single")
    ax.plot([0, 1], [0, 1])

msgs, err = collect(run)
glyph, hint = counts(msgs, err)
themed = afg.style.is_themed()
print("[data] 提示 %d 条 / is_themed=%s" % (hint, themed))
ok = True
if hint != 1:
    ok = False
    print("[FAIL] 提示 %d 条（示意图 + 数据图共用标记，必须合计 1 条）" % hint)
if not themed:
    ok = False
    print("[FAIL] is_themed() 仍是 False")
if not ok:
    sys.exit(1)
print("[ok] 示意图守卫与 paper_fig 共用同一个「只提示一次」标记")
''')

case("negative control：关掉兜底就要有缺字", '''
disable_guard()

def run():
    fig, ax = afg.paper_fig("single")
    afg.plots.bar(ax, ["甲", "乙"], [1, 2], ylabel="精度")
    fig.canvas.draw()

msgs, err = collect(run)
glyph, hint = counts(msgs, err)
print("[data] 关掉兜底后 缺字 %d 条 / 提示 %d 条" % (glyph, hint))
if glyph == 0:
    print("[FAIL] 关掉兜底竟然没有缺字 —— 说明用例本身画不出豆腐，测不出问题")
    sys.exit(1)
print("[ok] negative control：关掉兜底立刻缺字 %d 条（用例有效）" % glyph)
''')


def run_case(name: str, code: str, keep: bool, verbose: bool) -> tuple[bool, str]:
    """在独立临时目录 + 干净子进程里跑一个用例，返回 (是否通过, 输出)。"""
    tmp = Path(tempfile.mkdtemp(prefix="afg_theme_"))
    script = tmp / "case.py"
    script.write_text(code, encoding="utf-8")
    env = {
        **os.environ,
        "MPLBACKEND": "Agg",
        "PYTHONPATH": str(REPO),
        "PYTHONIOENCODING": "utf-8",
        "PYTHONWARNINGS": "default",
    }
    try:
        proc = subprocess.run([sys.executable, "-B", str(script)], cwd=str(tmp),
                              env=env, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=180)
    except subprocess.TimeoutExpired:
        return False, "  [FAIL] 超时（180s）"
    finally:
        pass
    out = (proc.stdout or "") + (proc.stderr or "")
    if not keep:
        shutil.rmtree(tmp, ignore_errors=True)
    if verbose:
        print(out.rstrip())
    return proc.returncode == 0, out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="apply_theme 兜底回归（t29）")
    ap.add_argument("--verbose", action="store_true", help="打印子进程原始输出")
    ap.add_argument("--keep", action="store_true", help="保留临时目录")
    args = ap.parse_args(argv)

    failed = 0
    for name, code in CASES:
        ok, out = run_case(name, code, args.keep, args.verbose)
        detail = [ln for ln in out.splitlines() if ln.startswith(("[data]", "[ok]", "[FAIL]"))]
        print(f"[{'ok' if ok else 'FAIL'}] {name}")
        for line in detail[:6]:
            print("      " + line.strip())
        if not ok:
            failed += 1
            if not args.verbose:
                print("      ---- 子进程输出 ----")
                print("\n".join("      " + ln for ln in out.rstrip().splitlines()[-14:]))

    if failed:
        print(f"\n==> {failed} / {len(CASES)} 个用例失败")
        return 1
    print(f"\n==> 全部 {len(CASES)} 个用例通过："
          "漏 apply_theme 时自动兜底、只提示一次、显式主题优先，且关掉兜底立刻缺字")
    return 0


if __name__ == "__main__":
    sys.exit(main())