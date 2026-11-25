# research-tracker

**让 AI agent 做科研时，进度看得见，思路看得见，结论信得过。**

当你让 Claude Code 之类的 agent 帮你做研究：提出假设、设计实验、跑结果、改结论，几十轮对话之后，你会遇到三个问题：

- **进度散在对话里。** 做过什么、现在卡在哪、下一步是什么，要翻聊天记录才知道。
- **思路是一团。** agent 头脑风暴出的假设、被推翻的想法、悄悄改过的结论，没有结构，没法一眼看清"我们到底在验证什么"。
- **agent 很会事后解释。** 实验跑完才"其实我预期就是这样"，数字算错了悄悄改掉，说得越流畅越难发现。

research-tracker 是一个 Claude Code skill，解决这三个问题：

1. **让 agent 把研究写成结构化笔记**：课题、假设、实验、错误登记，每一类有固定模板。
2. **一条命令生成一页看板**：进度、假设台账、实验对比，可视化成一个离线可打开的 HTML 文件。
3. **看板会检查纪律**：哪个实验没有事前预测、预测写得比开跑晚、假设没有反面、已完成的实验没有审查。agent 违反方法的地方会被标出来。

![总览：课题卡、阶段进度条、纪律警告数](docs/images/overview.png)

## 它把 agent 的头脑风暴变成什么

agent 提出的每个想法，会落成三个有固定位置的东西，而不是散在对话里：

| agent 说的话 | 落成什么 | 看板上看到什么 |
|---|---|---|
| "我猜 X 有帮助" | **假设**，必须同时写反面："如果看到什么，X 就不成立" | 假设台账：陈述、反面、判据、状态、哪些实验在检验它 |
| "我来试一下" | **实验**，开跑**之前**写预测和判否条件 | 实验记录：预测、配置、结果，可勾选多条并排对比，不同的配置项高亮 |
| "之前那个数字算错了" | **错误登记**：错在哪、怎么发现、怎么处理 | 错误页，并挂在被影响的实验和假设旁边 |

没写反面的假设、没有实验支持却下了结论的假设，会在台账里直接标出来：

![假设台账：每条假设的反面和对应实验，缺失处被标出](docs/images/hypotheses.png)

## 它检查什么

16 项检查，覆盖这套方法的六条纪律（预测先写、假设带反面、对照口径一致、错误公开登记、证据分级、不凭印象）。最重要的几项：

- 实验没有**事前预测**，或预测的时间晚于开跑
- 预测在登记之后被**改动**
- 有预测但没有**判否条件**（什么结果会推翻它）
- 假设没有**反面**
- 已完成的实验没有**判定**或**审查**
- 假设已下结论，但没有任何实验指向它
- 课题久无记录，状态已经没有依据

![纪律检查页：每条警告指向具体文件](docs/images/discipline-check.png)

**警告不是处罚，是告诉你哪些结论目前还不能当结论。** 某一项不想要，在 `tracker.yaml` 的 `checks_off` 里关掉。

## 30 秒看效果

```bash
git clone https://github.com/zhanglr77/research-tracker.git
cd research-tracker
python3 scripts/init.py ~/my-research --demo      # 放入一组虚构的示例笔记
python3 scripts/build.py ~/my-research            # 生成 ~/my-research/看板.html
open ~/my-research/看板.html                       # macOS；其他系统直接双击打开
```

需要 Python 3.9 或更高版本（在 3.9 和 3.14 上跑过全部自带测试）。**不需要安装任何包，不联网。** 生成的 `看板.html` 是单个自包含文件，可以直接发给别人。

## 用在自己的研究上

### 作为 Claude Code 的 skill

把整个文件夹放到 `~/.claude/skills/research-tracker/`：

```bash
git clone https://github.com/zhanglr77/research-tracker.git ~/.claude/skills/research-tracker
```

之后对 Claude 说：

- "给我的研究做一个科研看板"
- "把这些实验日志整理成课题、假设和实验"
- "检查我的实验有没有事前预测"
- "我要开始一个新实验，先帮我把预测和判否条件写下来"

`SKILL.md` 告诉 Claude 怎么做：先读你的材料再拆成笔记，**不替你补没写过的预测**，回填的旧记录单独标出。

### 手动使用

```bash
python3 scripts/init.py ~/my-research --name "我的研究"
```

然后把 `assets/templates/` 里的四个模板复制到对应目录填写：

| 模板 | 放到 | 写什么 |
|---|---|---|
| `project.md` | `projects/` | 一个要回答的问题，几个阶段，卡点和下一步 |
| `hypothesis.md` | `hypotheses/` | 一条假设和它的**反面** |
| `experiment.md` | `experiments/` | **开跑之前**写预测和判否条件，跑完追加结果和审查 |
| `error.md` | `errors/` | 自己发现并改掉的错误 |

每次改完笔记，重新运行 `build.py`。笔记写错时，构建会一次列出全部问题（带文件名），不生成页面。

## 它不做什么

- **不替你做科研，也不判断科研对不对。** 它检查的是**记录的纪律**，不是**科学的正确性**。守全了所有纪律的研究，仍然可能是错的。
- **不防篡改。** 时间戳靠自觉；`.tracker-lock.json` 能发现无意中改了预测，防不住有意作假。需要的话把研究目录放进 git，并在开跑前提交一次。
- **不联网，不上传。** 没有遥测，没有外部请求。

## 方法来由

为什么是这六条纪律，每一条对应什么真实的失败，见 [`references/methodology.md`](references/methodology.md)。字段含义和 16 项检查的代码见 [`references/field-reference.md`](references/field-reference.md)。把已有的日志和聊天记录迁进来的做法见 [`references/porting.md`](references/porting.md)。

## 仓库结构

```
research-tracker/
  SKILL.md                 给 Claude 的指令
  scripts/                 init.py build.py check.py（只用标准库）
  assets/templates/        四种笔记模板
  assets/web/              看板的样式和脚本
  references/              方法来由、字段参考、迁移指南
  examples/demo/           虚构的示例笔记（故意触发每一类检查）
  tests/run_tests.py       自带测试：124 项，含无头浏览器交互和注入攻击样例
  docs/images/             README 里的截图
```

运行测试：`python3 tests/run_tests.py`（找不到 Chrome/Chromium 时，浏览器相关的一组会跳过并说明）。

## 许可

[MIT](LICENSE)
