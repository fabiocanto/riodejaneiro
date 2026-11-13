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
    pg.goto(base); pg.wait_for_selector('ul#lst li')
    n = pg.locator('ul#lst li').count() + pg.locator('ul#lst2 li').count()
    assert n == 60, 'lista de vereadores com %d nomes' % n
    pg.goto(base + '#v43'); pg.wait_for_selector('button[data-t=r]')
    assert 'Faltas' in pg.inner_text('#s-p')
    pg.click('button[data-t=r]'); pg.click('details.gd >> nth=2'); pg.wait_for_timeout(500)
    pg.click('button[data-t=v]'); assert 'votações' in pg.inner_text('#s-v')
    pg.goto(base + '#busca'); pg.wait_for_timeout(300)
    campo = pg.locator('input').first; campo.fill('rua'); pg.wait_for_timeout(1200)
    assert pg.inner_text('#app').strip(), 'busca sem conteúdo'
    b.close()
srv.shutdown()
erros = [e for e in erros if 'favicon' not in e]
assert not erros, erros
print('smoke ok: 60 vereadores, abas, busca, sem erros')
