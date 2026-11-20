"""Testes dos leitores com trechos no formato real das páginas oficiais.
rodar: python -m pytest -q tests   (ou: python tests/test_parsers.py)"""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'pipeline'))
import collect_presenca as P, collect_props as R, collect_votos as V
import collect_noticias as N
from common import norm_name

CANON = json.load(open(os.path.join(os.path.dirname(__file__), '..', 'baseline', 'canon.json'), encoding='utf-8'))
IDX = {norm_name(c): i for i, c in enumerate(CANON)}


def test_presenca():
    t = ('\r\n\r\n<table class="TabelaPadrao TabelaPadraoHover">\r\n<tbody>\r\n<tr class="central">\r\n  <td colspan="4" class="azul"><strong>10 / 2026</strong></td>\r\n  </tr>\r\n'
         '<td class="azul-claro"><strong>Vereador</strong></td>\r\n</tr>\r\n\r\n\r\n<tr>\r\n<td>ÁTILA NUNES</td>\r\n<td class="central">3</td>\r\n<td class="central">1</td>\r\n\r\n\r\n<td class="central">2</td>\r\n</tr>\r\n'
         '<tr>\r\n<td>ZICO</td>\r\n<td class="central">0</td>\r\n<td class="central">0</td>\r\n\r\n\r\n<td class="central">0</td>\r\n</tr>\r\n</tbody>\r\n</table>\r\n')
    assert P.parse(t) == [['ÁTILA NUNES', 3, 1, 2], ['ZICO', 0, 0, 0]]
    assert P.parse('<table><tbody></tbody></table>') == []
    try: P.parse(t.replace('<td class="central">2</td>', '<td class="central">9</td>')); assert False
    except ValueError: pass


LISTA = '''<table border="0" cellpadding="2" cellspacing="0">
<tr><th>x</th></tr>
<tr valign="top"><td><img width="16" height="1" src="/icons/ecblank.gif"><font size="1"><a href="/APL/Legislativos/scpro.nsf/8446f2be3d9bb8730325863200569352/22d355f98a8bedf903258eab005b2787?OpenDocument">2771/2026</a></font></td><td><img src="/icons/vwicn104.gif"></td><td></td><td><font size="1">ALTERA OS LIMITES DO REFÚGIO. =&gt;20260302771 =&gt; {Comissão de Constituição}</font></td><td><font size="1">13/11/2026</font></td><td><font size="1">VEREADORA TAINÁ DE PAULA</font></td></tr>
<tr valign="top"><td><font size="1"><a href="/APL/Legislativos/scpro.nsf/5097d413bef5511203258632005692ff/be52fa7cd0e027cb03258d5b004d62f2?OpenDocument">0207/2025</a></font></td><td></td><td></td><td><font size="1">CONCEDE TÍTULO</font></td><td><font size="1">11/11/2025 00:00:00</font></td><td><font size="1">VEREADOR CARLO CAIADO,VEREADORA TÂNIA BASTOS,MESA DIRETORA</font></td></tr>
</table>'''


def test_lista():
    rows = R.parse_page(LISTA, 0)
    assert rows[0] == ('2771/2026', '8446f2be3d9bb8730325863200569352/22d355f98a8bedf903258eab005b2787', 'ALTERA OS LIMITES DO REFÚGIO.', '13/11/2026', ['VEREADORA TAINÁ DE PAULA'])
    assert rows[1][3] == '11/11/2025' and len(rows[1][4]) == 3
    assert norm_name('VEREADORA TANIA BASTOS') in IDX and norm_name('VEREADOR DR. ROGÉRIO AMORIM') in IDX


DOC = '''<html><body>ORDEM DO DIA
Projeto De Lei 1277/2025
<script>function _dSectionExpand(sec){}</script>
Data da Sessão:10/11/2026Hora:12:40
Texto da Ordem do Dia
O SR. PRESIDENTE - ANUNCIA-SE: EM DISCUSSÃO ÚNICA, PROJETO DE LEI Nº 1277/2025.
Em discussão.
(Concluída a votação nominal, constata-se que votaram SIM os Senhores Vereadores Alana Passos, Átila Nunes, Carlo Caiado, Maíra do Mst e William Siri 5 (cinco). E que votou NÃO o Senhor Vereador Pedro Duarte 1 (um). Absteve-se o Senhor Vereador Rafael Aloisio Freitas 1 (um). Presentes 7 (sete) senhores vereadores. Votando 6 (seis) senhores vereadores. Absteve-se 1 (um) senhor vereador).
O SR. PRESIDENTE - O Projeto de Lei nº 1277/2025 está aprovado.
</body></html>'''


def test_votacao():
    r = V.parse_doc(DOC, IDX)
    assert r['ok'] and r['code'] == 'PL 1277/2025' and r['date'] == '10/11/26' and not r['veto']
    assert [CANON[i] for i in r['S']] == ['ALANA PASSOS', 'ÁTILA NUNES', 'CARLO CAIADO', 'MAÍRA DO MST', 'WILLIAM SIRI']
    assert [CANON[i] for i in r['N']] == ['PEDRO DUARTE'] and [CANON[i] for i in r['A']] == ['RAFAEL ALOISIO FREITAS']
    # total declarado diferente do número de nomes => descartada
    assert not V.parse_doc(DOC.replace('5 (cinco)', '6 (seis)'), IDX)['ok']
    # nome desconhecido => descartada
    assert not V.parse_doc(DOC.replace('William Siri', 'Fulano de Tal'), IDX)['ok']
    # sem votação nominal => não entra
    assert V.parse_doc('<html><body>Em votação. (Os senhores vereadores registram seus votos)</body></html>', IDX) is None
    # plural de abstenção ("abstiveram-se")
    d2 = DOC.replace('Absteve-se o Senhor Vereador Rafael Aloisio Freitas 1 (um).',
                     'Abstiveram-se os Senhores Vereadores Rafael Aloisio Freitas e Rick Azevedo 2 (dois).')
    r2 = V.parse_doc(d2, IDX)
    assert r2['ok'] and sorted(CANON[i] for i in r2['A']) == ['RAFAEL ALOISIO FREITAS', 'RICK AZEVEDO']
    # "e as Senhoras Vereadoras" no meio da lista
    d3 = DOC.replace('Maíra do Mst e William Siri', 'Maíra do Mst e a Senhora Vereadora Joyce Trindade').replace('5 (cinco)', '5 (cinco)')
    r3 = V.parse_doc(d3.replace('Carlo Caiado, Maíra do Mst', 'Carlo Caiado, Maíra do Mst'), IDX)
    assert r3['ok'], r3
    # veto
    assert V.parse_doc(DOC.replace('PROJETO DE LEI Nº 1277/2025.', 'VETO TOTAL APOSTO AO PROJETO'), IDX)['veto']
    assert V.codigo('Projeto De Decreto Legislativo 200/2026') == 'PDL 200/2026' and V.codigo(' Requerimento - Vereador X - ') == '?'


def test_noticias():
    rss = ('<?xml version="1.0"?><rss version="2.0"><channel>'
           '<item><title>Câmara do Rio derruba 12 vetos da Prefeitura em sessão</title>'
           '<link>https://diariodorio.com/a.html</link><pubDate>Wed, 18 Nov 2026 10:00:00 -0300</pubDate></item>'
           '<item><title>Opinião: a política carioca em debate</title>'
           '<link>https://diariodorio.com/opiniao/b.html</link><pubDate>Wed, 18 Nov 2026 09:00:00 -0300</pubDate></item>'
           '<item><title>Vereador propõe nova lei de trânsito</title>'
           '<link>https://diariodorio.com/c.html</link><pubDate>Wed, 18 Nov 2026 08:00:00 -0300</pubDate></item>'
           '</channel></rss>')
    itens = N._parse_feed(rss)
    assert [t for t, _, _ in itens] == [
        'Câmara do Rio derruba 12 vetos da Prefeitura em sessão',
        'Opinião: a política carioca em debate',
        'Vereador propõe nova lei de trânsito']
    # item de opinião é descartado pela própria URL, mesmo citando Câmara/Prefeitura no título
    assert N.PADRAO_OPINIAO.search('https://diariodorio.com/opiniao/b.html')
    # título citando os dois: fica com quem aparece primeiro
    assert N._categoria('Câmara do Rio derruba 12 vetos da Prefeitura em sessão') == 'camara'
    assert N._categoria('Prefeitura do Rio pede aval à Câmara para obras') == 'prefeitura'
    assert N._categoria('Vereador propõe nova lei de trânsito') == 'camara'
    assert N._categoria('Chuva forte atinge o Rio nesta terça') is None  # nem um nem outro


if __name__ == '__main__':
    for n, f in list(globals().items()):
        if n.startswith('test_'): f(); print('ok', n)
