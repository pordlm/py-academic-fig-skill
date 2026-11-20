# 空间与连续场类图表规范 (prompts/30_cat_spatial.md)

> 适用：《图表词典》第11类：空间、地理、场量与连续标量/矢量场
> 与代码的对应：`academic_fig.diagrams.field`, `academic_fig.style`, `academic_fig.layout`, `academic_fig.palette`

---

## 0. 何时用这一篇

用：物理空间地理坐标映射、连续介质场（流场、温度场、应力场、高程曲面）或二维矢量方向分布（如等值线图、流线图、矢量场 Quiver）。
不用：若标量场仅为参数优化过程中的损失曲面示意图改用 40_diagram_field.md；若仅表达两特征变量的联合统计密度改用 30_cat_relation.md 的 Hexbin/2D 直方。
边界：连续场着色严禁使用非感知均匀的彩虹色图（如 jet/rainbow），必须使用单色渐变或感知均匀的发散色图；空间散点地图必须有比例尺或归一化坐标。

## 1. 成员图型清单

| 图型 | Matplotlib / 推荐 API | 颜色角色 | 唯一必须注意的点 |
|---|---|---|---|
| 空间散点地图 (Point Map) | 地理边界 + 空间散点 `ax.scatter()` | 散点 `INK`（alpha=0.6），高亮站点 `BLUE` | 必须标明比例尺（Scale bar）与指北针，标注地理投影坐标系 |
| 设色分级地图 (Choropleth) | 多边形面要素填色 `PolygonPatch` | 单色顺序色图 `afg.palette.cmap_seq()` | 分级方法在图注明确（分位数、自然断点法或等间距） |
| 空间热力图 (Spatial Heatmap) | 2D 核密度插值 + `ax.imshow()` | 连续渐变 `afg.palette.cmap_seq()` | 绝对禁止使用 `jet` 或 `rainbow`；右侧挂垂直标尺带单位 |
| 连续等高线/填色图 (Contour) | `ax.contour()` / `ax.contourf()` | 等值线 `INK`（0.6pt），填色阶梯渐变 | 轮廓线间距设置合理；核心峰值处标注等值线数值 |
| 矢量场箭头图 (Quiver Plot) | `ax.quiver(X, Y, U, V)` | 箭头统一使用墨黑 `INK` 或 `SLATE` | 必须在右下角或图例区给出参考向量基准长度图例 |
| 流线图 (Streamplot) | `ax.streamplot(x, y, u, v)` | 流线 `SLATE`（0.8pt），密度用线宽编码 | 避免流线过密形成死黑块；流向用微小箭头标明 |
| 3D 标量曲面图 (Surface) | `ax.plot_surface(X, Y, Z, cmap=...)` | 柔和单色渐变色板，光照关闭 | 视角高度仰角合理（如 `elev=30, azim=45`），避免大面积遮挡 |
| 三元相图 (Ternary Plot) | 等边三角形坐标系内三组分投点 | 轮廓三角形 `INK`（1.0pt），散点 `BLUE` | 三顶点组分按顺时针严格标注，各顶点刻度方向箭头指示 |

---

## 2. 本类专属风格塌陷点

1. **死守 Rainbow/Jet 毒彩虹色图**：在温度场、压力场中无脑使用红黄绿蓝彩虹渐变，导致无物理意义的人工伪阶梯（False boundaries）；必须强制使用感知均匀色图。
2. **矢量箭头图缺少参考基准长度**：画满整个画面的小箭头，却没有任何一条标明“箭头长度代表 10 m/s 还是 100 m/s”；必须在角落放置基准比例尺箭头。
3. **地理地图缺少物理比例尺与坐标基准**：只截取地图局部，没有经纬网、比例尺或指北针，变成无地理参考的示意涂鸦；必须补全必要空间地理要素。
4. **3D 曲面图视角不当导致背部死角**：仰角过低或角度选择不当，使得前方的假山波峰把后方全部关键低谷遮挡得干干净净；优先改用 2D 填色等高线俯视图。

---

## 3. 通用规范引用

- 色值与语义：严格遵守 `20_palette_typography.md`。
- 线宽规范：等值线 `0.6pt`，矢量箭头与流线 `0.8pt`，边界墨线 `1.0pt`。
- 坐标轴：带物理坐标的空间场保留刻度；地理地图添加经纬度刻度。

---

## 4. 核心代码骨架（连续场等值线填色与流线复合图，<=20 行）

```python
import academic_fig as afg
import numpy as np

afg.apply_theme()
fig, ax = afg.paper_fig("single", nrows=1)

y, x = np.mgrid[-2:2:100j, -2:2:100j]
u = -1 - x**2 + y; v = 1 + x - y**2
speed = np.sqrt(u**2 + v**2)

cf = ax.contourf(x, y, speed, levels=8, cmap=afg.palette.cmap_seq(), alpha=0.85)
ax.streamplot(x, y, u, v, color=afg.palette.INK, density=0.8, linewidth=0.7, arrowsize=0.8)

cbar = fig.colorbar(cf, ax=ax, fraction=0.046, pad=0.04)
cbar.set_label("流速标量 / (m/s)", fontsize=9); cbar.outline.set_linewidth(0.8)
afg.panel(ax, xlabel="横向空间坐标 x / m", ylabel="纵向空间坐标 y / m", title="流动速度场与流线轨迹分布")
afg.footnote(fig, "填色阶梯表示合速度大小；黑色流线指示局部速度矢量流向。")
afg.save(fig, "out/fig_cat_spatial")
```

---

## 5. 自检要点

- [ ] 场量连续填色是否避开了 Rainbow/Jet 伪彩，采用统一规范色图？
- [ ] 标尺（Colorbar）是否清晰标注了物理量与国际单位制？
- [ ] 矢量图元是否配备了清晰的参考基准指示？
