# -*- coding: utf-8 -*-
"""从示例 JSON 与渲染器源码生成「示意图 spec 字段表」（acceptance #3）。

用法::

    python scripts/diagram_fields.py            # 打印 markdown 表
    python scripts/diagram_fields.py --write    # 写到 references/diagram-spec-fields.md
    python scripts/diagram_fields.py --check    # 只比对文件是否最新（不一致则退出码 1）

字段来源有两处，缺一不可：

1. ``examples/data/diagrams/*.json`` —— 真实示例用到的键（给出示例值的类型）；
2. 渲染器源码里 ``sp.get("…")`` / ``sp["…"]`` 的键 —— 渲染器读得出来、但示例还没用到的键。

`_guard.known_spec_keys` 已经做了第 2 步（并且是未知键校验的唯一依据），这里复用。
"""
from __future__ import annotations

import argparse
import ast
import json
import pathlib
import re
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from academic_fig.diagrams._guard import known_spec_keys  # noqa: E402

DIAGRAM_DIR = ROOT / "examples" / "data" / "diagrams"
TARGET = ROOT / "references" / "diagram-spec-fields.md"

CATEGORIES: tuple[tuple[str, str, str], ...] = (
    ("architecture", "框架结构图", "架构图：分层、模块、跨层连线"),
    ("flow", "流程/时序图", "流程、泳道、判断分支"),
    ("field", "场量/响应面", "响应面、等高线、场分布"),
    ("geometry", "区域与覆盖", "区域、圆、基站、关键点、比例尺"),
    ("gate", "门限与权衡", "帕累托前沿、门限带、指标权衡"),
)

_TYPE_NAMES = {
    str: "str",
    int: "int",
    float: "float",
    bool: "bool",
    list: "list",
    dict: "dict",
    type(None): "null",
}


def _type_of(value: Any) -> str:
    if isinstance(value, bool):
        return "bool"
    for py_type, name in _TYPE_NAMES.items():
        if isinstance(value, py_type):
            return name
    return type(value).__name__


def _defaults(module_name: str) -> dict[str, str]:
    """扫源码里 ``sp.get("k", <默认值>)`` 的默认值字面量（只取能一层括号内写完的）。"""
    import importlib

    mod = importlib.import_module(module_name)
    src = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    found: dict[str, str] = {}
    for match in re.finditer(r'sp\.get\(\s*["\']([A-Za-z_]\w*)["\']\s*,\s*', src):
        key = match.group(1)
        i = match.end()
        depth = 1
        j = i
        while j < len(src) and depth:
            if src[j] in "([{":
                depth += 1
            elif src[j] in ")]}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        literal = src[i:j].strip()
        if key not in found and len(literal) <= 32:
            found[key] = literal
    return found


def _samples() -> dict[str, list[tuple[str, dict[str, Any]]]]:
    """按类别收集示例：``{category: [(文件名, spec)]}``。"""
    out: dict[str, list[tuple[str, dict]]] = {key: [] for key, _, _ in CATEGORIES}
    for path in sorted(DIAGRAM_DIR.glob("*.json")):
        try:
            spec = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:  # pragma: no cover - 坏 JSON 要显式报
            raise SystemExit(f"{path.name}: JSON 解析失败：{exc}") from exc
        for key, _, _ in CATEGORIES:
            if path.stem.startswith(key) or (key == "architecture" and path.stem.startswith("arch")):
                out[key].append((path.name, spec))
                break
    return out


def build() -> str:
    samples = _samples()
    lines: list[str] = [
        "# 示意图 spec 字段表（自动生成，勿手改）",
        "",
        "由 `scripts/diagram_fields.py` 从 `examples/data/diagrams/*.json` 与渲染器源码生成。",
        "改动 spec 键或示例后重跑：`python scripts/diagram_fields.py --write`。",
        "",
        "「来源」列：`示例` = 至少一个示例 JSON 在用（括号里给出示例值的类型）；",
        "`源码` = 渲染器读得出来、但示例还没覆盖。未知键在 `strict=True`（默认）下直接抛",
        "`ValueError`，不会再画出一张空图。",
        "",
    ]
    for key, title, blurb in CATEGORIES:
        module = f"academic_fig.diagrams.{key}"
        keys = sorted(known_spec_keys(module))
        defaults = _defaults(module)
        used: dict[str, str] = {}
        for filename, spec in samples.get(key, []):
            for k, v in spec.items():
                used.setdefault(k, f"{_type_of(v)}（{filename}）")
        rows: list[tuple[str, str, str, str]] = []
        for k in keys:
            source = "示例" if k in used else "源码"
            rows.append((k, used.get(k, "—"), defaults.get(k, "—"), source))
        lines.append(f"## {title}（`{key}`）")
        lines.append("")
        lines.append(blurb + "。")
        lines.append("")
        if not rows:  # pragma: no cover - 五个渲染器都有键
            lines.append("（无）")
            lines.append("")
            continue
        lines.append("| 键 | 示例值类型 | 默认值 | 来源 |")
        lines.append("| --- | --- | --- | --- |")
        for k, typ, default, source in rows:
            lines.append(f"| `{k}` | {typ} | `{default}` | {source} |")
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="生成示意图 spec 字段表")
    ap.add_argument("--write", action="store_true", help="写入 references/diagram-spec-fields.md")
    ap.add_argument("--check", action="store_true", help="只比对文件是否最新")
    args = ap.parse_args(argv)

    text = build()
    if args.check:
        if not TARGET.exists():
            print(f"[fail] 缺少 {TARGET.relative_to(ROOT)}")
            return 1
        current = TARGET.read_text(encoding="utf-8")
        if current != text:
            print("[fail] 字段表已过期，重跑：python scripts/diagram_fields.py --write")
            return 1
        print("[ok] 字段表是最新的")
        return 0
    if args.write:
        TARGET.parent.mkdir(parents=True, exist_ok=True)
        TARGET.write_text(text, encoding="utf-8")
        print(f"[ok] 已写入 {TARGET.relative_to(ROOT)}（{len(text.encode('utf-8'))} B）")
        return 0
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())