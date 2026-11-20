# -*- coding: utf-8 -*-
"""自证「提示词骨架检查」不会漏报缺字形。

背景：``scripts/check_prompt_skeletons.py`` 曾经把 ``UserWarning: Glyph … missing from
font(s)`` 放进 ``IGNORE_MARKERS``，而 ``bad_markers()`` 是「先过滤 IGNORE、再判 FAIL」，
于是**最常见的缺字形警告被提前忽略**——中文全变方框也照样 exit 0。本脚本把判据钉住：

1. ``UserWarning: Glyph … missing from current font`` 必须被判为错误（不能再被忽略）；
2. PDF 字体子集化的 ``MERG NOT subset`` 与 ``findfont: Font family`` 属已知噪音，放行；
3. ``does not have a glyph`` / ``ParseFatalException`` / ``TypeError`` / ``KeyError``
   仍然照旧判错；
4. ``extract_blocks`` 能找到一篇里的**多段**骨架，行号指向 ```` ```python ```` 那一行；
5. ``IGNORE_MARKERS`` 里不得再出现 ``UserWarning: Glyph``（防止有人「修回去」）。

另加一条真实渲染的反向用例：让 matplotlib 画一个几乎必然缺字形的字符，确认它的
stderr 会被 ``bad_markers`` 抓出来（字体齐全的机器上可能不报警，则跳过该子场景）。

用法::

    python scripts/selftest_prompt_skel.py        # 全绿 exit 0；任一断言失败 exit 1
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parent.parent
CHECKER = ROOT / "scripts" / "check_prompt_skeletons.py"

FAILS: list[str] = []


def ok(msg: str) -> None:
    print(f"[ok] {msg}")


def expect(label: str, cond: bool, detail: str = "") -> None:
    if cond:
        ok(label + (f"  {detail}" if detail else ""))
    else:
        FAILS.append(label)
        print(f"[!!] {label}  {detail}", file=sys.stderr)


def load_checker():
    spec = importlib.util.spec_from_file_location("check_prompt_skeletons_under_test", CHECKER)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[x] 加载不了 {CHECKER}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    mod = load_checker()
    print(f"检查器：{CHECKER}")

    # 1) 缺字形必须判错 ---------------------------------------------------------
    glyph = ("UserWarning: Glyph 20998 (\\N{CJK UNIFIED IDEOGRAPH-20998}) "
             "missing from current font.")
    hits = mod.bad_markers(glyph)
    expect("UserWarning: Glyph … missing 被判错", bool(hits), f"{hits}")
    expect("缺字形不再列在 IGNORE_MARKERS",
           not any("Glyph" in m for m in mod.IGNORE_MARKERS), f"{mod.IGNORE_MARKERS}")
    expect("does not have a glyph 仍判错",
           bool(mod.bad_markers("RuntimeError: Font X does not have a glyph for U+20998")))
    expect("ParseFatalException 仍判错",
           bool(mod.bad_markers("matplotlib._mathtext.ParseFatalException: Expected end of math")))
    expect("TypeError/KeyError 仍判错",
           bool(mod.bad_markers("TypeError: unexpected keyword 'foo'"))
           and bool(mod.bad_markers("KeyError: 'spec_key'")))

    # 2) 已知噪音必须放行 -------------------------------------------------------
    for noise in ("MERG NOT subset; don't know how to subset; dropped",
                  "findfont: Font family ['Noto Sans CJK SC'] not found."):
        expect(f"噪音放行：{noise[:28]}…", mod.bad_markers(noise) == [],
               f"{mod.bad_markers(noise)}")

    # 3) 多段骨架与行号 ---------------------------------------------------------
    text = (
        "# 标题\n"
        "```python\n"
        "print(1)\n"
        "```\n"
        "\n"
        "中间说明\n"
        "```python\n"
        "print(2)\n"
        "print(3)\n"
        "```\n"
    )
    blocks = mod.extract_blocks(text)
    expect("一篇里抽出两段骨架", len(blocks) == 2, f"{len(blocks)}")
    expect("行号指向 ```python 那一行", [b[0] for b in blocks] == [2, 7],
           f"{[b[0] for b in blocks]}")
    expect("第二段内容完整", "print(3)" in blocks[1][1], f"{blocks[1][1]!r}")

    # 4) 真实渲染的反向用例（字体齐全的机器可能不报警 → 跳过） -------------------
    with tempfile.TemporaryDirectory(prefix="afg_glyph_") as raw:
        script = Path(raw) / "glyph_probe.py"
        script.write_text(
            "import matplotlib\n"
            "matplotlib.use('Agg')\n"
            "import matplotlib.pyplot as plt\n"
            "fig, ax = plt.subplots()\n"
            "ax.set_title('\\N{TIBETAN LETTER KA}\\N{TIBETAN LETTER KHA}')\n"
            "fig.savefig('out.png')\n"
            "print('ok')\n",
            encoding="utf-8",
        )
        proc = subprocess.run([sys.executable, "-B", str(script)], cwd=raw,
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace")
        if proc.returncode != 0 or not (Path(raw) / "out.png").is_file():
            print("[--] 跳过真实渲染子场景（本机 matplotlib/Agg 无法出图）")
        elif "Glyph" in (proc.stderr or ""):
            expect("真实缺字形渲染被 bad_markers 抓到",
                   bool(mod.bad_markers(proc.stderr)), proc.stderr.strip()[:120])
        else:
            print("[--] 本机字体覆盖藏文，真实渲染不报警；跳过该子场景")

    print()
    if FAILS:
        print(f"[!!] {len(FAILS)} 项失败：{FAILS}", file=sys.stderr)
        return 1
    print("[ok] 提示词骨架检查器自检全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())