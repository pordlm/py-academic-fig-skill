"""图 6：双栏三层方法框架图（输入层 3 框 / 方法层 4 框 / 输出层 2 框，核心模块高亮）。

框架为**示意结构**（自拟的方法流程），不涉及真实实验数据。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib
matplotlib.use("Agg")

import academic_fig as afg

OUT = Path(__file__).resolve().parent / "out" / "blind"

spec = {
    "title": "本文方法的三层框架",
    "auto_cols": True,
    "layers": [
        {
            "name": "输入层",
            "note": "多源观测",
            "nodes": [
                {"label": "传感器序列", "note": "10 Hz 原始采样"},
                {"label": "历史轨迹", "note": "近 5 s 位置"},
                {"label": "先验地图", "note": "路网与限速"},
            ],
        },
        {
            "name": "方法层",
            "note": "本文贡献",
            "nodes": [
                {"label": "特征编码", "note": "共享骨干"},
                {"label": "时空融合", "note": "跨模态注意力"},
                {"label": "自适应门控", "note": "核心模块", "highlight": True},
                {"label": "一致性校验", "note": "物理约束"},
            ],
        },
        {
            "name": "输出层",
            "note": "",
            "nodes": [
                {"label": "轨迹预测", "note": "未来 3 s"},
                {"label": "不确定度", "note": "95% 区间"},
            ],
        },
    ],
    "links": [
        {"from": "传感器序列", "to": "特征编码"},
        {"from": "历史轨迹", "to": "特征编码"},
        {"from": "先验地图", "to": "一致性校验"},
        {"from": "特征编码", "to": "时空融合"},
        {"from": "时空融合", "to": "自适应门控"},
        {"from": "自适应门控", "to": "一致性校验"},
        {"from": "自适应门控", "to": "轨迹预测"},
        {"from": "一致性校验", "to": "不确定度"},
        {"from": "不确定度", "to": "自适应门控", "kind": "return"},
    ],
    "highlight": ["自适应门控"],
}

afg.apply_theme()
ax = afg.diagrams.architecture(
    spec,
    width="double",
    note="示意结构：框的大小与位置只表示数据流向，不代表计算量或参数量；蓝色填充为本文的核心模块，虚线为闭环反馈。",
)
afg.save(ax.figure, OUT / "fig06_architecture")
print("done")
