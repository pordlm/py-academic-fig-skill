# -*- coding: utf-8 -*-
"""自证 R-02：字形检查不是死检查——坏字体必须被抓到，好字体必须放过。

复评时的质疑是：``probe_glyphs`` 用 ``matplotlib.figure.Figure()`` 建图，
canvas 是 ``FigureCanvasBase``，其 ``draw()`` 是空实现，于是探针**恒返回 []**，
全乱码的图 ``check --strict`` 照样 exit 0。修复后本脚本负责把这条证明补上：

1. ``probe_glyphs(families=["NoSuchFontFamily"])`` → 必须报 ``glyph`` error；
2. 把 ``academic_fig.typography.font_stack`` 临时替换成「坏字体」后再走完整链路
   ``check_dir(..., strict=True)`` → 必须带 ``glyph`` error（这条证明
   ``check_dir`` 真的接上了探针，而不是各写各的）；
3. 恢复字体栈后同一个目录 → 必须 0 条 ``glyph`` error；
4. R2-02：mathtext 缺字报的是 ``does not have a glyph … dummy symbol``（走 logging），
   坏公式抛 ``ParseFatalException`` —— 两条通道都必须落到 error，中文+``$...$`` 混排
   由 ``check_text`` 静态判 ``math-mix``。
5. R2-02 的 **CLI 级回归**：``python -m academic_fig.cli check --dir … --script …``
   在脚本里写「中文 + ``$...$``」（也就是会产生 dummy-symbol 图的那种写法）时
   **必须 exit 1**；同一目录配干净脚本必须 exit 0。这条走真子进程，钉住「退出码」。

用法::

    python scripts/selftest_glyph_check.py       # 全部通过 exit 0；任一断言失败 exit 1

只用 numpy + matplotlib（包本身已有的依赖）。
"""
from __future__ import annotations

import logging
import sys
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import academic_fig as afg                                  # noqa: E402
from academic_fig import typography                         # noqa: E402
from academic_fig.checks import check_dir, probe_glyphs      # noqa: E402

BAD = ["NoSuchFontFamilyForSelftest"]


def _ok(msg: str) -> None:
    print(f"[ok] {msg}")


def _fail(msg: str) -> None:
    print(f"[!!] {msg}", file=sys.stderr)


def _render_sample(folder: Path) -> Path:
    """在 folder 里正常渲一张中文图（用框架字体栈），当作「待体检目录」。"""
    with matplotlib.rc_context({"font.family": typography.font_stack(),
                                "font.sans-serif": typography.font_stack(),
                                "axes.unicode_minus": False}):
        fig, ax = afg.paper_fig("single", height=2.4)
        afg.panel(ax, "(a)", title="降噪验证 中位数 αβ ± 0.8", xlabel="迭代轮次", ylabel="响应（a.u.）")
        ax.plot([1, 2, 3], [0.4, 0.7, 0.9], color=afg.palette.BLUE)
        afg.footnote(fig, "数据来源：本脚本自造，仅用于字形自检；口径：单次渲染。")
        afg.save(fig, folder / "fig01_glyph", formats=("png", "pdf"), target_width="single")
    return folder / "fig01_glyph.png"


def _mute_findfont() -> None:
    """坏字体自测会刷几十行 ``findfont: Font family … not found``——只在自测里压掉。"""
    logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)


def main() -> int:
    failures = 0
    _mute_findfont()

    # ---- 1) 探针本体：坏字体必须报错 -------------------------------------
    bad = probe_glyphs(families=BAD)
    if any(i.code == "glyph" and i.severity == "error" for i in bad):
        _ok(f"探针在坏字体下报出 {len(bad)} 条 glyph error（证明 Agg canvas 真的在排字）")
    else:
        _fail("探针在坏字体下没报错——R-02 回归了")
        failures += 1

    good = probe_glyphs()
    if not good:
        _ok("探针在框架字体栈下 0 条 glyph issue（不误报）")
    else:
        _fail(f"探针在正常字体下误报 {len(good)} 条：{good[0].message}")
        failures += 1

    # ---- 1b) R2-02：mathtext 的 dummy-symbol 通道 -------------------------
    # 复评复现：中文与 `$...$` 混排时 mathtext 把汉字当缺字形，报的是
    # 「does not have a glyph … substituting with a dummy symbol」，走 **logging**
    # 而不是 warnings —— 旧的过滤词只认 "missing from"/"Glyph"，于是 28 张
    # dummy 图 `check --strict` 照样 exit 0。这里逐层钉住：
    from academic_fig import checks as _c
    if any(k in "Font 'default' does not have a glyph for '\\u0394' [U+0394], "
                 "substituting with a dummy symbol" for k in _c._GLYPH_MARKERS):
        _ok("dummy-symbol 原话已被 _GLYPH_MARKERS 覆盖")
    else:
        _fail("_GLYPH_MARKERS 仍漏掉 'does not have a glyph'")
        failures += 1

    broken = probe_glyphs(text=r"相对误差 $\frac{a}{$ 中位数")
    if any(i.code == "math-mix" and i.severity == "error" for i in broken):
        _ok("坏公式探针报出 math-mix error（ParseFatal 不会静默通过）")
    else:
        _fail(f"坏公式没报 math-mix：{[i.code for i in broken]}")
        failures += 1

    mixed = _c.check_text("中位数 $\\Delta E$ 为 0.32")
    if any(i.code == "math-mix" and i.severity == "error" for i in mixed):
        _ok("中文与 $...$ 混排被静态判为 math-mix error")
    else:
        _fail("check_text 没抓到中文+$...$ 混排")
        failures += 1

    # ---- 1c) R2-02 的 CLI 级回归：混排脚本必须 exit 1 --------------------
    # 「中文 + $...$」写在同一串里，渲染时汉字会被 mathtext 当缺字形（dummy symbol）。
    # 这里走真子进程，钉的是退出码而不是返回值——CI 只看退出码。
    import os
    import subprocess

    with tempfile.TemporaryDirectory(prefix="afg_cli_glyph_") as tmp:
        folder = Path(tmp) / "out"
        folder.mkdir()
        _render_sample(folder)
        mixed = Path(tmp) / "make_mixed.py"
        mixed.write_text(
            "import academic_fig as afg\n"
            "afg.apply_theme()\n"
            "fig, ax = afg.paper_fig('single')\n"
            "ax.plot([1, 2, 3], [0.1, 0.2, 0.3])\n"
            "afg.panel(ax, xlabel='中位数 $\\\\Delta E$', ylabel='相对误差')\n",
            encoding="utf-8")
        clean = Path(tmp) / "make_clean.py"
        clean.write_text(
            "import academic_fig as afg\n"
            "afg.apply_theme()\n"
            "fig, ax = afg.paper_fig('single')\n"
            "ax.plot([1, 2, 3], [0.1, 0.2, 0.3])\n"
            "afg.panel(ax, xlabel='中位数', ylabel='相对误差')\n",
            encoding="utf-8")
        env = dict(os.environ, MPLBACKEND="Agg", PYTHONPATH=str(ROOT),
                   PYTHONIOENCODING="utf-8")
        cmd = [sys.executable, "-m", "academic_fig.cli", "check", "--dir", str(folder), "--strict"]

        def _cli(script: Path) -> tuple[int, str]:
            r = subprocess.run(cmd + ["--script", str(script)], cwd=tmp, capture_output=True,
                               text=True, encoding="utf-8", errors="replace", env=env)
            return r.returncode, (r.stdout or "") + (r.stderr or "")

        rc, text = _cli(mixed)
        if rc == 1 and "math-mix" in text:
            _ok("CLI 级负例：脚本里中文与 $...$ 混排 → check --strict exit 1（math-mix）")
        else:
            _fail(f"CLI 级负例没生效：rc={rc}，输出里没有 math-mix")
            failures += 1
        rc, _ = _cli(clean)
        if rc == 0:
            _ok("CLI 级正例：同一目录配干净脚本 → exit 0")
        else:
            _fail(f"CLI 级正例被误判：rc={rc}")
            failures += 1

        # ---- 1d) R3-01：纯图目录不许「假绿」--------------------------------
        # 目录里只有 png/pdf、没有生成脚本时，字形/混排**根本没查**。此时不能只打
        # 「✓ 未发现问题」——那会让用户以为验过了。要求：结论行标注「未检查」。
        def _cli_plain() -> tuple[int, str]:
            r = subprocess.run(cmd, cwd=tmp, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", env=env)
            return r.returncode, (r.stdout or "") + (r.stderr or "")

        rc, text = _cli_plain()
        if rc == 0 and "未检查" in text and "本次跳过" in text:
            _ok("纯图目录（无生成脚本）：exit 0 但结论行标注「字形/混排：未检查」")
        else:
            _fail(f"纯图目录没有自报跳过：rc={rc}，输出缺「未检查」/「本次跳过」")
            failures += 1
        if "未检查" in text:
            line = next((ln for ln in text.splitlines() if "未检查" in ln), "")
            _ok(f"negative control 原文：{line.strip()}")

        # 生成脚本放进目录后，跳过项必须消失（否则「跳过」就成了永久免责声明）
        (folder / "make_clean.py").write_text(clean.read_text(encoding="utf-8"),
                                              encoding="utf-8")
        rc, text = _cli_plain()
        if "字形/混排" not in text:
            _ok("脚本进目录后不再报「字形/混排」跳过（该查的查了）")
        else:
            _fail("脚本已在目录里却仍报跳过：「跳过」被当成免责声明")
            failures += 1

        # ---- 1e) R5-02：字形假绿的**第二形态**（脚本自己换字体栈）----------
        # 复评复现：合规脚本 + 一行 `rcParams["font.family"] = ["DejaVu Sans"]` →
        # 渲染 54 条 Glyph missing、图片满屏空框，而 `check --strict` 仍 exit 0：
        # 字体探针测的是**本机栈**，脚本自己把字体换掉它照样绿。这条规则必须由
        # check_script 静态判。目录里已放了一个 .py（1d 之后），纯图目录的跳过
        # 分支兜不住，正好检验「有脚本也没漏」。
        bad_font = Path(tmp) / "make_bad_font.py"
        bad_font.write_text(
            "import matplotlib\n"
            "import academic_fig as afg\n"
            "afg.apply_theme()\n"
            "matplotlib.rcParams[\"font.family\"] = [\"DejaVu Sans\"]\n"
            "fig, ax = afg.paper_fig('single')\n"
            "ax.plot([1, 2, 3], [0.1, 0.2, 0.3])\n"
            "afg.panel(ax, xlabel='中位数', ylabel='相对误差')\n",
            encoding="utf-8")
        rc, text = _cli(bad_font)
        if rc == 1 and "font-family" in text:
            _ok("CLI 级负例：脚本把字体栈换成无中文字体 → check --strict exit 1（font-family）")
        else:
            _fail(f"字体栈负例没生效：rc={rc}，输出里没有 font-family")
            failures += 1
        good_font = Path(tmp) / "make_good_font.py"
        good_font.write_text(
            "import matplotlib\n"
            "import academic_fig as afg\n"
            "afg.apply_theme()\n"
            "matplotlib.rcParams[\"font.family\"] = [\"Times New Roman\", \"SimSun\"]\n"
            "fig, ax = afg.paper_fig('single')\n"
            "ax.plot([1, 2, 3], [0.1, 0.2, 0.3])\n"
            "afg.panel(ax, xlabel='中位数', ylabel='相对误差')\n",
            encoding="utf-8")
        rc, text = _cli(good_font)
        if rc == 0:
            _ok("CLI 级正例：字体栈里留着 SimSun → exit 0（规则不误伤中文栈）")
        else:
            _fail(f"带中文的字体栈被误判：rc={rc}，输出：{text.strip()[:120]}")
            failures += 1

    # ---- 2) 完整链路：坏字体 → check 必须失败；恢复 → 必须通过 -------------
    with tempfile.TemporaryDirectory(prefix="afg_glyph_") as tmp:
        folder = Path(tmp)
        _render_sample(folder)

        real = typography.font_stack
        try:
            typography.font_stack = lambda: list(BAD)     # type: ignore[assignment]
            import academic_fig.checks as _checks
            _checks._typo = typography                     # 探针走同一个对象
            issues = check_dir(folder, strict=True)
            glyph = [i for i in issues if i.code == "glyph"]
            if glyph:
                _ok(f"check_dir 在坏字体下报出 {len(glyph)} 条 glyph（链路已接通）")
            else:
                _fail("check_dir 在坏字体下没有 glyph issue——探针没被调用")
                failures += 1
        finally:
            typography.font_stack = real                   # type: ignore[assignment]

        issues = check_dir(folder, strict=True)
        glyph = [i for i in issues if i.code == "glyph"]
        if not glyph:
            _ok("字体恢复后同一目录 0 条 glyph issue（可复核、不粘锅）")
        else:
            _fail(f"字体恢复后仍有 {len(glyph)} 条 glyph：{glyph[0].message}")
            failures += 1
        others = [i for i in issues if i.severity == "error"]
        if others:
            _fail("干净样本还有其它 error：" + "；".join(i.message for i in others[:3]))
            failures += 1

    if failures:
        _fail(f"{failures} 项断言失败")
        return 1
    _ok("字形自检自证通过（坏字体被抓、好字体放过、完整链路可达）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())