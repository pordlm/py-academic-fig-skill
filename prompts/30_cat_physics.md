# 物理、化学与材料科学类图表规范 (prompts/30_cat_physics.md)

> 适用：《图表词典》第12类：实验物理、化学合成与材料表征
> 与代码的对应：`academic_fig.style`, `academic_fig.layout`, `academic_fig.palette`

---

## 0. 何时用这一篇

用：物理、化学、材料学科的标准实验测量曲线与物理表征谱图（如光谱/质谱、XRD 衍射谱、电化学 I-V/C-V、阻抗 Nyquist、应力-应变）。
不用：若为纯时序过程信号连续记录改用 30_cat_trend.md；若关注断裂应力等单点材料性能横向比大小改用 30_cat_compare.md。
边界：多谱线沿垂直方向堆叠排布时必须保持相同物理量纲与刻度比例，仅允许添加固定常数垂直偏置，且图注必须声明偏置数值以防误读。

## 1. 成员图型清单

| 图型 | Matplotlib / 推荐 API | 颜色角色 | 唯一必须注意的点 |
|---|---|---|---|
| 光谱/质谱族 (Spectra) | `ax.plot()` 垂直等距常数偏移叠加 | 各测试条件曲线用深灰/蓝/红棕区分 | 谱峰关键峰位（如波数、m/z）垂直小虚线标出数值 |
| X射线衍射图 (XRD Pattern) | 谱线叠加 + 底部标准卡片条形码棒图 | 样品谱 `BLUE`/`INK`（1.2pt），标准卡条形 `GREY` | 横轴必须标注 $2\theta$ / (°)；标出特征晶面指数 (hkl) |
| 电化学 I-V / C-V 曲线 | `ax.plot()` 循环闭合回路 | 正反向扫速曲线用低饱和色，基准线 `GREY` | 标明扫速（如 $50\ \text{mV/s}$）与电解液环境及参比电极 |
| 阻抗奈奎斯特图 (Nyquist) | `ax.scatter()` + `ax.plot()` | 实验点 `INK`（空心圈），拟合等效电路 `CLAY` | 横纵轴比例必须严格 1:1（`ax.set_aspect('equal')`）；纵轴通常为 $-Z''$ |
| 伯德图 (Bode Plot) | 双联上下对齐子图（幅频 + 相频特性） | 幅频 `BLUE`，相频 `CLAY`（1.2pt） | 横轴必须对数尺度（Log10）；标明相位裕度与截止频率 |
| 应力-应变曲线 (Stress-Strain) | `ax.plot()` + 屈服点切线 | 试验曲线 `BLUE`（1.5pt），弹性斜率切线 `GREY` | 明确标注屈服强度（Yield）、抗拉强度（UTS）与断裂延伸率 |
| 磁滞回线 (Hysteresis Loop) | 闭合中心对称曲线 `ax.plot()` | 材料曲线 `BLUE`（1.2pt），坐标零十字基线 | 标示饱和磁化强度 $M_s$、剩磁 $M_r$ 与矫顽力 $H_c$ |
| 阿伦尼乌斯图 (Arrhenius) | 倒数横轴 $\ln(k)$ vs $1000/T$ | 拟合直线 `CLAY`（1.5pt），实验测量点 `INK` | 标出活化能 $E_a$ 数值及其拟合优度 $R^2$ |

---

## 2. 本类专属风格塌陷点

1. **Nyquist 图横纵轴未设 1:1 等比例**：实部 $Z'$ 与虚部 $-Z''$ 物理量纲相同，若横纵坐标拉伸不成比例，半圆会被压成扁平椭圆，造成极化阻抗视觉误判；必须强制 `ax.set_aspect('equal')`。
2. **多谱图堆叠基线杂乱**：将 5~10 条 XRD 或光谱曲线放在同一图内，彼此相互交叉打架，无法辨识；必须使用恒定垂直偏置（Vertical offset）将其平滑瀑布式错开。
3. **物理量符号与单位书写不规范**：写出如 `Temperature (C)` 或 `current/mA` 等不合出版规范的格式；必须严格遵从标准化写法：`物理量符号 / 单位`（如 $T$ / K, $I$ / mA, $2\theta$ / (°)）。
4. **循环伏安图未注扫描方向**：闭合回路上没有任何指示箭头，读者完全无法辨识氧化还原峰对应的正反向扫描历程；必须在曲线上附带细小箭头标明电压扫描方向。

---

## 3. 通用规范引用

- 色值与语义：严格遵守 `20_palette_typography.md`。
- 线宽与标记：主测试谱线 `1.2pt`，理论/等效拟合线 `1.0pt`，标准峰位辅助线 `0.8pt` 虚线。
- 坐标轴细框：四边封闭，刻度朝内 `3.5pt`。

---

## 4. 核心代码骨架（材料 X 射线衍射 XRD 谱图，<=20 行）

```python
import academic_fig as afg
import numpy as np

afg.apply_theme()
fig, ax = afg.paper_fig("single", nrows=1)

two_theta = np.linspace(10, 80, 500)
p1 = np.exp(-((two_theta - 28.4)**2)/1.2) * 80 + np.exp(-((two_theta - 47.3)**2)/1.5) * 40 + np.random.normal(5, 1, 500)
p2 = p1 * 0.8 + 60

ax.plot(two_theta, p2, color=afg.palette.BLUE, lw=1.2, label="Sample-400 °C")
ax.plot(two_theta, p1, color=afg.palette.SLATE, lw=1.0, label="Pristine Sample")
ax.text(28.4, 155, "(111)", ha="center", fontsize=8.5, color=afg.palette.INK)

ax.set_yticks([]); ax.legend(frameon=False, fontsize=9, loc="upper right")
afg.panel(ax, xlabel="衍射角 2θ / (°)", ylabel="衍射强度 / a.u.", title="样品高温退火 XRD 衍射谱")
afg.footnote(fig, "谱线经垂直偏置以便对比；(111) 标示为主晶相特征衍射峰。")
afg.save(fig, "out/fig_cat_physics")
```

---

## 5. 自检要点

- [ ] 物理量符号与单位是否严格按照“物理量 / 单位”标准书写？
- [ ] 阻抗奈奎斯特图等物理量等比例图是否严格执行 `aspect='equal'`？
- [ ] 堆叠谱线间距是否规整、特征峰标示清晰？
