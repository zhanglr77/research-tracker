# research-tracker

把科研写成**课题、假设、实验、错误**四类笔记，一条命令生成一页离线可开的 HTML 看板。看板除了显示进度，还会**检查纪律**：哪个实验没有事前预测、预测写得比开跑晚、假设没有反面、已完成的实验没有审查。

## 30 秒看效果

```bash
python3 scripts/init.py ~/my-research --demo      # 放入一组虚构的示例笔记
python3 scripts/build.py ~/my-research            # 生成 ~/my-research/看板.html
open ~/my-research/看板.html                       # macOS；其他系统直接双击
```

需要：Python 3.9 或更高版本（在 3.9 和 3.14 上跑过全部自带测试；语法层面按 3.8 检查过，但没有在 3.8 上实际运行）。**不需要安装任何包**，不联网。

## 开始用自己的

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

每次改完笔记，重新运行 `build.py`。

## 作为 Claude Code 的 skill 使用

把整个 `research-tracker/` 文件夹放到 `~/.claude/skills/` 下，之后对 Claude 说"梳理我的科研""给我做科研看板""检查我的实验有没有事前预测"即可。`SKILL.md` 告诉 Claude 怎么做。

## 它检查什么

16 项检查，详见 `references/field-reference.md`。最重要的几项：

- 无事前预测、预测晚于开跑、预测在登记后被改动、有预测没有判否条件
- 假设没有反面或判据
- 已完成的实验没有判定或审查
- 假设已下结论，但没有任何实验指向它
- 课题久无记录

**警告不是处罚。** 它告诉你哪些结论目前还不能当结论。某一项不想要，在 `tracker.yaml` 的 `checks_off` 里关掉。

## 它不做什么

- 不替你做科研，也不判断科研对不对。它检查的是**记录的纪律**，不是**科学的正确性**。
- 不防篡改。时间戳靠自觉，`.tracker-lock.json` 能发现无意中改了预测，防不住有意作假。需要的话把目录放进 git。
- 不联网，不上传任何东西。生成的 `看板.html` 是单个自包含文件，可以直接发给别人。

## 目录

```
research-tracker/
  SKILL.md                 给 Claude 的指令
  scripts/                 init.py build.py check.py（只用标准库）
  assets/templates/        四种笔记模板
  assets/web/              看板的样式和脚本
  references/              方法来由、字段参考、迁移指南
  examples/demo/           虚构的示例笔记
  tests/run_tests.py       自带测试
```

## 许可

MIT。见 `LICENSE`。
