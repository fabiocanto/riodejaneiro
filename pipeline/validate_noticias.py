"""Trava de qualidade da seção de notícias: confere se a coleta trouxe itens de verdade,
de fontes permitidas, com título/link/fonte preenchidos e só conteúdo factual (sem opinião).
Se não houver pelo menos MIN_ITENS de cada lado, a seção de notícias não é publicada nesta
execução — o site mantém as últimas notícias boas (baseline/noticias.json).
uso: python validate_noticias.py RAW_DIR BASELINE_DIR RELATORIO.md"""
import json
import os
import sys

from collect_noticias import FONTES, PADRAO_OPINIAO

MIN_ITENS = 3     # abaixo disso, a seção não publica (dado incompleto demais pra confiar)
ALVO_ITENS = 5    # quantidade-alvo por lado


def carregar(p, padrao=None):
    try:
        return json.load(open(p, encoding='utf-8'))
    except FileNotFoundError:
        return padrao


def _dominios_ok(url):
    return any(d in url for d in (dom for _, _, dom in FONTES))


def checar_lado(nome, itens, E, W, I):
    if not itens:
        E.append('%s: nenhuma notícia coletada.' % nome)
        return
    for it in itens:
        if not it.get('titulo') or not it.get('url') or not it.get('fonte'):
            E.append('%s: item sem título, link ou fonte — %r' % (nome, it))
        elif not _dominios_ok(it['url']):
            E.append('%s: link fora das fontes permitidas: %s' % (nome, it['url']))
        elif PADRAO_OPINIAO.search(it['url']):
            E.append('%s: link parece ser de opinião/coluna, não deveria ter passado: %s' % (nome, it['url']))
    if len(itens) < MIN_ITENS:
        E.append('%s: só %d notícia(s) (mínimo %d).' % (nome, len(itens), MIN_ITENS))
    elif len(itens) < ALVO_ITENS:
        W.append('%s: %d notícia(s) coletada(s) (meta: %d).' % (nome, len(itens), ALVO_ITENS))
    else:
        I.append('%s: %d notícias coletadas.' % (nome, len(itens)))


def main(raw, base, rel):
    E, W, I = [], [], []
    dados = carregar(os.path.join(raw, 'noticias.json'))
    if dados is None:
        E.append('Nenhum arquivo de notícias foi gerado pela coleta.')
        dados = {'camara': [], 'prefeitura': []}

    checar_lado('Notícias da Câmara', dados.get('camara') or [], E, W, I)
    checar_lado('Notícias da Prefeitura', dados.get('prefeitura') or [], E, W, I)

    for erro_fonte in dados.get('erros_fonte') or []:
        W.append('Fonte com problema nesta coleta: %s' % erro_fonte)

    ok = not E
    linhas = ['# Relatório — Notícias', '',
              '**Resultado: %s**' % ('APROVADO — notícias publicadas' if ok
                                      else 'REPROVADO — notícias desta coleta não publicadas; mantidas as últimas boas'), '']
    for t, L in (('Erros (bloqueiam a publicação)', E), ('Avisos', W), ('Conferências', I)):
        if L:
            linhas += ['## ' + t] + ['- ' + x for x in L] + ['']
    open(rel, 'w', encoding='utf-8').write('\n'.join(linhas))
    print('\n'.join(linhas))

    # Mesmo padrão da seção Prefeitura: só com este sinalizador presente é que o build.py e o
    # update_baseline.py usam a coleta desta execução; sem ele, ficam as últimas notícias boas.
    flag = os.path.join(raw, 'noticias_ok')
    if ok:
        open(flag, 'w').close()
    elif os.path.exists(flag):
        os.remove(flag)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3]))
