# -*- coding: utf-8 -*-
"""README「示意图：5 个渲染器」一节的**可执行版本**。

README 里那三段示例必须能照抄就跑（评审 R-01/R-03）：本文件把每一段原样放进来，
跑一遍，产物落在 ``examples/out/readme/``，并顺手证明：

* 示意图 spec 的**真实键名**（``layers[].nodes``，不是 ``modules``）；
* ``afg.apply_theme()`` 必须在画图前调用 —— 不调用中文会变方框；
* ``diagrams.*`` **不吃 ax**（它们自己建整幅图，返回的就是画布上的 ax）；
* 五个渲染器都返回 ax，``ax.figure`` 直接交给 ``afg.save``。

用法::

    python examples/readme_diagram_examples.py             # 5 张 → examples/out/readme/
    python examples/readme_diagram_examples.py --out out/readme

脚本在导入 pyplot **之前** 固定 Agg 后端（服务器无显示环境时必须）。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # 必须在 pyplot 之前

import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))

import academic_fig as afg  # noqa: E402

DATA = ROOT / "data" / "diagrams"
NOTE = "数据来源：自绘示意；口径：模块仅表层级关系，非真实指标"


def _spec(name: str) -> dict:
    """读一个示例 spec（README 里用 ``json.load``，这里走统一路径）。"""
    return json.loads((DATA / f"{name}.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------- 五个示例
# 每个函数就是 README 里那段代码（可以逐字对照），返回 (标签, ax)。
def example_architecture():
    """README 示例 1：分层框架图（spec 顶层 ``layers``，层内元素是 ``nodes``）。"""
    spec = _spec("arch_layers")
    ax = afg.diagrams.architecture(spec, width="double", note=NOTE)
    return "fig01_architecture", ax


def example_flow():
    """README 示例 2：纵向流程图（``direction`` + ``nodes`` + ``edges``）。"""
    spec = _spec("flow_vertical")
    ax = afg.diagrams.flow(spec, note=NOTE)
    return "fig02_flow", ax


def example_field():
    """README 示例 3：响应面（``kind="surface3d"``，3D 曲面 + 等高线投影）。

    可选的 kind 只有 ``contourf / contour / both / surface3d / scatter``
    （``"surface"`` 不是合法值，会抛 ValueError 并列出全部合法值）。
    """
    spec = _spec("field_surface")
    ax = afg.diagrams.field(spec, kind="surface3d", note=NOTE)
    return "fig03_field_surface", ax


def example_geometry():
    """README 示例 4：几何与覆盖（``regions`` / ``circles`` / ``stations``）。"""
    spec = _spec("geometry_coverage")
    ax = afg.diagrams.geometry(spec, note=NOTE)
    return "fig04_geometry", ax


def example_gate():
    """README 示例 5：门限与权衡（``kind="pareto"``，帕累托前沿 + 判定线）。"""
    spec = _spec("gate_pareto")
    ax = afg.diagrams.gate(spec, note=NOTE)
    return "fig05_gate", ax


EXAMPLES = (example_architecture, example_flow, example_field,
            example_geometry, example_gate)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="跑通 README 里的示意图示例")
    parser.add_argument("--out", default=str(ROOT / "out" / "readme"),
                        help="产物目录（默认 examples/out/readme）")
    args = parser.parse_args(argv)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    if afg.diagrams is None:
        print("[!!] 本安装里没有 diagrams 模块，无法跑示意图示例", file=sys.stderr)
        return 1

    # 全局风格必须在画图之前套上（README 里第一行就是它）
    afg.apply_theme()

    written = 0
    for fn in EXAMPLES:
        stage, ax = fn()
        paths = afg.save(ax.figure, out_dir / stage)
        plt.close(ax.figure)
        written += len(afg.figure_paths(paths))
        print(f"[ok] {fn.__name__:<22} -> "
              + ", ".join(p.name for p in afg.figure_paths(paths).values()))
    print(f"共写出 {written} 个文件 → {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())