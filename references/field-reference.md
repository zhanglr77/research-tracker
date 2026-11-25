# 字段参考

所有笔记都是 Markdown 文件，开头用两行 `---` 夹住 frontmatter。frontmatter 是 YAML 的一个子集（见末尾"支持的写法"）。

日期格式：`2026-11-25`；需要时间时写 `"2026-11-25 14:30"`（带引号）。一律用你所在时区的本地时间。

## tracker.yaml（可选）

| 字段 | 默认 | 含义 |
|---|---|---|
| `title` | 科研看板 | 页面标题 |
| `lines` | `[课题]` | 研究线分组；每个课题的 `line` 必须是其中一项 |
| `stale_days` | 90 | 进行中的课题最后记录超过这么多天就提醒 |
| `min_runs` | `{}` | 某种实验至少记几次，如 `{实机: 3}` |
| `result_words` | 成功、失败、部分、无效、完成 | 逐次记录里允许的结果词 |
| `checks_off` | `[]` | 关闭的检查代码 |
| `today` | 今天 | 用来固定"今天"，演示或复现时用 |

## projects/*.md

| 字段 | 必填 | 允许值 / 格式 |
|---|---|---|
| `id` | 是 | 字母、数字、下划线、短横线，以字母或数字开头；全局唯一 |
| `name` | 是 | 文字 |
| `line` | 是 | 必须在 `lines` 里 |
| `status` | 是 | 进行中、待推进、搁置、无近期记录 |
| `status_basis` | 是 | 判断状态的依据，没有记录就写「没有记录」 |
| `updated` | 是 | 日期 |
| `question` | 是 | 要回答的问题 |
| `stages` | 是 | 非空列表，每项 `{n: 阶段名, s: done/doing/blocked/todo/unk, note: 说明}` |
| `facts` | 否 | 列表，每项 `{ev: 证据等级, t: 内容}` |
| `blockers` `next` `retracted` `sources` `related` | 否 | 文字列表；`related` 里是其他课题的 id |
| `links` | 否 | 列表，每项 `{label, path}`；本地路径相对于研究目录，或写 `https://` 网址 |
| `deadline` | 否 | `{date: 2026-12-01, what: 说明}` |
| `kind` | 否 | 核心问题、子课题、想法分支。默认：有 `parent` 时是子课题，否则是核心问题 |
| `parent` | 否 | 父课题的 id，表示这个课题是从它分出来的。核心问题不能有 `parent`；不能指向自己，不能成环 |
| `origin` | 建议 | 在哪次讨论、因为什么分出来的。有 `parent` 却没写会被提示 |
| `ideas` | 否 | 讨论中冒出的想法，每项 `{t: 内容, status: 待评估/已开课题/暂不做/放弃, why: 理由, date: 日期, to: 开成的课题 id}`。`已开课题` 必须写 `to` |

证据等级：有数据、仿真、推断、未验证、决定、记录、想法。

## hypotheses/*.md

| 字段 | 必填 | 含义 |
|---|---|---|
| `id` | 是 | 唯一 |
| `project` | 是 | 课题 id |
| `statement` | 是 | 假设的陈述 |
| `status` | 是 | 待检验、支持、部分、反对、推翻 |
| `updated` | 是 | 日期 |
| `converse` | 建议 | 反面：看到什么就不成立。**空着会被标出** |
| `criterion` | 建议 | 判据：口径和阈值 |
| `result` | 否 | 一句话结论 |

## experiments/*.md

frontmatter：

| 字段 | 必填 | 含义 |
|---|---|---|
| `id` `date` `title` `project` `kind` `status` | 是 | `status`：计划中、进行中、已完成、作废；`kind` 是你自己的分类，如 离线、实机 |
| `predicted_at` | 建议 | 写下预测的时间 |
| `started_at` | 建议 | 实际开跑的时间；`predicted_at` 晚于它会被标红 |
| `tests` | 否 | 检验的假设 id 列表 |
| `control` | 否 | 对照实验的 id |
| `setting` `subject` `task` | 否 | 设置简称、被测对象、任务或数据集 |
| `evidence` | 否 | 证据等级 |
| `backfilled` | 否 | 日期；事后补记的旧记录加这一项，看板单独标出 |

正文章节（用二级标题 `##`，名字要对得上）：

- `## 目的与预测`：三行 `- 要回答的问题：`、`- 预测（跑之前写）：`、`- 判否条件（……）：`、`- 对照条目（id）：`。预测和判否条件为空、写"待补/无/没有"都算没写。
- `## 配置指纹`：一张两列表格（项 / 值）。值写"待补"的会被统计。
- `## 逐次记录`：表格，第 2 列是结果词。
- `## 结果` `## 判定` `## 审查`：自由文字。**已完成的实验这三节缺了会被标出。**

## errors/*.md

必填：`id` `date` `what`（错在哪）`found_by`（怎么发现）`fix`（怎么处理）；可选 `affects`（被影响的课题/假设/实验 id 列表）。

## 纪律检查代码

| 代码 | 级别 | 含义 |
|---|---|---|
| no-prediction | 警告 | 实验没有预测（回填的不报） |
| no-predicted-at | 提示 | 写了预测但没写 `predicted_at` |
| late-prediction | 警告 | 预测晚于开跑 |
| prediction-changed | 警告 | 预测文字和首次登记时不同 |
| no-falsifier | 警告 | 有预测没有判否条件 |
| no-converse | 警告 | 假设没有反面 |
| no-criterion | 提示 | 假设没有判据 |
| no-review | 警告 | 已完成但没有审查 |
| no-verdict | 警告 | 已完成但没有判定 |
| few-runs | 警告 | 次数少于 `min_runs` |
| stale-project | 警告 | 进行中的课题久无记录 |
| hyp-no-experiment | 警告 | 假设已下结论但没有实验指向它 |
| link-missing | 警告 | 链接指向的本地文件不存在 |
| backfilled | 提示 | 回填记录 |
| config-tbd | 提示 | 配置指纹有待补项 |
| skipped-note | 提示 | 没有 frontmatter 的文件被跳过 |
| orphan-subtopic | 警告 | kind 是子课题或想法分支，但没有 `parent` |
| no-origin | 提示 | 有 `parent` 但没写 `origin` |
| stale-idea | 提示 | 想法“待评估”超过 `stale_days` 天 |

结果词不在 `result_words` 里、字段缺失、日期格式错、引用了不存在的 id、`parent` 指向自己或成环，这些是**构建错误**，必须改了才能生成。

## 支持的 YAML 写法

块映射；块列表（元素可以是文字、`{a: b}` 流式映射，或 `- key: value` 开头的块映射）；`[a, b]` 流式列表；双引号和单引号字符串；`|` 和 `>` 块文字；`#` 注释；true/false/null/整数/小数。日期不会被转换，保持文字。

不支持（会报错并给出行号，不会静默读错）：锚点 `&x` 和引用 `*x`、标签 `!!x`、多文档、多行的 `[ ]` 或 `{ }`、制表符缩进。

常见坑：
- 值里有冒号加空格（`a: b`）或以 `#`、`[`、`{`、`-` 开头，要加引号。
- Windows 路径用单引号，或在双引号里把反斜杠写两个。
- 中文引号 `“ ”` 不是 YAML 的引号，不能用来包裹值。
