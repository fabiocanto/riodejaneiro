"""Depois de uma publicação aprovada, grava a coleta como nova 'última versão boa'.
uso: python update_baseline.py RAW_DIR BASELINE_DIR"""
import json, os, sys, collections

raw, base = sys.argv[1:3]
L = lambda n: json.load(open(os.path.join(raw, n), encoding='utf-8'))
W = lambda n, o: json.dump(o, open(os.path.join(base, n), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
W('presenca.json', L('presenca.json'))
v = L('votos.json')
W('votos.json', {'docs': v['docs'], 'dropped': v['dropped']})
props = L('props.json')
W('props_stats.json', {'por_lista': dict(collections.Counter(str(r[0]) for r in props)), 'linhas': len(props)})
if os.path.exists(os.path.join(raw, 'canon.json')): W('canon.json', L('canon.json'))
if os.path.exists(os.path.join(raw, 'votos_cache.json')): W('votos_cache.json', L('votos_cache.json'))
flag = os.path.join(base, 'ACEITAR_VOTOS')
if os.path.exists(flag): os.remove(flag)  # o aceite vale para uma publicação só

# Seção Prefeitura: só grava como "última versão boa" quando a coleta desta execução passou
# na própria conferência (validate_prefeitura.py criou raw/prefeitura_ok). Caso contrário, o
# baseline/ fica como estava, preservando os últimos dados bons da Prefeitura.
if os.path.exists(os.path.join(raw, 'prefeitura_ok')):
    for n in ('prefeitura_despesas.json', 'prefeitura_contratos.json', 'prefeitura_fontes.json'):
        if os.path.exists(os.path.join(raw, n)): W(n, L(n))
