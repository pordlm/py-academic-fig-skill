#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""文档与代码「零漂移」核对器。

做两件事：

1. **生成** README 里两张表（大类→渲染器→提示词文件、词典覆盖度），
   保证表格不是手抄的。``--write`` 把生成结果写回 README 的标记区块。
2. **核对**（默认模式）：
   - `prompts/index.json` 里每个 `file` 存在、每个 `api` 都能在 `academic_fig` 上解析到；
   - README 两张表与生成结果逐字一致；
   - README / references 里出现的 `academic_fig.*` 函数名都真实存在；
   - `references/palette-role.md` 里写的十六进制色值都在 `palette.py` 里；
   - `references/journal-specs.md` 里写的字号都在 `typography.TEXT_SIZES` 里；
   - 文档里不出现私有路径（`/home/milistone`、`proj_4398`、`C:\\Users\\` 之类）。

退出码：全部通过 0，否则 1（每类问题打印前几条，便于定位）。

用法::

    python scripts/check_docs.py            # 核对
    python scripts/check_docs.py --write    # 用当前代码重写 README 的两张表
    python scripts/check_docs.py --verbose  # 打印每一条检查项
"""
from __future__ import annotations

import argparse
import importlib
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:      # 直接 python scripts/check_docs.py 时也能 import 本包
    sys.path.insert(0, str(REPO))
README = REPO / "README.md"
INDEX = REPO / "prompts" / "index.json"

# index.json 的 category -> (中文名, 提示词文件前缀)；顺序即 README 表格顺序
CATEGORY_ORDER = [
    ("compare", "比较与组成"),
    ("trend", "趋势与时序"),
    ("dist", "分布与描述统计"),
    ("relation", "关系与回归"),
    ("inference", "假设检验与 Meta"),
    ("ml", "机器学习与模型评估"),
    ("dimred", "降维与多维"),
    ("clinical", "临床与生存分析"),
    ("omics", "组学与生物信息"),
    ("flow", "流程与流向"),
]

# docs/图表词典.md 的 14 大类 -> (直接支持, 兜底方式)
COVERAGE = [
    ("1 基础比较与组成", "bar · grouped_bar · stacked_bar · lollipop", "帕累托/瀑布/环形等手写，`style_axes` 兜底"),
    ("2 趋势与时间序列", "line · area", "阶梯/事件图/甘特用 `line(step=…)` 或手写"),
    ("3 数据分布与描述统计", "violin · box · hist", "ECDF/雨云/山脊用 `hist`/`violin` 组合或手写"),
    ("4 变量关系与回归", "scatter · corr", "气泡/Hexbin/Q-Q 手写（`scatter` 换 marker 大小即可）"),
    ("5 假设检验与 Meta", "forest", "漏斗图/系数图手写（`annotate_point` + `refline`）"),
    ("6 机器学习与模型", "roc · pr · confusion", "校准/学习曲线/特征重要性手写（`line` + `bar`）"),
    ("7 多维与降维", "pca · radar", "碎石图/平行坐标/树状图手写；t-SNE/UMAP 传入二维坐标即可"),
    ("8 临床与生存", "km", "游泳道/累积发病率手写；PRISMA 用 `diagrams.flow`"),
    ("9 组学与生物信息", "volcano · heatmap", "MA/曼哈顿/UpSet 手写（`scatter` + 阈值线）"),
    ("10 流程与网络", "sankey · diagrams.flow · diagrams.architecture", "DAG/拓扑网络手写（`diagrams.flow` 加边）"),
    ("11 空间与连续场", "diagrams.field", "填色等高线/quiver/3D/三元图手写（matplotlib 原生 + `style_axes`）"),
    ("12 物理化材实验", "—（通用三件套）", "光谱/XRD/I-V/Nyquist/Bode 都是 `line`，套 `paper_fig` 即可"),
    ("13 图像型科研结果", "不支持（位图是数据本身）", "按 `references/why-not-native-png.md` 嵌入矢量排版"),
    ("14 科研表格", "不支持（不是图）", "用 Word/LaTeX 三线表；本 skill 只出图"),
]

PRIVATE_PATHS = ("milistone", "proj_4398", r"C:\Users\\", "/home/", "/mnt/c/Windows")
CAT_START, CAT_END = "<!-- cat-table:start -->", "<!-- cat-table:end -->"
COV_START, COV_END = "<!-- coverage-table:start -->", "<!-- coverage-table:end -->"


# --------------------------------------------------------------------------- 表格生成
def _index() -> list[dict]:
    return json.loads(INDEX.read_text(encoding="utf-8"))


def _registry() -> dict:
    from academic_fig import plots

    return plots.REGISTRY


def category_table() -> str:
    """数据图大类表：大类 | 渲染器 | 提示词文件。"""
    idx = {it["category"]: it for it in _index()}
    reg = _registry()
    lines = ["| 大类 | 渲染器 | 提示词 | 用来画什么 |", "|---|---|---|---|"]
    for cat, cn in CATEGORY_ORDER:
        entry = idx.get(cat)
        if entry is None:
            lines.append(f"| {cn} | — | — | （`prompts/index.json` 缺 {cat}） |")
            continue
        names = [a.rsplit(".", 1)[-1] for a in entry["api"]
                 if a.startswith("academic_fig.plots.")]
        rendered = " ".join(f"`{n}`" for n in names) or "—（通用原语）"
        missing = [n for n in names if n not in reg]
        if missing:
            rendered += f" ⚠ 未实现：{', '.join(missing)}"
        lines.append(f"| {cn} | {rendered} | `{entry['file']}` | {entry['title']} |")
    return "\n".join(lines)


def coverage_table() -> str:
    """词典覆盖度表：14 大类 | 直接支持 | 兜底方式。"""
    reg = _registry()
    lines = ["| 词典大类 | 直接支持 | 没有专属渲染器时怎么办 |", "|---|---|---|"]
    for name, support, fallback in COVERAGE:
        for token in re.findall(r"`?([a-z_]+)`?", support):
            if token in {"—", "bar", "grouped_bar", "stacked_bar", "lollipop", "line", "area",
                         "violin", "box", "hist", "scatter", "corr", "forest", "roc", "pr",
                         "confusion", "pca", "radar", "km", "volcano", "heatmap", "sankey"}:
                if token not in reg:
                    support += f" ⚠ 未实现：{token}"
        lines.append(f"| {name} | {support} | {fallback} |")
    return "\n".join(lines)


def _inject(text: str, start: str, end: str, body: str) -> str:
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.S)
    if not pattern.search(text):
        raise SystemExit(f"[x] README 缺标记块 {start} … {end}")
    return pattern.sub(f"{start}\n{body}\n{end}", text, count=1)


# --------------------------------------------------------------------------- spec 键真伪
#: 这些词在「Spec 字段」章节里出现，但不是 spec 键（函数参数、类型名、字面量）
SPEC_WHITELIST = {
    "str", "bool", "int", "float", "list", "dict", "tuple", "none", "true", "false",
    "width", "height", "note", "strict", "debug", "layer_border", "spec", "json",
    "px", "in", "pt", "dpi", "fig", "ax", "true", "false", "optional",
}

#: 章节标题里出现这些词，才把该节反引号里的标识符当 spec 键
SPEC_SECTION_HINTS = ("spec", "字段", "键")


def _diagram_spec_keys() -> dict[str, set[str]]:
    """从 ``academic_fig/diagrams/*.py`` 里抽「真正被读取的 spec 键」。

    只认两种写法：``x.get("key")``（含 ``sp.get("key", default)``）与
    ``x["key"]``——渲染器读 spec 就这两条路径，其余字符串不可能是键。
    返回 ``{键: {来源文件}}``，报告里能指到是哪个渲染器读它。
    """
    keys: dict[str, set[str]] = {}
    for src in sorted((REPO / "academic_fig" / "diagrams").glob("*.py")):
        text = src.read_text(encoding="utf-8")
        for pat in (r"\.get\(\s*[\"']([A-Za-z_]\w*)[\"']",
                    r"\[\s*[\"']([A-Za-z_]\w*)[\"']\s*\]"):
            for m in re.finditer(pat, text):
                keys.setdefault(m.group(1), set()).add(src.name)
    return keys


def _spec_key_candidates(path: Path) -> list[tuple[int, str]]:
    """文档里「像 spec 键」的标识符：Spec 章节内的反引号词 + ```json 块的键。

    只在章节标题含 spec/字段/键 时收反引号词——否则 ``linewidth``、``ax`` 这类
    正文代码词会淹没结果；JSON 代码块里的键不受章节限制（它就是 spec 字面量）。
    """
    out: list[tuple[int, str]] = []
    stack: list[str] = []
    in_fence = False
    fence_is_json = False
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("```"):
            if not in_fence:
                in_fence = True
                fence_is_json = stripped[3:].strip().lower().startswith(("json", "python", "py"))
            else:
                in_fence = False
                fence_is_json = False
            continue
        if in_fence:
            if fence_is_json and stripped[:1] in '{"':
                for m in re.finditer(r"[\"']([a-z][a-z0-9_]{1,24})[\"']\s*:", stripped):
                    out.append((lineno, m.group(1)))
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            level = len(m.group(1))
            stack = stack[:level - 1]
            stack.append(m.group(2))
            continue
        if any(h in heading.lower() or h in heading
               for heading in stack for h in ("spec", "字段", "键")):
            for m in re.finditer(r"`([A-Za-z_][A-Za-z0-9_]{0,24})`", line):
                out.append((lineno, m.group(1)))
    return out


def check_spec_keys(verbose: bool = False) -> list[str]:
    """核对文档里写的 spec 字段名都真实存在（防止提示词再次「编造字段」）。

    背景：提示词由外部模型撰写，它会把不存在的字段写得很像真的（例如把
    ``route`` 写成字符串枚举 ``straight/hv/vh``、把 ``auto_cols`` 说成默认 True）。
    命名层面的错误可以静态抓住：文档里出现的 spec 键必须能在
    ``academic_fig/diagrams/*.py`` 的 ``.get("…")`` / ``["…"]`` 里找到。
    """
    problems: list[str] = []
    known = _diagram_spec_keys()
    known_names = set(known) | SPEC_WHITELIST
    scanned = 0
    for doc in [REPO / "README.md"] + sorted((REPO / "prompts").glob("*.md")):
        if not doc.is_file():
            continue
        for lineno, key in _spec_key_candidates(doc):
            scanned += 1
            if key in known_names:
                continue
            problems.append(
                f"{doc.relative_to(REPO).as_posix()}:{lineno} 写了 spec 键 `{key}`，"
                f"但 academic_fig/diagrams 里没有任何渲染器读取它")
    if verbose and not problems:
        print(f"  spec 键 {len(known)} 个（文档里出现 {scanned} 处，全部对得上）")
    return problems


# --------------------------------------------------------------------------- 核对
def _resolve(dotted: str) -> bool:
    parts = dotted.split(".")
    if not parts or parts[0] != "academic_fig":
        return False
    obj = importlib.import_module("academic_fig")
    for part in parts[1:]:
        if hasattr(obj, part):
            obj = getattr(obj, part)
            continue
        try:
            obj = importlib.import_module(f"{obj.__name__}.{part}")
        except (ImportError, AttributeError):
            return False
    return True


def check(verbose: bool = False) -> list[str]:
    problems: list[str] = []

    # 1. index.json：文件存在、api 可解析、diagram_* 指向 diagrams 模块
    for item in _index():
        f = REPO / item["file"]
        if not f.is_file():
            problems.append(f"index.json 指向的提示词文件不存在：{item['file']}")
        for api in item["api"]:
            if not _resolve(api):
                problems.append(f"index.json[{item['category']}] 的 api 解析不到：{api}")
        if item["category"].startswith("diagram_") and not any(
                a.startswith("academic_fig.diagrams.") for a in item["api"]):
            problems.append(f"index.json[{item['category']}] 应指向 academic_fig.diagrams.*")

    # 2. README 两张表与生成结果逐字一致
    readme = README.read_text(encoding="utf-8")
    for start, end, body, label in (
        (CAT_START, CAT_END, category_table(), "大类表"),
        (COV_START, COV_END, coverage_table(), "覆盖度表"),
    ):
        got = re.search(re.escape(start) + r"(.*?)" + re.escape(end), readme, re.S)
        if not got:
            problems.append(f"README 缺标记块 {start} … {end}")
        elif got.group(1).strip() != body.strip():
            problems.append(f"README {label}与代码不一致（跑 --write 重新生成）")

    # 3. README / references 里提到的 academic_fig.* 都要真实存在
    docs = [README] + sorted((REPO / "references").glob("*.md"))
    seen: set[str] = set()
    for doc in docs:
        text = doc.read_text(encoding="utf-8")
        for raw in re.findall(r"\b(?:academic_fig|afg)(?:\.[A-Za-z_][A-Za-z0-9_]*)+", text):
            name = "academic_fig" + raw.split("afg", 1)[1] if raw.startswith("afg") else raw
            if name in seen:
                continue
            seen.add(name)
            if not _resolve(name):
                problems.append(f"{doc.name} 提到不存在的接口：{raw}")

    # 4. palette-role.md 里的十六进制色值必须在 palette.py 里
    from academic_fig import palette

    known = {v.upper() for k, v in vars(palette).items()
             if isinstance(v, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", v)}
    pal_doc = (REPO / "references" / "palette-role.md").read_text(encoding="utf-8")
    for hexval in set(re.findall(r"#[0-9A-Fa-f]{6}", pal_doc)):
        if hexval.upper() not in known:
            problems.append(f"palette-role.md 里的色值不在 palette.py：{hexval}")

    # 5. journal-specs.md 里的「语义 | 值」字号行必须与 TEXT_SIZES 一致
    from academic_fig import typography

    sizes = typography.TEXT_SIZES
    spec_doc = (REPO / "references" / "journal-specs.md").read_text(encoding="utf-8")
    for name in ("title", "body", "label", "tick", "footnote", "footnote_wrapped"):
        m = re.search(rf"\|\s*`{name}`\s*\|\s*([0-9.]+)\s*\|", spec_doc)
        if not m:
            problems.append(f"journal-specs.md 缺字号行 `{name}`")
        elif abs(float(m.group(1)) - float(sizes[name])) > 1e-9:
            problems.append(f"journal-specs.md 的 {name}={m.group(1)} 与代码 {sizes[name]} 不一致")

    # 6. 私有路径不得出现在文档里
    for doc in docs + [REPO / "SKILL.md"]:
        text = doc.read_text(encoding="utf-8")
        for bad in PRIVATE_PATHS:
            if bad in text:
                problems.append(f"{doc.name} 出现私有路径片段：{bad}")

    # 7. 字号字典的取值集合必须与 ALLOWED_SIZES 相等（F-08）
    #    否则会出现「代码里有 12pt、检查器却说 12 不合法」这种自相矛盾；
    #    反过来，ALLOWED_SIZES 里躺着一个没人用的值，等于放行了野字号。
    allowed = set(typography.ALLOWED_SIZES)
    used = set(sizes.values())
    for extra in sorted(used - allowed):
        problems.append(f"TEXT_SIZES 用了 {extra}pt，但不在 ALLOWED_SIZES {sorted(allowed)} 里")
    for spare in sorted(allowed - used):
        problems.append(f"ALLOWED_SIZES 放了 {spare}pt，但 TEXT_SIZES 没有任何语义用到它")

    # 8. 文档里的 spec 字段名必须真实存在（防「编造字段」）
    problems.extend(check_spec_keys(verbose))

    if verbose and not problems:
        print(f"  index.json {len(_index())} 条 · 文档 {len(docs)} 篇 · 接口 {len(seen)} 个 · 色值 {len(known)} 个")
    return problems


# --------------------------------------------------------------------------- 入口
def selftest_spec_keys() -> int:
    """自证 spec 键检查有效：造一份「编了字段」的文档，必须被抓到。

    检查器自己空转过一次（旧配色检查），所以这里也留一条反例：
    真实键 ``title`` 不能报，编造键 ``bogus_field`` 与 JSON 里的 ``fake_key`` 必须报。
    """
    import tempfile

    known = set(_diagram_spec_keys()) | SPEC_WHITELIST
    sample = (
        "# 假文档\n\n"
        "## 4. 声明式 Spec 字段说明\n\n"
        "- `title` (str): 真键。\n"
        "- `bogus_field` (str): 编造的键，必须被抓。\n\n"
        "```json\n{\"fake_key\": 1, \"layers\": []}\n```\n"
    )
    with tempfile.TemporaryDirectory(prefix="afg_spectest_") as tmp:
        path = Path(tmp) / "fake.md"
        path.write_text(sample, encoding="utf-8")
        found = {k for _, k in _spec_key_candidates(path)}
    must_hit = {"bogus_field", "fake_key"}
    must_miss = {"title"}
    ok = must_hit <= found and not (must_miss & (found - known))
    print(f"[{'PASS' if ok else 'FAIL'}] spec 键检查自证："
          f"抓到 {sorted(must_hit & found)}，放过 {sorted(must_miss & found)}")
    if not ok:
        print(f"        未抓到的：{sorted(must_hit - found)}")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="文档与代码零漂移核对器")
    ap.add_argument("--write", action="store_true", help="用当前代码重写 README 的两张表")
    ap.add_argument("--verbose", action="store_true", help="通过时也打印统计")
    ap.add_argument("--selftest-spec", action="store_true",
                    help="只跑「编造字段必须被抓」的自证")
    args = ap.parse_args(argv)

    if args.selftest_spec:
        return selftest_spec_keys()

    if args.write:
        text = README.read_text(encoding="utf-8")
        text = _inject(text, CAT_START, CAT_END, category_table())
        text = _inject(text, COV_START, COV_END, coverage_table())
        README.write_text(text, encoding="utf-8")
        print("[ok] 已重写 README 的两张表")

    problems = check(verbose=args.verbose)
    if problems:
        print(f"[x] 发现 {len(problems)} 处不一致：")
        for p in problems[:20]:
            print(f"  - {p}")
        if len(problems) > 20:
            print(f"  … 其余 {len(problems) - 20} 处")
        return 1
    print("[ok] 文档与代码一致：index.json 可解析、README 两表同步、接口/色值/字号/路径全部对得上")
    return 0


if __name__ == "__main__":
    sys.exit(main())