"""md：研究看板笔记正文的 Markdown 子集渲染，只依赖标准库。

支持：# 标题（正文里的 # 降一级成 h3 起）、段落、引用块、无序列表、有序列表、表格、``` 代码块、
行内 `code`、**粗体**、[文字](链接)。所有文本先转义，再加标签，所以笔记里的尖括号不会变成 HTML。
链接只放行 http(s)://、相对路径和 #锚点，其余（javascript: 等）一律去掉链接只留文字。
"""
from __future__ import annotations
import html
import re


def esc(t):
    return html.escape(t, quote=True)


_SAFE = re.compile(r'^(https?://|#|\./|\.\./|/|[A-Za-z0-9_\-一-鿿][^:]*$)', re.I)


def _link(m):
    text, url = m.group(1), html.unescape(m.group(2)).strip()
    if _SAFE.match(url) and not re.match(r'^\s*(javascript|data|vbscript):', url, re.I):
        return '<a href="%s">%s</a>' % (esc(url), text)
    return text


def inline(t):
    t = esc(t)
    t = re.sub(r'`([^`]+)`', r'<code>\1</code>', t)
    t = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', t)
    t = re.sub(r'\[([^\]]+)\]\(([^)\s]+)\)', _link, t)
    return t.replace('待补', '<span class="tbd">待补</span>')


def split_row(line):
    return [c.strip() for c in line.strip().strip('|').split('|')]


def is_sep(line):
    return bool(re.match(r'^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$', line))


def render(body):
    out, para = [], []
    lines = body.split('\n')
    i = 0

    def flush():
        if para:
            out.append('<p>' + inline(' '.join(para)) + '</p>')
            para.clear()

    while i < len(lines):
        ln = lines[i]
        if ln.strip().startswith('```'):
            flush()
            i += 1
            buf = []
            while i < len(lines) and not lines[i].strip().startswith('```'):
                buf.append(lines[i])
                i += 1
            i += 1
            out.append('<pre class="code">%s</pre>' % esc('\n'.join(buf)))
            continue
        if not ln.strip():
            flush()
            i += 1
            continue
        m = re.match(r'^(#{1,4})\s+(.*)$', ln)
        if m:
            flush()
            level = len(m.group(1))
            if level >= 2:
                out.append('<h%d>%s</h%d>' % (level + 1, inline(m.group(2)), level + 1))
            i += 1
            continue
        if ln.lstrip().startswith('>'):
            flush()
            buf = []
            while i < len(lines) and lines[i].lstrip().startswith('>'):
                buf.append(lines[i].lstrip()[1:].strip())
                i += 1
            out.append('<blockquote>' + ''.join('<p>%s</p>' % inline(b) for b in buf if b) + '</blockquote>')
            continue
        if ln.lstrip().startswith('|') and i + 1 < len(lines) and is_sep(lines[i + 1]):
            flush()
            head = split_row(ln)
            i += 2
            rows = []
            while i < len(lines) and lines[i].lstrip().startswith('|'):
                rows.append(split_row(lines[i]))
                i += 1
            th = ''.join('<th>%s</th>' % inline(c) for c in head)
            tb = ''.join('<tr>' + ''.join('<td>%s</td>' % inline(c) for c in r) + '</tr>' for r in rows)
            out.append('<div class="scroll"><table><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>' % (th, tb))
            continue
        if re.match(r'^\s*[-*]\s+', ln):
            flush()
            items = []
            while i < len(lines) and re.match(r'^\s*[-*]\s+', lines[i]):
                items.append(re.sub(r'^\s*[-*]\s+', '', lines[i]))
                i += 1
            out.append('<ul>' + ''.join('<li>%s</li>' % inline(t) for t in items) + '</ul>')
            continue
        if re.match(r'^\s*\d+[.)]\s+', ln):
            flush()
            items = []
            while i < len(lines) and re.match(r'^\s*\d+[.)]\s+', lines[i]):
                items.append(re.sub(r'^\s*\d+[.)]\s+', '', lines[i]))
                i += 1
            out.append('<ol>' + ''.join('<li>%s</li>' % inline(t) for t in items) + '</ol>')
            continue
        para.append(ln.strip())
        i += 1
    flush()
    return '\n'.join(out)


def sections(body):
    """返回 {二级标题: 该节文本}"""
    secs, cur, buf = {}, None, []
    for ln in body.split('\n'):
        m = re.match(r'^##\s+(.*)$', ln)
        if m:
            if cur is not None:
                secs[cur] = '\n'.join(buf)
            cur, buf = m.group(1).strip(), []
        elif cur is not None:
            buf.append(ln)
    if cur is not None:
        secs[cur] = '\n'.join(buf)
    return secs


def table_rows(text):
    """第一张表的数据行（去掉表头和分隔行），每行是单元格列表。"""
    rows, seen_head, started = [], False, False
    for ln in text.split('\n'):
        if not ln.lstrip().startswith('|'):
            if started:
                break
            continue
        started = True
        if not seen_head:
            seen_head = True
            continue
        if is_sep(ln):
            continue
        rows.append(split_row(ln))
    return rows


def table_head(text):
    for ln in text.split('\n'):
        if ln.lstrip().startswith('|'):
            return split_row(ln)
    return []
