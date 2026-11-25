#!/usr/bin/env python3
"""校验笔记并生成自包含的 看板.html（样式、脚本、数据全部内联，离线可打开，不引用任何外部资源）。

用法：python3 build.py <研究目录> [--out 文件] [--today 2026-11-25] [--no-lock]
退出码：0 成功（可能有纪律警告）；1 有必须修的错误，不生成；2 用法不对。
"""
import json
import os
import sys
import datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import tracker as T
import lockfile as L

ASSETS = os.path.join(os.path.dirname(HERE), 'assets', 'web')


def read_asset(rel):
    with open(os.path.join(ASSETS, rel), encoding='utf-8') as f:
        return f.read()


def json_for_script(obj):
    """放进 <script type="application/json"> 的 JSON：转义 < > & 和行分隔符，使其不可能提前结束标签。"""
    s = json.dumps(obj, ensure_ascii=False, separators=(',', ':'))
    return s.replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')


def payload(data):
    cfg = data['cfg']
    projects = []
    for p in data['projects']:
        links = []
        for l in p['links']:
            path = l['path']
            web = path.lower().startswith(('http://', 'https://'))
            q = os.path.expanduser(path)
            if not web and not os.path.isabs(q):
                q = os.path.join(data['root'], q)
            exists = web or os.path.exists(q)
            url = path if web else (('file://' + q.replace(' ', '%20')) if exists else '')
            links.append({'label': l['label'], 'path': path, 'url': url, 'exists': bool(exists)})
        item = {k: p[k] for k in ('id', 'name', 'short', 'line', 'status', 'basis', 'updated', 'question', 'stages', 'facts', 'blockers', 'next', 'retracted',
                                  'sources', 'related', 'deadline', 'counts', 'hyps', 'exps', 'age', 'body')}
        item['links'] = links
        projects.append(item)
    exps = []
    for e in data['exps']:
        exps.append({'id': e['id'], 'date': e['date'], 'title': e['title'], 'project': e['project'], 'kind': e['kind'], 'status': e['status'], 'setting': e['setting'],
                     'subject': e['subject'], 'task': e['task'], 'evidence': e['evidence'], 'backfilled': e['backfilled'], 'control': e['control'], 'tests': e['tests'],
                     'nRuns': e['n_runs'], 'nOk': e['n_ok'], 'cfg': e['cfg'], 'prediction': e['prediction'], 'falsifier': e['falsifier'], 'file': e['file'], 'body': e['body']})
    return {
        'title': cfg['title'], 'today': data['today'].isoformat(), 'generated': dt.datetime.now().strftime('%Y-%m-%d %H:%M'), 'staleDays': cfg['stale_days'],
        'lines': cfg['lines'], 'statusOrder': T.STATUS, 'projects': projects, 'hyps': [{k: v for k, v in h.items() if k != 'body'} for h in data['hyps']], 'exps': exps,
        'errors': data['errors'], 'audit': data['audit'], 'checksOff': cfg['checks_off'],
        'codes': {k: {'name': v[0], 'level': v[1], 'what': v[2]} for k, v in T.CODES.items()}, 'names': {},
    }


def render(data):
    page = '<!doctype html>\n<html lang="zh-CN">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width,initial-scale=1">\n'
    page += '<title>%s</title>\n<style>\n%s\n</style>\n</head>\n<body>\n' % (_esc(data['cfg']['title']), read_asset('css/tracker.css'))
    page += ('<div class="shell">\n  <nav class="side" aria-label="导航">\n    <div class="brand">%s<small id="today"></small></div>\n'
             '    <div><h4>总览</h4><button class="nv" type="button" data-go="home">全部课题</button>'
             '<button class="nv" type="button" data-go="hyps">假设台账</button><button class="nv" type="button" data-go="exps">实验记录</button>'
             '<button class="nv" type="button" data-go="errors">错误登记</button><button class="nv" type="button" data-go="audit">纪律检查</button>'
             '<button class="nv" type="button" data-go="how">怎么更新</button></div>\n    <div class="grp" id="navProjects"></div>\n  </nav>\n  <main id="main"></main>\n</div>\n') % _esc(data['cfg']['title'])
    page += '<script id="tracker-data" type="application/json">%s</script>\n' % json_for_script(payload(data))
    page += '<script>\nconst DATA = JSON.parse(document.getElementById("tracker-data").textContent);\n%s\n</script>\n</body>\n</html>\n' % read_asset('js/tracker.js').replace('</script', '<\\/script')
    return page


def _esc(s):
    return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def main(argv):
    args = argv[1:]
    out = today = None
    nolock = False
    rest = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == '--out' and i + 1 < len(args):
            out = args[i + 1]; i += 2
        elif a == '--today' and i + 1 < len(args):
            today = args[i + 1]; i += 2
        elif a == '--no-lock':
            nolock = True; i += 1
        else:
            rest.append(a); i += 1
    if len(rest) != 1:
        print('用法：python3 build.py <研究目录> [--out 文件] [--today 2026-11-25] [--no-lock]')
        return 2
    root = rest[0]
    td = T.parse_date(today) if today else None
    if today and td is None:
        print('--today 的格式不对，应为 2026-11-25')
        return 2
    prev = L.read(root)
    try:
        data = T.load_all(root, today=td, lock=prev)
    except T.TrackerError as e:
        print('有 %d 处必须修的错误，没有生成看板：' % len(e.errors))
        for x in e.errors:
            print('  ✗ ' + x)
        return 1
    page = render(data)
    dest = os.path.abspath(os.path.expanduser(out)) if out else os.path.join(data['root'], '看板.html')
    tmp = dest + '.tmp'
    try:
        with open(tmp, 'w', encoding='utf-8') as f:
            f.write(page)
        os.replace(tmp, dest)
    except OSError as e:
        print('写不了输出文件 %s：%s' % (dest, e))
        return 1
    added = 0
    if not nolock:
        try:
            added = L.write(data['root'], data['fingerprints'], prev)
        except OSError as e:
            print('提示：写不了 .tracker-lock.json（%s），预测被改动的检查本次不会生效。' % e)
    print('已生成 %s（%.1f KB）' % (dest, len(page.encode('utf-8')) / 1024))
    print(L.summary(data))
    if added:
        print('已登记 %d 个实验的预测指纹（.tracker-lock.json）。之后改动预测文字会被提醒。' % added)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
