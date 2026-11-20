#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把本仓库安装成一个 DSH skill（默认装到 ``<仓库上级>/.dsh/skills/academic-figures``）。

三种安装形态：

1. **复制**（默认，``--copy``）——把 ``SKILL.md`` / ``academic_fig/`` / ``prompts/`` /
   ``references/`` / ``examples/`` / ``assets/`` 拷过去。装完可脱离本仓库运行，
   代价是改代码后要重装。
2. **目录联接 / 符号链接**（``--junction``，别名 ``--link``）——目标目录直接指向本仓库，
   改代码立即生效，适合边改边用。Windows 用 ``mklink /J``（不需要管理员），
   Linux/macOS 用 ``os.symlink``。
3. **只演练**（``--dry-run``）——打印将要做的每一步（含将要删除的陈旧文件），
   不写盘、不改任何文件。

默认目标怎么定（**别把 skill 装进仓库自己肚子里**）：

* 裸跑时落在**仓库上级目录**的 ``.dsh/skills/academic-figures``——那是 DSH 扫描的项目级
  skill 根。所以从仓库根裸跑**不会**再造一份 ``<仓库>/.dsh/skills/…`` 的嵌套副本。
* 显式 ``--target`` 若落在仓库目录树内，直接报错退出（并给一条可照抄的命令）：
  否则「升级」写进了仓库自己，而真正被扫描的那份还停在旧版本，`__build__` 也对不上。
* 想装到别处（用户级 ``~/.dsh/skills``、另一个工作区）就显式 ``--target``。

升级（``--force``）会按上次的 ``.install-manifest.json`` **修剪陈旧文件**：源码里已经删掉的
文件（例如废弃的样张 PNG/PDF）会从目标目录里一并删除，删空了的子目录也清掉。只删
「上次装过」的路径，用户自己往目标目录里放的文件不动。``--dry-run`` 会先把将删清单打出来。

重复执行是幂等的：复制模式会先算一遍文件清单指纹，和上次装好的完全一致就直接说
「已是最新」，不会动目标目录。

用法::

    python scripts/install_skill.py                      # 装到 <仓库上级>/.dsh/skills/academic-figures
    python scripts/install_skill.py --dry-run            # 只看计划（含将删文件）
    python scripts/install_skill.py --target D:/x/skills/academic-figures --force
    python scripts/install_skill.py --junction            # 链接安装（改代码立刻生效）

结束时总会打印两行 ``build=<BUILD.json 的 build>`` 与 ``目标：<路径>``，
方便一眼核对仓库与安装副本是不是同一版。

注意：本脚本只用标准库，不 import academic_fig，因此没装依赖也能跑。
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MANIFEST_NAME = ".install-manifest.json"

# 装过去的东西：顺序即打印顺序
COPY_DIRS = ("academic_fig", "prompts", "references", "examples", "assets")
# BUILD.json 是构建戳的唯一来源（`academic_fig.__build__` 读它）：漏装会让安装版的
# `__build__` 退化成 ``__version__ + '+00000000-0000'``，与仓库对不上，排障时误判版本
COPY_FILES = ("SKILL.md", "README.md", "pyproject.toml", "BUILD.json")
# 不装：源包、阶段报告、缓存、出图产物
SKIP_DIR_NAMES = {"_src", "__pycache__", ".git", ".pytest_cache", ".mypy_cache",
                  "out", "reports", ".ipynb_checkpoints"}
SKIP_PATTERNS = ("*.pyc", "*.pyo", "*.tmp", ".DS_Store", "Thumbs.db")

DEFAULT_NAME = "academic-figures"
KEBAB_RE = r"^[a-z0-9]+(-[a-z0-9]+)*$"


# --------------------------------------------------------------------------- 目标路径
def default_target() -> Path:
    """默认安装目录：**仓库上级目录**下的 ``.dsh/skills/academic-figures``。

    这是 DSH 扫的项目级 skill 根。以前这里写的是相对当前目录的
    ``.dsh/skills/academic-figures``，于是从仓库根裸跑就在仓库里造出第二份嵌套副本
    ——那份副本不会被 DSH 扫描，而真正生效的那份还停在旧版本。
    """
    parent = REPO.parent
    if parent == REPO:          # 仓库恰好坐在盘符根（D:\），上级还是自己 → 退回用户目录
        parent = Path.home()
    return parent / ".dsh" / "skills" / DEFAULT_NAME


def _norm(path: Path) -> Path:
    """绝对化 + 大小写归一（Windows 上 ``D:\\X`` 与 ``d:\\x`` 是同一个目录）。"""
    return Path(os.path.normcase(os.path.abspath(path)))


def _is_within(child: Path, root: Path) -> bool:
    """``child`` 是否在 ``root`` 目录树内（含相等）。"""
    try:
        _norm(child).relative_to(_norm(root))
    except ValueError:
        return False
    return True


def resolve_target(raw: Path | None) -> Path:
    """把 ``--target`` 解析成绝对路径，并挡住两个会伤到仓库的位置。

    * 目标在仓库目录树内 —— 会造出不被扫描的嵌套副本，并且让「升级」写错地方；
    * 目标是仓库的上级 —— ``--force`` 修剪陈旧文件时会波及仓库自身。
    """
    if raw is None:
        target = default_target()
    else:
        target = raw.expanduser()
        if not target.is_absolute():
            # 只做绝对化，不做 resolve()：resolve 会顺着已有的 junction 指回仓库，末级目录名就丢了
            target = Path(os.path.abspath(target))
    fallback = default_target().as_posix()
    if _is_within(target, REPO):
        raise SystemExit(
            f"[x] 拒绝把 skill 装进仓库自己的目录树：{target}\n"
            f"    仓库根：{REPO}\n"
            f"    装在仓库里只会得到一份 DSH 不会扫描的嵌套副本，真正生效的那份仍停在旧版本。\n"
            f"    换一个位置：--target \"{fallback}\"\n"
            f"    （不带 --target 裸跑时默认就装到这里；用户级可以 --target ~/.dsh/skills/{DEFAULT_NAME}）")
    if _is_within(REPO, target):
        raise SystemExit(
            f"[x] 目标目录是仓库的上级：{target}\n"
            f"    仓库根：{REPO}\n"
            f"    --force 会修剪该目录里「上次装过、源码已删」的文件，把它当安装目录会波及仓库自身。\n"
            f"    请指向一个只装这个 skill 的目录：--target \"{fallback}\"")
    return target


# --------------------------------------------------------------------------- 前置校验
@dataclass
class FrontMatter:
    """``SKILL.md`` 的 YAML 头部（只取需要校验的字段，不引 PyYAML）。"""

    name: str = ""
    description: str = ""
    raw: dict[str, str] = field(default_factory=dict)


def read_frontmatter(skill_md: Path) -> FrontMatter:
    """读 ``SKILL.md`` 顶部 ``---`` 之间的字段。

    只做最朴素的 ``key: value`` 解析——够校验 name/description，且不引第三方依赖。
    """
    text = skill_md.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise SystemExit(f"[x] {skill_md} 没有 YAML 头（首行必须是 ---）")
    body: list[str] = []
    for line in lines[1:]:
        if line.strip() == "---":
            break
        body.append(line)
    else:
        raise SystemExit(f"[x] {skill_md} 的 YAML 头没有闭合的 ---")
    raw: dict[str, str] = {}
    for line in body:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith((" ", "\t")):        # metadata: 这类嵌套块不校验
            continue
        key, _, val = line.partition(":")
        raw[key.strip()] = val.strip().strip("\"'")
    return FrontMatter(name=raw.get("name", ""), description=raw.get("description", ""), raw=raw)


def validate_skill_md(target_name: str, *, skip_name_check: bool = False) -> FrontMatter:
    """校验 ``SKILL.md``：name 必须是 kebab-case 且等于安装目录名，description 非空。"""
    skill_md = REPO / "SKILL.md"
    if not skill_md.is_file():
        raise SystemExit(f"[x] 找不到 {skill_md}")
    fm = read_frontmatter(skill_md)
    problems: list[str] = []
    if not fm.name:
        problems.append("frontmatter 缺 name")
    elif not __import__("re").match(KEBAB_RE, fm.name):
        problems.append(f"name 不是 kebab-case：{fm.name!r}（只允许小写字母/数字/连字符）")
    elif not skip_name_check and fm.name != target_name:
        problems.append(f"name（{fm.name}）与安装目录名（{target_name}）不一致："
                        f"改 --target 的末级目录名，或加 --skip-name-check")
    if not fm.description.strip():
        problems.append("frontmatter 的 description 为空（skill 靠它决定何时被唤醒）")
    if problems:
        raise SystemExit("[x] SKILL.md 校验失败：\n  - " + "\n  - ".join(problems))
    return fm


# --------------------------------------------------------------------------- 清单 / 指纹
def _skipped(path: Path, root: Path) -> bool:
    parts = path.relative_to(root).parts
    if any(p in SKIP_DIR_NAMES for p in parts[:-1]):
        return True
    return any(fnmatch.fnmatch(path.name, pat) for pat in SKIP_PATTERNS)


def collect_sources() -> list[tuple[str, Path]]:
    """列出要装的文件：``[(相对路径 posix, 源路径)]``，已排序、已排除缓存与产物。"""
    items: list[tuple[str, Path]] = []
    for name in COPY_FILES:
        src = REPO / name
        if src.is_file():
            items.append((name, src))
    for name in COPY_DIRS:
        base = REPO / name
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_file() and not _skipped(path, REPO):
                items.append((path.relative_to(REPO).as_posix(), path))
    return items


def fingerprint(items: list[tuple[str, Path]]) -> str:
    """整包指纹：路径 + 内容的 sha256，用来判断「已是最新」。"""
    h = hashlib.sha256()
    for rel, src in items:
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(src.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def _total_bytes(items: list[tuple[str, Path]]) -> int:
    return sum(src.stat().st_size for _, src in items)


# --------------------------------------------------------------------------- 安装
def _is_junction(path: Path) -> bool:
    if path.is_symlink():
        return True
    if os.name != "nt":
        return False
    try:   # junction 在 Python 里不算 symlink，用 FILE_ATTRIBUTE_REPARSE_POINT 判定
        attrs = os.stat(path, follow_symlinks=False).st_file_attributes  # type: ignore[attr-defined]
    except (OSError, AttributeError):
        return False
    return bool(attrs & 0x400)


def _remove_target(target: Path) -> None:
    """删掉旧安装：链接直接解链，普通目录整个删掉。"""
    if _is_junction(target):
        if os.name == "nt" and not target.is_symlink():
            os.rmdir(target)          # junction 用 rmdir 解链，不碰源目录
        else:
            target.unlink()
        return
    shutil.rmtree(target)


def install_copy(items: list[tuple[str, Path]], target: Path, *,
                 dry: bool, stale: list[str] | None = None) -> None:
    """把 ``items`` 拷进 ``target``；``dry`` 时只打印计划（含将删的陈旧文件）。"""
    stale = list(stale or [])
    if dry:
        print(f"[dry] 会写入 {len(items)} 个文件到 {target}")
        for rel, _ in items[:6]:
            print(f"      + {rel}")
        if len(items) > 6:
            print(f"      … 其余 {len(items) - 6} 个")
        if stale:
            print(f"[dry] 会删除 {len(stale)} 个陈旧文件（上次装过、这次源码里已没有）：")
            for rel in stale[:12]:
                print(f"      - {rel}")
            if len(stale) > 12:
                print(f"      … 其余 {len(stale) - 12} 个")
        return
    target.mkdir(parents=True, exist_ok=True)
    for rel, src in items:
        dst = target / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def install_link(target: Path, *, dry: bool) -> None:
    if dry:
        kind = "junction" if os.name == "nt" else "symlink"
        print(f"[dry] 会建立 {kind}：{target} -> {REPO}")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        res = subprocess.run(["cmd", "/c", "mklink", "/J", str(target), str(REPO)],
                             capture_output=True, text=True)
        if res.returncode != 0:
            raise SystemExit(f"[x] mklink /J 失败：{res.stderr.strip() or res.stdout.strip()}")
    else:
        os.symlink(REPO, target, target_is_directory=True)


def read_build() -> str:
    """读 ``BUILD.json`` 的 build 串（缺失或坏了返回空串：只影响打印，不影响安装）。"""
    try:
        data = json.loads((REPO / "BUILD.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    build = data.get("build") if isinstance(data, dict) else None
    return build if isinstance(build, str) else ""


def _manifest_paths(manifest: dict[str, object] | None) -> list[str] | None:
    """上次装过的相对路径清单；旧版清单没有 ``paths`` 字段时返回 ``None``。"""
    if not isinstance(manifest, dict):
        return None
    paths = manifest.get("paths")
    if isinstance(paths, list) and paths and all(isinstance(p, str) for p in paths):
        return [p for p in paths if p]
    return None


def stale_paths(target: Path, items: list[tuple[str, Path]],
                manifest: dict[str, object] | None) -> list[str]:
    """源码里已经没有、目标目录里却还留着的文件（相对 posix 路径，已排序）。

    只认「上次装过」的路径：新版清单记了完整 ``paths``；旧版清单没记，就退化成在
    我们自己的交付根（``COPY_FILES`` / ``COPY_DIRS``）里扫一遍，不越界碰别的东西。
    """
    current = {rel for rel, _ in items}
    known = _manifest_paths(manifest)
    if known is None:
        candidates: list[str] = list(COPY_FILES)
        for name in COPY_DIRS:
            base = target / name
            if not base.is_dir():
                continue
            for path in base.rglob("*"):
                if path.is_file():
                    candidates.append(path.relative_to(target).as_posix())
    else:
        candidates = list(known)
    out: list[str] = []
    for rel in sorted(set(candidates)):
        if rel in current or rel == MANIFEST_NAME:
            continue
        path = target / rel
        if path.is_file() or path.is_symlink():
            out.append(rel)
    return out


def prune_stale(target: Path, stale: list[str], *, dry: bool) -> list[str]:
    """删掉陈旧文件并清理被删空的目录，返回实际（演练时是「将」）删除的清单。"""
    removed: list[str] = []
    for rel in stale:
        path = target / rel
        if not (path.is_file() or path.is_symlink()):
            continue
        if not dry:
            try:
                path.unlink()
            except OSError as exc:      # 只读/占用：报一声继续，不整体失败
                print(f"[!] 删不掉陈旧文件 {rel}：{exc}")
                continue
        removed.append(rel)
    if not dry:
        for name in COPY_DIRS:
            base = target / name
            if not base.is_dir():
                continue
            for path in sorted(base.rglob("*"), key=lambda q: len(q.parts), reverse=True):
                if path.is_dir() and not any(path.iterdir()):
                    try:
                        path.rmdir()
                    except OSError:
                        pass
    return removed


def write_manifest(target: Path, fp: str, items: list[tuple[str, Path]], mode: str) -> None:
    payload = {"mode": mode, "fingerprint": fp, "source": str(REPO),
               "files": len(items), "bytes": _total_bytes(items),
               "build": read_build(),
               # 记全路径：--force 升级时靠它精确修剪「上次装过、这次源码已没有」的文件
               "paths": sorted(rel for rel, _ in items)}
    (target / MANIFEST_NAME).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                                        encoding="utf-8")


def read_manifest(target: Path) -> dict[str, object] | None:
    path = target / MANIFEST_NAME
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


# --------------------------------------------------------------------------- 主流程
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="install_skill.py",
        description="把 academic-figures 安装成 DSH skill（复制或链接）；重复执行是幂等的。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="装好后验证：python -c \"import academic_fig; print(academic_fig.__version__)\"",
    )
    p.add_argument("--target", "--dest", dest="target", type=Path, default=None,
                   help=f"安装目录（默认 {default_target().as_posix()}；"
                        f"落在仓库目录树内会被拒绝）")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--copy", action="store_true", help="复制安装（默认）")
    mode.add_argument("--junction", "--link", dest="junction", action="store_true",
                      help="目录联接/符号链接安装（Windows 用 mklink /J）")
    p.add_argument("--dry-run", action="store_true",
                   help="只打印计划（含将删除的陈旧文件），不写盘")
    p.add_argument("--force", action="store_true",
                   help="目标已存在时覆盖，并按清单修剪源码已删除的陈旧文件（默认拒绝覆盖）")
    p.add_argument("--skip-name-check", action="store_true",
                   help="允许 SKILL.md 的 name 与安装目录名不一致（不建议）")
    p.add_argument("--quiet", action="store_true", help="只输出 build 与目标两行")
    return p


def _print_summary(target: Path, build: str) -> None:
    """收尾两行：build 串 + 目标路径（一眼核对仓库与安装副本是不是同一版）。"""
    print(f"build={build or '(BUILD.json 缺失)'}")
    print(f"目标：{target}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    target = resolve_target(args.target)          # 默认装到仓库上级；拒绝装进仓库内
    mode = "junction" if args.junction else "copy"
    say = (lambda *a, **k: None) if args.quiet else print
    build = read_build()

    validate_skill_md(target.name, skip_name_check=args.skip_name_check)
    say(f"[1/4] SKILL.md 校验通过（name={target.name}，description 非空）")

    items = collect_sources()
    fp = fingerprint(items)
    say(f"[2/4] 待安装 {len(items)} 个文件 / {_total_bytes(items) / 1024:.0f} KB")

    exists = target.exists() or target.is_symlink()
    manifest = read_manifest(target) if exists else None
    same = bool(manifest and manifest.get("fingerprint") == fp
                and manifest.get("mode") == mode and target.exists())
    if mode == "junction" and exists and os.path.realpath(target) == os.path.realpath(REPO):
        same = True          # 链接已经指向本仓库，重跑即「已是最新」
    stale = stale_paths(target, items, manifest) if (exists and mode == "copy") else []

    if args.dry_run:
        say(f"[3/4] 目标：{target}  （{'已存在' if exists else '不存在'}）")
        if same and not args.force:
            say("[4/4] 指纹一致：已是最新，实际执行时不会写任何文件")
            _print_summary(target, build)
            return 0
        if exists and not args.force:
            say("[4/4] 目标已存在且指纹不同：实际执行会报错；下面是 --force 的计划")
        if mode == "junction":
            install_link(target, dry=True)
        else:
            install_copy(items, target, dry=True, stale=stale)
        say("[4/4] 演练结束，未写盘")
        _print_summary(target, build)
        return 0

    if exists and not args.force:
        if same:
            say(f"[3/4] 已是最新（指纹 {fp[:12]}…，build={build or '未知'}），未做任何修改")
            _print_summary(target, build)
            if not args.quiet:
                _print_next_steps(target, mode)
            return 0
        raise SystemExit(
            f"[x] 目标目录已存在旧版本：{target}\n"
            f"    它与当前源码不一致（安装指纹 {(manifest or {}).get('fingerprint', '缺失')!s:.12}"
            f"… ≠ 当前 {fp[:12]}…），所以默认不覆盖——避免把别人改过的 skill 悄悄冲掉。\n"
            f"    升级：加 --force（原地覆盖，并按清单删掉源码里已不存在的陈旧文件；\n"
            f"    你自己往目标目录里放的文件不动）；\n"
            f"    只想先看计划：加 --dry-run（不写盘，会列出将覆盖与将删除的文件）；\n"
            f"    想彻底重来：先手动删掉该目录再跑一次。")

    if exists and mode == "copy" and _is_junction(target):
        # 上次装的是链接、这次要复制：先解链，否则 copy 会顺着链接写进仓库
        say(f"[3/4] 目标是链接，先解链再复制：{target}")
        _remove_target(target)
        exists = False
    elif exists:
        say(f"[3/4] {'替换旧链接' if mode == 'junction' else '升级旧安装（原地覆盖）'}：{target}")
        if mode == "junction":
            _remove_target(target)
    else:
        say(f"[3/4] 新建安装：{target}")

    if mode == "junction":
        install_link(target, dry=False)
    else:
        install_copy(items, target, dry=False, stale=stale)
        removed = prune_stale(target, stale, dry=False)
        if removed:
            say(f"      已删除 {len(removed)} 个陈旧文件：{'、'.join(removed[:6])}"
                + ("…" if len(removed) > 6 else ""))
        write_manifest(target, fp, items, mode)

    say(f"[4/4] 完成（{mode}，{len(items)} 个文件）")
    _print_summary(target, build)
    if not args.quiet:
        _print_next_steps(target, mode)
    return 0


def _print_next_steps(target: Path, mode: str) -> None:
    print("\n验证（在安装目录里跑，三条都应通过）：")
    print(f'  cd "{target}"')
    print('  python -c "import academic_fig as afg; print(afg.__version__, afg.__build__)"')
    print("  python -m academic_fig.cli list")
    # 首条自检必须打**已经装进来**的产物：``examples/out/`` 是出图结果、不随包安装，
    # 直接 check 它只会得到「目录不存在」。``assets/`` 里的样张与示意图是自带的。
    print("  python -m academic_fig.cli check --dir assets --strict        # 应 0 error")
    print("\n想验证数据图渲染链路（两步：先渲，再检）：")
    print("  python examples/render_plots.py --out examples/out")
    print("  python -m academic_fig.cli check --dir examples/out --strict  # 应 0 error")
    print("\n在任意项目里用：")
    print("  import matplotlib; matplotlib.use('Agg')")
    print("  import academic_fig as afg")
    print("  afg.apply_theme(); fig, ax = afg.paper_fig('single')")
    if mode == "junction":
        print(f"\n提示：这是链接安装，{target} 指向仓库；不要在里面改文件，改仓库即可。")


if __name__ == "__main__":
    sys.exit(main())