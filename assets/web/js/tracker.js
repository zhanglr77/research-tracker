// 研究追踪看板：纯原生脚本，数据由 build.py 以 JSON 内联。所有用户文本只经 textContent 或 h() 写入，不经 innerHTML，
// 唯一例外是笔记正文（body 字段），它在 Python 端已经转义并只生成白名单标签。
const $ = (s, r) => (r || document).querySelector(s);
function h(tag, attrs, kids) {
  const e = document.createElement(tag);
  if (attrs) for (const k in attrs) {
    const v = attrs[k];
    if (v == null || v === false) continue;
    if (k === 'class') e.className = v;
    else if (k === 'text') e.textContent = v;
    else if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v === true ? '' : v);
  }
  (kids || []).forEach(c => { if (c == null || c === false) return; e.appendChild(typeof c === 'string' ? document.createTextNode(c) : c); });
  return e;
}
const P = {}, X = {}, HY = {};
DATA.projects.forEach(p => P[p.id] = p);
DATA.exps.forEach(e => X[e.id] = e);
DATA.hyps.forEach(x => HY[x.id] = x);
const STAGE_LABEL = { done: '已完成', doing: '进行中', blocked: '受阻', todo: '未开始', unk: '无记录' };
const store = { get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }, set(k, v) { try { localStorage.setItem(k, v); } catch (e) {} } };
const pill = (cls, text) => h('span', { class: 'pill ' + cls, text });
function bar(c) {
  const tot = Object.values(c).reduce((a, b) => a + b, 0) || 1;
  return h('div', { class: 'bar', role: 'img', 'aria-label': '阶段：已完成 ' + c.done + '，进行中 ' + c.doing + '，受阻 ' + c.blocked + '，无记录 ' + c.unk + '，未开始 ' + c.todo },
    ['done', 'doing', 'blocked', 'unk', 'todo'].filter(k => c[k]).map(k => h('i', { class: 'b-' + k, style: 'width:' + (c[k] / tot * 100) + '%' })));
}
function ageText(p) { const d = p.age; return d <= 0 ? '今天' : d <= 30 ? d + ' 天前' : d <= 365 ? Math.round(d / 30) + ' 个月前' : '1 年以上'; }
const warnsOf = id => DATA.audit.filter(a => a.id === id && a.level === 'warn');
const auditN = (lvl) => DATA.audit.filter(a => a.level === lvl).length;
const NAMES = DATA.names;

function viewHome() {
  const v = h('div', { class: 'view' });
  const total = DATA.projects.length;
  const by = s => DATA.projects.filter(p => p.status === s).length;
  v.appendChild(h('div', null, [h('h1', { text: DATA.title }), h('p', { class: 'sub', text: '每个课题的状态和判断依据都来自笔记文件，没有记录的写「无近期记录」。点课题卡进入详情。' })]));
  v.appendChild(h('div', { class: 'sum' }, [
    h('div', null, [h('span', { text: '课题' }), h('strong', { text: String(total) })]),
    h('div', null, [h('span', { text: '进行中' }), h('strong', { text: String(by('进行中')) })]),
    h('div', null, [h('span', { text: '假设' }), h('strong', { text: String(DATA.hyps.length) })]),
    h('div', null, [h('span', { text: '实验' }), h('strong', { text: String(DATA.exps.length) })]),
    h('div', null, [h('span', { text: '错误登记' }), h('strong', { text: String(DATA.errors.length) })]),
    h('div', { class: auditN('warn') ? 'hot' : '' }, [h('span', { text: '纪律警告' }), h('strong', { text: String(auditN('warn')) })]),
  ]));
  DATA.projects.filter(p => p.deadline).forEach(p => {
    const days = Math.round((new Date(p.deadline.date) - new Date(DATA.today)) / 86400000);
    v.appendChild(h('div', { class: 'deadline' }, [h('strong', { text: p.deadline.date + '  ' }), p.deadline.what + '（' + p.name + '），距今天 ' + days + ' 天。']));
  });
  v.appendChild(h('div', { class: 'legend' }, [['done', '已完成'], ['doing', '进行中'], ['blocked', '受阻'], ['unk', '无记录'], ['todo', '未开始']].map(([k, t]) => h('span', null, [h('i', { style: 'background:var(--s-' + k + ')' }), t]))));
  DATA.lines.forEach(L => {
    const ps = DATA.projects.filter(p => p.line === L).sort((a, b) => DATA.statusOrder.indexOf(a.status) - DATA.statusOrder.indexOf(b.status) || a.age - b.age);
    if (!ps.length) return;
    const g = h('section', { class: 'group' }, [h('h2', null, [L, h('small', { text: ps.length + ' 个课题' })])]);
    const cards = h('div', { class: 'cards' });
    ps.forEach(p => {
      const open = p.stages.find(s => s.s === 'doing') || p.stages.find(s => s.s === 'blocked') || p.stages.find(s => s.s === 'todo');
      const w = DATA.audit.filter(a => a.level === 'warn' && (a.id === p.id || p.exps.includes(a.id) || p.hyps.includes(a.id))).length;
      cards.appendChild(h('button', { class: 'card', type: 'button', 'data-go': 'p:' + p.id }, [
        h('div', { class: 'top' }, [h('div', { class: 'nm', text: p.name }), pill('p-' + p.status, p.status)]),
        h('div', { class: 'q', text: p.question }),
        bar(p.counts),
        h('div', { class: 'meta' }, [
          h('span', { text: p.counts.done + ' / ' + p.stages.length + ' 阶段完成' }),
          h('span', { class: p.age > DATA.staleDays ? 'age-old' : '', text: '最后记录 ' + p.updated + '（' + ageText(p) + '）' }),
          p.exps.length ? h('span', { text: p.exps.length + ' 个实验' }) : null,
          w ? h('span', { class: 'age-old', text: w + ' 条纪律警告' }) : null]),
        open ? h('div', { class: 'meta', text: '当前：' + open.n }) : null,
        p.blockers.length ? h('div', { class: 'blk', text: '卡点：' + p.blockers[0] }) : null]));
    });
    g.appendChild(cards); v.appendChild(g);
  });
  if (!DATA.projects.length) v.appendChild(h('div', { class: 'empty', text: '还没有课题。复制 assets/templates/project.md 到 projects/ 目录，再重新生成。' }));
  return v;
}

function linkEl(l) {
  const web = /^https?:\/\//i.test(l.path);
  const label = l.url ? h('a', { href: l.url, text: l.label }) : h('span', { text: l.label });
  return h('li', null, [label, h('span', { class: 'pth', text: l.path }), l.exists || web ? null : h('span', { class: 'gone', text: '文件不存在' })]);
}

function viewProject(id) {
  const p = P[id]; const v = h('div', { class: 'view' });
  v.appendChild(h('div', { class: 'crumb' }, [h('button', { type: 'button', 'data-go': 'home', text: '← 全部课题' })]));
  v.appendChild(h('div', { class: 'hero' }, [h('h1', { text: p.name }),
    h('div', { class: 'row' }, [pill('p-' + p.status, p.status), h('span', { class: 'sub', text: '所属：' + p.line + ' · 最后记录 ' + p.updated })]),
    h('p', { class: 'sub', text: '状态依据：' + p.basis })]));
  if (p.deadline) v.appendChild(h('div', { class: 'deadline' }, [h('strong', { text: p.deadline.date + '  ' }), p.deadline.what]));
  v.appendChild(h('div', { class: 'panel' }, [h('h2', { text: '要回答的问题' }), h('p', { text: p.question })]));
  v.appendChild(h('div', { class: 'panel' }, [h('h2', { text: '阶段' }), bar(p.counts),
    h('ul', { class: 'timeline' }, p.stages.map(s => h('li', null, [h('span', { class: 'mk s-' + s.s, title: STAGE_LABEL[s.s] }),
      h('div', null, [h('b', { text: s.n }), h('span', { class: 'sl', text: STAGE_LABEL[s.s] }), s.note ? h('p', { class: 'note', text: s.note }) : null])])))]));
  if (p.facts.length) v.appendChild(h('div', { class: 'panel' }, [h('h2', { text: '已确认的内容与依据' }),
    h('ul', { class: 'facts' }, p.facts.map(f => h('li', null, [pill('ev-' + f.ev, f.ev), h('span', { text: f.t })])))]));
  const two = h('div', { class: 'two' });
  two.appendChild(h('div', { class: 'panel' }, [h('h2', { text: '卡点' }), p.blockers.length ? h('ul', { class: 'plain' }, p.blockers.map(t => h('li', { text: t }))) : h('p', { class: 'sub', text: '没有记录卡点。' })]));
  two.appendChild(h('div', { class: 'panel' }, [h('h2', { text: '下一步' }), p.next.length ? h('ul', { class: 'plain' }, p.next.map(t => h('li', { text: t }))) : h('p', { class: 'sub', text: '没有记录。' })]));
  v.appendChild(two);
  if (p.retracted.length) v.appendChild(h('div', { class: 'panel' }, [h('h2', { text: '已撤回，不要再引用' }), h('ul', { class: 'plain' }, p.retracted.map(t => h('li', { text: t })))]));
  const hs = p.hyps.map(i => HY[i]).filter(Boolean);
  if (hs.length) v.appendChild(h('div', { class: 'panel' }, [h('h2', { text: '相关假设' }),
    h('ul', { class: 'plain' }, hs.map(x => h('li', null, [h('button', { class: 'linkbtn', type: 'button', 'data-go': 'h:' + x.id, text: x.id }), ' ', pill('h-' + x.status, x.status), ' ' + x.statement])))]));
  const ev = p.exps.map(i => X[i]).filter(Boolean);
  if (ev.length) v.appendChild(h('div', { class: 'panel' }, [h('h2', { text: '相关实验' }),
    h('ul', { class: 'plain' }, ev.map(e => h('li', null, [h('button', { class: 'linkbtn', type: 'button', 'data-go': 'e:' + e.id, text: e.date + ' ' + e.title }), ' ', pill('x-' + e.status, e.status)])))]));
  const errs = DATA.errors.filter(e => e.affects.includes(p.id) || e.affects.some(a => p.exps.includes(a) || p.hyps.includes(a)));
  if (errs.length) v.appendChild(h('div', { class: 'panel' }, [h('h2', { text: '与本课题相关的错误登记' }),
    h('ul', { class: 'plain' }, errs.map(e => h('li', null, [h('button', { class: 'linkbtn', type: 'button', 'data-go': 'errors', text: e.id }), '：' + e.what])))]));
  if (p.links.length) v.appendChild(h('div', { class: 'panel' }, [h('h2', { text: '相关文件' }), h('ul', { class: 'links' }, p.links.map(linkEl)),
    h('p', { class: 'sub', style: 'margin-top:10px', text: '本机文件路径的链接只在生成看板的这台电脑上有效；网址链接不受影响。' })]));
  if (p.related.length) v.appendChild(h('div', { class: 'panel' }, [h('h2', { text: '相关课题' }),
    h('div', { class: 'relset' }, p.related.filter(r => P[r]).map(r => h('button', { class: 'linkbtn', type: 'button', 'data-go': 'p:' + r, text: P[r].name })))]));
  if (p.sources.length) v.appendChild(h('p', { class: 'sub', text: '本页依据：' + p.sources.join('；') }));
  if (p.body) { const d = h('div', { class: 'panel detail' }); d.innerHTML = p.body; v.appendChild(d); }
  return v;
}

// ---------- 实验 ----------
const selected = new Set(); let openId = null; let cmpOpen = false;
const flt = { q: '', kind: '', project: '', status: '', warn: '' };
const uniq = k => [...new Set(DATA.exps.map(e => e[k]))].filter(Boolean).sort();
function sel(label, key, opts, map) {
  const s = h('select', { id: 'f-' + key, onchange: ev => { flt[key] = ev.target.value; renderExps(); } }, [h('option', { value: '', text: '全部' }), ...opts.map(o => h('option', { value: o, text: map ? map(o) : o }))]);
  s.value = flt[key]; return h('label', { for: 'f-' + key }, [label, s]);
}
const resultSummary = e => !e.nRuns ? '无逐次记录' : e.nRuns + ' 次，完成 ' + e.nOk;
function expFlags(e) {
  return DATA.audit.filter(a => a.id === e.id).map(a => h('span', { class: a.level === 'warn' ? 'warn' : 'info', title: a.msg, text: a.name }));
}
function expRows() {
  return DATA.exps.filter(e => {
    if (flt.kind && e.kind !== flt.kind) return false;
    if (flt.project && e.project !== flt.project) return false;
    if (flt.status && e.status !== flt.status) return false;
    if (flt.warn === 'warn' && !warnsOf(e.id).length) return false;
    if (flt.warn === 'ok' && warnsOf(e.id).length) return false;
    if (flt.q && !(e.title + ' ' + e.setting + ' ' + e.subject + ' ' + e.task + ' ' + e.id).toLowerCase().includes(flt.q.toLowerCase())) return false;
    return true;
  });
}
function cmpTable(items) {
  const keys = []; items.forEach(e => e.cfg.forEach(r => { if (!keys.includes(r[0])) keys.push(r[0]); }));
  const t = h('table', { class: 'cmp' });
  t.appendChild(h('thead', null, [h('tr', null, [h('th', { text: '项' }), ...items.map(e => h('th', { text: e.date + ' ' + (e.setting || e.title) }))])]));
  const tb = h('tbody');
  [['日期', e => e.date], ['种类', e => e.kind], ['被测对象', e => e.subject || '—'], ['任务', e => e.task || '—'], ['次数', e => resultSummary(e)], ['预测', e => e.prediction || '（无）'], ['判否条件', e => e.falsifier || '（无）']]
    .forEach(([k, f]) => tb.appendChild(h('tr', { class: new Set(items.map(f)).size > 1 ? 'diff' : '' }, [h('td', { class: 'k', text: k }), ...items.map(e => h('td', { text: f(e) }))])));
  keys.forEach(k => {
    const vals = items.map(e => { const r = e.cfg.find(x => x[0] === k); return r ? r[1] : '无此项'; });
    tb.appendChild(h('tr', { class: new Set(vals).size > 1 ? 'diff' : '' }, [h('td', { class: 'k', text: k }), ...vals.map(x => h('td', { text: x }))]));
  });
  t.appendChild(tb); return t;
}
function updateCmp() {
  const n = selected.size; const b = $('#cmpBtn');
  if (b) { b.disabled = n < 2; b.textContent = n < 2 ? '选 2 条以上并排对比' : '并排对比 ' + n + ' 条'; }
  const c = $('#cmpBox'); if (!c) return; c.textContent = '';
  if (cmpOpen && n >= 2) {
    const items = [...selected].map(i => X[i]).filter(Boolean).sort((a, b) => a.date < b.date ? -1 : 1);
    c.appendChild(h('div', { class: 'panel' }, [h('h2', { text: '并排对比' }), h('p', { class: 'sub', text: '底色高亮的行表示这几条在该项上取值不同。把「不同」的项和结果放在一起看，才知道结果差异可能来自什么；如果配置里不同的项不止一个，就无法把差异归因给其中任何一个。' }), h('div', { class: 'scroll' }, [cmpTable(items)])]));
  }
}
function renderExps() {
  const box = $('#evbox'); box.textContent = '';
  const rows = expRows();
  const t = h('table', { class: 'ev' });
  t.appendChild(h('thead', null, [h('tr', null, ['选', '日期', '种类', '设置', '课题', '状态', '结果', '纪律提醒'].map(x => h('th', { text: x })))]));
  const tb = h('tbody');
  rows.forEach(e => {
    const cb = h('input', { type: 'checkbox', class: 'chk', 'aria-label': '选择 ' + e.title, onchange: ev => { ev.target.checked ? selected.add(e.id) : selected.delete(e.id); updateCmp(); } });
    cb.checked = selected.has(e.id);
    tb.appendChild(h('tr', { class: openId === e.id ? 'open' : '' }, [
      h('td', null, [cb]), h('td', { class: 'n', text: e.date }), h('td', { text: e.kind }),
      h('td', null, [h('button', { class: 'linkbtn', type: 'button', onclick: () => { openId = openId === e.id ? null : e.id; renderExps(); }, text: e.setting || e.title })]),
      h('td', { text: P[e.project] ? P[e.project].name : e.project }), h('td', null, [pill('x-' + e.status, e.status)]),
      h('td', { class: 'n', text: resultSummary(e) }), h('td', null, expFlags(e))]));
    if (openId === e.id) {
      const d = h('div', { class: 'detail' }); d.innerHTML = e.body;
      const meta = [h('span', null, ['课题：', P[e.project] ? P[e.project].name : e.project]), e.evidence ? h('span', null, [' · 证据：', pill('ev-' + e.evidence, e.evidence)]) : null,
        e.tests.length ? h('span', { text: ' · 检验假设：' + e.tests.join('、') }) : null, e.control ? h('span', { text: ' · 对照：' + e.control }) : null,
        h('span', { class: 'pth', text: ' · ' + e.file })];
      d.insertBefore(h('p', { class: 'sub' }, meta), d.firstChild);
      tb.appendChild(h('tr', null, [h('td', { colspan: '8', style: 'padding:0;border:0' }, [d])]));
    }
  });
  t.appendChild(tb);
  if (!rows.length) box.appendChild(h('div', { class: 'empty', text: DATA.exps.length ? '没有符合筛选条件的记录。' : '还没有实验。复制 assets/templates/experiment.md 到 experiments/ 目录。' }));
  else box.appendChild(h('div', { class: 'scroll' }, [t]));
  updateCmp();
}
function viewExps() {
  const v = h('div', { class: 'view' });
  v.appendChild(h('div', null, [h('h1', { text: '实验记录' }), h('p', { class: 'sub', text: '每次实验一份笔记，一种设置一条。预测和判否条件在开跑之前写，写完不改。「待补」是当时没记下的项，不是 0。' })]));
  const noPred = DATA.audit.filter(a => a.code === 'no-prediction').length, late = DATA.audit.filter(a => a.code === 'late-prediction').length;
  v.appendChild(h('div', { class: 'sum' }, [
    h('div', null, [h('span', { text: '记录' }), h('strong', { text: String(DATA.exps.length) })]),
    h('div', { class: noPred ? 'hot' : '' }, [h('span', { text: '无事前预测' }), h('strong', { text: String(noPred) })]),
    h('div', { class: late ? 'hot' : '' }, [h('span', { text: '预测晚于开跑' }), h('strong', { text: String(late) })]),
    h('div', null, [h('span', { text: '回填' }), h('strong', { text: String(DATA.exps.filter(e => e.backfilled).length) })])]));
  const bf = DATA.exps.filter(e => e.backfilled);
  if (bf.length) v.appendChild(h('div', { class: 'warnbar', text: '其中 ' + bf.length + ' 条（标「回填」）是事后补记的，不是当时按模板记的：没有事前预测，配置里可能有「待补」。把它们当线索，不当结论。' }));
  v.appendChild(h('div', { class: 'filters' }, [
    h('label', { for: 'f-q' }, ['搜索', h('input', { type: 'search', id: 'f-q', value: flt.q, placeholder: '设置、任务、对象', oninput: ev => { flt.q = ev.target.value; renderExps(); } })]),
    sel('课题', 'project', [...new Set(DATA.exps.map(e => e.project))], id => P[id] ? P[id].name : id), sel('种类', 'kind', uniq('kind')), sel('状态', 'status', uniq('status')),
    sel('纪律', 'warn', ['warn', 'ok'], x => x === 'warn' ? '有警告' : '无警告'),
    h('button', { class: 'btn', id: 'cmpBtn', type: 'button', disabled: true, onclick: () => { cmpOpen = !cmpOpen; updateCmp(); }, text: '选 2 条以上并排对比' }),
    h('button', { class: 'btn', type: 'button', onclick: () => { Object.keys(flt).forEach(k => flt[k] = ''); selected.clear(); cmpOpen = false; openId = null; go('exps', true); }, text: '清除筛选' })]));
  v.appendChild(h('div', { id: 'cmpBox' })); v.appendChild(h('div', { id: 'evbox' }));
  return v;
}

// ---------- 假设台账 ----------
function viewHyps() {
  const v = h('div', { class: 'view' });
  v.appendChild(h('div', null, [h('h1', { text: '假设台账' }), h('p', { class: 'sub', text: '每条假设写成「如果它为真会看到什么，看到什么就不成立」。没有反面的假设无法被检验，会被标出来。' })]));
  const cnt = s => DATA.hyps.filter(x => x.status === s).length;
  v.appendChild(h('div', { class: 'sum' }, ['待检验', '支持', '部分', '反对', '推翻'].map(s => h('div', null, [h('span', { text: s }), h('strong', { text: String(cnt(s)) })]))));
  if (!DATA.hyps.length) v.appendChild(h('div', { class: 'empty', text: '还没有假设。复制 assets/templates/hypothesis.md 到 hypotheses/ 目录。' }));
  DATA.hyps.forEach(x => {
    const exps = DATA.exps.filter(e => e.tests.includes(x.id));
    const kv = h('dl', { class: 'kv' }, [
      h('dt', { text: '假设' }), h('dd', { text: x.statement }),
      h('dt', { text: '反面' }), x.converse && !/^(待补|无|没有)$/.test(x.converse.trim()) ? h('dd', { text: x.converse }) : h('dd', { class: 'miss', text: '没写。没有反面就无法证伪。' }),
      h('dt', { text: '判据' }), x.criterion && !/^(待补|无|没有)$/.test(x.criterion.trim()) ? h('dd', { text: x.criterion }) : h('dd', { class: 'miss', text: '没写。' }),
      x.result ? h('dt', { text: '结论' }) : null, x.result ? h('dd', { text: x.result }) : null,
      h('dt', { text: '实验' }), h('dd', null, exps.length ? exps.flatMap((e, i) => [i ? '、' : '', h('button', { class: 'linkbtn', type: 'button', 'data-go': 'e:' + e.id, text: e.id })]) : [h('span', { class: x.status === '待检验' ? '' : 'miss', text: '没有实验指向它' })])]);
    v.appendChild(h('div', { class: 'panel hyp', id: 'hyp-' + x.id }, [
      h('div', { class: 'row' }, [h('h2', { style: 'margin:0', text: x.id }), pill('h-' + x.status, x.status), h('span', { class: 'sub', text: (P[x.project] ? P[x.project].name : x.project) + ' · 更新 ' + x.updated }), ...warnsOf(x.id).map(a => h('span', { class: 'warn', title: a.msg, text: a.name }))]),
      kv]));
  });
  return v;
}

// ---------- 错误登记 ----------
function viewErrors() {
  const v = h('div', { class: 'view' });
  v.appendChild(h('div', null, [h('h1', { text: '错误登记' }), h('p', { class: 'sub', text: '自己发现并改掉的做法、说法和数字。登记得越具体，别人越能信任没登记的部分。不要删旧条目，数字更正了就再登记一条。' })]));
  if (!DATA.errors.length) v.appendChild(h('div', { class: 'empty', text: '还没有登记。这不等于没有错误：复制 assets/templates/error.md 到 errors/ 目录，把你最近改过的一个数字或结论写进去。' }));
  DATA.errors.slice().sort((a, b) => a.date < b.date ? 1 : -1).forEach(e => v.appendChild(h('div', { class: 'panel hyp' }, [
    h('div', { class: 'row' }, [h('h2', { style: 'margin:0', text: e.id }), h('span', { class: 'sub', text: e.date })]),
    h('dl', { class: 'kv' }, [h('dt', { text: '错在哪' }), h('dd', { text: e.what }), h('dt', { text: '怎么发现' }), h('dd', { text: e.found_by }), h('dt', { text: '怎么处理' }), h('dd', { text: e.fix }),
      e.affects.length ? h('dt', { text: '影响' }) : null, e.affects.length ? h('dd', null, e.affects.flatMap((a, i) => [i ? '、' : '', X[a] ? h('button', { class: 'linkbtn', type: 'button', 'data-go': 'e:' + a, text: a }) : HY[a] ? h('button', { class: 'linkbtn', type: 'button', 'data-go': 'h:' + a, text: a }) : P[a] ? h('button', { class: 'linkbtn', type: 'button', 'data-go': 'p:' + a, text: a }) : a])) : null])])));
  return v;
}

// ---------- 纪律检查 ----------
function viewAudit() {
  const v = h('div', { class: 'view' });
  v.appendChild(h('div', null, [h('h1', { text: '纪律检查' }), h('p', { class: 'sub', text: '看板不只显示进度，也检查这套方法的纪律有没有被守住：预测是否先写、假设有没有反面、已完成的实验有没有审查。警告不是处罚，是告诉你哪里的结论还不能当结论。' })]));
  const by = {}; DATA.audit.forEach(a => { (by[a.code] = by[a.code] || { name: a.name, level: a.level, items: [] }).items.push(a); });
  v.appendChild(h('div', { class: 'sum' }, [h('div', { class: auditN('warn') ? 'hot' : '' }, [h('span', { text: '警告' }), h('strong', { text: String(auditN('warn')) })]), h('div', null, [h('span', { text: '提示' }), h('strong', { text: String(auditN('info')) })]), h('div', null, [h('span', { text: '检查项' }), h('strong', { text: String(Object.keys(DATA.codes).length - DATA.checksOff.length) })])]));
  if (DATA.checksOff.length) v.appendChild(h('div', { class: 'warnbar', text: '已在 tracker.yaml 里关闭的检查：' + DATA.checksOff.map(c => DATA.codes[c].name).join('、') + '。' }));
  if (!DATA.audit.length) v.appendChild(h('div', { class: 'empty', text: '没有发现问题。' }));
  Object.keys(by).sort((a, b) => (by[a].level === 'warn' ? 0 : 1) - (by[b].level === 'warn' ? 0 : 1) || (a < b ? -1 : 1)).forEach(code => {
    const g = by[code];
    v.appendChild(h('div', { class: 'panel' }, [h('div', { class: 'row' }, [h('h2', { style: 'margin:0', text: g.name }), h('span', { class: g.level === 'warn' ? 'warn' : 'info', text: g.level === 'warn' ? '警告' : '提示' }), h('span', { class: 'sub', text: g.items.length + ' 条' })]),
      h('p', { class: 'sub', style: 'margin-top:6px', text: DATA.codes[code].what }),
      h('ul', { class: 'aud' }, g.items.map(a => h('li', null, [h('span', { class: 'pth', text: a.file }), h('span', null, [a.msg, a.id ? h('span', null, [' ', h('button', { class: 'linkbtn', type: 'button', 'data-go': (X[a.id] ? 'e:' : HY[a.id] ? 'h:' : P[a.id] ? 'p:' : 'audit:') + a.id, text: '查看' })]) : null])])))]));
  });
  return v;
}

function viewHow() {
  const v = h('div', { class: 'view' });
  v.appendChild(h('div', null, [h('h1', { text: '怎么更新这个页面' }), h('p', { class: 'sub', text: '页面是从笔记文件生成的。你不用改 HTML：改笔记，重新生成。' })]));
  v.appendChild(h('div', { class: 'panel howto' }, [h('h2', { text: '日常流程' }), h('ol', null, [
    h('li', { text: '新实验：复制 assets/templates/experiment.md 到 experiments/，先写预测和判否条件并存盘，再开跑。' }),
    h('li', { text: '跑完：只追加「结果」「判定」「审查」，不改预测。要更正，写在审查里，或登记一条错误。' }),
    h('li', { text: '新假设：复制 hypothesis.md 到 hypotheses/，先写反面。' }),
    h('li', { text: '发现自己错了：复制 error.md 到 errors/。' }),
    h('li', { text: '重新生成页面。' })]), h('pre', { class: 'cmdline', text: 'python3 <skill>/scripts/build.py <你的研究目录>' })]));
  v.appendChild(h('div', { class: 'panel' }, [h('h2', { text: '课题 id' }), h('div', { class: 'scroll' }, [h('table', { class: 'ev' }, [h('thead', null, [h('tr', null, ['id', '课题', '所属'].map(x => h('th', { text: x })))]),
    h('tbody', null, DATA.projects.map(p => h('tr', null, [h('td', { class: 'n', text: p.id }), h('td', { text: p.name }), h('td', { text: p.line })])))])])]));
  v.appendChild(h('p', { class: 'sub', text: '状态判断是读笔记得出的。笔记没更新，页面就显示「无近期记录」，这不等于课题没有进展。生成时间：' + DATA.generated }));
  return v;
}

function renderNav() {
  const box = $('#navProjects'); box.textContent = '';
  DATA.lines.forEach(L => {
    const ps = DATA.projects.filter(p => p.line === L); if (!ps.length) return;
    box.appendChild(h('h4', { text: L }));
    ps.forEach(p => box.appendChild(h('button', { class: 'nv', type: 'button', 'data-go': 'p:' + p.id }, [h('span', { class: 'dot st-' + p.status }), p.name])));
  });
}
function setCurrent(route) { document.querySelectorAll('nav.side button.nv').forEach(b => b.setAttribute('aria-current', String(b.getAttribute('data-go') === route))); }
function go(route, keep) {
  let r = route; let scrollTo = null;
  if (r.startsWith('e:')) { const e = X[r.slice(2)]; openId = e ? e.id : null; r = 'exps'; }
  else if (r.startsWith('h:')) { scrollTo = 'hyp-' + r.slice(2); r = 'hyps'; }
  else if (r.startsWith('audit:')) { r = 'audit'; }
  const main = $('#main'); main.textContent = '';
  let view;
  if (r === 'home') view = viewHome(); else if (r === 'exps') view = viewExps(); else if (r === 'hyps') view = viewHyps(); else if (r === 'errors') view = viewErrors();
  else if (r === 'audit') view = viewAudit(); else if (r === 'how') view = viewHow();
  else if (r.startsWith('p:') && P[r.slice(2)]) view = viewProject(r.slice(2)); else { r = 'home'; view = viewHome(); }
  main.appendChild(view);
  if (r === 'exps') renderExps();
  setCurrent(r);
  const hash = r === 'home' ? '' : (r.startsWith('p:') ? 'p-' + r.slice(2) : r);
  if (!keep && location.hash.slice(1) !== hash) { try { history.replaceState(null, '', hash ? '#' + hash : location.pathname + location.search); } catch (e) {} }
  store.set('lastRoute', r);
  const t = scrollTo && document.getElementById(scrollTo);
  if (t) t.scrollIntoView(); else window.scrollTo(0, 0);
}
function fromHash() { const x = location.hash.slice(1); if (!x) return null; if (x.startsWith('p-')) return 'p:' + x.slice(2); return ['exps', 'hyps', 'errors', 'audit', 'how'].includes(x) ? x : null; }
document.addEventListener('click', ev => { const t = ev.target.closest('[data-go]'); if (t) { ev.preventDefault(); go(t.getAttribute('data-go')); } });
window.addEventListener('hashchange', () => { const r = fromHash(); go(r || 'home', true); });
$('#today').textContent = '数据日期 ' + DATA.today;
renderNav();
go(fromHash() || 'home', true);
