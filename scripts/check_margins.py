#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""四边留白核对器（F-03）。

判据
----
论文插图在 Word/LaTeX 里会被裁到内容外接框。任何一边只剩 1–2px 的非白像素，
缩放或重新采样时就会被切掉笔画（刻度数字、轴标签、右上角的图例框）。
:data:`academic_fig.checks.MIN_MARGIN_PX` 定为 8px @300dpi（≈0.027in≈0.68mm），
这是「肉眼看不出来、但足够容纳一次重采样」的下限。

本脚本量的是**非白像素外接框到图像四边的距离**（和 PDF 阅读器的裁切框无关），
逐张打印，任一图最小边 < ``--min`` 时退出码 1。

用法::

    python scripts/check_margins.py                     # 默认扫 examples/out
    python scripts/check_margins.py --dir assets --min 12
    python scripts/check_margins.py --json              # 机器可读
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:      # 直接 python scripts/check_margins.py
    sys.path.insert(0, str(REPO))

from academic_fig import checks      # noqa: E402

DEFAULT_DIR = REPO / "examples" / "out"


def measure(root: Path) -> list[dict]:
    """递归量 ``root`` 下所有 PNG 的留白，按「最小边」升序返回。"""
    rows: list[dict] = []
    for png in sorted(root.rglob("*.png")):
        m = checks.png_margins(png)
        if not m:
            rows.append({"file": png.relative_to(root).as_posix(), "ok": False,
                         "worst": -1, "margins": None})
            continue
        worst = min(m["left"], m["right"], m["top"], m["bottom"])
        rows.append({"file": png.relative_to(root).as_posix(), "ok": True,
                     "worst": worst, "margins": m})
    rows.sort(key=lambda r: r["worst"])
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="check_margins.py",
        description="量 PNG 四边留白，任一 < 阈值即失败。")
    ap.add_argument("--dir", default=str(DEFAULT_DIR), help="要扫描的目录（递归）")
    ap.add_argument("--min", type=int, default=checks.MIN_MARGIN_PX,
                    help=f"四边留白下限，px（默认 {checks.MIN_MARGIN_PX}）")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args(argv)

    root = Path(args.dir)
    if not root.is_dir():
        print(f"目录不存在：{root}", file=sys.stderr)
        return 2
    rows = measure(root)
    if not rows:
        print(f"{root} 下没有 PNG", file=sys.stderr)
        return 2

    bad = [r for r in rows if not r["ok"] or r["worst"] < args.min]
    if args.json:
        print(json.dumps({"dir": str(root), "min": args.min,
                          "count": len(rows), "bad": len(bad), "rows": rows},
                         ensure_ascii=False, indent=2))
        return 1 if bad else 0

    print(f"四边留白核对：{root}（下限 {args.min}px @ {len(rows)} 张）")
    print(f"{'图':<44}{'左':>5}{'右':>5}{'上':>5}{'下':>5}{'最小':>6}")
    print("-" * 72)
    for r in rows:
        if not r["ok"]:
            print(f"{r['file']:<44}{'—':>5}{'—':>5}{'—':>5}{'—':>5}{'读不出':>6}")
            continue
        m = r["margins"]
        mark = "" if r["worst"] >= args.min else "  <<"
        print(f"{r['file']:<44}{m['left']:>5}{m['right']:>5}"
              f"{m['top']:>5}{m['bottom']:>5}{r['worst']:>6}{mark}")
    print("-" * 72)
    if bad:
        print(f"[FAIL] {len(bad)}/{len(rows)} 张图留白不足 {args.min}px")
        return 1
    print(f"[OK] 全部 {len(rows)} 张图四边留白 ≥ {args.min}px")
    return 0


if __name__ == "__main__":
    sys.exit(main())