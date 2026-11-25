#!/usr/bin/env python3
"""research-tracker 自带测试。用法：python3 tests/run_tests.py

只依赖标准库。浏览器相关的测试（需要 Chrome/Chromium 的无头模式）找不到浏览器时跳过并说明，不算失败。
退出码：0 全部通过（含跳过）；1 有失败。
"""
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import html as H

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(SKILL, 'scripts'))
import miniyaml as MY
import mdlite as MD
import tracker as T
import lockfile as L

PASS, FAIL, SKIP = [], [], []


def check(name, cond, detail=''):
    (PASS if cond else FAIL).append(name)
    print(('通过  ' if cond else '失败  ') + name + (('  | ' + str(detail)) if (detail and not cond) else ''))


def raises(fn, exc):
    try:
        fn()
    except exc:
        return True
    except Exception:
        return False
    return False


def tmp():
    return tempfile.mkdtemp(prefix='rt_')


def run(*args):
    return subprocess.run([sys.executable] + list(args), capture_output=True, text=True, timeout=120)


def mk(files, cfg='lines: [L]\nstale_days: 30\nmin_runs: {实机: 3}\ntoday: 2026-06-01\n'):
    r = tmp()
    for d in ('projects', 'hypotheses', 'experiments', 'errors'):
        os.makedirs(os.path.join(r, d))
    open(os.path.join(r, 'tracker.yaml'), 'w', encoding='utf-8').write(cfg)
    for rel, txt in files.items():
        open(os.path.join(r, rel), 'w', encoding='utf-8').write(txt)
    return r


P = '---\nid: p\nname: N\nline: L\nstatus: 进行中\nstatus_basis: b\nupdated: %s\nquestion: q\nstages:\n  - {n: a, s: doing}\n%s---\n'
H1 = '---\nid: H1\nproject: p\nstatement: s\nstatus: %s\nupdated: 2026-05-01\n%s---\n'
E = '---\nid: E1\ndate: 2026-05-02\ntitle: t\nproject: p\nkind: %s\nstatus: %s\n%s---\n# E\n%s'
PRED = '## 目的与预测\n- 预测（跑之前写）：%s\n- 判否条件（x）：%s\n'


# ---------------------------------------------------------------- 1 YAML 子集
def t_yaml():
    src = 'a: 1\nb: "x: y"\nc: [1, "two", {k: v}]\nd:\n  - {n: "阶段", s: done}\n  - plain\n  - key: v\n    k2: [a, b]\ne: |\n  l1\n  l2\nf: >\n  w1\n  w2\ng: null\nh: 2026-11-25\ni: "C:\\\\p"\nj: \'it\'\'s\'\nk: true\nl: -3\nm: 1.5\nn: "# 不是注释"\no: 值 # 注释\n'
    d = MY.load(src)
    check('yaml: 标量与类型', d['a'] == 1 and d['g'] is None and d['k'] is True and d['l'] == -3 and d['m'] == 1.5 and d['h'] == '2026-11-25')
    check('yaml: 引号与转义', d['b'] == 'x: y' and d['i'] == 'C:\\p' and d['j'] == "it's" and d['n'] == '# 不是注释' and d['o'] == '值')
    check('yaml: 流式与块列表', d['c'] == [1, 'two', {'k': 'v'}] and d['d'] == [{'n': '阶段', 's': 'done'}, 'plain', {'key': 'v', 'k2': ['a', 'b']}])
    check('yaml: 块文字', d['e'] == 'l1\nl2' and d['f'] == 'w1 w2')
    for bad, why in (('a: [1, 2\n', '未闭合列表'), ('a: "x\n', '未闭合引号'), ('a:\n\tb: 1\n', '制表符'), ('a: 1\na: 2\n', '重复键'), ('a: "\\q"\n', '非法转义'), ('- x\n', '顶层列表')):
        check('yaml: 报错 ' + why, raises(lambda b=bad: MY.load(b), MY.YamlError))
    for v in ['plain', 'a: b', '#x', 'true', '12', '', ' lead', 'x # y', 'C:\\p', 'line\nbreak', '- d', '[x]', 'null', '有中文', '2026-11-25']:
        check('yaml: 往返 %r' % v, MY.load('k: ' + MY.dump_scalar(v) + '\n')['k'] == v)
    import time
    big = 'k:\n' + ''.join('  - {n: "x%d", s: done}\n' % i for i in range(5000))
    t0 = time.time(); MY.load(big)
    check('yaml: 5000 项不超过 3 秒', time.time() - t0 < 3, '%.2f 秒' % (time.time() - t0))


# ---------------------------------------------------------------- 2 Markdown 子集
def t_md():
    out = MD.render('# 标题\n\n<img src=x onerror=alert(1)> **粗** `c<b>`\n\n[好](https://a.b/c?d=1&e=2) [坏](javascript:alert(1)) [数据](data:text/html,x)\n\n| a | b |\n|---|---|\n| 1 | 待补 |\n\n- x\n- y\n\n1. p\n2. q\n\n```\n<script>1</script>\n```\n')
    check('md: 原始标签被转义', '<img' not in out and '&lt;img' in out and '<script>' not in out)
    check('md: 好链接保留', 'href="https://a.b/c?d=1&amp;e=2"' in out)
    check('md: javascript:/data: 链接被去掉', 'javascript' not in out.split('坏')[0][-40:] and 'href="javascript' not in out and 'href="data' not in out)
    # 纵深防御：白名单正则本身就要拦住危险协议，不能只靠后面的黑名单
    danger = ['javascript:alert(1)', 'JaVaScRiPt:alert(1)', ' javascript:alert(1)', 'data:text/html,x', 'vbscript:x', 'mailto:a@b.c', 'file:///etc/passwd', 'x:y']
    check('md: 白名单自己就拦住危险协议', not any(MD._SAFE.match(u) for u in danger), [u for u in danger if MD._SAFE.match(u)])
    safe = ['https://a.b/c', 'http://a.b', '#frag', 'rel/path.md', '../up.md', '/abs.md', '中文/路径.md']
    check('md: 白名单放行常见的好链接', all(MD._SAFE.match(u) for u in safe), [u for u in safe if not MD._SAFE.match(u)])
    check('md: 表格、列表、代码块', '<table>' in out and '<ul>' in out and '<ol>' in out and '<pre class="code">' in out and 'class="tbd"' in out)


# ---------------------------------------------------------------- 3 校验与纪律检查
def t_audit():
    cases = {
        'stale-project': {'projects/p.md': P % ('2026-01-01', '')},
        'link-missing': {'projects/p.md': P % ('2026-05-30', 'links:\n  - {label: x, path: nofile.md}\n')},
        'no-converse': {'projects/p.md': P % ('2026-05-30', ''), 'hypotheses/H1.md': H1 % ('待检验', '')},
        'no-criterion': {'projects/p.md': P % ('2026-05-30', ''), 'hypotheses/H1.md': H1 % ('待检验', '')},
        'hyp-no-experiment': {'projects/p.md': P % ('2026-05-30', ''), 'hypotheses/H1.md': H1 % ('支持', 'converse: c\ncriterion: k\n')},
        'no-prediction': {'projects/p.md': P % ('2026-05-30', ''), 'experiments/E1.md': E % ('离线', '已完成', '', '## 结果\n- r\n')},
        'no-predicted-at': {'projects/p.md': P % ('2026-05-30', ''), 'experiments/E1.md': E % ('离线', '计划中', '', PRED % ('会降', '升了就错'))},
        'late-prediction': {'projects/p.md': P % ('2026-05-30', ''), 'experiments/E1.md': E % ('离线', '计划中', 'predicted_at: "2026-05-02 12:00"\nstarted_at: "2026-05-02 09:00"\n', PRED % ('会降', '升了就错'))},
        'no-falsifier': {'projects/p.md': P % ('2026-05-30', ''), 'experiments/E1.md': E % ('离线', '计划中', 'predicted_at: "2026-05-01 09:00"\n', PRED % ('会降', ''))},
        'no-review': {'projects/p.md': P % ('2026-05-30', ''), 'experiments/E1.md': E % ('离线', '已完成', '', PRED % ('会降', '升了就错') + '## 判定\n- 成立\n')},
        'no-verdict': {'projects/p.md': P % ('2026-05-30', ''), 'experiments/E1.md': E % ('离线', '已完成', '', PRED % ('会降', '升了就错') + '## 审查\n- 样本少\n')},
        'few-runs': {'projects/p.md': P % ('2026-05-30', ''), 'experiments/E1.md': E % ('实机', '已完成', '', PRED % ('会降', '升了就错') + '## 判定\n- 成立\n## 审查\n- x\n## 逐次记录\n| # | 结果 |\n|---|---|\n| 1 | 成功 |\n')},
        'backfilled': {'projects/p.md': P % ('2026-05-30', ''), 'experiments/E1.md': E % ('离线', '已完成', 'backfilled: 2026-05-20\n', '## 结果\n- r\n')},
        'config-tbd': {'projects/p.md': P % ('2026-05-30', ''), 'experiments/E1.md': E % ('离线', '计划中', '', PRED % ('会降', '升了就错') + '## 配置指纹\n| 项 | 值 |\n|---|---|\n| 种子 | 待补 |\n')},
        'skipped-note': {'projects/p.md': P % ('2026-05-30', ''), 'projects/无头.md': '没有 frontmatter\n'},
    }
    for code, files in cases.items():
        d = T.load_all(mk(files))
        check('检查能触发: ' + code, any(a['code'] == code for a in d['audit']))
    r = mk({'projects/p.md': P % ('2026-05-30', ''), 'experiments/E1.md': E % ('离线', '计划中', 'predicted_at: "2026-05-01 09:00"\n', PRED % ('会降', '升了就错'))})
    lock = T.load_all(r)['fingerprints']
    open(os.path.join(r, 'experiments/E1.md'), 'w', encoding='utf-8').write(E % ('离线', '计划中', 'predicted_at: "2026-05-01 09:00"\n', PRED % ('会升', '升了就错')))
    check('检查能触发: prediction-changed', any(a['code'] == 'prediction-changed' for a in T.load_all(r, lock=lock)['audit']))
    check('覆盖了全部检查代码', len(cases) + 1 + 3 == len(T.CODES), '%d 种用例 对 %d 个代码（树检查 3 个在 t_tree 里）' % (len(cases) + 1 + 3, len(T.CODES)))
    d = T.load_all(mk({'projects/p.md': P % ('2026-01-01', '')}, 'lines: [L]\nstale_days: 30\ntoday: 2026-06-01\nchecks_off: [stale-project]\n'))
    check('checks_off 能关闭检查', not any(a['code'] == 'stale-project' for a in d['audit']))
    d = T.load_all(mk({'projects/p.md': P % ('2026-05-30', ''), 'experiments/E1.md': E % ('离线', '已完成', 'backfilled: 2026-05-20\n', '## 结果\n- r\n')}))
    check('回填记录不报"无事前预测"', not any(a['code'] == 'no-prediction' for a in d['audit']))
    d = T.load_all(mk({'projects/p.md': P % ('2026-05-30', ''), 'experiments/E1.md': E % ('离线', '作废', '', '## 结果\n- r\n')}))
    check('作废的实验不参与检查', not any(a['id'] == 'E1' for a in d['audit']))


def t_errors():
    bad = {
        'projects/a.md': '---\nid: a\nname: A\nline: 无此线\nstatus: 进展顺利\nstatus_basis: x\nupdated: 2026/03/01\nquestion: q\nstages:\n  - {n: x, s: finished}\nfacts:\n  - {ev: 很确定, t: t}\nrelated: [ghost]\n---\n',
        'projects/b.md': '---\nid: a\nname: B\n---\n',
        'projects/c.md': '---\nid: c\nname: C\nstatus_basis: "没闭合\n---\n',
        'hypotheses/H1.md': '---\nid: H1\nproject: nope\nstatement: s\nstatus: 对了\nupdated: 2026-03-01\n---\n',
        'experiments/E1.md': '---\nid: E1\ndate: 昨天\ntitle: t\nproject: a\nkind: k\nstatus: 做完了\ntests: [H9]\ncontrol: E7\n---\n## 逐次记录\n| # | 结果 |\n|---|---|\n| 1 | 搞定 |\n',
        'errors/r.md': '---\nid: ERR1\ndate: 2026-03-01\nwhat: w\naffects: [nothing]\n---\n',
    }
    r = mk(bad, 'lines: [主线]\n')
    try:
        T.load_all(r); check('错误: 坏笔记被拒绝', False)
    except T.TrackerError as e:
        msgs = '\n'.join(e.errors)
        check('错误: 坏笔记被拒绝并一次列出多处', len(e.errors) >= 15, '%d 处' % len(e.errors))
        for key in ('进展顺利', '2026/03/01', '无此线', 'finished', '很确定', '重复', 'ghost', '没有闭合' if '没有闭合' in msgs else '没有结束', 'nope', '对了', '昨天', '做完了', 'H9', 'E7', '搞定', 'nothing', 'found_by'):
            check('错误信息里提到 ' + key, key in msgs)
        check('错误信息都带文件名', all(re.search(r'(projects|hypotheses|experiments|errors)/', m) or 'tracker.yaml' in m for m in e.errors))
    p = run(os.path.join(SKILL, 'scripts', 'build.py'), r, '--out', os.path.join(r, 'x.html'))
    check('build: 有错误时退出码 1 且不生成页面', p.returncode == 1 and not os.path.exists(os.path.join(r, 'x.html')), p.returncode)
    check('build: 用法错误退出码 2', run(os.path.join(SKILL, 'scripts', 'build.py')).returncode == 2)
    check('build: 目录不存在退出码 1', run(os.path.join(SKILL, 'scripts', 'build.py'), '/nonexistent_dir_zz').returncode == 1)


# ---------------------------------------------------------------- 4 init 与 build 端到端
def t_cli():
    r = tmp(); d = os.path.join(r, 'x')
    p = run(os.path.join(SKILL, 'scripts', 'init.py'), d, '--name', '我的 "研究": 看板')
    check('init: 新目录成功', p.returncode == 0 and all(os.path.isdir(os.path.join(d, s)) for s in ('projects', 'hypotheses', 'experiments', 'errors', '_归档')))
    p = run(os.path.join(SKILL, 'scripts', 'build.py'), d)
    check('build: 空目录能生成', p.returncode == 0 and os.path.isfile(os.path.join(d, '看板.html')), p.stdout[-200:] + p.stderr[-200:])
    check('init: 含特殊字符的标题能写回读出', T.load_config(d, [])['title'] == '我的 "研究": 看板')
    n = os.path.join(r, 'busy'); os.makedirs(n); open(os.path.join(n, '草稿.txt'), 'w').write('hi')
    check('init: 非空目录默认拒绝', run(os.path.join(SKILL, 'scripts', 'init.py'), n).returncode == 1)
    check('init: --force 不覆盖已有文件', run(os.path.join(SKILL, 'scripts', 'init.py'), n, '--force').returncode == 0 and open(os.path.join(n, '草稿.txt')).read() == 'hi')
    q = os.path.join(r, 'demo'); run(os.path.join(SKILL, 'scripts', 'init.py'), q, '--demo')
    mine = os.path.join(q, 'projects', 'denoise.md'); open(mine, 'a', encoding='utf-8').write('\n我的修改\n')
    run(os.path.join(SKILL, 'scripts', 'init.py'), q, '--demo')
    check('init: 再次 --demo 不覆盖用户的修改', '我的修改' in open(mine, encoding='utf-8').read())
    p = run(os.path.join(SKILL, 'scripts', 'build.py'), q, '--today', '2026-03-20')
    check('build: 示例能生成', p.returncode == 0 and '纪律检查' in p.stdout, p.stdout[-300:])
    html_ = open(os.path.join(q, '看板.html'), encoding='utf-8').read()
    check('build: 页面自包含（无外部引用）', not re.search(r'(src|href)=["\']https?://', html_) and 'googleapis' not in html_ and not re.search(r'@import|url\(', html_))
    check('build: 页面只有 2 个 script（数据 + 脚本）', len(re.findall(r'<script', html_)) == 2)
    check('build: 页面无乱码字符', '\ufffd' not in html_)
    check('build: 写出预测指纹锁文件', os.path.isfile(os.path.join(q, L.NAME)))
    p = run(os.path.join(SKILL, 'scripts', 'check.py'), q)
    check('check: 能运行且退出码 0', p.returncode == 0 and '纪律检查' in p.stdout)
    e3 = os.path.join(q, 'experiments', 'E3-prior.md'); s = open(e3, encoding='utf-8').read()
    open(e3, 'w', encoding='utf-8').write(s.replace('强度 0.2 时误差降到 0.064 以下', '强度 0.2 时误差降到 0.069 以下'))
    p = run(os.path.join(SKILL, 'scripts', 'build.py'), q, '--today', '2026-03-20')
    check('build: 改了预测会被锁文件发现', '预测被改动' in p.stdout, p.stdout[-200:])
    p2 = run(os.path.join(SKILL, 'scripts', 'build.py'), q, '--today', '2026-03-20')
    check('build: 再构建仍提醒（锁不被覆盖）', '预测被改动' in p2.stdout)


# ---------------------------------------------------------------- 5 对抗样例（XSS）与模板
def t_templates():
    for name in ('project', 'hypothesis', 'experiment', 'error'):
        text = open(os.path.join(SKILL, 'assets', 'templates', name + '.md'), encoding='utf-8').read()
        try:
            meta, _ = MY.load_note(text); ok = bool(meta)
        except MY.YamlError as e:
            ok = False
        check('模板能被解析: ' + name, ok)
    check('示例笔记无乱码', all('\ufffd' not in open(f, encoding='utf-8').read() for f in glob.glob(os.path.join(SKILL, 'examples', '**', '*.md'), recursive=True)))
    check('全部文件无乱码', all('\ufffd' not in open(f, encoding='utf-8').read() for f in glob.glob(os.path.join(SKILL, '**', '*'), recursive=True) if os.path.isfile(f) and f.endswith(('.md', '.py', '.js', '.css', '.yaml'))))


# ---------------------------------------------------------------- 6 问题树
TP = '---\nid: %s\nname: "%s"\nline: L\n%sstatus: 进行中\nstatus_basis: b\nupdated: 2026-05-30\nquestion: q\nstages:\n  - {n: a, s: doing}\n%s---\n'


def t_tree():
    files = {
        'projects/root.md': TP % ('root', '核心', 'kind: 核心问题\n', 'ideas:\n  - {t: "想法A", status: 待评估, date: 2026-01-01}\n  - {t: "想法B", status: 已开课题, to: a}\n  - {t: "想法C", status: 放弃}\n'),
        'projects/a.md': TP % ('a', '子A', 'kind: 子课题\nparent: root\norigin: "讨论中分出"\n', ''),
        'projects/b.md': TP % ('b', '子B', 'parent: root\n', ''),
        'projects/c.md': TP % ('c', '孙C', 'kind: 想法分支\nparent: a\norigin: o\n', ''),
        'projects/orph.md': TP % ('orph', '孤儿', 'kind: 子课题\n', ''),
        'projects/legacy.md': TP % ('legacy', '旧格式', '', ''),
    }
    d = T.load_all(mk(files))
    by = {p['id']: p for p in d['projects']}
    check('树: 子课题挂在 parent 下', by['root']['children'] == ['a', 'b'] or sorted(by['root']['children']) == ['a', 'b'], by['root']['children'])
    check('树: 深度与根', by['c']['depth'] == 2 and by['c']['root'] == 'root' and by['root']['depth'] == 0)
    check('树: 子孙数', by['root']['descendants'] == 3, by['root']['descendants'])
    check('树: 有 parent 没写 kind 时默认是子课题', by['b']['kind'] == '子课题')
    check('树: 旧格式（无 kind/parent）默认是核心问题', by['legacy']['kind'] == '核心问题' and 'legacy' in d['tree']['roots'])
    check('树: 统计想法数', d['tree']['n_ideas'] == 3 and d['tree']['n_ideas_open'] == 1, d['tree'])
    codes = {(a['code'], a['id']) for a in d['audit']}
    check('树检查: 子课题没有 parent → orphan-subtopic', ('orphan-subtopic', 'orph') in codes)
    check('树检查: 有 parent 没写 origin → no-origin', ('no-origin', 'b') in codes and ('no-origin', 'a') not in codes)
    check('树检查: 想法待评估太久 → stale-idea', ('stale-idea', 'root') in codes)
    for name, extra, key in (
        ('parent 指向不存在的课题', {'projects/x.md': TP % ('x', 'X', 'parent: ghost\n', '')}, 'ghost'),
        ('parent 指向自己', {'projects/x.md': TP % ('x', 'X', 'parent: x\n', '')}, '自己'),
        ('parent 成环', {'projects/x.md': TP % ('x', 'X', 'parent: y\n', ''), 'projects/y.md': TP % ('y', 'Y', 'parent: x\n', '')}, '环'),
        ('核心问题不能有 parent', {'projects/r.md': TP % ('r', 'R', 'kind: 核心问题\n', ''), 'projects/x.md': TP % ('x', 'X', 'kind: 核心问题\nparent: r\n', '')}, '核心问题'),
        ('kind 不在允许范围', {'projects/x.md': TP % ('x', 'X', 'kind: 大问题\n', '')}, '大问题'),
        ('想法状态不在允许范围', {'projects/x.md': TP % ('x', 'X', '', 'ideas:\n  - {t: t, status: 想想}\n')}, '想想'),
        ('已开课题的想法必须写 to', {'projects/x.md': TP % ('x', 'X', '', 'ideas:\n  - {t: t, status: 已开课题}\n')}, 'to'),
        ('想法的 to 指向不存在的课题', {'projects/x.md': TP % ('x', 'X', '', 'ideas:\n  - {t: t, status: 已开课题, to: nope}\n')}, 'nope'),
    ):
        try:
            T.load_all(mk(extra)); check('树错误: ' + name, False)
        except T.TrackerError as e:
            check('树错误: ' + name, any(key in m for m in e.errors), e.errors[:2])
    # 环不能让程序卡死，且只报一次
    r = mk({'projects/x.md': TP % ('x', 'X', 'parent: y\n', ''), 'projects/y.md': TP % ('y', 'Y', 'parent: z\n', ''), 'projects/z.md': TP % ('z', 'Z', 'parent: x\n', '')})
    try:
        T.load_all(r)
    except T.TrackerError as e:
        check('树错误: 三节点环只报一次', sum('环' in m for m in e.errors) == 1, e.errors)
    # 大树: 40 个节点 6 层，构建要快
    import random, time
    random.seed(7); fs = {'projects/n0.md': TP % ('n0', 'n0', 'kind: 核心问题\n', '')}; ns = [('n0', 0)]
    for i in range(1, 300):
        par = random.choice([x for x in ns if x[1] < 8]); ns.append(('n%d' % i, par[1] + 1))
        fs['projects/n%d.md' % i] = TP % ('n%d' % i, 'n%d' % i, 'parent: %s\norigin: o\n' % par[0], '')
    t0 = time.time(); d = T.load_all(mk(fs))
    check('树: 300 个节点 9 层能在 3 秒内读完', time.time() - t0 < 3 and len(d['projects']) == 300, '%.2f 秒' % (time.time() - t0))
    check('树: 300 节点全部挂到同一个根', d['tree']['roots'] == ['n0'] and d['projects'][0]['root'] == 'n0')


def chrome():
    for p in ('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/Applications/Chromium.app/Contents/MacOS/Chromium'):
        if os.path.exists(p):
            return p
    for n in ('google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser', 'chrome'):
        p = shutil.which(n)
        if p:
            return p
    return None


def headless(path, extra=''):
    c = chrome()
    p = subprocess.run([c, '--headless=new', '--disable-gpu', '--no-sandbox', '--enable-logging=stderr', '--v=0', '--window-size=1280,1800', '--virtual-time-budget=6000', '--allow-file-access-from-files', '--dump-dom', 'file://' + path],
                       capture_output=True, text=True, timeout=120)
    m = re.search(r'<pre id="TESTOUT">(.*?)</pre>', p.stdout, re.S)
    return (H.unescape(m.group(1)) if m else None), p.stderr


def t_browser():
    if not chrome():
        SKIP.append('浏览器测试')
        print('跳过  浏览器测试：没有找到 Chrome/Chromium（装了就会自动运行这一组）')
        return
    r = tmp(); q = os.path.join(r, 'demo'); run(os.path.join(SKILL, 'scripts', 'init.py'), q, '--demo'); run(os.path.join(SKILL, 'scripts', 'build.py'), q, '--today', '2026-03-20')
    src = open(os.path.join(q, '看板.html'), encoding='utf-8').read()
    js = r"""<script>window.addEventListener('load',function(){var out=[];function ok(n,c,x){out.push((c?'PASS ':'FAIL ')+n+(x?' | '+x:''))}
try{ok('默认打开问题树',document.querySelector('main h1').textContent==='问题树');go('home',true);ok('课题页有 5 张课题卡',document.querySelectorAll('.card').length===5,document.querySelectorAll('.card').length);document.querySelector('.card').click();ok('点课题卡进入详情',!!document.querySelector('.crumb'));
go('exps');var r0=document.querySelectorAll('table.ev tbody tr').length;ok('实验表 6 行',r0===6,r0);document.querySelectorAll('table.ev tbody .linkbtn')[0].click();ok('展开详情',!!document.querySelector('.detail'));
var sf=document.getElementById('f-warn');sf.value='warn';sf.dispatchEvent(new Event('change'));var rw=document.querySelectorAll('table.ev tbody tr:not(:has(.detail))').length;ok('筛选有警告',rw<r0&&rw>0,r0+'->'+rw);sf.value='';sf.dispatchEvent(new Event('change'));
var q=document.getElementById('f-q');q.value='泊松';q.dispatchEvent(new Event('input'));ok('搜索',document.querySelectorAll('table.ev tbody .linkbtn').length===1);q.value='';q.dispatchEvent(new Event('input'));
var c=document.querySelectorAll('table.ev .chk');c[0].checked=true;c[0].dispatchEvent(new Event('change'));c[1].checked=true;c[1].dispatchEvent(new Event('change'));var b=document.getElementById('cmpBtn');ok('对比按钮可用',!b.disabled);b.click();ok('对比表有高亮行',document.querySelectorAll('.cmp tr.diff').length>0);
go('hyps');ok('假设页 4 条',document.querySelectorAll('.panel.hyp').length===4);ok('H2 缺反面提示',document.getElementById('hyp-H2').textContent.indexOf('没写')>=0);ok('H3 无实验提示',document.getElementById('hyp-H3').textContent.indexOf('没有实验指向它')>=0);
go('errors');ok('错误页',document.body.textContent.indexOf('ERR1')>=0);go('audit');ok('纪律页',document.body.textContent.indexOf('预测晚于开跑')>=0);go('how');ok('说明页',document.querySelector('h1').textContent==='怎么更新这个页面');
go('p:survey');ok('课题详情',document.querySelector('h1').textContent.indexOf('文献调研')>=0);go('p:不存在');ok('未知路由回问题树',!!document.querySelector('svg.mind'));go('tree',true);var nn=document.querySelectorAll('svg.mind .node').length,ii=document.querySelectorAll('svg.mind .idea').length;ok('树: 5 个课题节点 4 个想法',nn===5&&ii===4,nn+'/'+ii);var rs=[].map.call(document.querySelectorAll('svg.mind .node .box, svg.mind .idea rect'),function(r){return r.getBoundingClientRect()});var ov=0;for(var i=0;i<rs.length;i++)for(var j=i+1;j<rs.length;j++){var A=rs[i],B=rs[j];if(A.left<B.right-1&&B.left<A.right-1&&A.top<B.bottom-1&&B.top<A.bottom-1)ov++}ok('树: 节点互不重叠',ov===0,ov);var tb=0;[].forEach.call(document.querySelectorAll('svg.mind .node, svg.mind .idea'),function(g){var bx=(g.querySelector('.box')||g.querySelector('rect')).getBoundingClientRect();[].forEach.call(g.querySelectorAll('text'),function(t){if(t.closest('.wbadge')||t.closest('.toggle'))return;var r=t.getBoundingClientRect();if(r.right>bx.right+1||r.bottom>bx.bottom+1)tb++})});ok('树: 文字不超出框',tb===0,tb);document.querySelector('svg.mind .toggle').dispatchEvent(new MouseEvent('click',{bubbles:true}));ok('树: 收起根后只剩 1 个节点',document.querySelectorAll('svg.mind .node').length===1);document.querySelector('svg.mind .toggle').dispatchEvent(new MouseEvent('click',{bubbles:true}));var cb=document.querySelector('.chkl input');cb.checked=false;cb.dispatchEvent(new Event('change'));ok('树: 可隐藏想法',document.querySelectorAll('svg.mind .idea').length===0);cb=document.querySelector('.chkl input');cb.checked=true;cb.dispatchEvent(new Event('change'));[].filter.call(document.querySelectorAll('svg.mind .node'),function(g){return g.getAttribute('data-go')==='p:low-noise-harm'})[0].dispatchEvent(new MouseEvent('click',{bubbles:true}));var cr=document.querySelector('.crumb').textContent;ok('树: 点节点进详情且面包屑是完整路径',cr.indexOf('去噪先验')>=0&&cr.indexOf('噪声强度')>=0,cr);go('tree',true);var dd=document.querySelector('details');dd.open=true;ok('树: 文字版列出 5 个课题',dd.querySelectorAll('.tl-row').length===5);
['tree','home','hyps','exps','errors','audit','how','p:denoise','p:survey'].forEach(function(r){go(r,true);var d=document.documentElement;ok('无横向溢出 '+r,d.scrollWidth-d.clientWidth<=1,d.clientWidth+'/'+d.scrollWidth)})
}catch(e){out.push('FAIL 异常 '+e.message)}var pre=document.createElement('pre');pre.id='TESTOUT';pre.textContent=out.join('\n');document.body.appendChild(pre)})</script>"""
    f = os.path.join(r, 't.html'); open(f, 'w', encoding='utf-8').write(src.replace('</body>', js + '</body>'))
    out, err = headless(f)
    if out is None:
        check('浏览器: 页面脚本运行', False, '没有测试输出；' + err[-200:])
    else:
        for ln in out.split('\n'):
            check('浏览器: ' + ln[5:].split(' | ')[0], ln.startswith('PASS'), ln)
    check('浏览器: 无 JS 报错', not re.search(r'Uncaught|SyntaxError|TypeError|ReferenceError', err))
    # 对抗样例
    e = tmp()
    for d_ in ('projects', 'hypotheses', 'experiments', 'errors'):
        os.makedirs(os.path.join(e, d_))
    X = '<img src=x onerror=window.PWN_%s=1>'
    open(os.path.join(e, 'tracker.yaml'), 'w', encoding='utf-8').write('title: "T</title><script>window.PWN_T=1</script>"\nlines: ["线%s"]\n' % (X % 'LINE'))
    open(os.path.join(e, 'projects/p.md'), 'w', encoding='utf-8').write('---\nid: evil\nname: "名%s"\nline: "线%s"\nstatus: 进行中\nstatus_basis: "b</script><script>window.PWN_B=1</script>"\nupdated: 2026-03-01\nquestion: "q%s"\nstages:\n  - {n: "s%s", s: doing, note: "n<script>window.PWN_N=1</script>"}\nfacts:\n  - {ev: "有数据", t: "f%s"}\nblockers: ["b%s"]\nnext: ["x%s"]\nlinks:\n  - {label: "l%s", path: "javascript:window.PWN_JS=1"}\n---\n# 正文\n%s <script>window.PWN_BODY=1</script> [点](javascript:window.PWN_L=1)\n' % (X % 'NAME', X % 'LINE', X % 'Q', X % 'ST', X % 'F', X % 'BLK', X % 'NX', X % 'LBL', X % 'BODY'))
    open(os.path.join(e, 'hypotheses/h.md'), 'w', encoding='utf-8').write('---\nid: H1\nproject: evil\nstatement: "s%s"\nconverse: "c%s"\ncriterion: "k%s"\nstatus: 待检验\nupdated: 2026-03-01\nresult: "r%s"\n---\n' % ((X % 'HS'), (X % 'HC'), (X % 'HK'), (X % 'HR')))
    open(os.path.join(e, 'experiments/e.md'), 'w', encoding='utf-8').write('---\nid: E1\ndate: 2026-03-02\ntitle: "t%s"\nproject: evil\nkind: "k%s"\nstatus: 已完成\ntests: [H1]\nsetting: "s%s"\n---\n## 目的与预测\n- 预测（跑之前写）：p%s\n- 判否条件（x）：f%s\n## 配置指纹\n| 项 | 值 |\n|---|---|\n| %s | %s |\n## 逐次记录\n| # | 结果 | 备注 |\n|---|---|---|\n| 1 | 完成 | %s |\n' % tuple([X % n for n in ('ET', 'EK', 'ES', 'EP', 'EF', 'CK', 'CV', 'RUN')]))
    open(os.path.join(e, 'errors/r.md'), 'w', encoding='utf-8').write('---\nid: ERR1\ndate: 2026-03-03\nwhat: "w%s"\nfound_by: "f%s"\nfix: "x%s"\naffects: [E1]\n---\n' % ((X % 'W'), (X % 'F2'), (X % 'X')))
    p = run(os.path.join(SKILL, 'scripts', 'build.py'), e, '--today', '2026-03-20')
    check('对抗样例: 能构建', p.returncode == 0, p.stdout[-200:] + p.stderr[-200:])
    src = open(os.path.join(e, '看板.html'), encoding='utf-8').read()
    check('对抗样例: 页面只有 2 个 script 标签', len(re.findall(r'<script', src)) == 2 and src.count('</script') == 2)
    js2 = r"""<script>window.addEventListener('load',function(){var out=[];try{['home','p:evil','hyps','exps','errors','audit','how'].forEach(function(r){go(r,true)});go('exps',true);var b=document.querySelector('table.ev tbody .linkbtn');if(b)b.click();
var hs=[].map.call(document.querySelectorAll('main a'),function(a){return a.getAttribute('href')||''});var bad=hs.filter(function(h){return /^\s*(javascript|data|vbscript):/i.test(h)});out.push((bad.length?'FAIL':'PASS')+' 无危险链接 '+JSON.stringify(bad));
var fired=Object.keys(window).filter(function(k){return k.indexOf('PWN_')===0});out.push((fired.length?'FAIL':'PASS')+' 无注入代码执行 '+JSON.stringify(fired));
out.push((document.querySelectorAll('main img[onerror],main svg[onload],main script,nav img,nav script').length?'FAIL':'PASS')+' 无活的注入元素')}catch(e){out.push('FAIL 异常 '+e.message)}
var pre=document.createElement('pre');pre.id='TESTOUT';pre.textContent=out.join('\n');document.body.appendChild(pre)})</script>"""
    f2 = os.path.join(e, 't.html'); open(f2, 'w', encoding='utf-8').write(src.replace('</body>', js2 + '</body>'))
    out, err = headless(f2)
    if out is None:
        check('对抗样例: 页面脚本运行', False, err[-200:])
    else:
        for ln in out.split('\n'):
            check('对抗样例: ' + ln[5:].split(' | ')[0], ln.startswith('PASS'), ln)


def main():
    for fn in (t_yaml, t_md, t_audit, t_errors, t_cli, t_templates, t_tree, t_browser):
        print('\n== ' + fn.__name__)
        try:
            fn()
        except Exception as e:
            import traceback
            FAIL.append(fn.__name__ + ' 抛出异常')
            print('失败  %s 抛出异常: %s' % (fn.__name__, e)); traceback.print_exc()
    print('\n通过 %d，失败 %d，跳过 %d 组' % (len(PASS), len(FAIL), len(SKIP)))
    if FAIL:
        print('失败的项：\n  ' + '\n  '.join(FAIL))
    return 1 if FAIL else 0


if __name__ == '__main__':
    sys.exit(main())
