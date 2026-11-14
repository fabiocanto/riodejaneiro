"""Gera o site (pasta de saída) a partir dos dados coletados.
uso: python build.py RAW_DIR OUT_DIR [--data dd/mm/aaaa]
RAW_DIR contém: presenca.json, props.json, votos.json   (+ baseline/canon.json)"""
import json, os, re, sys, datetime
sys.path.insert(0, os.path.dirname(__file__))
import build_data as B
from common import norm_name

MES = ["", "janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
       "agosto", "setembro", "outubro", "novembro", "dezembro"]
MM = ["", "jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def juntar(xs):
    return xs[0] if len(xs) == 1 else ', '.join(xs[:-1]) + ' e ' + xs[-1]


def meses_sem(months, hoje):
    have = {tuple(m) for m in months}
    (y0, m0), (y1, m1) = months[0], months[-1]
    por_ano, y, m = {}, y0, m0
    while (y, m) <= (y1, m1):
        if (y, m) not in have: por_ano.setdefault(y, []).append(MES[m])
        m += 1
        if m == 13: y, m = y + 1, 1
    partes = ['%s de %d' % (juntar(v), a) for a, v in por_ano.items()]
    fim = (y1, m1 + 1) if m1 < 12 else (y1 + 1, 1)
    if fim <= (hoje.year, hoje.month):
        partes.append('%s de %d em diante' % (MES[fim[1]], fim[0]))
    return juntar(partes) if len(partes) < 2 else ', '.join(partes[:-1]) + ', e ' + partes[-1]


def main(raw, out, hoje):
    canon = json.load(open(os.path.join(os.path.dirname(__file__), '..', 'baseline', 'canon.json'), encoding='utf-8'))
    pres = json.load(open(os.path.join(raw, 'presenca.json'), encoding='utf-8'))
    rows = json.load(open(os.path.join(raw, 'props.json'), encoding='utf-8'))
    votos = json.load(open(os.path.join(raw, 'votos.json'), encoding='utf-8'))
    n = len(canon)
    idx = {norm_name(c): i for i, c in enumerate(canon)}
    cidx = {}
    for k, r in pres.items():
        for nome, *_ in r: cidx[nome] = idx[norm_name(nome)]
    months, lines = B.presenca_lines(pres, cidx, n)
    props, groups, lists, ind = B.props_outputs(rows, n)
    rep = B.repeated(ind)
    docs = votos['docs']
    V = [B.rle([('S' if i in d['S'] else 'N' if i in d['N'] else 'A' if i in d['A'] else '-') for d in docs])
         for i in range(n)]
    D = {"canon": canon, "months": months, "pres": lines,
         "rows": ['%s|%s|%s|%d' % (d['code'] or '?', d['date'], d['id'], 1 if d['veto'] else 0) for d in docs],
         "V": V, "dropped": votos['dropped'], "props": props, "last": {}, "groups": groups}
    datas = [d['date'] for d in docs]
    ultimo = '%s de %d' % (MES[months[-1][1]], months[-1][0])
    meta = {
        'PERIODO': 'fevereiro de 2025 a %s de %d' % (MES[hoje.month], hoje.year),
        'DATA': hoje.strftime('%d/%m/%Y'), 'ULTIMO_MES': ultimo,
        'MESES_SEM': meses_sem(months, hoje),
        'VOTOS_PERIODO': 'fev/2025 e %s/%d' % (MM[hoje.month], hoje.year),
        'N_IND': '{:,}'.format(len(ind)).replace(',', '.'), 'N_CANON': str(n)}
    html = open(os.path.join(os.path.dirname(__file__), 'template.html'), encoding='utf-8').read()
    for k, v in meta.items(): html = html.replace('{{%s}}' % k, v)
    assert '{{' not in html, 'placeholder sem valor'
    data = 'var D=' + json.dumps(D, ensure_ascii=False, separators=(',', ':')) + ';'
    html = html.replace('/*DATA*/', data)
    os.makedirs(os.path.join(out, 'data'), exist_ok=True)
    open(os.path.join(out, 'index.html'), 'w', encoding='utf-8').write(html)
    for i in range(n):
        json.dump(lists[i], open(os.path.join(out, 'data', 'v%d.json' % i), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    json.dump(ind, open(os.path.join(out, 'data', 'ind.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    json.dump(rep, open(os.path.join(out, 'data', 'rep.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    open(os.path.join(out, '.nojekyll'), 'w').write('')
    open(os.path.join(out, 'CNAME'), 'w').write('carrapeta.com.br\n')
    json.dump({'meta': meta, 'D_keys': list(D)}, open(os.path.join(raw, 'build_info.json'), 'w'))
    return D


if __name__ == '__main__':
    raw, out = sys.argv[1], sys.argv[2]
    hoje = datetime.date.today()
    if '--data' in sys.argv:
        d, m, y = map(int, sys.argv[sys.argv.index('--data') + 1].split('/')); hoje = datetime.date(y, m, d)
    main(raw, out, hoje)
