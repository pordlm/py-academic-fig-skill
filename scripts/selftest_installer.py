# -*- coding: utf-8 -*-
"""自证安装器的修剪安全性：清单里的路径不得越出安装目录。

`--force` 会按 `.install-manifest.json` 删除「上次装过、源码里已没有」的文件。清单是
目标目录里的普通文件，**可以被人改坏或篡改**；一旦 ``target / rel`` 直接成立，一条
``../../某人的文件`` 或绝对路径就能删掉安装目录之外的东西。本脚本把这条边界钉成
可执行断言：

1. ``safe_relpath`` 拒绝绝对路径 / 盘符 / ``..`` / 空串，接受普通相对路径；
2. 清单里混入 ``../escape.txt`` 时，它既不会进待删清单，也不会被 ``prune_stale`` 删掉；
3. 中间目录是指向外部目录的链接时（能建则测），同样拒绝；
4. 清单损坏（不是合法 JSON）时**一条都不删**，并给出告警；
5. 旧版清单（没有 ``paths`` 字段）同样不删，避免误删用户自己放进去的文件；
6. ``COPY_FILES`` 带 ``LICENSE``（GPL 要求分发时附许可证全文）。

用法::

    python scripts/selftest_installer.py        # 全绿 exit 0；任一断言失败 exit 1

只用标准库：安装器本身不 import academic_fig。
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parent.parent
INSTALLER = ROOT / "scripts" / "install_skill.py"

FAILS: list[str] = []


def ok(msg: str) -> None:
    print(f"[ok] {msg}")


def expect(label: str, cond: bool, detail: str = "") -> None:
    if cond:
        ok(label + (f"  {detail}" if detail else ""))
    else:
        FAILS.append(label)
        print(f"[!!] {label}  {detail}", file=sys.stderr)


def load_installer():
    spec = importlib.util.spec_from_file_location("install_skill_under_test", INSTALLER)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[x] 加载不了 {INSTALLER}")
    mod = importlib.util.module_from_spec(spec)
    # dataclass 装饰器要按 __module__ 回查 sys.modules，先登记再执行
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _make_install(tmp: Path, mod, manifest: dict | None, name: str = "academic-figures") -> Path:
    """造一个「像装过」的目标目录：一个陈旧文件 + 一个用户自己的文件。"""
    target = tmp / "skills" / name
    (target / "academic_fig").mkdir(parents=True)
    (target / "academic_fig" / "old.py").write_text("# stale\n", encoding="utf-8")
    (target / "SKILL.md").write_text("# skill\n", encoding="utf-8")
    (target / "academic_fig" / "user_notes.txt").write_text("mine\n", encoding="utf-8")
    if manifest is not None:
        (target / mod.MANIFEST_NAME).write_text(
            json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    return target


def _items() -> list[tuple[str, Path]]:
    return [("SKILL.md", ROOT / "SKILL.md")]


def main() -> int:
    mod = load_installer()
    print(f"安装器：{INSTALLER}")

    # 1) 词法过滤 ---------------------------------------------------------------
    rejects = ["/etc/passwd", "C:/Windows/win.ini", "c:\\x\\y", "..\\escape.txt",
               "a/../../b", "", "   ", "../", ".."]
    for bad in rejects:
        expect(f"safe_relpath 拒绝 {bad!r}", mod.safe_relpath(bad) is None,
               f"→ {mod.safe_relpath(bad)!r}")
    for good in ("academic_fig/x.py", "a/./b.txt", "./SKILL.md", "prompts/a.md"):
        expect(f"safe_relpath 接受 {good!r}", isinstance(mod.safe_relpath(good), str),
               f"→ {mod.safe_relpath(good)!r}")

    with tempfile.TemporaryDirectory(prefix="afg_install_") as raw:
        tmp = Path(raw)

        # 2) 清单混入 ../escape.txt：不删越界文件 ---------------------------------
        outside = tmp / "escape.txt"
        outside.write_text("do not delete\n", encoding="utf-8")
        target = _make_install(tmp, mod, {
            "mode": "copy", "fingerprint": "x", "source": str(ROOT),
            "paths": ["SKILL.md", "academic_fig/old.py", "../escape.txt",
                      str(outside).replace("/", "\\")],
        })
        stale, notes = mod.stale_paths(target, _items(), mod.read_manifest(target)[0])
        expect("陈旧清单只含源码已删的相对路径", stale == ["academic_fig/old.py"], f"{stale}")
        expect("越界路径被记入告警", any("不安全路径" in n or "越界" in n for n in notes), f"{notes}")
        mod.prune_stale(target, stale, dry=False)
        expect("安装目录外的 escape.txt 仍然存在", outside.is_file())
        expect("陈旧文件被正常删除", not (target / "academic_fig" / "old.py").exists())
        expect("用户自己的文件不被误删",
               (target / "academic_fig" / "user_notes.txt").is_file())

        # 3) 中间目录是指向外部的链接 ---------------------------------------------
        link_target = tmp / "linked"
        target3 = _make_install(tmp, mod, None, "t3")
        made_link = False
        try:
            if os.name == "nt":
                # 普通用户可建 junction；sandbox 可能拒绝，失败就跳过该子场景
                import subprocess
                res = subprocess.run(["cmd", "/c", "mklink", "/J",
                                      str(target3 / "linked"), str(link_target)],
                                     capture_output=True, text=True)
                made_link = res.returncode == 0
            else:
                os.symlink(link_target, target3 / "linked", target_is_directory=True)
                made_link = True
        except OSError:
            made_link = False
        if made_link:
            link_target.mkdir(exist_ok=True)
            (link_target / "victim.txt").write_text("keep\n", encoding="utf-8")
            manifest3 = {"mode": "copy", "fingerprint": "x",
                         "paths": ["linked/victim.txt"]}
            stale3, notes3 = mod.stale_paths(target3, _items(), manifest3)
            expect("符号链接越界的陈旧路径被拒", stale3 == [], f"{stale3} / {notes3}")
            mod.prune_stale(target3, ["linked/victim.txt"], dry=False)
            expect("链接指向的外部文件仍然存在", (link_target / "victim.txt").is_file())
        else:
            print("[--] 跳过链接越界子场景（当前环境建不了 junction/symlink）")

        # 4) 清单损坏：一条都不删 --------------------------------------------------
        target4 = _make_install(tmp, mod, None, "t4")
        (target4 / mod.MANIFEST_NAME).write_text("{not json", encoding="utf-8")
        manifest4, corrupt4 = mod.read_manifest(target4)
        expect("损坏清单被标记为 corrupt", manifest4 is None and corrupt4 is True)
        stale4, notes4 = mod.stale_paths(target4, _items(), manifest4, corrupt=corrupt4)
        expect("清单损坏时不修剪任何文件", stale4 == [], f"{stale4}")
        expect("清单损坏时给出告警", any("损坏" in n for n in notes4), f"{notes4}")

        # 5) 旧版清单没有 paths：同样不删 ------------------------------------------
        target5 = _make_install(tmp, mod, {"mode": "copy", "fingerprint": "x"}, "t5")
        stale5, notes5 = mod.stale_paths(target5, _items(), mod.read_manifest(target5)[0])
        expect("旧版清单（无 paths）不修剪", stale5 == [], f"{stale5}")
        expect("旧版清单给出告警", any("旧版本" in n for n in notes5), f"{notes5}")

        # 6) 干净的新清单：正常的陈旧文件照删 --------------------------------------
        target6 = _make_install(tmp, mod, {
            "mode": "copy", "fingerprint": "x",
            "paths": ["SKILL.md", "academic_fig/old.py"],
        }, "t6")
        stale6, notes6 = mod.stale_paths(target6, _items(), mod.read_manifest(target6)[0])
        expect("正常清单仍能识别陈旧文件", stale6 == ["academic_fig/old.py"], f"{stale6}")
        expect("正常清单无告警", notes6 == [], f"{notes6}")

    # 7) 分发合规：LICENSE 跟着复制安装走 -----------------------------------------
    expect("COPY_FILES 含 LICENSE", "LICENSE" in mod.COPY_FILES, f"{mod.COPY_FILES}")

    print()
    if FAILS:
        print(f"[!!] {len(FAILS)} 项失败：{FAILS}", file=sys.stderr)
        return 1
    print("[ok] 安装器修剪安全性自检全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())