#!/usr/bin/env python3
"""初始化研究追踪目录：创建 projects/ hypotheses/ experiments/ errors/ _归档/ 和 tracker.yaml。

用法：python3 init.py <目录> [--name 看板标题] [--demo] [--force]
  --demo   同时放入一组虚构的示例笔记（用来看看板长什么样，用完删掉 projects/ 等目录里的示例文件即可）
  --force  目录里已有 tracker.yaml 或笔记时也继续（只补缺的，不覆盖已有文件）
不会覆盖任何已存在的文件。
"""
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
SUBDIRS = ['projects', 'hypotheses', 'experiments', 'errors', '_归档']

CONFIG = """# 研究追踪设置。所有项都可以删掉，用默认值。
title: {title}
# 研究线分组：每个课题的 line 必须是这里的一项。
lines: [课题]
# 状态是「进行中」的课题，最后记录超过这么多天就在纪律检查里提醒。
stale_days: 90
# 某种实验至少要记几次，例如 {{实机: 3, 离线: 1}}。没写的种类不检查次数。
min_runs: {{}}
# 逐次记录里允许的结果词。
result_words: [成功, 失败, 部分, 无效, 完成]
# 不想要的检查，写代码进来，例如 [config-tbd]。代码见 SKILL.md 的「校验与警告」。
checks_off: []
# today: 2026-11-25   # 一般不需要写，默认用今天的日期
"""


def main(argv):
    args = argv[1:]
    title, demo, force, rest = '科研看板', False, False, []
    i = 0
    while i < len(args):
        a = args[i]
        if a == '--name' and i + 1 < len(args):
            title = args[i + 1]; i += 2
        elif a == '--demo':
            demo = True; i += 1
        elif a == '--force':
            force = True; i += 1
        else:
            rest.append(a); i += 1
    if len(rest) != 1:
        print('用法：python3 init.py <目录> [--name 看板标题] [--demo] [--force]')
        return 2
    root = os.path.abspath(os.path.expanduser(rest[0]))
    if os.path.isdir(root) and os.listdir(root) and not force and not os.path.isfile(os.path.join(root, 'tracker.yaml')):
        # 非空目录里没有 tracker.yaml：可能是用户误指了别的目录
        names = [n for n in os.listdir(root) if not n.startswith('.')]
        if names:
            print('目录 %s 不是空的，里面有：%s' % (root, '、'.join(names[:6]) + ('……' if len(names) > 6 else '')))
            print('如果确实要在这里初始化，加 --force（只补缺的文件，不覆盖已有内容）。')
            return 1
    os.makedirs(root, exist_ok=True)
    made = []
    for d in SUBDIRS:
        p = os.path.join(root, d)
        if not os.path.isdir(p):
            os.makedirs(p); made.append(d + '/')
    cfg = os.path.join(root, 'tracker.yaml')
    if not os.path.exists(cfg):
        import miniyaml as MY
        with open(cfg, 'w', encoding='utf-8') as f:
            f.write(CONFIG.format(title=MY.dump_scalar(title)))
        made.append('tracker.yaml')
    if demo:
        src = os.path.join(SKILL, 'examples', 'demo')
        for sub in ['projects', 'hypotheses', 'experiments', 'errors']:
            for name in sorted(os.listdir(os.path.join(src, sub))):
                dst = os.path.join(root, sub, name)
                if not os.path.exists(dst):
                    shutil.copyfile(os.path.join(src, sub, name), dst); made.append('%s/%s' % (sub, name))
        # 示例配置覆盖默认配置（只在我们刚创建的 tracker.yaml 上），让示例的 lines 和 min_runs 生效
        demo_cfg = os.path.join(src, 'tracker.yaml')
        if 'tracker.yaml' in made:
            shutil.copyfile(demo_cfg, cfg)
    print('已初始化 %s' % root)
    for m in made:
        print('  + ' + m)
    if not made:
        print('  （没有需要创建的内容，已经是初始化过的目录）')
    print('下一步：python3 %s %s' % (os.path.join(HERE, 'build.py'), root))
    return 0


if __name__ == '__main__':
    sys.path.insert(0, HERE)
    sys.exit(main(sys.argv))
