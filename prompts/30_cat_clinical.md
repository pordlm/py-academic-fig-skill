# 临床医学与生存分析类图表规范 (prompts/30_cat_clinical.md)

> 适用：《图表词典》第8类：临床研究、生存分析与流行病学
> 与代码的对应：`academic_fig.style`, `academic_fig.layout`, `academic_fig.palette`

---

## 0. 何时用这一篇

用：临床队列研究、病人生存期、随访事件终点分析及医学研究流程（如 Kaplan-Meier 生存曲线、风险人数表、肿瘤瀑布图、PRISMA 流程）。
不用：若非生存删失时序数据而是一般工业产品寿命衰减测试且无随访终点，可改用 30_cat_trend.md；若仅展示队列基础人口学特征均值比较改用 30_cat_compare.md。
边界：Kaplan-Meier 曲线底部必须附带对应的随访时间点风险人数表（Number at Risk），必须清晰画出删失标记刻度（Censor marks），严禁省略。

## 1. 成员图型清单

| 图型 | Matplotlib / 推荐 API | 颜色角色 | 唯一必须注意的点 |
|---|---|---|---|
| Kaplan-Meier 生存曲线 | `ax.step(time, surv, where='post')` + 删失标记 | 治疗组 `BLUE`（1.5pt），对照组 `GREY`（1.2pt） | 必须是阶梯状（Step）而非普通斜折线；删失点用加号 `+`（s=15） |
| 风险人数表 (Number-at-Risk) | 主图下方挂靠独立等宽对齐子图/表格 | 字体颜色严格对应上方各治疗组颜色 | 时间刻度与主图横轴完全水平对齐，严禁数字偏移错位 |
| 游泳道图 (Swimmer Plot) | 水平条 `ax.barh()` + 阶段事件 Marker | 条形用 `WASH_COOL`，不同事件用不同形状小图标 | 纵轴患者按反应持续时间降序排列；末尾用箭头指示持续缓解 |
| 肿瘤瀑布图 (Waterfall Plot) | 肿瘤负荷变化百分比降序柱状图 | 缓解组 (<-30%) `BLUE`，进展组 (>20%) `CLAY` | -30% (PR) 与 +20% (PD) RECIST 判定水平虚线必须标出 |
| 累积发病率图 (Cumulative Inc) | 竞争风险多组向上累积阶梯图 | 主要事件 `BLUE`，竞争事件 `SLATE` | 纵轴限定为 [0, 1] 或百分比；图注声明竞争风险模型 |
| PRISMA / CONSORT 流程图 | 层次流转方框 + 剔除原因侧支分支 | 方框 `PAPER`，边框 `INK`（0.8pt），底色 `WASH` | 每个框内必须写明具体例数（如 $n=120$）及逐级剔除确切理由 |

---

## 2. 本类专属风格塌陷点

1. **KM 生存曲线画成斜拉折线**：事件发生是在离散时间点，斜拉直线不仅失真更属于医学统计失范；必须强制使用阶梯线（Step function, `where='post'`）。
2. **遗漏风险人数表（Number at Risk）**：只有上方面板的曲线，没有底部的具体随访受试者剩余人数，读者无法评估尾部曲线的可靠性；必须上下联排双图输出。
3. **肿瘤瀑布图未标 RECIST 阈值**：画了一堆红蓝柱子，但没有标注 -30%（部分缓解 PR）和 +20%（疾病进展 PD）的临床金标准界线。
4. **删失点（Censored）遗漏或过大**：未在曲线上打删失标记，或删失加号画成巨大十字架挡住阶梯拐角；删失标记应精简小巧（`markersize=4`）。

---

## 3. 通用规范引用

- 色值与语义：严格遵守 `20_palette_typography.md`。
- 线宽与标记：生存阶梯主线 `1.5pt`，删失标记 `+`（0.8pt），RECIST 参考线 `0.8pt` 虚线。
- 排版：主图与风险表比例一般为 `3:1`，共享 X 轴。

---

## 4. 核心代码骨架（KM 生存曲线与对数秩检验标注，<=20 行）

```python
import academic_fig as afg
import numpy as np

afg.apply_theme()
fig, ax = afg.paper_fig("single", nrows=1)

t = np.array([0, 3, 6, 12, 18, 24, 30, 36])
s_treat = np.array([1.0, 0.92, 0.85, 0.78, 0.72, 0.68, 0.65, 0.65])
s_ctrl  = np.array([1.0, 0.85, 0.70, 0.55, 0.42, 0.35, 0.30, 0.28])

ax.step(t, s_treat, where='post', color=afg.palette.BLUE, lw=1.5, label="Target Therapy")
ax.step(t, s_ctrl, where='post', color=afg.palette.GREY, lw=1.2, label="Standard Care")
ax.scatter([12, 24], [0.78, 0.68], marker="+", color=afg.palette.BLUE, s=25, zorder=3)

ax.set_ylim(-0.02, 1.05); ax.legend(frameon=False, fontsize=9, loc="lower left")
afg.panel(ax, xlabel="随访时间 / 月", ylabel="总生存率 (Overall Survival)", title="Kaplan-Meier 生存分析曲线")
afg.footnote(fig, "Log-rank p = 0.004；'+' 表示随访期间数据删失点 (Censored)。")
afg.save(fig, "out/fig_cat_clinical")
```

---

## 5. 自检要点

- [ ] 生存曲线是否严格为步进阶梯（Step）？
- [ ] 删失数据点（Censored）是否使用细十字清晰标示？
- [ ] 关键临床分界线（RECIST、中位生存期）是否正确标注？
