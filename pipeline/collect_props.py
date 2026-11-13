"""Baixa as listas oficiais de proposições (2025 e 2026) e liga cada uma aos vereadores autores.
uso: python collect_props.py CANON.json SAIDA.json [ESTAT.json]"""
import re, sys, json, collections
from concurrent.futures import ThreadPoolExecutor
from bs4 import BeautifulSoup
from common import sessao, get, APL, norm_name
from classify import VIEWS

PAGE = 500
ANO_MIN = 2025


def limpar_ementa(t):
    t = re.sub(r'\s+', ' ', t).strip()
    return t.split(' =>')[0].strip()[:260]


def parse_page(html_text, idx):
    """-> lista de (num, href, ementa, data, [nomes de autores]) de uma página de lista do scpro."""
    soup = BeautifulSoup(html_text, 'lxml')
    out = []
    for tr in soup.find_all('tr'):
        a = tr.find('a', href=re.compile(r'OpenDocument'))
        tds = tr.find_all('td', recursive=False)
        if not a or len(tds) < 5 or tr.find('tr'): continue
        href = a['href'].split('scpro.nsf/')[-1].split('?')[0]
        num = a.get_text(strip=True)
        dt = tds[-2].get_text(strip=True)[:10]
        dt = dt if re.match(r'\d\d/\d\d/\d{4}$', dt) else ''
        autores = [x.strip() for x in tds[-1].get_text(' ', strip=True).split(',') if x.strip()]
        out.append((num, href, limpar_ementa(tds[-3].get_text(' ')), dt, autores))
    return out


def ano(num):
    m = re.search(r'/(\d{4})\s*$', num)
    return int(m.group(1)) if m else 0


def coletar_view(vi, nome, sess):
    rows, start, sem, vistos = [], 1, 0, set()
    for _ in range(400):
        pg = parse_page(get(sess, '%sscpro.nsf/Internet/%s?OpenForm&Start=%d&Count=%d' % (APL, nome, start, PAGE)), vi)
        if not pg: break
        novos = [r for r in pg if r[1] not in vistos]
        vistos.update(r[1] for r in novos)
        rows += novos
        sem = 0 if any(ano(r[0]) >= ANO_MIN for r in pg) else sem + 1
        if sem >= 2 or not novos: break
        start += PAGE
    return [r for r in rows if ano(r[0]) >= ANO_MIN]


def main(canon_path, saida, estat_path=None):
    canon = json.load(open(canon_path, encoding='utf-8'))
    idx = {norm_name(c): i for i, c in enumerate(canon)}
    sess = sessao()
    with ThreadPoolExecutor(5) as ex:
        res = list(ex.map(lambda p: coletar_view(p[0], p[1], sess), enumerate(VIEWS)))
    final, sem_autor, desc = [], collections.Counter(), collections.Counter()
    tot_view = {}
    for vi, rows in enumerate(res):
        tot_view[VIEWS[vi]] = len(rows)
        for num, href, em, dt, autores in rows:
            ids = sorted({idx[norm_name(a)] for a in autores if norm_name(a) in idx})
            for a in autores:
                if norm_name(a) not in idx: desc[norm_name(a)] += 1
            if ids: final.append([vi, num, href, em, dt, ids])
            else: sem_autor[VIEWS[vi]] += 1
    json.dump(final, open(saida, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    stat = {'total_por_lista': tot_view, 'sem_autor_conhecido': dict(sem_autor), 'autores_nao_mapeados': dict(desc.most_common(40)),
            'linhas_gravadas': len(final)}
    if estat_path: json.dump(stat, open(estat_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps(stat, ensure_ascii=False))


if __name__ == '__main__':
    main(*sys.argv[1:4])
