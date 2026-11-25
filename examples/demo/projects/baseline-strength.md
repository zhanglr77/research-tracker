---
id: baseline-strength
name: "基线是否太弱"
short: "基线强度"
line: 主线课题
kind: 子课题
parent: denoise
status: 搁置
status_basis: "E5 显示加宽网络误差只降 2%，暂时认为容量不是瓶颈；经典方法基线还没做。"
updated: 2026-03-19
question: "换成更强的基线（加宽网络、经典 BM3D），先验的收益还在吗？"
stages:
  - {n: "网络宽度加倍", s: done, note: "E5：只降 2%。"}
  - {n: "经典 BM3D 基线", s: todo, note: ""}
facts:
  - {ev: "有数据", t: "宽度加倍后误差 0.080，基线 0.082，只降 2%（但预测写晚了，见 E5）。"}
blockers: []
next:
  - "补 BM3D 基线。"
retracted: []
ideas: []
sources: ["experiments/E5-late.md"]
links: []
related: []
---

# 基线是否太弱

示例：一个没写 origin 的子课题，纪律检查会提示。
