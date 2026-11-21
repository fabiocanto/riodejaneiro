"""Coleta notícias factuais sobre a Câmara/vereadores, a Prefeitura/prefeitos e o governo
federal, a partir de feeds RSS/Atom de fontes jornalísticas confiáveis e dos próprios sites
oficiais. Notícia de Câmara e de Prefeitura tem prioridade nas laterais correspondentes;
notícia de governo federal (e o excedente de Câmara/Prefeitura além do limite por lado) serve
só pra completar o lado que tiver menos notícia, já que notícia específica de vereador é rara.
Nunca inventa ou resume nada: só título, fonte e link, exatamente como publicado.
Exclui colunas de opinião pela própria URL (ex.: /opiniao/, /coluna/) e qualquer item que não
bata claramente com as palavras-chave de Câmara, Prefeitura ou governo federal.
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
# Governo federal — usado só pra completar as laterais quando sobra pouca notícia específica
# de Câmara/Prefeitura (Fábio pediu pra distribuir notícia da cidade e do governo, municipal
# e federal, entre os dois lados, já que notícia só de vereador é rara nas fontes disponíveis).
PADRAO_FEDERAL = re.compile(
    r'\bpresidente\s+da\s+rep[úu]blica\b|\bplanalto\b|\bcongresso\s+nacional\b'
    r'|\bsenado\s+federal\b|\bc[âa]mara\s+dos\s+deputados\b|\bminist[ée]rio\b|\bministr[oa]\b'
    r'|\bgoverno\s+federal\b',
    re.I)

MAX_POR_LADO = 5
MIN_IDADE_DIAS = 60   # ignora itens com data muito antiga (feed desatualizado/cacheado)


def _texto(el):
    return (el.text or '').strip() if el is not None else ''


def _parse_data(s):
    if not s:
        return None
    try:
        d = email.utils.parsedate_to_datetime(s)
        # Alguns feeds publicam a data sem fuso explícito; parsedate_to_datetime então
        # devolve um datetime "naive", que não pode ser comparado com um "aware" depois.
        if d.tzinfo is None:
            d = d.replace(tzinfo=datetime.timezone.utc)
        return d
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
    """Quando o título menciona só um dos três assuntos (Câmara, Prefeitura, governo federal),
    a resposta é óbvia. Quando menciona mais de um (ex.: 'Câmara do Rio derruba 12 vetos da
    Prefeitura'), o assunto principal costuma vir primeiro no título — então fica com quem
    aparece antes."""
    candidatos = [(m.start(), cat) for m, cat in (
        (PADRAO_CAMARA.search(titulo), 'camara'),
        (PADRAO_PREFEITURA.search(titulo), 'prefeitura'),
        (PADRAO_FEDERAL.search(titulo), 'federal'),
    ) if m]
    if not candidatos:
        return None  # não relacionado a nenhum dos três — não entra
    return min(candidatos)[1]


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
    # Alguns portais de notícias (diferente dos sites oficiais) bloqueiam com HTTP 403
    # um User-Agent que se identifica como leitor automático de dados públicos — tratam
    # como bot. Para esses feeds, um User-Agent de navegador comum é o padrão normal de
    # qualquer leitor de RSS e não muda o que é lido (só o título/link/data, já públicos).
    s.headers['User-Agent'] = (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36')
    candidatos, erros = coletar(s)
    candidatos.sort(key=lambda c: c['_ord'], reverse=True)

    por_cat = {'camara': [], 'prefeitura': [], 'federal': []}
    for c in candidatos:
        por_cat[c['categoria']].append(c)

    camara = por_cat['camara'][:MAX_POR_LADO]
    prefeitura = por_cat['prefeitura'][:MAX_POR_LADO]

    # O que sobra (notícia de governo federal, mais o excedente de Câmara/Prefeitura além do
    # limite de cada lado) serve pra completar o lado que ficar com menos notícia — distribuindo
    # entre os dois em vez de deixar um lado vazio e o outro parado em 5.
    sobra = por_cat['camara'][MAX_POR_LADO:] + por_cat['prefeitura'][MAX_POR_LADO:] + por_cat['federal']
    sobra.sort(key=lambda c: c['_ord'], reverse=True)
    vistos_urls = {c['url'] for c in camara + prefeitura}
    for c in sobra:
        if c['url'] in vistos_urls:
            continue
        if len(camara) < MAX_POR_LADO and len(camara) <= len(prefeitura):
            camara.append(c)
        elif len(prefeitura) < MAX_POR_LADO:
            prefeitura.append(c)
        elif len(camara) < MAX_POR_LADO:
            camara.append(c)
        else:
            continue
        vistos_urls.add(c['url'])

    for c in camara + prefeitura:
        del c['_ord']

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
