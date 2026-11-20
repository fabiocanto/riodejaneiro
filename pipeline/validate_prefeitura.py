"""Trava de qualidade da seção Prefeitura: compara a coleta nova com a última versão boa (baseline/).
Se houver qualquer ERRO, sai com código 1 e a seção Prefeitura não é publicada (resto do site segue normal).
uso: python validate_prefeitura.py RAW_DIR BASELINE_DIR RELATORIO.md"""
import json, os, sys

ANOS = [str(a) for a in range(2021, 2027)]
TOTAL_MINIMO = 1e9          # piso de verossimilhança: Rio gasta bem mais que R$1bi/ano
QUEDA_MAX = 0.20            # total pago não pode cair mais que 20% frente à última versão boa
MIN_SECRETARIAS = 5


def carregar(p, padrao=None):
    try: return json.load(open(p, encoding='utf-8'))
    except FileNotFoundError: return padrao


def main(raw, base, rel):
    E, W, I = [], [], []
    desp = carregar(os.path.join(raw, 'prefeitura_despesas.json'), {})
    contratos = carregar(os.path.join(raw, 'prefeitura_contratos.json'), {})
    b_desp = carregar(os.path.join(base, 'prefeitura_despesas.json'), {})

    if not desp:
        E.append('Prefeitura/Despesas: nenhum dado coletado.')
    for ano in ANOS:
        d = desp.get(ano)
        if not d:
            E.append('Prefeitura/Despesas %s: ano ausente na coleta.' % ano)
            continue
        total = sum(d.values())
        if len(d) < MIN_SECRETARIAS:
            E.append('Prefeitura/Despesas %s: só %d secretarias/órgãos (esperado pelo menos %d).' % (ano, len(d), MIN_SECRETARIAS))
        if total < TOTAL_MINIMO:
            E.append('Prefeitura/Despesas %s: total pago R$ %.0f é baixo demais para ser crível.' % (ano, total))
        else:
            I.append('Prefeitura/Despesas %s: R$ %.0f pagos, %d secretarias/órgãos.' % (ano, total, len(d)))
        bt = sum((b_desp.get(ano) or {}).values())
        if bt and total < bt * (1 - QUEDA_MAX):
            E.append('Prefeitura/Despesas %s: total caiu de R$ %.0f para R$ %.0f — queda maior que %.0f%%.' % (ano, bt, total, 100 * QUEDA_MAX))

    if not contratos:
        E.append('Prefeitura/Contratos: nenhum dado coletado.')
    for ano in ANOS:
        lst = contratos.get(ano)
        if not lst:
            W.append('Prefeitura/Contratos %s: nenhum contrato no topo da lista.' % ano)
            continue
        I.append('Prefeitura/Contratos %s: %d contratos no topo (maior: R$ %.0f).' % (ano, len(lst), lst[0]['valor']))
        total_desp = sum((desp.get(ano) or {}).values())
        if total_desp and lst[0]['valor'] > total_desp:
            W.append('Prefeitura/Contratos %s: o maior contrato (R$ %.0f, %s) é maior que todo o gasto pago do ano — pode ser erro na fonte oficial; conferir antes de confiar no número.' % (ano, lst[0]['valor'], lst[0]['orgao']))

    ok = not E
    linhas = ['# Relatório — seção Prefeitura', '',
              '**Resultado: %s**' % ('APROVADA — seção publicada' if ok else 'REPROVADA — seção Prefeitura não publicada; resto do site segue normal'), '']
    for t, L in (('Erros (bloqueiam a publicação da seção)', E), ('Avisos', W), ('Conferências', I)):
        if L: linhas += ['## ' + t] + ['- ' + x for x in L] + ['']
    open(rel, 'w', encoding='utf-8').write('\n'.join(linhas))
    print('\n'.join(linhas))
    # Marca para o build.py e o update_baseline.py: só com este arquivo presente a coleta desta
    # execução é usada; sem ele, a seção Prefeitura fica na última versão boa (baseline/).
    flag = os.path.join(raw, 'prefeitura_ok')
    if ok:
        open(flag, 'w').close()
    elif os.path.exists(flag):
        os.remove(flag)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3]))
