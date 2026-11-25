"""lockfile：记下每个实验首次登记时的预测指纹，之后发现预测文字变了就提醒。也负责终端摘要。

指纹只存预测和判否条件的文字哈希之前的原文（很短），存放在 <根>/.tracker-lock.json。
这不是防篡改：用户随时可以删掉这个文件。它的作用是防止“无意中改了预测”。
"""
import json
import os

NAME = '.tracker-lock.json'


def read(root):
    p = os.path.join(os.path.abspath(os.path.expanduser(root)), NAME)
    try:
        with open(p, encoding='utf-8') as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def write(root, fingerprints, previous):
    """只追加新实验的指纹；已有的不覆盖（覆盖就失去了意义）。返回新增条数。"""
    merged = dict(previous)
    added = 0
    for k, v in fingerprints.items():
        if k not in merged:
            merged[k] = v
            added += 1
    p = os.path.join(os.path.abspath(os.path.expanduser(root)), NAME)
    tmp = p + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(merged, f, ensure_ascii=False, indent=1, sort_keys=True)
    os.replace(tmp, p)
    return added


def summary(data):
    items = data['audit']
    lines = ['课题 %d，假设 %d，实验 %d，错误登记 %d；今天按 %s 计算。' % (len(data['projects']), len(data['hyps']), len(data['exps']), len(data['errors']), data['today'])]
    warn = [x for x in items if x['level'] == 'warn']
    info = [x for x in items if x['level'] == 'info']
    lines.append('纪律检查：%d 条警告，%d 条提示。' % (len(warn), len(info)))
    by = {}
    for x in items:
        by.setdefault((x['level'], x['code'], x['name']), []).append(x)
    for (lvl, code, name), xs in sorted(by.items(), key=lambda kv: (kv[0][0] != 'warn', kv[0][1])):
        lines.append('  %s %s（%d）' % ('!' if lvl == 'warn' else 'i', name, len(xs)))
        for x in xs[:4]:
            lines.append('      %s：%s' % (x['file'], x['msg']))
        if len(xs) > 4:
            lines.append('      ……还有 %d 条' % (len(xs) - 4))
    return '\n'.join(lines)
