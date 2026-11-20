"""Depois de uma publicação aprovada, grava a coleta como nova 'última versão boa'.
uso: python update_baseline.py RAW_DIR BASELINE_DIR"""
import json, os, sys, collections

raw, base = sys.argv[1:3]
L = lambda n: json.load(open(os.path.join(raw, n), encoding='utf-8'))
W = lambda n, o: json.dump(o, open(os.path.join(base, n), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
# Dados da Câmara (presença/propostas/votos): só existem em RAW_DIR quando esta execução
# de fato recoletou a Câmara. Numa rodada mais leve que só atualiza notícias, esses arquivos
# não existem aqui — e então o baseline/ fica como estava (já é a última versão boa).
if os.path.exists(os.path.join(raw, 'presenca.json')):
    W('presenca.json', L('presenca.json'))
    v = L('votos.json')
    W('votos.json', {'docs': v['docs'], 'dropped': v['dropped']})
    props = L('props.json')
    W('props_stats.json', {'por_lista': dict(collections.Counter(str(r[0]) for r in props)), 'linhas': len(props)})
    W('props.json', props)  # completo, não só as estatísticas — permite ao build.py montar o
                             # site inteiro numa rodada que não recoletou a Câmara (ex.: só notícias)
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

# Notícias: mesma regra — só grava como "última versão boa" quando esta coleta passou na
# conferência (validate_noticias.py criou raw/noticias_ok). Caso contrário, mantém as últimas
# notícias boas em baseline/noticias.json.
if os.path.exists(os.path.join(raw, 'noticias_ok')):
    if os.path.exists(os.path.join(raw, 'noticias.json')): W('noticias.json', L('noticias.json'))
