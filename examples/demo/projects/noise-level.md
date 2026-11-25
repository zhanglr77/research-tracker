---
id: noise-level
name: "先验的收益是否随噪声强度变化"
short: "噪声强度"
line: 主线课题
kind: 子课题
parent: denoise
origin: "2026-03-16 讨论 E3 结果时，agent 注意到低噪声组没有收益，提出收益可能只在高噪声下存在。"
status: 进行中
status_basis: "E4 计划中，预测已写（2026-03-19）。"
updated: 2026-03-19
question: "平滑先验带来的误差下降，在 σ=10、25、50 三个噪声强度下是否不同？"
stages:
  - {n: "把 E3 按噪声强度分组重看", s: done, note: "低噪声几乎没有收益。"}
  - {n: "三个噪声强度各跑 5 个种子", s: doing, note: "E4 计划中。"}
  - {n: "换噪声类型复核", s: todo, note: ""}
facts:
  - {ev: "推断", t: "E3 里低噪声组的收益接近 0，但每组只有 30 张测试图，区间很宽。"}
blockers: []
next:
  - "跑 E4，先写预测。"
retracted: []
ideas:
  - {t: "收益和信噪比成正比，可以写成一条曲线", status: 待评估, why: "如果三个点单调，值得拟合", date: 2026-03-19}
  - {t: "低噪声时先验反而有害", status: 已开课题, to: low-noise-harm, why: "E3 里 σ=10 组的误差略高于基线", date: 2026-03-19}
sources: ["E3 分组结果", "hypotheses/H2.md"]
links: []
related: []
---

# 先验的收益是否随噪声强度变化

示例：一个从核心问题分出来的子课题。
