"""Abre o site gerado num navegador de verdade e confere o básico. Falha => não publica.
uso: python tests/smoke.py PASTA_DO_SITE"""
import sys, threading, http.server, functools, socketserver
from playwright.sync_api import sync_playwright

pasta = sys.argv[1]
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=pasta)
H.log_message = lambda *a, **k: None
srv = socketserver.TCPServer(('127.0.0.1', 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
base = 'http://127.0.0.1:%d/' % srv.server_address[1]
erros = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={'width': 390, 'height': 800})
    pg.on('pageerror', lambda e: erros.append(str(e)))
    pg.on('console', lambda m: erros.append(m.text) if m.type == 'error' else None)
    pg.on('response', lambda r: erros.append('HTTP %d %s' % (r.status, r.url)) if r.status >= 400 else None)
    pg.goto(base); pg.wait_for_selector('#qh')
    assert pg.locator('a[href="#camara"]').count() == 1, 'página inicial sem link para a Câmara'
    assert pg.locator('a[href="#prefeitura"]').count() == 1, 'página inicial sem link para a Prefeitura'
    pg.fill('#qh', 'a'); pg.wait_for_timeout(300)
    res = pg.inner_text('#qh-res')
    assert 'bairro ou rua' in res, 'busca da página inicial sem atalho para bairro/rua'
    assert pg.locator('#qh-res a[href^="#v"]').count() > 0, 'busca da página inicial não lista nenhum vereador'
    sw0 = pg.evaluate('document.documentElement.scrollWidth')
    cw0 = pg.evaluate('document.documentElement.clientWidth')
    assert sw0 <= cw0 + 1, 'rolagem horizontal na página inicial: scrollWidth=%d clientWidth=%d' % (sw0, cw0)
    pg.goto(base + '#camara'); pg.wait_for_selector('ul#lst li')
    n = pg.locator('ul#lst li').count() + pg.locator('ul#lst2 li').count()
    assert n == 60, 'lista de vereadores com %d nomes' % n
    sw = pg.evaluate('document.documentElement.scrollWidth')
    cw = pg.evaluate('document.documentElement.clientWidth')
    assert sw <= cw + 1, 'rolagem horizontal na tela estreita: scrollWidth=%d clientWidth=%d' % (sw, cw)
    for caminho in ('assets/favicon.svg', 'assets/og-image.png', 'robots.txt', 'sitemap.xml'):
        r = pg.request.get(base + caminho)
        assert r.status == 200, '%s respondeu %d' % (caminho, r.status)
    pg.goto(base + '#v43'); pg.wait_for_selector('button[data-t=r]')
    assert 'Faltas' in pg.inner_text('#s-p')
    pg.click('button[data-t=r]'); pg.click('details.gd >> nth=2'); pg.wait_for_timeout(500)
    pg.click('button[data-t=v]'); assert 'votações' in pg.inner_text('#s-v')
    pg.click('#app a.back'); pg.wait_for_timeout(200)
    assert pg.url == base + '#camara', 'botão voltar do vereador não volta para a lista da Câmara'
    pg.goto(base + '#busca'); pg.wait_for_timeout(300)
    campo = pg.locator('input').first; campo.fill('rua'); pg.wait_for_timeout(1200)
    assert pg.inner_text('#app').strip(), 'busca sem conteúdo'
    pg.goto(base + '#prefeitura'); pg.wait_for_timeout(800)
    texto_pref = pg.inner_text('#app')
    assert 'Prefeitura' in texto_pref, 'seção Prefeitura sem conteúdo'
    if 'Não foi possível carregar' not in texto_pref and 'Carregando' not in texto_pref:
        links = pg.locator('#app details.box a[target=_blank]').count()
        assert links > 0, 'seção Prefeitura sem links para fontes oficiais'
        pg.click('#app a.back'); pg.wait_for_timeout(200)
        assert pg.url == base or pg.url == base + '#', 'botão voltar da Prefeitura não volta à página inicial'
    sw2 = pg.evaluate('document.documentElement.scrollWidth')
    cw2 = pg.evaluate('document.documentElement.clientWidth')
    assert sw2 <= cw2 + 1, 'rolagem horizontal na seção Prefeitura: scrollWidth=%d clientWidth=%d' % (sw2, cw2)

    # notícias nas laterais: só aparecem em telas largas; não devem causar rolagem horizontal
    # nem em tela estreita (precisam ficar escondidas) nem em tela larga (com conteúdo real).
    assert pg.locator('#rail-camara').count() == 1 and pg.locator('#rail-prefeitura').count() == 1
    assert not pg.locator('#rail-camara').is_visible(), 'laterais de notícias visíveis em tela estreita'
    pw = b.new_page(viewport={'width': 1400, 'height': 1000})
    pw.on('pageerror', lambda e: erros.append(str(e)))
    pw.on('response', lambda r: erros.append('HTTP %d %s' % (r.status, r.url)) if r.status >= 400 else None)
    pw.goto(base); pw.wait_for_timeout(600)
    assert pw.locator('#rail-camara').is_visible(), 'lateral da Câmara não aparece em tela larga'
    assert pw.locator('#rail-prefeitura').is_visible(), 'lateral da Prefeitura não aparece em tela larga'
    swl = pw.evaluate('document.documentElement.scrollWidth')
    cwl = pw.evaluate('document.documentElement.clientWidth')
    assert swl <= cwl + 1, 'rolagem horizontal em tela larga: scrollWidth=%d clientWidth=%d' % (swl, cwl)
    pw.close()
    b.close()
srv.shutdown()
erros = [e for e in erros if 'favicon' not in e]
assert not erros, erros
print('smoke ok: 60 vereadores, abas, busca, sem erros')
