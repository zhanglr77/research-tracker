"""tracker：读取研究笔记目录，校验字段，计算纪律检查，产出看板用的数据。只依赖标准库，Python 3.9+（3.9 与 3.14 上测过）。

目录约定见 SKILL.md。本模块不写任何文件，写文件（看板.html、.tracker-lock.json）由 build.py 负责。
"""
from __future__ import annotations
import os
import re
import datetime as dt
import miniyaml as MY
import mdlite as MD

STATUS = ['进行中', '待推进', '搁置', '无近期记录']
STAGE = ['done', 'doing', 'blocked', 'todo', 'unk']
EVIDENCE = ['有数据', '仿真', '推断', '未验证', '决定', '记录', '想法']
HYP_STATUS = ['待检验', '支持', '部分', '反对', '推翻']
EXP_STATUS = ['计划中', '进行中', '已完成', '作废']
PROJECT_KIND = ['核心问题', '子课题', '想法分支']
IDEA_STATUS = ['待评估', '已开课题', '暂不做', '放弃']
DEFAULT_RESULT_WORDS = ['成功', '失败', '部分', '无效', '完成']
OK_WORDS = ('成功', '完成')
ID_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]*$')
EMPTY_RE = re.compile(r'^(待补|无|没有|未写|不适用|—|-|n/?a)[。.]?$', re.I)

# 纪律检查的代码表：代码 -> (名称, 级别, 含义)
CODES = {
    'no-prediction': ('无事前预测', 'warn', '实验没有写预测，或预测是空的/待补。预测必须在开跑之前写。'),
    'no-predicted-at': ('未记录预测时间', 'info', '写了预测但没有 predicted_at，无法核对预测是否早于开跑。'),
    'late-prediction': ('预测晚于开跑', 'warn', 'predicted_at 晚于 started_at：预测是看了结果之后才写的。'),
    'prediction-changed': ('预测被改动', 'warn', '预测或判否条件在首次登记后文字变了。要更正请追加到“审查”，不要改原文。'),
    'no-falsifier': ('没有判否条件', 'warn', '写了预测，但没写“什么结果会推翻它”。'),
    'no-converse': ('假设没有反面', 'warn', '假设没写“如果看到什么，它就不成立”，无法证伪。'),
    'no-criterion': ('假设没有判据', 'info', '假设没写用什么口径和阈值来判断。'),
    'no-review': ('已完成但没有审查', 'warn', '已完成的实验没有“审查”：没写任何削弱这个结果的因素。'),
    'no-verdict': ('已完成但没有判定', 'warn', '已完成的实验没有逐条对照预测的“判定”。'),
    'few-runs': ('次数不足', 'warn', '该种类的实验按 tracker.yaml 的 min_runs 要求更多次数。'),
    'stale-project': ('课题久无记录', 'warn', '课题最后一次记录距今超过 stale_days 天。'),
    'hyp-no-experiment': ('假设下了结论但没有实验', 'warn', '假设状态已不是“待检验”，却没有任何实验指向它。'),
    'link-missing': ('链接目标不存在', 'warn', 'links 里的本地路径找不到。'),
    'backfilled': ('回填记录', 'info', '事后补记的旧记录，没有事前预测是正常的；当作线索，不当结论。'),
    'config-tbd': ('配置有待补项', 'info', '配置指纹里有“待补”：当时没记下，不是 0。'),
    'skipped-note': ('已跳过的文件', 'info', '文件没有 frontmatter，没有被读入。'),
    'orphan-subtopic': ('子课题没有挂到树上', 'warn', 'kind 是子课题或想法分支，但没有 parent：它从哪个问题分出来的没有记录。'),
    'no-origin': ('分叉来源没写', 'info', '子课题没有 origin：没记下是在哪次讨论、因为什么想法分出来的。'),
    'stale-idea': ('想法久未评估', 'info', '问题树上的想法状态是待评估，且超过 stale_days 天没有更新。'),
}


def parse_dt(s):
    """'2026-11-25' 或 '2026-11-25 14:30'（也接受 T 分隔）。返回 (datetime, 是否带时间)；格式不对返回 None。"""
    if not isinstance(s, str):
        return None
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2}))?$', s.strip())
    if not m:
        return None
    try:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if m.group(4) is None:
            return dt.datetime(y, mo, d), False
        return dt.datetime(y, mo, d, int(m.group(4)), int(m.group(5))), True
    except ValueError:
        return None


def parse_date(s):
    r = parse_dt(s)
    return r[0].date() if r else None


class TrackerError(Exception):
    """笔记或配置有必须修的错误。errors 是带文件名（和行号）的中文消息列表。"""

    def __init__(self, errors):
        self.errors = list(errors)
        Exception.__init__(self, '\n'.join(self.errors))


def is_empty(v):
    return v is None or str(v).strip() == '' or bool(EMPTY_RE.match(str(v).strip()))


def field(text, label):
    """在一节文本里找 "- 标签（括号说明）：内容"，返回内容（含缩进续行），找不到返回空串。"""
    pat = re.compile(r'^\s*[-*]\s*' + re.escape(label) + r'(?:[（(][^）)]*[）)])?\s*[:：]\s*(.*)$')
    lines = text.split('\n')
    for i, ln in enumerate(lines):
        m = pat.match(ln)
        if m:
            val, j = [m.group(1).strip()], i + 1
            while j < len(lines) and lines[j][:1] in (' ', '\t') and lines[j].strip():
                val.append(lines[j].strip())
                j += 1
            return ' '.join(v for v in val if v)
    return ''


def read_dir(root, sub, errs, skipped):
    """读 <root>/<sub>/*.md，返回 [(相对路径, frontmatter dict, 正文)]。以 . 或 _ 开头的文件不读。"""
    d = os.path.join(root, sub)
    out = []
    if not os.path.isdir(d):
        return out
    for name in sorted(os.listdir(d)):
        p = os.path.join(d, name)
        if not name.lower().endswith('.md') or name[0] in '._' or not os.path.isfile(p):
            continue
        rel = sub + '/' + name
        try:
            with open(p, encoding='utf-8') as f:
                text = f.read()
        except (OSError, UnicodeDecodeError) as e:
            errs.append('%s：读不了这个文件（%s）。请确认是 UTF-8 编码的文本文件' % (rel, e))
            continue
        try:
            fm, body = MY.split_frontmatter(text)
            if fm is None:
                skipped.append(rel)
                continue
            meta = MY.load(fm)
        except MY.YamlError as e:
            errs.append('%s：frontmatter 写法有问题：%s' % (rel, e))
            continue
        out.append((rel, meta, body))
    return out


def need(meta, key, rel, errs, typ=None, allowed=None):
    """取必填字段。缺失、类型不对、不在允许范围都记入 errs，并返回 None。"""
    v = meta.get(key)
    if v is None or (isinstance(v, str) and v.strip() == ''):
        errs.append('%s：缺少必填字段 %s' % (rel, key))
        return None
    if typ is not None and not isinstance(v, typ):
        errs.append('%s：字段 %s 的类型不对（应为 %s）' % (rel, key, {str: '文字', list: '列表', dict: '映射', int: '整数'}.get(typ, typ)))
        return None
    if allowed is not None and v not in allowed:
        errs.append('%s：字段 %s 的值「%s」不在允许范围：%s' % (rel, key, v, '、'.join(map(str, allowed))))
        return None
    return v


def need_date(meta, key, rel, errs, required=True):
    v = meta.get(key)
    if v is None or v == '':
        if required:
            errs.append('%s：缺少必填字段 %s（格式 2026-11-25）' % (rel, key))
        return None
    if not isinstance(v, str) or parse_dt(v) is None:
        errs.append('%s：字段 %s 的日期格式不对：「%s」，应为 2026-11-25 或 2026-11-25 14:30（日期要加引号或直接写成这个样子）' % (rel, key, v))
        return None
    return v


def as_list(v):
    return [] if v is None else (v if isinstance(v, list) else [v])


def load_config(root, errs):
    cfg = {'title': '科研看板', 'lines': ['课题'], 'stale_days': 90, 'min_runs': {}, 'result_words': list(DEFAULT_RESULT_WORDS), 'checks_off': []}
    p = os.path.join(root, 'tracker.yaml')
    if not os.path.isfile(p):
        return cfg
    try:
        with open(p, encoding='utf-8') as f:
            user = MY.load(f.read())
    except (OSError, UnicodeDecodeError, MY.YamlError) as e:
        errs.append('tracker.yaml：%s' % e)
        return cfg
    for k, v in user.items():
        if k not in cfg and k != 'today':
            errs.append('tracker.yaml：不认识的设置项 %s（允许：%s）' % (k, '、'.join(sorted(list(cfg) + ['today']))))
        elif v is not None:
            cfg[k] = v
    if not (isinstance(cfg['lines'], list) and cfg['lines'] and all(isinstance(x, str) and x.strip() for x in cfg['lines'])):
        errs.append('tracker.yaml：lines 必须是非空的文字列表，例如 [主线, 支线]')
        cfg['lines'] = ['课题']
    if not (isinstance(cfg['stale_days'], int) and not isinstance(cfg['stale_days'], bool) and cfg['stale_days'] >= 1):
        errs.append('tracker.yaml：stale_days 必须是 ≥1 的整数')
        cfg['stale_days'] = 90
    mr = cfg['min_runs']
    if not (isinstance(mr, dict) and all(isinstance(k, str) and isinstance(n, int) and not isinstance(n, bool) and n >= 1 for k, n in mr.items())):
        errs.append('tracker.yaml：min_runs 必须是「实验种类: 最少次数」的映射，例如 {实机: 3}')
        cfg['min_runs'] = {}
    if not (isinstance(cfg['result_words'], list) and cfg['result_words'] and all(isinstance(x, str) for x in cfg['result_words'])):
        errs.append('tracker.yaml：result_words 必须是非空的文字列表')
        cfg['result_words'] = list(DEFAULT_RESULT_WORDS)
    co = cfg['checks_off']
    if not (isinstance(co, list) and all(x in CODES for x in co)):
        errs.append('tracker.yaml：checks_off 里有不认识的检查代码，允许：%s' % '、'.join(CODES))
        cfg['checks_off'] = []
    if 'today' in user and user['today'] is not None and parse_date(user['today']) is None:
        errs.append('tracker.yaml：today 的格式不对，应为 2026-11-25')
    cfg['today_override'] = user.get('today')
    return cfg


def check_id(v, rel, seen, errs, what):
    if v is None:
        return None
    s = str(v)
    if not ID_RE.match(s):
        errs.append('%s：id「%s」只能用字母、数字、下划线和短横线，且以字母或数字开头' % (rel, s))
        return None
    if s in seen:
        errs.append('%s：%s id「%s」和 %s 重复' % (rel, what, s, seen[s]))
        return None
    seen[s] = rel
    return s


def check_str_list(meta, key, rel, errs):
    v = meta.get(key)
    if v is None:
        return []
    if not isinstance(v, list) or not all(isinstance(x, (str, int, float)) for x in v):
        errs.append('%s：字段 %s 必须是文字列表（每行以 "- " 开头）' % (rel, key))
        return []
    return [str(x) for x in v]


def load_projects(root, cfg, errs, skipped):
    seen, items, partial = {}, [], []
    for rel, m, body in read_dir(root, 'projects', errs, skipped):
        pid = check_id(need(m, 'id', rel, errs), rel, seen, errs, '课题')
        name = need(m, 'name', rel, errs, str)
        status = need(m, 'status', rel, errs, allowed=STATUS)
        basis = need(m, 'status_basis', rel, errs, str)
        upd = need_date(m, 'updated', rel, errs)
        q = need(m, 'question', rel, errs, str)
        line = need(m, 'line', rel, errs, str)
        if line is not None and line not in cfg['lines']:
            errs.append('%s：line「%s」不在 tracker.yaml 的 lines 里（%s）' % (rel, line, '、'.join(cfg['lines'])))
        stages = []
        raw = m.get('stages')
        if not isinstance(raw, list) or not raw:
            errs.append('%s：stages 必须是非空列表，每项形如 {n: "阶段名", s: done, note: "说明"}' % rel)
        else:
            for k, s in enumerate(raw, 1):
                if not isinstance(s, dict) or not isinstance(s.get('n'), str) or not s['n'].strip():
                    errs.append('%s：stages 第 %d 项缺少 n（阶段名）' % (rel, k))
                elif s.get('s') not in STAGE:
                    errs.append('%s：stages 第 %d 项的状态「%s」不在允许范围：%s' % (rel, k, s.get('s'), '、'.join(STAGE)))
                else:
                    stages.append({'n': s['n'], 's': s['s'], 'note': str(s.get('note') or '')})
        facts = []
        for k, f in enumerate(as_list(m.get('facts')), 1):
            if not isinstance(f, dict) or not isinstance(f.get('t'), str) or not f['t'].strip():
                errs.append('%s：facts 第 %d 项缺少 t（内容）' % (rel, k))
            elif f.get('ev') not in EVIDENCE:
                errs.append('%s：facts 第 %d 项的证据等级「%s」不在允许范围：%s' % (rel, k, f.get('ev'), '、'.join(EVIDENCE)))
            else:
                facts.append({'ev': f['ev'], 't': f['t']})
        links = []
        for k, l in enumerate(as_list(m.get('links')), 1):
            if not isinstance(l, dict) or not isinstance(l.get('label'), str) or not isinstance(l.get('path'), str):
                errs.append('%s：links 第 %d 项必须有 label 和 path' % (rel, k))
                continue
            links.append({'label': l['label'], 'path': l['path'].strip()})
        kind = m.get('kind') or ('子课题' if m.get('parent') else '核心问题')
        if kind not in PROJECT_KIND:
            errs.append('%s：kind「%s」不在允许范围：%s' % (rel, kind, '、'.join(PROJECT_KIND)))
            kind = None
        parent = m.get('parent')
        if parent is not None and not isinstance(parent, str):
            errs.append('%s：parent 必须是一个课题 id（文字）' % rel)
            parent = None
        if kind == '核心问题' and parent:
            errs.append('%s：kind 是核心问题，就不应有 parent；要挂到别的问题下面，把 kind 改成子课题' % rel)
        ideas = []
        for k, it in enumerate(as_list(m.get('ideas')), 1):
            if not isinstance(it, dict) or not isinstance(it.get('t'), str) or not it['t'].strip():
                errs.append('%s：ideas 第 %d 项缺少 t（想法内容）' % (rel, k))
                continue
            st = it.get('status') or '待评估'
            if st not in IDEA_STATUS:
                errs.append('%s：ideas 第 %d 项的状态「%s」不在允许范围：%s' % (rel, k, st, '、'.join(IDEA_STATUS)))
                continue
            when = it.get('date')
            if when is not None and parse_date(str(when)) is None:
                errs.append('%s：ideas 第 %d 项的 date 格式不对，应为 2026-11-25' % (rel, k))
                continue
            ideas.append({'t': it['t'], 'status': st, 'why': str(it.get('why') or ''), 'date': str(when) if when else '', 'to': str(it.get('to') or '')})
        deadline = None
        d = m.get('deadline')
        if d is not None:
            if not isinstance(d, dict) or parse_date(d.get('date')) is None or not isinstance(d.get('what'), str):
                errs.append('%s：deadline 必须形如 {date: 2026-12-01, what: 提交初稿}' % rel)
            else:
                deadline = {'date': d['date'], 'what': d['what']}
        if None in (pid, name, status, basis, upd, q, line, kind):
            partial.append({'id': pid or str(m.get('id') or ''), 'related': check_str_list(m, 'related', rel, errs), 'parent': parent, 'file': rel})
            continue
        items.append({'id': pid, 'name': name, 'short': str(m.get('short') or ''), 'line': line, 'status': status, 'basis': basis, 'updated': upd,
                      'question': q, 'stages': stages, 'facts': facts, 'blockers': check_str_list(m, 'blockers', rel, errs),
                      'next': check_str_list(m, 'next', rel, errs), 'retracted': check_str_list(m, 'retracted', rel, errs),
                      'sources': check_str_list(m, 'sources', rel, errs), 'related': check_str_list(m, 'related', rel, errs),
                      'links': links, 'deadline': deadline, 'file': rel, 'body': MD.render(body),
                      'kind': kind, 'parent': parent or '', 'origin': str(m.get('origin') or ''), 'ideas': ideas})
    ids = [p['id'] for p in items] + [p['id'] for p in partial if p['id']]
    for p in items + partial:
        for r in p['related']:
            if r not in ids:
                errs.append('%s：related 指向不存在的课题「%s」' % (p['file'], r))
        if p.get('parent'):
            if p['parent'] == p['id']:
                errs.append('%s：parent 不能指向自己' % p['file'])
            elif p['parent'] not in ids:
                errs.append('%s：parent 指向不存在的课题「%s」' % (p['file'], p['parent']))
    for p in items:
        for it in p['ideas']:
            if it['to'] and it['to'] not in ids:
                errs.append('%s：ideas 里的 to 指向不存在的课题「%s」' % (p['file'], it['to']))
            if it['status'] == '已开课题' and not it['to']:
                errs.append('%s：想法「%s」状态是已开课题，但没有写 to（开成了哪个课题的 id）' % (p['file'], it['t'][:20]))
    par = {p['id']: p['parent'] for p in items + partial if p['id'] and p.get('parent')}
    reported = set()
    for start in par:
        seen_c, cur = [], start
        while cur in par and cur not in seen_c:
            seen_c.append(cur); cur = par[cur]
        if cur in seen_c:
            cyc = seen_c[seen_c.index(cur):]
            key = frozenset(cyc)
            if key not in reported:
                reported.add(key)
                f = next(x['file'] for x in items + partial if x['id'] == cur)
                errs.append('%s：parent 形成了环：%s' % (f, ' → '.join(cyc + [cur])))
    return items, [p['id'] for p in partial if p['id']]


def load_hypotheses(root, project_ids, errs, skipped):
    seen, items, all_ids = {}, [], []
    for rel, m, body in read_dir(root, 'hypotheses', errs, skipped):
        hid = check_id(need(m, 'id', rel, errs), rel, seen, errs, '假设')
        all_ids.append(hid or str(m.get('id') or ''))
        proj = need(m, 'project', rel, errs, str)
        if proj is not None and proj not in project_ids:
            errs.append('%s：project「%s」不对应任何课题' % (rel, proj))
            proj = None
        stmt = need(m, 'statement', rel, errs, str)
        status = need(m, 'status', rel, errs, allowed=HYP_STATUS)
        upd = need_date(m, 'updated', rel, errs)
        if None in (hid, proj, stmt, status, upd):
            continue
        items.append({'id': hid, 'project': proj, 'statement': stmt, 'converse': str(m.get('converse') or ''), 'criterion': str(m.get('criterion') or ''),
                      'status': status, 'updated': upd, 'result': str(m.get('result') or ''), 'file': rel, 'body': MD.render(body)})
    return items, all_ids


def load_experiments(root, cfg, project_ids, hyp_ids, errs, skipped):
    seen, items, all_ids, controls = {}, [], [], []
    for rel, m, body in read_dir(root, 'experiments', errs, skipped):
        eid = check_id(need(m, 'id', rel, errs), rel, seen, errs, '实验')
        date = need_date(m, 'date', rel, errs)
        title = need(m, 'title', rel, errs, str)
        proj = need(m, 'project', rel, errs, str)
        if proj is not None and proj not in project_ids:
            errs.append('%s：project「%s」不对应任何课题' % (rel, proj))
            proj = None
        kind = need(m, 'kind', rel, errs, str)
        status = need(m, 'status', rel, errs, allowed=EXP_STATUS)
        predicted_at = need_date(m, 'predicted_at', rel, errs, required=False)
        started_at = need_date(m, 'started_at', rel, errs, required=False)
        hyps = check_str_list(m, 'tests', rel, errs)
        for h in hyps:
            if h not in hyp_ids:
                errs.append('%s：tests 指向不存在的假设「%s」' % (rel, h))
        ev = m.get('evidence')
        if ev is not None and ev not in EVIDENCE:
            errs.append('%s：evidence「%s」不在允许范围：%s' % (rel, ev, '、'.join(EVIDENCE)))
            ev = None
        bf = m.get('backfilled')
        if bf is not None and parse_date(str(bf)) is None:
            errs.append('%s：backfilled 的日期格式不对，应为 2026-11-25' % rel)
            bf = None
        ctrl = m.get('control')
        secs = MD.sections(body)
        runs = [r for r in MD.table_rows(secs.get('逐次记录', '')) if len(r) > 1 and r[1].strip()]
        cfgrows = MD.table_rows(secs.get('配置指纹', ''))
        pred_sec = secs.get('目的与预测', '')
        for r in runs:
            if r[1] not in cfg['result_words']:
                errs.append('%s：逐次记录里的结果词「%s」不在 result_words 里（%s）。要么改词，要么在 tracker.yaml 里加上它' % (rel, r[1], '、'.join(cfg['result_words'])))
        all_ids.append(eid or str(m.get('id') or ''))
        if m.get('control'):
            controls.append((rel, str(m['control'])))
        if None in (eid, date, title, proj, kind, status):
            continue
        items.append({'id': eid, 'date': date, 'title': title, 'project': proj, 'kind': kind, 'status': status, 'predicted_at': predicted_at, 'started_at': started_at,
                      'tests': hyps, 'evidence': ev, 'backfilled': str(bf) if bf else '', 'control': str(ctrl) if ctrl else '', 'setting': str(m.get('setting') or ''),
                      'subject': str(m.get('subject') or ''), 'task': str(m.get('task') or ''), 'method': str(m.get('method') or ''),
                      'runs': runs, 'n_runs': len(runs), 'n_ok': sum(1 for r in runs if r[1] in OK_WORDS), 'cfg': cfgrows,
                      'n_tbd': sum(1 for r in cfgrows if len(r) > 1 and r[1].strip() == '待补'),
                      'prediction': field(pred_sec, '预测'), 'falsifier': field(pred_sec, '判否条件'), 'question': field(pred_sec, '要回答的问题'),
                      'verdict': secs.get('判定', '').strip(), 'review': secs.get('审查', '').strip(), 'result_text': secs.get('结果', '').strip(),
                      'file': rel, 'body': MD.render(body)})
    for rel, c in controls:
        if c not in all_ids:
            errs.append('%s：control 指向不存在的实验「%s」' % (rel, c))
    return items, all_ids


def load_errors(root, errs, skipped):
    seen, items, partial_aff = {}, [], []
    for rel, m, body in read_dir(root, 'errors', errs, skipped):
        eid = check_id(need(m, 'id', rel, errs), rel, seen, errs, '错误')
        date = need_date(m, 'date', rel, errs)
        what = need(m, 'what', rel, errs, str)
        found = need(m, 'found_by', rel, errs, str)
        fix = need(m, 'fix', rel, errs, str)
        affects = check_str_list(m, 'affects', rel, errs)
        if None in (eid, date, what, found, fix):
            partial_aff.append((rel, affects))
            continue
        items.append({'id': eid, 'date': date, 'what': what, 'found_by': found, 'fix': fix, 'affects': affects, 'file': rel})
    return items, partial_aff


def audit(root, cfg, projects, hyps, exps, today, skipped, lock):
    """纪律检查。返回 [{code, level, file, id, msg}]。lock 是上次构建时记下的预测指纹，用来发现预测被改。"""
    out = []

    def add(code, file, id_, msg):
        if code in cfg['checks_off']:
            return
        out.append({'code': code, 'name': CODES[code][0], 'level': CODES[code][1], 'file': file, 'id': id_, 'msg': msg})

    pids = {p['id']: p for p in projects}
    tested = {}
    for e in exps:
        for h in e['tests']:
            tested.setdefault(h, []).append(e['id'])
    for e in exps:
        planned = e['status'] in ('计划中',)
        voided = e['status'] == '作废'
        if voided:
            continue
        pred_ok = not is_empty(e['prediction'])
        fals_ok = not is_empty(e['falsifier'])
        if e['backfilled']:
            add('backfilled', e['file'], e['id'], '「%s」是 %s 回填的，当线索，不当结论。' % (e['title'], e['backfilled']))
        if not pred_ok:
            if not e['backfilled']:
                add('no-prediction', e['file'], e['id'], '「%s」没有事前预测。' % e['title'])
        else:
            if e['predicted_at'] is None:
                add('no-predicted-at', e['file'], e['id'], '「%s」写了预测但没有 predicted_at。' % e['title'])
            if e['predicted_at'] and e['started_at']:
                a, b = parse_dt(e['predicted_at']), parse_dt(e['started_at'])
                if a and b and a[0] > b[0]:
                    add('late-prediction', e['file'], e['id'], '「%s」的预测（%s）晚于开跑（%s）。' % (e['title'], e['predicted_at'], e['started_at']))
            if not fals_ok:
                add('no-falsifier', e['file'], e['id'], '「%s」有预测但没有判否条件。' % e['title'])
            fp = (e['prediction'] + '||' + e['falsifier']).strip()
            old = lock.get(e['id'])
            if old is not None and old != fp:
                add('prediction-changed', e['file'], e['id'], '「%s」的预测或判否条件和首次登记时不同。' % e['title'])
        if e['status'] == '已完成':
            if is_empty(e['review']):
                add('no-review', e['file'], e['id'], '「%s」已完成但没有“审查”。' % e['title'])
            if is_empty(e['verdict']):
                add('no-verdict', e['file'], e['id'], '「%s」已完成但没有“判定”。' % e['title'])
            need_n = cfg['min_runs'].get(e['kind'])
            if need_n and e['n_runs'] < need_n:
                add('few-runs', e['file'], e['id'], '「%s」是「%s」类，要求至少 %d 次，只记了 %d 次。' % (e['title'], e['kind'], need_n, e['n_runs']))
        if e['n_tbd']:
            add('config-tbd', e['file'], e['id'], '「%s」的配置指纹有 %d 项待补。' % (e['title'], e['n_tbd']))
    for h in hyps:
        if is_empty(h['converse']):
            add('no-converse', h['file'], h['id'], '假设 %s 没有反面：%s' % (h['id'], h['statement'][:40]))
        if is_empty(h['criterion']):
            add('no-criterion', h['file'], h['id'], '假设 %s 没有判据。' % h['id'])
        if h['status'] != '待检验' and h['id'] not in tested:
            add('hyp-no-experiment', h['file'], h['id'], '假设 %s 状态是「%s」，但没有任何实验的 tests 指向它。' % (h['id'], h['status']))
    for p in projects:
        age = (today - parse_date(p['updated'])).days
        p['age'] = age
        if p['status'] == '进行中' and age > cfg['stale_days']:
            add('stale-project', p['file'], p['id'], '课题「%s」状态是进行中，但最后记录是 %d 天前。' % (p['name'], age))
        for l in p['links']:
            if re.match(r'^[a-z][a-z0-9+.-]*://', l['path'], re.I):
                continue
            q = os.path.expanduser(l['path'])
            if not os.path.isabs(q):
                q = os.path.join(root, q)
            if not os.path.exists(q):
                add('link-missing', p['file'], p['id'], '课题「%s」的链接「%s」指向的文件不存在：%s' % (p['name'], l['label'], l['path']))
    for p in projects:
        if p['kind'] in ('子课题', '想法分支') and not p['parent']:
            add('orphan-subtopic', p['file'], p['id'], '「%s」是%s，但没有 parent，不知道它从哪个问题分出来。' % (p['name'], p['kind']))
        if p['parent'] and is_empty(p['origin']):
            add('no-origin', p['file'], p['id'], '「%s」没有 origin：没记下它是在哪次讨论里、因为什么分出来的。' % p['name'])
        for it in p['ideas']:
            if it['status'] == '待评估':
                d0 = parse_date(it['date']) if it['date'] else parse_date(p['updated'])
                if d0 and (today - d0).days > cfg['stale_days']:
                    add('stale-idea', p['file'], p['id'], '「%s」下的想法「%s」待评估已 %d 天。' % (p['name'], it['t'][:24], (today - d0).days))
    for s in skipped:
        add('skipped-note', s, None, '%s 没有 frontmatter，已跳过。' % s)
    return out


def prediction_fingerprints(exps):
    return {e['id']: (e['prediction'] + '||' + e['falsifier']).strip() for e in exps if not is_empty(e['prediction'])}


def load_all(root, today=None, lock=None):
    """读全部笔记并校验。有必须修的错误就抛 TrackerError（一次性给出全部）。
    返回 dict: cfg, today, projects, hyps, exps, errors, audit, fingerprints。"""
    root = os.path.abspath(os.path.expanduser(root))
    if not os.path.isdir(root):
        raise TrackerError(['目录不存在：%s' % root])
    errs, skipped = [], []
    cfg = load_config(root, errs)
    if today is None:
        today = parse_date(cfg.get('today_override')) if cfg.get('today_override') else dt.date.today()
    projects, p_extra = load_projects(root, cfg, errs, skipped)
    pids = {p['id'] for p in projects}
    all_pids = pids | set(p_extra)
    hyps, h_ids = load_hypotheses(root, all_pids, errs, skipped)
    all_hids = {h['id'] for h in hyps} | set(h_ids)
    exps, e_ids = load_experiments(root, cfg, all_pids, all_hids, errs, skipped)
    errors, partial_aff = load_errors(root, errs, skipped)
    known = all_pids | all_hids | set(e_ids)
    for rel, affects in [(e['file'], e['affects']) for e in errors] + list(partial_aff):
        for a in affects:
            if a not in known:
                errs.append('%s：affects 指向不存在的 id「%s」' % (rel, a))
    if errs:
        raise TrackerError(errs)
    findings = audit(root, cfg, projects, hyps, exps, today, skipped, lock or {})
    for p in projects:
        p['counts'] = {k: sum(1 for s in p['stages'] if s['s'] == k) for k in STAGE}
        p['hyps'] = [h['id'] for h in hyps if h['project'] == p['id']]
        p['exps'] = [e['id'] for e in exps if e['project'] == p['id']]
    exps.sort(key=lambda e: (e['date'], e['id']), reverse=True)
    tree = build_tree(projects)
    return {'root': root, 'cfg': cfg, 'today': today, 'projects': projects, 'hyps': hyps, 'exps': exps, 'errors': errors,
            'audit': findings, 'fingerprints': prediction_fingerprints(exps), 'tree': tree}


def build_tree(projects):
    """问题树：核心问题是根，parent 指向父课题。返回 {roots, children, depth}；没有 parent 的子课题单独作为根（并已在纪律检查里提醒）。
    同时给每个课题写入 children（子课题 id 列表）、depth（深度，根为 0）、root（所在树的根 id）、descendants（子孙数）。"""
    ids = {p['id'] for p in projects}
    by = {p['id']: p for p in projects}
    kids = {p['id']: [] for p in projects}
    for p in projects:
        if p['parent'] in ids:
            kids[p['parent']].append(p['id'])
    order = {'核心问题': 0, '子课题': 1, '想法分支': 2}
    for k in kids:
        kids[k].sort(key=lambda c: (order.get(by[c]['kind'], 9), by[c]['name']))
    roots = sorted([p['id'] for p in projects if p['parent'] not in ids], key=lambda r: (order.get(by[r]['kind'], 9), by[r]['name']))

    def walk(nid, d, r):
        by[nid]['depth'], by[nid]['root'], by[nid]['children'] = d, r, kids[nid]
        n = 0
        for c in kids[nid]:
            n += 1 + walk(c, d + 1, r)
        by[nid]['descendants'] = n
        return n
    for r in roots:
        walk(r, 0, r)
    return {'roots': roots, 'max_depth': max([p['depth'] for p in projects] or [0]),
            'n_ideas': sum(len(p['ideas']) for p in projects), 'n_ideas_open': sum(1 for p in projects for i in p['ideas'] if i['status'] == '待评估')}
