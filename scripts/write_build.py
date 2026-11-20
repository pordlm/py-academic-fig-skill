# -*- coding: utf-8 -*-
"""写仓库根的 ``BUILD.json``：给「哪个状态被复评过」一个可核对的指纹。

复评场景：30 分钟内多个文件被反复改写，只报版本号 ``0.2.0`` 无法证明「你戳的就是
我改的那份」。所以每次交付前跑一次本脚本，把关键文件的 sha256 与包指纹落盘；
``academic_fig.__build__`` 里的时间戳与该文件的 ``generated_at`` 对得上。

用法::

    python scripts/write_build.py            # 写 BUILD.json
    python scripts/write_build.py --check     # 只校验：BUILD.json 与当前文件一致则 0，否则 1

只用标准库，不依赖包是否可 import（避免「生成指纹的脚本自己先挂」）。
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "BUILD.json"

#: 需要单独记 sha256 的关键文件（相对仓库根）
KEY_FILES = (
    "academic_fig/__init__.py",
    "academic_fig/checks.py",
    "academic_fig/export.py",
    "academic_fig/layout.py",
    "academic_fig/style.py",
    "academic_fig/plots/__init__.py",
    "academic_fig/palette.py",
    "README.md",
    "SKILL.md",
)

#: 计入「交付文件」的目录（相对仓库根）
DELIVERY_DIRS = ("academic_fig", "examples", "prompts", "references", "scripts", "assets")

#: **派生目录**：跑一次示例 / 自检就会长出来或变样，不能算进交付面。
#: 教训（r5）：``examples/out`` 曾把 64 个渲染产物（5.9 MB）算进 ``delivery_bytes``，
#: 于是「按文档冷启动一次」（删 out → 重渲）就能让 build 串与 BUILD.json 对不上，
#: 校验报「已过期」——指纹绑的是生成物，不是交付物。派生目录在此显式列出。
DERIVED_DIRS = (
    "examples/out",
    "reports",
    "out",
    "build",
    "dist",
    "__pycache__",
    ".pytest_cache",
)


def _rel_posix(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _is_derived(rel: str) -> bool:
    """``rel``（POSIX，相对仓库根）是否落在派生目录里。"""
    return any(rel == d or rel.startswith(d + "/") for d in DERIVED_DIRS)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _tree_files(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.rglob("*") if p.is_file()
                  and "__pycache__" not in p.parts)


def _runtime_build() -> str:
    """读运行时的 ``academic_fig.__build__``（导入失败则返回空串，不阻断校验）。"""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    try:
        import academic_fig as _afg
    except Exception:                                       # pragma: no cover - 环境缺依赖
        return ""
    return str(getattr(_afg, "__build__", "") or "")


def collect() -> dict:
    pkg_py = _tree_files(ROOT / "academic_fig")
    pkg_py = [p for p in pkg_py if p.suffix == ".py"]
    delivery: list[Path] = []
    for d in DELIVERY_DIRS:
        delivery.extend(_tree_files(ROOT / d))
    # 顶层文档也算交付面
    for name in ("README.md", "SKILL.md"):
        p = ROOT / name
        if p.is_file():
            delivery.append(p)
    delivery = [p for p in delivery if not _is_derived(_rel_posix(p))]
    delivery_total = sum(p.stat().st_size for p in delivery)

    key = {}
    newest = 0.0
    for rel in KEY_FILES:
        p = ROOT / rel
        if p.is_file():
            key[rel] = {"sha256": _sha256(p), "bytes": p.stat().st_size}
            newest = max(newest, p.stat().st_mtime)
    for p in pkg_py:
        newest = max(newest, p.stat().st_mtime)

    stamp = dt.datetime.fromtimestamp(newest) if newest else dt.datetime.now()
    version = "0.2.0"
    for line in (ROOT / "academic_fig" / "__init__.py").read_text(encoding="utf-8").splitlines():
        if line.startswith("__version__"):
            version = line.split("=", 1)[1].strip().strip("\"'")
            break
    return {
        "version": version,
        "build": f"{version}+{stamp.strftime('%Y%m%d-%H%M')}",
        "generated_at": dt.datetime.now().strftime("%Y-%m-%dT%H:%M:%S%z") or "",
        "source_mtime": stamp.strftime("%Y-%m-%dT%H:%M:%S"),
        "package_py_files": len(pkg_py),
        "delivery_files": len(delivery),
        "delivery_bytes": delivery_total,
        "delivery_excludes": list(DERIVED_DIRS),
        "key_files": key,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="写/校验仓库根 BUILD.json")
    ap.add_argument("--write", action="store_true",
                    help="写盘（默认行为；显式写出来只是为了让调用方读得懂）")
    ap.add_argument("--check", action="store_true", help="只校验，不写")
    ap.add_argument("--json", action="store_true", help="打印完整 JSON")
    args = ap.parse_args(argv)

    data = collect()
    text = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=False) + "\n"

    if args.check:
        if not BUILD.is_file():
            print(f"[!!] 缺 {BUILD.name}；跑 python scripts/write_build.py", file=sys.stderr)
            return 1
        old = json.loads(BUILD.read_text(encoding="utf-8"))
        drift = [k for k in ("build", "package_py_files", "delivery_files",
                             "delivery_bytes", "delivery_excludes", "key_files")
                 if old.get(k) != data.get(k)]
        if drift:
            print(f"[!!] BUILD.json 已过期（{', '.join(drift)}）——重跑 write_build.py",
                  file=sys.stderr)
            return 1
        runtime = _runtime_build()
        if runtime and runtime != data["build"]:
            print(f"[!!] academic_fig.__build__={runtime} 与 BUILD.json 的 "
                  f"{data['build']} 不一致——重跑 write_build.py", file=sys.stderr)
            return 1
        print(f"[ok] BUILD.json 与当前文件一致：build {data['build']}，"
              f"{data['package_py_files']} 个 .py，{data['delivery_files']} 个交付文件，"
              f"{data['delivery_bytes']} B")
        return 0

    BUILD.write_text(text, encoding="utf-8")
    if args.json:
        print(text, end="")
    print(f"[ok] 写出 {BUILD.name}：build {data['build']}，"
          f"{data['package_py_files']} 个 .py，{data['delivery_files']} 个交付文件，"
          f"{data['delivery_bytes']} B")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())