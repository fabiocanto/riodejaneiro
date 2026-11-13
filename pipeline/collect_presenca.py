"""Baixa a tabela mensal de faltas (exportação oficial da Câmara) de jan/2025 até o mês atual.
uso: python collect_presenca.py SAIDA.json"""
import re, sys, json, html, datetime
from common import sessao, get

URL = "https://www.camara.rio/includes_php/vereadores_frequencia_excel.php?ano=%d&mes=%d"
ROW = re.compile(r'<tr>\s*<td>([^<]+)</td>\s*<td[^>]*>\s*(\d+)\s*</td>\s*<td[^>]*>\s*(\d+)\s*</td>\s*<td[^>]*>\s*(\d+)\s*</td>\s*</tr>', re.S)


def parse(texto):
    """-> lista [nome, faltas, abonadas, total]; lança erro se o total não bater (dado estranho)."""
    out = []
    for nome, f, a, t in ROW.findall(texto):
        nome = re.sub(r'\s+', ' ', html.unescape(nome)).strip()
        f, a, t = int(f), int(a), int(t)
        if t != f - a:
            raise ValueError('Total != Faltas - Abonadas para %s (%d, %d, %d)' % (nome, f, a, t))
        out.append([nome, f, a, t])
    return out


def meses(hoje):
    y, m = 2025, 1
    while (y, m) <= (hoje.year, hoje.month):
        yield y, m
        m += 1
        if m == 13: y, m = y + 1, 1


def main(saida, hoje=None):
    hoje = hoje or datetime.date.today()
    s = sessao()
    res = {}
    for y, m in meses(hoje):
        rows = parse(get(s, URL % (y, m)))
        if rows: res['%d-%d' % (y, m)] = rows
        print('%d-%02d: %d vereadores' % (y, m, len(rows)))
    json.dump(res, open(saida, 'w', encoding='utf-8'), ensure_ascii=False)


if __name__ == '__main__':
    main(sys.argv[1])
