# -*- coding: utf-8 -*-
"""把「提示词里的骨架必须能跑」变成机器门（t21 captain 追加项）。

背景：``prompts/*.md`` 里的 Python 骨架是**给人和模型抄的模板**。前两轮返工都是同一类
错误——骨架里写了不存在的 spec 键、不存在的 ``ax=`` 参数——靠人眼逐条读代码去抓。
本脚本把它变成一条命令：

1. 扫 ``prompts/*.md``，抽出**每个** ```` ```python ```` 代码块（不止第一个：
   ``40_diagram_architecture.md`` 有两段）；
2. 每块单独写到临时目录，把 ``examples/data/`` 拷进去（骨架里常引用相对路径），
   若块里没调 ``apply_theme()`` 就先补一行（否则中文全是方框，判据会失真）；
3. 在临时目录里 ``cwd=temp`` 起子进程跑，收集 rc 与 stderr；
4. 判据：**rc 必须 0**，且 stderr 里
   ``does not have a glyph`` / ``Glyph`` / ``ParseFatalException`` / ``TypeError``
   出现次数必须为 0（``MERG NOT subset`` 是 PDF 字体子集化的已知噪音，放行）。
5. 失败逐条打印 ``文件:行 → rc → stderr 首行``，exit 1；全绿 exit 0 并报
   「扫了 N 篇 / M 段骨架」。

它和 ``academic_fig.diagrams._guard``（未 ``apply_theme`` 自动补、未知 spec 键 ValueError）
是一对：``_guard`` 管**运行时**，本脚本管**文档示例**。

用法::

    python scripts/check_prompt_skeletons.py              # 全量，全绿 exit 0
    python scripts/check_prompt_skeletons.py --verbose    # 每段都打印 rc
    python scripts/check_prompt_skeletons.py --only 30_cat_omics --keep  # 留现场

只依赖标准库 + 本包已有的 numpy/matplotlib。
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROMPT_DIR = ROOT / "prompts"
DATA_DIR = ROOT / "examples" / "data"

#: stderr 里出现这些字样就判失败（缺字形 / 公式语法错 / 类型错）
FAIL_MARKERS: tuple[str, ...] = (
    "does not have a glyph",
    "Glyph",
    "ParseFatalException",
    "ParseException",
    "TypeError",
    "AttributeError",
    "KeyError",
    "ValueError",
)

#: 已知噪音：matplotlib 的 PDF 字体子集化提示，与骨架正确性无关。
#: **不要**把 ``UserWarning: Glyph … missing from font(s)`` 放进来：那正是「中文变方框」
#: 的报警，放过它等于让缺字形问题混过门禁（0.2.1 及以前就把它错了过滤掉）。
IGNORE_MARKERS: tuple[str, ...] = (
    "MERG NOT subset",
    "findfont: Font family",
)

#: 显式豁免名单：``{文件名: 原因}``。**默认必须能跑**，别用「跳过」掩盖问题。
EXEMPT: dict[str, str] = {}

FENCE_RE = re.compile(r"^```python[ \t]*\n(.*?)^```[ \t]*$", re.S | re.M)

PREAMBLE = """\
import matplotlib
matplotlib.use("Agg")
import academic_fig as afg
afg.apply_theme()
"""


def extract_blocks(text: str) -> list[tuple[int, str]]:
    """返回 ``[(起始行号(1-based), 代码)]``，行号指向 ```` ```python ```` 那一行。"""
    out: list[tuple[int, str]] = []
    for m in FENCE_RE.finditer(text):
        line = text.count("\n", 0, m.start()) + 1
        out.append((line, m.group(1)))
    return out


def drip(path: Path, code: str, source: str, line: int) -> str:
    """把骨架落成独立脚本：加来源注释，缺 ``apply_theme`` 就补前导。"""
    head = f"# source: {source}:{line}\n"
    body = code if "apply_theme" in code else PREAMBLE + code
    return head + body


def run_one(script: Path, workdir: Path, timeout: float) -> tuple[int, str, str, float]:
    env = dict(os.environ)
    env["MPLBACKEND"] = "Agg"
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONIOENCODING"] = "utf-8"
    t0 = time.time()
    proc = subprocess.run([sys.executable, "-B", str(script)], cwd=str(workdir),
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout, env=env)
    return proc.returncode, proc.stdout or "", proc.stderr or "", time.time() - t0


def first_meaningful(stderr: str) -> str:
    """挑一行最能说明问题的：异常尾行 > 首个非噪音行。"""
    lines = [ln.strip() for ln in stderr.splitlines()
             if ln.strip() and not any(k in ln for k in IGNORE_MARKERS)]
    for ln in reversed(lines):
        if re.match(r"^[A-Za-z_][\w.]*(Error|Exception|Warning)\b", ln) or ln.startswith("TypeError"):
            return ln[:220]
    return lines[0][:200] if lines else "(stderr 为空)"


def bad_markers(stderr: str) -> list[str]:
    hits: list[str] = []
    for raw in stderr.splitlines():
        if any(k in raw for k in IGNORE_MARKERS):
            continue
        for marker in FAIL_MARKERS:
            if marker in raw:
                hits.append(raw.strip()[:200])
                break
    return hits


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="检查 prompts/*.md 里的 Python 骨架能否跑通")
    ap.add_argument("--prompts", default=str(PROMPT_DIR), help="提示词目录（默认 prompts/）")
    ap.add_argument("--only", default=None, help="只跑文件名含该子串的篇目")
    ap.add_argument("--timeout", type=float, default=120.0, help="单段超时秒数（默认 120）")
    ap.add_argument("--verbose", action="store_true", help="每段都打印 rc 与耗时")
    ap.add_argument("--keep", action="store_true", help="保留临时目录（排查用）")
    ap.add_argument("--list", action="store_true", help="只列出骨架，不执行")
    args = ap.parse_args(argv)

    pdir = Path(args.prompts)
    if not pdir.is_dir():
        print(f"[!!] 找不到提示词目录：{pdir}", file=sys.stderr)
        return 2
    files = sorted(p for p in pdir.glob("*.md"))
    if args.only:
        files = [p for p in files if args.only in p.name]

    total_parts = 0
    checked_parts = 0
    failures: list[str] = []
    skipped: list[str] = []
    tmp_root = Path(tempfile.mkdtemp(prefix="afg_prompt_skel_"))
    try:
        for path in files:
            text = path.read_text(encoding="utf-8")
            blocks = extract_blocks(text)
            rel = path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else path.name
            if not blocks:
                continue
            total_parts += len(blocks)
            if path.name in EXEMPT:
                skipped.append(f"{rel}（{EXEMPT[path.name]}）")
                continue
            for idx, (line, code) in enumerate(blocks, start=1):
                workdir = tmp_root / f"{path.stem}_{idx}"
                workdir.mkdir(parents=True, exist_ok=True)
                if DATA_DIR.is_dir():
                    # 骨架里常写 examples/data/xxx.csv 或 data/xxx.csv，两种都照顾到
                    shutil.copytree(DATA_DIR, workdir / "examples" / "data", dirs_exist_ok=True)
                    shutil.copytree(DATA_DIR, workdir / "data", dirs_exist_ok=True)
                script = workdir / f"skel_{path.stem}_{idx}.py"
                script.write_text(drip(path, code, rel, line), encoding="utf-8")
                if args.list:
                    print(f"{rel}:{line}  ->  {script.name}（{len(code.splitlines())} 行）")
                    checked_parts += 1
                    continue
                try:
                    rc, out, err, dt = run_one(script, workdir, args.timeout)
                except subprocess.TimeoutExpired:
                    failures.append(f"{rel}:{line} → 超时 {args.timeout:.0f}s")
                    continue
                checked_parts += 1
                hits = bad_markers(err)
                if rc != 0 or hits:
                    why = "rc≠0" if rc != 0 else f"{len(hits)} 处报错字样"
                    failures.append(f"{rel}:{line} → rc={rc}（{why}）→ {first_meaningful(err)}")
                    for h in hits[:3]:
                        failures.append(f"    · {h}")
                elif args.verbose:
                    print(f"[ok] {rel}:{line}  rc=0  {dt:.1f}s")
    finally:
        if args.keep:
            print(f"\n临时目录保留在：{tmp_root}")
        else:
            shutil.rmtree(tmp_root, ignore_errors=True)

    if args.list:
        print(f"\n共 {checked_parts} 段骨架（--list 只列不跑）")
        return 0

    if skipped:
        print("豁免（显式维护，请定期复核）：")
        for s in skipped:
            print(f"  - {s}")
    if failures:
        print("\n失败的骨架：", file=sys.stderr)
        for f in failures:
            print(f"  {f}", file=sys.stderr)
        print(f"\n扫了 {len(files)} 篇 / {checked_parts} 段骨架，{len(failures)} 处失败",
              file=sys.stderr)
        return 1
    print(f"[ok] 扫了 {len(files)} 篇 / {checked_parts} 段骨架，全部 rc=0 且无缺字形/公式/类型报错")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())