"""miniyaml：研究看板笔记 frontmatter 用的 YAML 子集解析器，只依赖标准库。

支持：块映射；块列表（元素可以是标量、流式映射 {a: b}，或 "- key: value" 开头的块映射）；
流式列表 [a, b]；双引号/单引号字符串；| 和 > 块标量（末尾换行一律去掉）；# 注释；
true/false/null/整数/浮点数。日期不转换，保持字符串。
不支持：锚点、标签、多文档、多行的流式集合、复杂键。遇到不支持的写法会报错并给出行号，不会静默读错。
"""
from __future__ import annotations
import re


class YamlError(ValueError):
    pass


_INT = re.compile(r'^[-+]?(0|[1-9][0-9]*)$')
_FLT = re.compile(r'^[-+]?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][-+]?[0-9]+)?$')
_ESC = {'n': '\n', 't': '\t', 'r': '\r', '0': '\0', '"': '"', '\\': '\\', '/': '/'}
_KEYSEP = re.compile(r':(?:\s|$)')
_BLOCK = re.compile(r'^[|>][+-]?$')


def _plain(s):
    s = s.strip()
    if s in ('', '~', 'null', 'Null', 'NULL'):
        return None
    if s in ('true', 'True', 'TRUE'):
        return True
    if s in ('false', 'False', 'FALSE'):
        return False
    if _INT.match(s):
        return int(s)
    if _FLT.match(s):
        return float(s)
    return s


def _sp(s, p):
    while p < len(s) and s[p] == ' ':
        p += 1
    return p


def _dq(s, p, ln):
    out, i = [], p + 1
    while i < len(s):
        c = s[i]
        if c == '\\':
            i += 1
            e = s[i:i + 1]
            if e in _ESC:
                out.append(_ESC[e])
            elif e == 'u' and re.match(r'[0-9a-fA-F]{4}$', s[i + 1:i + 5]):
                out.append(chr(int(s[i + 1:i + 5], 16)))
                i += 4
            elif e == 'x' and re.match(r'[0-9a-fA-F]{2}$', s[i + 1:i + 3]):
                out.append(chr(int(s[i + 1:i + 3], 16)))
                i += 2
            else:
                raise YamlError('第 %d 行：双引号字符串里有不认识的转义 \\%s（Windows 路径请用单引号，或把反斜杠写成两个）' % (ln, e))
        elif c == '"':
            return ''.join(out), i + 1
        else:
            out.append(c)
        i += 1
    raise YamlError('第 %d 行：双引号字符串没有结束' % ln)


def _sq(s, p, ln):
    out, i = [], p + 1
    while i < len(s):
        if s[i] == "'":
            if s[i + 1:i + 2] == "'":
                out.append("'")
                i += 2
                continue
            return ''.join(out), i + 1
        out.append(s[i])
        i += 1
    raise YamlError('第 %d 行：单引号字符串没有结束' % ln)


def _quoted(s, p, ln):
    return _dq(s, p, ln) if s[p] == '"' else _sq(s, p, ln)


def _value(s, p, ln, in_flow):
    p = _sp(s, p)
    if p >= len(s):
        raise YamlError('第 %d 行：缺少值' % ln)
    c = s[p]
    if c in '"\'':
        return _quoted(s, p, ln)
    if c == '[':
        return _flow_list(s, p, ln)
    if c == '{':
        return _flow_map(s, p, ln)
    if in_flow:
        q = p
        while q < len(s) and s[q] not in ',]}':
            q += 1
        return _plain(s[p:q]), q
    return _plain(re.sub(r'\s+#.*$', '', s[p:])), len(s)


def _flow_list(s, p, ln):
    out, p = [], p + 1
    while True:
        p = _sp(s, p)
        if p >= len(s):
            raise YamlError('第 %d 行：[ 没有对应的 ]（多行的流式列表不支持，请改成块列表）' % ln)
        if s[p] == ']':
            return out, p + 1
        v, p = _value(s, p, ln, True)
        out.append(v)
        p = _sp(s, p)
        if s[p:p + 1] == ',':
            p += 1
        elif s[p:p + 1] != ']':
            raise YamlError('第 %d 行：流式列表里缺少逗号或 ]' % ln)


def _flow_map(s, p, ln):
    out, p = {}, p + 1
    while True:
        p = _sp(s, p)
        if p >= len(s):
            raise YamlError('第 %d 行：{ 没有对应的 }（多行的流式映射不支持，请改成块映射）' % ln)
        if s[p] == '}':
            return out, p + 1
        if s[p] in '"\'':
            k, p = _quoted(s, p, ln)
            p = _sp(s, p)
            if s[p:p + 1] != ':':
                raise YamlError('第 %d 行：流式映射的键后面缺少冒号' % ln)
            p += 1
        else:
            m = _KEYSEP.search(s, p)
            if not m:
                raise YamlError('第 %d 行：流式映射里缺少 "键: 值"（冒号后要有空格）' % ln)
            k, p = s[p:m.start()].strip(), m.end()
        if k in out:
            raise YamlError('第 %d 行：重复的键 %s' % (ln, k))
        out[k], p = _value(s, p, ln, True)
        p = _sp(s, p)
        if s[p:p + 1] == ',':
            p += 1
        elif s[p:p + 1] != '}':
            raise YamlError('第 %d 行：流式映射里缺少逗号或 }' % ln)


def _inline(s, ln):
    v, p = _value(s, 0, ln, False)
    rest = s[p:].strip()
    if rest and not rest.startswith('#'):
        raise YamlError('第 %d 行：值的后面有多余内容：%s' % (ln, rest[:30]))
    return v


def _split_key(c, ln):
    """c 是 "键: 值" 形式就返回 (键, 值文本)，否则返回 None。"""
    if c[0] in '"\'':
        try:
            k, p = _quoted(c, 0, ln)
        except YamlError:
            return None
        rest = c[p:].lstrip(' ')
        if not rest.startswith(':'):
            return None
        rest = rest[1:].strip()
    else:
        m = _KEYSEP.search(c)
        if not m or c[0] in '[{':
            return None
        k, rest = c[:m.start()].strip(), c[m.end():].strip()
        if k == '':
            return None
    return k, ('' if rest.startswith('#') else rest)


def _is_item(c):
    return c == '-' or c.startswith('- ')


class _Parser:
    def __init__(self, text):
        self.raw = text.replace('\r\n', '\n').replace('\r', '\n').split('\n')
        self.i = 0

    def peek(self):
        """跳过空行和注释行，返回 (行号下标, 缩进, 去掉缩进的内容)，没有了返回 None。"""
        while self.i < len(self.raw):
            line = self.raw[self.i].rstrip()
            s = line.lstrip(' \t')
            if s == '' or s.startswith('#'):
                self.i += 1
                continue
            lead = line[:len(line) - len(s)]
            if '\t' in lead:
                raise YamlError('第 %d 行：缩进里有制表符，请改用空格' % (self.i + 1))
            return self.i, len(lead), s
        return None

    def node(self, indent):
        pk = self.peek()
        return self.list(indent) if _is_item(pk[2]) else self.map(indent)

    def map(self, indent):
        m = {}
        while True:
            pk = self.peek()
            if pk is None:
                break
            idx, ind, c = pk
            if ind < indent or (ind == indent and _is_item(c)):
                break
            if ind > indent:
                raise YamlError('第 %d 行：缩进和上一行不一致' % (idx + 1))
            sk = _split_key(c, idx + 1)
            if sk is None:
                raise YamlError('第 %d 行：这一行不是 "键: 值" 形式：%s' % (idx + 1, c[:40]))
            key, rest = sk
            if key in m:
                raise YamlError('第 %d 行：重复的键 %s' % (idx + 1, key))
            self.i = idx + 1
            if rest == '':
                nx = self.peek()
                if nx is not None and nx[1] == indent and _is_item(nx[2]):
                    m[key] = self.list(indent)
                elif nx is not None and nx[1] > indent:
                    m[key] = self.node(nx[1])
                else:
                    m[key] = None
            elif _BLOCK.match(rest):
                m[key] = self.block(rest, indent)
            else:
                m[key] = _inline(rest, idx + 1)
        return m

    def list(self, indent):
        out = []
        while True:
            pk = self.peek()
            if pk is None:
                break
            idx, ind, c = pk
            if ind > indent:
                raise YamlError('第 %d 行：缩进和上一行不一致' % (idx + 1))
            if ind < indent or not _is_item(c):
                break
            after = c[1:].lstrip(' ')
            lead = len(c) - len(after)
            if after.startswith('#'):
                after = ''
            self.i = idx + 1
            if after == '':
                nx = self.peek()
                out.append(self.node(nx[1]) if (nx is not None and nx[1] > indent) else None)
            elif _split_key(after, idx + 1) is not None:
                self.raw[idx] = ' ' * (indent + lead) + after
                self.i = idx
                out.append(self.map(indent + lead))
            elif _BLOCK.match(after):
                out.append(self.block(after, indent))
            else:
                out.append(_inline(after, idx + 1))
        return out

    def block(self, header, parent):
        lines, bi, j = [], None, self.i
        while j < len(self.raw):
            line = self.raw[j].rstrip()
            if line.strip() == '':
                lines.append('')
                j += 1
                continue
            ind = len(line) - len(line.lstrip(' '))
            if bi is None:
                if ind <= parent:
                    break
                bi = ind
            if ind < bi:
                break
            lines.append(line[bi:])
            j += 1
        self.i = j
        while lines and lines[-1] == '':
            lines.pop()
        if header[0] == '|':
            return '\n'.join(lines)
        text = ''
        for x in lines:
            text += '\n' if x == '' else (' ' if text and not text.endswith('\n') else '') + x
        return text


def load(text):
    """把一段 YAML 子集文本读成 dict。"""
    p = _Parser(text)
    pk = p.peek()
    if pk is None:
        return {}
    if pk[1] != 0 or _is_item(pk[2]):
        raise YamlError('第 %d 行：frontmatter 必须是顶格的 "键: 值" 形式' % (pk[0] + 1))
    d = p.map(0)
    nx = p.peek()
    if nx is not None:
        raise YamlError('第 %d 行：无法解析（缩进不对，或列表没有跟在某个键后面）' % (nx[0] + 1))
    return d


def split_frontmatter(text):
    """返回 (frontmatter 文本或 None, 正文)。frontmatter 是开头被两行 --- 夹住的部分。"""
    text = text.lstrip('\ufeff').replace('\r\n', '\n')
    lines = text.split('\n')
    if not lines or lines[0].rstrip() != '---':
        return None, text
    for k in range(1, len(lines)):
        if lines[k].rstrip() == '---':
            return '\n'.join(lines[1:k]), '\n'.join(lines[k + 1:])
    raise YamlError('开头有 --- 但没有找到结束的 ---')


def load_note(text):
    """读一份笔记，返回 (frontmatter dict, 正文)。没有 frontmatter 时 dict 为空。"""
    fm, body = split_frontmatter(text)
    return (load(fm) if fm is not None else {}), body


_NEEDQ = re.compile(r'''^[\s\-?:,\[\]{}#&*!|>'"%@`]|:\s|:$|\s#|\s$|[\n\t\\]''')


def dump_scalar(v):
    """把一个标量写成 frontmatter 里能读回原值的文本。"""
    if v is None:
        return 'null'
    if v is True:
        return 'true'
    if v is False:
        return 'false'
    if isinstance(v, (int, float)):
        return repr(v)
    s = str(v)
    q = _plain(s)
    if s == '' or not isinstance(q, str) or q != s or _NEEDQ.search(s):
        return '"' + s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\t', '\\t') + '"'
    return s
