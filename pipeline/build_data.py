"""Transforma os dados coletados nos arquivos do site (funções puras, testáveis)."""
import re, json, collections
from classify import group, GROUPS, V_PL, V_PLC, V_ELO, V_PDL, V_PR, V_IND, V_MOC, V_RI, V_RQ
import ext

PROP_KEYS = {V_PL: 'pl', V_PLC: 'plc', V_ELO: 'pelom', V_PDL: 'pdl', V_PR: 'pr', V_IND: 'ind', V_MOC: 'moc', V_RI: 'ri', V_RQ: 'rq'}
MINREP = 3


def year_of(num):  # '12177/2026' -> 2026
    m = re.search(r'/(\d{4})\s*$', num)
    return int(m.group(1)) if m else 0


def short_date(d):  # dd/mm/yyyy -> dd/mm/yy
    m = re.match(r'(\d\d)/(\d\d)/\d\d(\d\d)', d or '')
    return '%s/%s/%s' % m.groups() if m else ''


def rle(chars):
    out, i = [], 0
    while i < len(chars):
        j = i
        while j < len(chars) and chars[j] == chars[i]: j += 1
        out.append(chars[i] + (str(j - i) if j - i > 1 else ''))
        i = j
    return ''.join(out)


def presenca_lines(pres, canon_idx, n):
    """pres: {'2025-2': [[nome, faltas, abonadas, total], ...]} -> (months, linhas)"""
    keys = sorted((k for k, r in pres.items() if r), key=lambda k: tuple(map(int, k.split('-'))))
    months = [list(map(int, k.split('-'))) for k in keys]
    cells = [['.'] * len(keys) for _ in range(n)]
    for c, k in enumerate(keys):
        for nome, f, a, t in pres[k]:
            cells[canon_idx[nome]][c] = '%d/%d' % (f, a)
    return months, [','.join(x) for x in cells]


def num_key(r):  # (ano, número) da proposta
    m = re.match(r'(\d+)\D*/(\d{4})', r[1])
    return (int(m.group(2)), int(m.group(1))) if m else (0, 0)


def date_key(r):
    m = re.match(r'(\d\d)/(\d\d)/(\d{4})', r[4] or '')
    return (m.group(3) + m.group(2) + m.group(1)) if m else ''


def props_outputs(rows, n):
    """rows: [view, num, href, ementa, data, [idx autores]] na ordem oficial."""
    per = [collections.defaultdict(lambda: [0, 0]) for _ in range(n)]
    grp = [{g: [0, 0] for g in GROUPS} for _ in range(n)]
    lists = [{g: [] for g in GROUPS} for _ in range(n)]
    rows = sorted(rows, key=num_key, reverse=True)
    for view, num, href, em, dt, au in rows:
        y = year_of(num)
        g = group(view, em)
        k = 0 if y == 2025 else 1 if y == 2026 else None
        for a in au:
            if view in PROP_KEYS and k is not None: per[a][PROP_KEYS[view]][k] += 1
            if k is not None: grp[a][g][k] += 1
            lists[a][g].append([num, href, em])
    ind_rows = sorted((r for r in rows if r[0] == V_IND), key=lambda r: (date_key(r),) + num_key(r), reverse=True)
    ind = [[r[1], r[2], r[3], short_date(r[4]), r[5], ext.cat(r[3])] for r in ind_rows]
    order = ['pl', 'plc', 'pelom', 'pdl', 'pr', 'ind', 'moc', 'ri', 'rq']
    props = [{k: p[k] for k in order if k in p} for p in per]
    groups = [' '.join('%d/%d' % tuple(grp[i][g]) for g in GROUPS) for i in range(n)]
    return props, groups, lists, ind


def repeated(ind):
    d = collections.defaultdict(list)
    for j, r in enumerate(ind):
        e = r[2]
        b = ext.bairro(e)
        for s in ext.streets(e):
            d[(s, b, r[5])].append(j)
    def dk(j):
        m = re.match(r'(\d\d)/(\d\d)/(\d\d)$', ind[j][3] or '')
        return (m.group(3), m.group(2), m.group(1)) if m else ('', '', '')
    rep = [[s, b, c, sorted(ix, key=dk)] for (s, b, c), ix in d.items() if len(ix) >= MINREP]
    rep.sort(key=lambda x: (-len(x[3]), x[0]))
    return {'cats': [c[0] for c in ext.CATS] + ['Outros pedidos'], 'rep': rep}
