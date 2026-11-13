"""Trava de qualidade: compara a coleta nova com a última versão boa (pasta baseline/).
Se houver qualquer ERRO, sai com código 1 e NADA é publicado.
uso: python validate.py RAW_DIR BASELINE_DIR RELATORIO.md [--aceitar]"""
import json, os, re, sys, collections

# limites (ajuste aqui se a Câmara mudar o jeito de publicar)
PRES_CELULAS_MUDADAS_MAX = 0.05    # até 5% das células de meses antigos podem mudar (abonos tardios)
PROPS_QUEDA_MAX = 0.005            # lista oficial não pode encolher mais que 0,5%
PROPS_ALTA_MAX = 0.10              # nem crescer mais que 10% de uma vez
SEM_AUTOR_MAX = 0.03               # linhas sem nenhum autor reconhecido
VOTOS_QUEDA_MAX = 0.02
VOTOS_DIVERGENTES_MAX = 0.02
VOTOS_DESCARTADOS_ALTA_MAX = 10
MOCOES_FALTANDO_MAX = 0.005       # moções: contagem vs maior número oficial


def carregar(p, padrao=None):
    try: return json.load(open(p, encoding='utf-8'))
    except FileNotFoundError: return padrao


def main(raw, base, rel, aceitar=False):
    E, W, I = [], [], []
    pres = carregar(os.path.join(raw, 'presenca.json'), {})
    props = carregar(os.path.join(raw, 'props.json'), [])
    votos = carregar(os.path.join(raw, 'votos.json'), {'docs': [], 'dropped': 0})
    estat = carregar(os.path.join(raw, 'props_estat.json'), {})
    canon = carregar(os.path.join(raw, 'canon.json')) or carregar(os.path.join(base, 'canon.json'))
    b_pres = carregar(os.path.join(base, 'presenca.json'))
    b_votos = carregar(os.path.join(base, 'votos.json'))
    b_props = carregar(os.path.join(base, 'props_stats.json'))

    # ---- presença
    if not pres: E.append('Presença: nenhuma tabela mensal baixada.')
    meses = sorted(pres, key=lambda k: tuple(map(int, k.split('-'))))
    if meses:
        ult = pres[meses[-1]]
        if not 40 <= len(ult) <= 75: E.append('Presença: o último mês (%s) tem %d vereadores (esperado 40–75).' % (meses[-1], len(ult)))
        I.append('Presença: %d meses com tabela, último = %s (%d vereadores).' % (len(meses), meses[-1], len(ult)))
        for k in meses:
            nomes = [r[0] for r in pres[k]]
            if len(set(nomes)) != len(nomes): E.append('Presença %s: nome repetido.' % k)
            for n, f, a, t in pres[k]:
                if min(f, a, t) < 0 or f > 60: E.append('Presença %s: valor absurdo para %s (%d/%d/%d).' % (k, n, f, a, t))
        if canon:
            from common import norm_name
            conhecidos = {norm_name(c) for c in canon}
            novos = {r[0] for k in meses for r in pres[k] if norm_name(r[0]) not in conhecidos}
            if novos: E.append('Presença: nomes fora da lista de vereadores: %s. Atualize baseline/canon.json.' % sorted(novos))
    if b_pres and meses:
        falt = sorted(set(b_pres) - set(pres))
        if falt: E.append('Presença: meses que existiam e sumiram: %s.' % falt)
        total = mud = 0
        for k, rows in b_pres.items():
            if k not in pres: continue
            novo = {r[0]: tuple(r[1:3]) for r in pres[k]}
            for n, f, a, t in rows:
                total += 1
                if novo.get(n) != (f, a): mud += 1
        frac = mud / total if total else 0
        (E if frac > PRES_CELULAS_MUDADAS_MAX else I).append('Presença: %d de %d células de meses já publicados mudaram (%.1f%%).' % (mud, total, 100 * frac))

    # ---- propostas
    por_view = collections.Counter(r[0] for r in props)
    if not props: E.append('Propostas: nenhuma linha coletada.')
    else:
        I.append('Propostas: %d linhas gravadas (%s).' % (len(props), dict(sorted(por_view.items()))))
        if len({r[2] for r in props}) != len(props): E.append('Propostas: links repetidos na coleta.')
        sem = sum((estat.get('sem_autor_conhecido') or {}).values())
        tot = sem + len(props)
        if tot and sem / tot > SEM_AUTOR_MAX: E.append('Propostas: %.1f%% das linhas sem autor reconhecido (limite %.0f%%).' % (100 * sem / tot, 100 * SEM_AUTOR_MAX))
        tv = estat.get('total_por_lista') or {}
        # moções: números são cumulativos; a contagem deve ser quase igual ao maior número
        moc = [r for r in props if r[0] == 6]
        if moc:
            mx = max(int(re.match(r'\d+', r[1]).group()) for r in moc if re.match(r'\d+', r[1]))
            falta = 1 - len(moc) / mx if mx else 0
            if falta > MOCOES_FALTANDO_MAX: E.append('Moções: %d lidas para número máximo %d (faltam %.1f%%).' % (len(moc), mx, 100 * falta))
            else: I.append('Moções: %d lidas, maior número oficial %d.' % (len(moc), mx))
    if b_props and props:
        for v, n0 in b_props['por_lista'].items():
            n1 = por_view.get(int(v), 0)
            if n0 and (n1 < n0 * (1 - PROPS_QUEDA_MAX) or n1 > n0 * (1 + PROPS_ALTA_MAX)):
                E.append('Propostas, lista %s: %d linhas (antes %d) — variação fora do esperado.' % (v, n1, n0))

    # ---- votos
    docs = votos['docs']
    I.append('Votos: %d votações nominais, %d descartadas (lista de nomes não bateu).' % (len(docs), votos['dropped']))
    if not docs: E.append('Votos: nenhuma votação nominal lida.')
    ids = [d['id'] for d in docs]
    if len(set(ids)) != len(ids): E.append('Votos: documentos repetidos.')
    if b_votos and docs:
        if len(docs) < len(b_votos['docs']) * (1 - VOTOS_QUEDA_MAX): E.append('Votos: %d votações (antes %d) — queda grande.' % (len(docs), len(b_votos['docs'])))
        ant = {d['id']: d for d in b_votos['docs']}
        comuns = [d for d in docs if d['id'] in ant]
        div = [d['id'] for d in comuns if (d['S'], d['N'], d['A'], d['veto']) != (ant[d['id']]['S'], ant[d['id']]['N'], ant[d['id']]['A'], ant[d['id']]['veto'])]
        perdidos = [i for i in ant if i not in set(ids)]
        frac = len(div) / len(comuns) if comuns else 0
        (E if frac > VOTOS_DIVERGENTES_MAX else I).append('Votos: %d de %d votações já publicadas vieram diferentes (%.1f%%); %d sumiram.' % (len(div), len(comuns), 100 * frac, len(perdidos)))
        if votos['dropped'] > b_votos['dropped'] + VOTOS_DESCARTADOS_ALTA_MAX: E.append('Votos: descartadas subiu de %d para %d.' % (b_votos['dropped'], votos['dropped']))
        if aceitar and E:
            W += ['(--aceitar) ERRO ignorado: ' + e for e in E]; E = []
    elif not b_votos:
        W.append('Votos: sem baseline para comparar.')

    ok = not E
    linhas = ['# Relatório da coleta', '', '**Resultado: %s**' % ('APROVADA — o site será publicado' if ok else 'REPROVADA — nada foi publicado; o site continua na última versão boa'), '']
    for t, L in (('Erros (bloqueiam a publicação)', E), ('Avisos', W), ('Conferências', I)):
        if L: linhas += ['## ' + t] + ['- ' + x for x in L] + ['']
    open(rel, 'w', encoding='utf-8').write('\n'.join(linhas))
    print('\n'.join(linhas))
    return 0 if ok else 1


if __name__ == '__main__':
    a = [x for x in sys.argv[1:] if not x.startswith('--')]
    sys.exit(main(a[0], a[1], a[2], '--aceitar' in sys.argv))
