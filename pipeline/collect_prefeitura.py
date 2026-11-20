"""Coleta dados abertos de orçamento/despesas e contratos da Prefeitura do Rio (Portal Contas Rio / SIAFIC Carioca).
Fonte: https://riotransparente.rio.rj.gov.br/arquivos/ — arquivos CSV públicos, sem login, por ano.
uso: python collect_prefeitura.py SAIDA_DIR
Grava SAIDA_DIR/prefeitura_despesas.json e SAIDA_DIR/prefeitura_contratos.json e SAIDA_DIR/prefeitura_fontes.json.
Se não conseguir reconhecer as colunas esperadas em algum ano, levanta erro (a coleta falha e o site
não é publicado — ver validate.py)."""
import csv, io, json, os, re, sys, unicodedata, collections
from common import sessao, get

BASE = 'https://riotransparente.rio.rj.gov.br/arquivos/'
ANOS = list(range(2021, 2027))  # 2021-2024: 1º e início do 2º mandato de Eduardo Paes; 2026: Paes até 20/mar, depois Eduardo Cavaliere
URL_DESPESAS = {a: BASE + 'Open_Data_Desp_%d.csv' % a for a in ANOS}
URL_CONTRATOS = BASE + 'Open_Data_CONTRATOS.csv'  # arquivo único, cobre todos os anos (coluna Ano_Celebracao)
TOP_CONTRATOS_POR_ANO = 15


def _sem_acento(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn').upper()


def _num(s):
    s = (s or '').strip()
    if not s: return 0.0
    s = s.replace('.', '').replace(',', '.')
    try: return float(s)
    except ValueError: return None


def _achar_coluna(campos, precisa_ter, *, prioriza=(), evita=()):
    """Entre os cabeçalhos do CSV, acha o único que contém todas as palavras-chave (sem acento/maiúsculas)
    e nenhuma das palavras de 'evita' (usado para excluir uma coluna parecida mas com outro significado,
    como 'Pago_Restos_Pagar' quando se quer só 'Pago' do exercício).
    Levanta erro se achar zero ou mais de um candidato (coleta não deve adivinhar)."""
    cand = []
    for c in campos:
        cu = _sem_acento(c)
        if all(p in cu for p in precisa_ter) and not any(e in cu for e in evita):
            cand.append(c)
    if len(cand) > 1:
        for pref in prioriza:
            melhores = [c for c in cand if pref in _sem_acento(c)]
            if len(melhores) == 1: return melhores[0]
    if len(cand) != 1:
        raise RuntimeError('coluna ambígua/não encontrada para %s em %s (candidatos: %s)' % (precisa_ter, campos, cand))
    return cand[0]


def _achar_coluna_tentativas(campos, tentativas):
    """Tenta várias combinações de palavras-chave em ordem (para quando o portal usa nomes de coluna
    diferentes conforme o ano/portal — ex. 'Pago' no portal novo, 'Despesa_Paga' no portal antigo).
    Usa a primeira tentativa que achar exatamente uma coluna; se nenhuma achar, levanta erro com todas
    as tentativas (a coleta não deve adivinhar)."""
    erros = []
    for precisa_ter, extras in tentativas:
        try:
            return _achar_coluna(campos, precisa_ter, **extras)
        except RuntimeError as e:
            erros.append(str(e))
    raise RuntimeError('nenhuma das colunas esperadas foi encontrada: ' + ' | '.join(erros))


def _col_valor_pago(campos):
    return _achar_coluna_tentativas(campos, [
        (('PAGO',), {'evita': ('RESTOS',)}),        # portal novo (SIAFIC Carioca): Pago / Pago_Restos_Pagar
        (('DESPESA', 'PAGA'), {}),                   # portal antigo: Despesa_Paga (distinto de Pagamento_RP)
    ])


def ler_csv(texto):
    amostra = texto[:4096]
    delim = ';' if amostra.count(';') > amostra.count(',') else ','
    return list(csv.DictReader(io.StringIO(texto), delimiter=delim))


def coletar_despesas(sess):
    """-> {ano: {secretaria: valor_pago_total}}, {ano: linhas}"""
    por_ano, linhas_por_ano = {}, {}
    for ano, url in URL_DESPESAS.items():
        texto = get(sess, url)
        linhas = ler_csv(texto)
        if not linhas:
            raise RuntimeError('Despesas %d: arquivo vazio (%s).' % (ano, url))
        campos = linhas[0].keys()
        col_org = _achar_coluna(campos, ('ORGAO',), prioriza=('DESCRICAO',))
        col_pago = _col_valor_pago(campos)
        soma = collections.Counter()
        ruim = 0
        for r in linhas:
            v = _num(r.get(col_pago))
            if v is None: ruim += 1; continue
            soma[r.get(col_org, '').strip() or '(não informado)'] += v
        if ruim / len(linhas) > 0.02:
            raise RuntimeError('Despesas %d: %.1f%% das linhas com valor ilegível na coluna %s.' % (ano, 100 * ruim / len(linhas), col_pago))
        por_ano[ano] = dict(soma)
        linhas_por_ano[ano] = len(linhas)
    return por_ano, linhas_por_ano


def coletar_contratos(sess):
    """-> {ano: [ {orgao, favorecido, objeto, valor, situacao} , ... maiores N ]}, total de linhas lidas"""
    texto = get(sess, URL_CONTRATOS)
    linhas = ler_csv(texto)
    if not linhas:
        raise RuntimeError('Contratos: arquivo vazio (%s).' % URL_CONTRATOS)
    campos = linhas[0].keys()
    col_ano = _achar_coluna(campos, ('ANO', 'CELEBR'))
    col_org = _achar_coluna(campos, ('ORGAO', 'CONTRATANTE'), prioriza=('DESCRICAO',))
    col_fav = _achar_coluna(campos, ('FAVORECID',), prioriza=('DESCRICAO',))
    col_obj = _achar_coluna(campos, ('OBJETO',))
    col_val = _achar_coluna(campos, ('VALOR', 'ATUALIZADO'))
    col_sit = _achar_coluna(campos, ('SITUACAO',))
    por_ano = collections.defaultdict(list)
    for r in linhas:
        ano = re.match(r'\s*(\d{4})\s*$', r.get(col_ano, '') or '')
        if not ano: continue
        ano = int(ano.group(1))
        if ano not in ANOS: continue
        v = _num(r.get(col_val))
        if v is None: continue
        por_ano[ano].append({
            'orgao': (r.get(col_org) or '').strip(),
            'favorecido': (r.get(col_fav) or '').strip(),
            'objeto': (r.get(col_obj) or '').strip(),
            'valor': v,
            'situacao': (r.get(col_sit) or '').strip(),
        })
    saida = {}
    for ano, lst in por_ano.items():
        lst.sort(key=lambda x: -x['valor'])
        saida[str(ano)] = lst[:TOP_CONTRATOS_POR_ANO]
    return saida, len(linhas)


def main(saida_dir):
    os.makedirs(saida_dir, exist_ok=True)
    sess = sessao()
    desp, desp_linhas = coletar_despesas(sess)
    contratos, n_contratos = coletar_contratos(sess)
    fontes = {'despesas': {str(a): u for a, u in URL_DESPESAS.items()}, 'contratos': URL_CONTRATOS}
    json.dump({str(a): v for a, v in desp.items()}, open(os.path.join(saida_dir, 'prefeitura_despesas.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    json.dump(contratos, open(os.path.join(saida_dir, 'prefeitura_contratos.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    json.dump(fontes, open(os.path.join(saida_dir, 'prefeitura_fontes.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('despesas: %s' % {a: n for a, n in desp_linhas.items()})
    print('contratos: %d linhas lidas, %d anos com top %d' % (n_contratos, len(contratos), TOP_CONTRATOS_POR_ANO))


if __name__ == '__main__':
    main(sys.argv[1])
