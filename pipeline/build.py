"""Gera o site (pasta de saída) a partir dos dados coletados.
uso: python build.py RAW_DIR OUT_DIR [--data dd/mm/aaaa]
RAW_DIR normalmente contém: presenca.json, props.json, votos.json (+ baseline/canon.json).
Quando algum desses arquivos não existir em RAW_DIR (ex.: uma rodada que só atualiza as
notícias, sem recoletar a Câmara), usa a última versão boa em baseline/ no lugar."""
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


def _ler_com_fallback(raw, baseline, nome):
    """Lê NOME de raw/; se esta execução não coletou o arquivo (ex.: rodada só de notícias,
    que não refaz a coleta pesada da Câmara), usa a última versão boa em baseline/."""
    caminho_raw = os.path.join(raw, nome)
    d = raw if os.path.exists(caminho_raw) else baseline
    return json.load(open(os.path.join(d, nome), encoding='utf-8'))


def noticias_data(raw, baseline):
    """Monta data/noticias.json. Mesma regra da Prefeitura: só usa a coleta desta execução se ela
    passou na conferência (validate_noticias.py); senão, ficam as últimas notícias boas."""
    def ler(d, nome, padrao):
        try:
            return json.load(open(os.path.join(d, nome), encoding='utf-8'))
        except FileNotFoundError:
            return padrao
    usar_raw = os.path.exists(os.path.join(raw, 'noticias_ok'))
    fonte = raw if usar_raw else baseline
    dados = ler(fonte, 'noticias.json', {})
    return {'camara': dados.get('camara') or [], 'prefeitura': dados.get('prefeitura') or []}


def prefeitura_data(raw, baseline):
    """Monta data/prefeitura.json. Se a coleta desta execução não passou na conferência
    (validate_prefeitura.py), usa a última versão boa gravada em baseline/ — a seção Prefeitura
    nunca publica dado estranho, mesmo quando o resto do site publica normalmente."""
    def ler(d, nome, padrao):
        try:
            return json.load(open(os.path.join(d, nome), encoding='utf-8'))
        except FileNotFoundError:
            return padrao
    usar_raw = os.path.exists(os.path.join(raw, 'prefeitura_ok'))
    fonte = raw if usar_raw else baseline
    return {
        'despesas': ler(fonte, 'prefeitura_despesas.json', {}),
        'contratos': ler(fonte, 'prefeitura_contratos.json', {}),
        'fontes': ler(fonte, 'prefeitura_fontes.json', {}),
    }


def main(raw, out, hoje):
    baseline_dir = os.path.join(os.path.dirname(__file__), '..', 'baseline')
    canon = json.load(open(os.path.join(baseline_dir, 'canon.json'), encoding='utf-8'))
    extra_path = os.path.join(baseline_dir, 'vereadores_extra.json')
    extra_raw = json.load(open(extra_path, encoding='utf-8')) if os.path.exists(extra_path) else []
    extra_by_idx = {e['idx']: e for e in extra_raw}
    # presenca/props/votos: usa a coleta desta execução quando ela rodou (execução normal da
    # Câmara); numa rodada mais leve que só atualiza as notícias (sem recoletar a Câmara), usa a
    # última versão boa em baseline/ para montar o site todo mesmo assim.
    pres = _ler_com_fallback(raw, baseline_dir, 'presenca.json')
    rows = _ler_com_fallback(raw, baseline_dir, 'props.json')
    votos = _ler_com_fallback(raw, baseline_dir, 'votos.json')
    n = len(canon)
    idx = {norm_name(c): i for i, c in enumerate(canon)}
    cidx = {}
    for k, r in pres.items():
        for nome, *_ in r: cidx[nome] = idx[norm_name(nome)]
    months, lines = B.presenca_lines(pres, cidx, n)
    props, groups, lists, ind = B.props_outputs(rows, n)
    rep = B.repeated(ind)
    rank = B.rankings(rows, ind, n)
    docs = votos['docs']
    V = [B.rle([('S' if i in d['S'] else 'N' if i in d['N'] else 'A' if i in d['A'] else '-') for d in docs])
         for i in range(n)]
    extra = [extra_by_idx.get(i) and {
        'partido': extra_by_idx[i].get('partido'),
        'cargo': extra_by_idx[i].get('cargo'),
        'foto': extra_by_idx[i].get('foto'),
        'sala': extra_by_idx[i].get('sala'),
        'telefone': extra_by_idx[i].get('telefone'),
        'email': extra_by_idx[i].get('email'),
        'partidoSite': extra_by_idx[i].get('partidoSite'),
    } for i in range(n)]
    D = {"canon": canon, "months": months, "pres": lines,
         "rows": ['%s|%s|%s|%d' % (d['code'] or '?', d['date'], d['id'], 1 if d['veto'] else 0) for d in docs],
         "V": V, "dropped": votos['dropped'], "props": props, "last": {}, "groups": groups,
         "extra": extra, "rank": rank}
    datas = [d['date'] for d in docs]
    ultimo = '%s de %d' % (MES[months[-1][1]], months[-1][0])
    meta = {
        'PERIODO': 'fevereiro de 2025 a %s de %d' % (MES[hoje.month], hoje.year),
        'PERIODO_CURTO': '2025 e 2026',
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
    json.dump(prefeitura_data(raw, baseline_dir), open(os.path.join(out, 'data', 'prefeitura.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    json.dump(noticias_data(raw, baseline_dir), open(os.path.join(out, 'data', 'noticias.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    open(os.path.join(out, '.nojekyll'), 'w').write('')
    open(os.path.join(out, 'CNAME'), 'w').write('carrapeta.com.br\n')
    open(os.path.join(out, 'robots.txt'), 'w').write(
        'User-agent: *\nAllow: /\nSitemap: https://carrapeta.com.br/sitemap.xml\n')
    open(os.path.join(out, 'sitemap.xml'), 'w', encoding='utf-8').write(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        '<url><loc>https://carrapeta.com.br/</loc><lastmod>%s</lastmod><changefreq>daily</changefreq></url>\n'
        '</urlset>\n' % hoje.isoformat())
    os.makedirs(os.path.join(out, 'assets'), exist_ok=True)
    for fn in ('favicon.svg', 'og-image.png'):
        src_f = os.path.join(os.path.dirname(__file__), '..', 'assets', fn)
        if os.path.exists(src_f):
            with open(src_f, 'rb') as fsrc, open(os.path.join(out, 'assets', fn), 'wb') as fdst:
                fdst.write(fsrc.read())
    fotos_src = os.path.join(os.path.dirname(__file__), '..', 'assets', 'vereadores')
    if os.path.isdir(fotos_src):
        fotos_dst = os.path.join(out, 'assets', 'vereadores')
        os.makedirs(fotos_dst, exist_ok=True)
        for fn in os.listdir(fotos_src):
            with open(os.path.join(fotos_src, fn), 'rb') as fsrc, open(os.path.join(fotos_dst, fn), 'wb') as fdst:
                fdst.write(fsrc.read())
    json.dump({'meta': meta, 'D_keys': list(D)}, open(os.path.join(raw, 'build_info.json'), 'w'))
    return D


if __name__ == '__main__':
    raw, out = sys.argv[1], sys.argv[2]
    hoje = datetime.date.today()
    if '--data' in sys.argv:
        d, m, y = map(int, sys.argv[sys.argv.index('--data') + 1].split('/')); hoje = datetime.date(y, m, d)
    main(raw, out, hoje)
