"""Coleta notícias factuais sobre a Câmara/vereadores e sobre a Prefeitura/prefeitos, a partir
de feeds RSS/Atom de fontes jornalísticas confiáveis e dos próprios sites oficiais.
Nunca inventa ou resume nada: só título, fonte e link, exatamente como publicado.
Exclui colunas de opinião pela própria URL (ex.: /opiniao/, /coluna/) e qualquer item que não
bata claramente com as palavras-chave de Câmara ou de Prefeitura.
uso: python collect_noticias.py RAW_DIR"""
import datetime
import email.utils
import html
import json
import re
import sys
from xml.etree import ElementTree as ET

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from common import sessao, get

# (nome de exibição, url do feed, domínio que o link precisa conter)
FONTES = [
    ('G1 Rio de Janeiro', 'https://g1.globo.com/rss/g1/rio-de-janeiro/', 'g1.globo.com'),
    ('G1 Política', 'https://g1.globo.com/rss/g1/politica/', 'g1.globo.com'),
    ('Diário do Rio', 'https://diariodorio.com/feed/', 'diariodorio.com'),
    ('Correio da Manhã', 'https://www.correiodamanha.com.br/feed', 'correiodamanha.com.br'),
    ('Prefeitura do Rio', 'https://prefeitura.rio/feed/', 'prefeitura.rio'),
    ('Câmara Municipal do Rio', 'https://www.camara.rio/noticias/feed', 'camara.rio'),
]

# URLs com estas palavras são opinião/coluna/blog — nunca factual, nunca entram
PADRAO_OPINIAO = re.compile(r'/(opiniao|colunas?|colunistas?|blog|editorial|cronica)/', re.I)

PADRAO_CAMARA = re.compile(
    r'\bvereador(a|es)?\b'
    r'|\bc[âa]mara\s+municipal\b'
    r'|\bc[âa]mara\s+d[oe]\s+rio\b'
    r'|\bc[âa]mara\s+de\s+vereadores\b'
    r'|\bc[âa]mara\s+dos\s+vereadores\b'
    r'|\bcmrj\b'
    r'|\bpal[áa]cio\s+pedro\s+ernesto\b',
    re.I)
PADRAO_PREFEITURA = re.compile(
    r'\bprefeito(a)?\b|\bprefeitura\b|\bsecretari[ao]\s+municipal\b|\bpaços?\s+municipal\b',
    re.I)

MAX_POR_LADO = 5
MIN_IDADE_DIAS = 60   # ignora itens com data muito antiga (feed desatualizado/cacheado)


def _texto(el):
    return (el.text or '').strip() if el is not None else ''


def _parse_data(s):
    if not s:
        return None
    try:
        return email.utils.parsedate_to_datetime(s)
    except (TypeError, ValueError):
        pass
    for fmt in ('%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%d'):
        try:
            d = datetime.datetime.strptime(s[:len(fmt) + 6], fmt)
            if d.tzinfo is None:
                d = d.replace(tzinfo=datetime.timezone.utc)
            return d
        except ValueError:
            continue
    return None


def _parse_feed(texto):
    """RSS 2.0 (<item>) ou Atom (<entry>). Devolve lista de (titulo, url, datetime|None)."""
    raiz = ET.fromstring(texto)
    itens = []
    for it in raiz.iter():
        tag = it.tag.rsplit('}', 1)[-1]
        if tag not in ('item', 'entry'):
            continue
        titulo = url = data_txt = None
        for filho in it:
            ftag = filho.tag.rsplit('}', 1)[-1]
            if ftag == 'title':
                titulo = _texto(filho)
            elif ftag == 'link':
                cand = filho.get('href') or _texto(filho)
                if cand:
                    url = cand
            elif ftag in ('pubDate', 'published', 'updated', 'date'):
                data_txt = data_txt or _texto(filho)
        if titulo and url:
            itens.append((html.unescape(titulo), url.strip(), _parse_data(data_txt)))
    return itens


def _categoria(titulo):
    """Quando o título menciona só um dos dois, a resposta é óbvia. Quando menciona os dois
    (ex.: 'Câmara do Rio derruba 12 vetos da Prefeitura'), o assunto principal costuma vir
    primeiro no título — então fica com quem aparece antes."""
    m_c = PADRAO_CAMARA.search(titulo)
    m_p = PADRAO_PREFEITURA.search(titulo)
    if m_c and not m_p:
        return 'camara'
    if m_p and not m_c:
        return 'prefeitura'
    if m_c and m_p:
        return 'camara' if m_c.start() < m_p.start() else 'prefeitura'
    return None  # não relacionado a nenhum dos dois — não entra


def coletar(s, agora=None):
    agora = agora or datetime.datetime.now(datetime.timezone.utc)
    limite = agora - datetime.timedelta(days=MIN_IDADE_DIAS)
    candidatos, erros, vistos = [], [], set()
    for nome, feed_url, dominio in FONTES:
        try:
            texto = get(s, feed_url)
            itens = _parse_feed(texto)
        except Exception as e:
            erros.append('%s (%s): %s' % (nome, feed_url, e))
            continue
        if not itens:
            erros.append('%s (%s): feed vazio ou formato não reconhecido.' % (nome, feed_url))
            continue
        for titulo, url, data in itens:
            if dominio not in url or PADRAO_OPINIAO.search(url):
                continue
            if url in vistos:
                continue
            cat = _categoria(titulo)
            if cat is None:
                continue
            if data is not None and data < limite:
                continue
            vistos.add(url)
            candidatos.append({
                'titulo': titulo,
                'url': url,
                'fonte': nome,
                'data': data.date().isoformat() if data else None,
                'categoria': cat,
                '_ord': data or datetime.datetime.min.replace(tzinfo=datetime.timezone.utc),
            })
    return candidatos, erros


def main(raw_dir):
    s = sessao()
    candidatos, erros = coletar(s)
    candidatos.sort(key=lambda c: c['_ord'], reverse=True)
    for c in candidatos:
        del c['_ord']
    camara = [c for c in candidatos if c['categoria'] == 'camara'][:MAX_POR_LADO]
    prefeitura = [c for c in candidatos if c['categoria'] == 'prefeitura'][:MAX_POR_LADO]
    saida = {
        'camara': camara,
        'prefeitura': prefeitura,
        'coletado_em': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'erros_fonte': erros,
    }
    with open('%s/noticias.json' % raw_dir, 'w', encoding='utf-8') as f:
        json.dump(saida, f, ensure_ascii=False, indent=2)
    if erros:
        sys.stderr.write('\n'.join(erros) + '\n')


if __name__ == '__main__':
    main(sys.argv[1])
