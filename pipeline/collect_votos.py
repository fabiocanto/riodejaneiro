"""Coleta as votações NOMINAIS (com o voto de cada vereador pelo nome) a partir das transcrições oficiais.
uso: python collect_votos.py CANON.json CACHE.json SAIDA.json"""
import re, sys, json, datetime
from concurrent.futures import ThreadPoolExecutor
from bs4 import BeautifulSoup
from common import sessao, get, APL, norm_name

LISTA = APL + 'discvot.nsf/anoint?OpenForm&Start=%d&Count=500&ExpandView'
DOC = APL + 'discvot.nsf/5d50d39bd976391b83256536006a2502/%s?OpenDocument'
MESES = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']
TIPOS = [('PROJETO DE LEI COMPLEMENTAR', 'PLC'), ('PROJETO DE DECRETO LEGISLATIVO', 'PDL'), ('PROJETO DE RESOLUCAO', 'PR'),
         ('PROPOSTA DE EMENDA', 'PELOM'), ('PROJETO DE LEI', 'PL')]
RECENTE_DIAS = 21  # reler documentos dos últimos dias (a Câmara pode corrigir)
ALIAS = {}


def _chave(pos):
    return tuple(int(x) for x in pos.split('.'))


def listar(sess, hoje):
    """-> [(id, (ano, mes, dia))] do mais novo ao mais antigo, só 2025 em diante.
    A lista oficial é paginada por posições hierárquicas (Start=ano.mes.dia.item)."""
    out, vistos, pos = [], set(), '1'
    ano = mes = dia = None  # o estado atravessa as páginas: muitas não repetem o cabeçalho de ano/mês
    for _ in range(300):
        html_text = get(sess, APL + 'discvot.nsf/anoint?OpenForm&Count=500&Start=' + pos)
        soup = BeautifulSoup(html_text, 'lxml')
        fim = False
        for tr in soup.find_all('tr'):
            if tr.find('tr'): continue
            a = tr.find('a', href=re.compile('OpenDocument'))
            txt = tr.get_text(' ', strip=True)
            if a:
                i = a['href'].split('/')[-1].split('?')[0]
                if i not in vistos:
                    vistos.add(i)
                    out.append((i, (ano, mes, dia)))
            elif re.fullmatch(r'\d{4}', txt):
                ano = int(txt)
                if ano < 2025: fim = True; break
            elif txt.lower() in MESES:
                mes = MESES.index(txt.lower()) + 1
            elif re.fullmatch(r'\d\d/\d\d', txt):
                dia = int(txt[:2])
        if fim: break
        cand = {m.group(1) for m in re.finditer(r'Start=([\d.]+)&(?:amp;)?Count=', html_text)}
        prox = max(cand, key=_chave) if cand else None
        if not prox or _chave(prox) <= _chave(pos): break
        pos = prox
    return [x for x in out if x[1][0] and x[1][0] >= 2025]


def codigo(titulo):
    t = re.sub(r'\s+', ' ', ''.join(c for c in titulo.upper() if c.isalnum() or c in ' /-')).strip()
    for nome, sigla in TIPOS:
        if t.startswith(nome):
            m = re.search(r'(\d+(?:-\w)?/\d{4})', t)
            return '%s %s' % (sigla, m.group(1)) if m else '?'
    return '?'


def nomes(s):
    s = re.sub(r'\b[Ee]?\s*(?:a|o|as|os)?\s*Senhor(?:es|a|as)?\s+Vereador(?:es|a|as)?\b', ',', s)
    return [x.strip() for x in re.split(r',\s*|\s+[eE]\s+', s.strip()) if x.strip()]


CL = r'Senhor\w*\s+Vereador\w*\s+(.+?)\s+(\d+)\s*\('
RE_SN = re.compile(r'vot(?:aram|ou)\s+(SIM|N[ÃA]O)\s+(?:os|o|as|a)\s+' + CL, re.I)
RE_AB = re.compile(r'Abst\w+-se\s+(?:os|o|as|a)\s+' + CL, re.I)


def parse_doc(html_text, idx):
    """-> None (sem votação nominal) ou dict {code,date,veto,S,N,A,ok}."""
    soup = BeautifulSoup(html_text, 'lxml')
    for t in soup(['script', 'style']): t.decompose()
    txt = soup.get_text('\n')
    m = re.search(r'Conclu[ií]d[ao] a vota[cç][aã]o nominal,?\s*constata-se que(.*?)(?:\n|$)', txt, re.S | re.I)
    if not m: return None
    bloco = m.group(1)
    tit = re.search(r'ORDEM DO DIA\s*\n\s*([^\n]+)', txt)
    dt = re.search(r'Data da Sess[ãa]o:\s*(\d\d)/(\d\d)/\d\d(\d\d)', txt)
    ordem = txt[txt.find('Texto da Ordem do Dia'):]
    ordem = re.split(r'Em discuss[ãa]o|Em vota[cç][aã]o', ordem, 1)[0]
    r = {'code': codigo(tit.group(1)) if tit else '?', 'date': '%s/%s/%s' % dt.groups() if dt else '',
         'veto': bool(re.search(r'\bveto\b', ordem, re.I)), 'S': [], 'N': [], 'A': [], 'ok': True}
    achou = False
    for chave, rx in (('SN', RE_SN), ('A', RE_AB)):
        for mm in rx.finditer(bloco):
            achou = True
            if chave == 'SN': k = 'S' if mm.group(1).upper() == 'SIM' else 'N'; lista, decl = mm.group(2), int(mm.group(3))
            else: k = 'A'; lista, decl = mm.group(1), int(mm.group(2))
            ns = nomes(lista)
            ids = [idx.get(norm_name(ALIAS.get(norm_name(n), n))) for n in ns]
            if len(ns) != decl or None in ids:
                r['ok'] = False
                r.setdefault('motivo', []).append('%s: %d nomes para %d declarados; desconhecidos=%s' % (k, len(ns), decl, [n for n, i in zip(ns, ids) if i is None]))
            r[k] += [i for i in ids if i is not None]
    if not achou or not r['date']: r['ok'] = False
    return r


def main(canon_path, cache_path, saida, hoje=None):
    hoje = hoje or datetime.date.today()
    canon = json.load(open(canon_path, encoding='utf-8'))
    idx = {norm_name(c): i for i, c in enumerate(canon)}
    try: cache = json.load(open(cache_path, encoding='utf-8'))
    except FileNotFoundError: cache = {}
    sess = sessao()
    lista = listar(sess, hoje)
    corte = hoje - datetime.timedelta(days=RECENTE_DIAS)

    def recente(d):
        try: return datetime.date(d[0], d[1], d[2]) >= corte
        except Exception: return True
    pend = [i for i, d in lista if i not in cache or recente(d)]
    print('documentos na lista:', len(lista), '| a baixar:', len(pend))
    with ThreadPoolExecutor(8) as ex:
        for i, r in zip(pend, ex.map(lambda i: parse_doc(get(sess, DOC % i), idx), pend)):
            cache[i] = r
    docs, dropped, debug = [], 0, []
    for i, d in lista:
        r = cache.get(i)
        if not r: continue
        if not r['ok']:
            dropped += 1
            debug.append({'id': i, 'code': r.get('code'), 'date': r.get('date'), 'motivo': r.get('motivo', ['sem data' if not r.get('date') else 'sem blocos de votos'])})
            continue
        docs.append({'id': i, 'code': '' if r['code'] == '?' else r['code'], 'date': r['date'], 'veto': r['veto'],
                     'S': sorted(set(r['S'])), 'N': sorted(set(r['N'])), 'A': sorted(set(r['A']))})
    json.dump(cache, open(cache_path, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    json.dump({'docs': docs, 'dropped': dropped, 'listados': len(lista)}, open(saida, 'w', encoding='utf-8'), ensure_ascii=False)
    json.dump(debug[:150], open(saida.replace('.json', '_debug.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('votações nominais:', len(docs), '| descartadas:', dropped)


if __name__ == '__main__':
    main(*sys.argv[1:4])
