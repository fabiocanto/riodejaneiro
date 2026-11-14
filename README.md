# Vereadores do Rio — o que cada um faz

Site em português simples, só com dados oficiais da Câmara Municipal do Rio de Janeiro
([camara.rio](https://www.camara.rio)): faltas por mês, propostas apresentadas e votos.
Cada número tem um link para a fonte. O site não dá nota nem opina.

## Como o site se atualiza sozinho

O fluxo `.github/workflows/atualizar.yml` roda **todo dia às 05:47 (Brasília)** — de madrugada, mas fora da janela (0h–4h) em que os servidores da Câmara costumam ficar fora do ar — e também pode ser disparado
à mão em *Actions → Atualizar site → Run workflow*.

1. **Coleta de novo** na Câmara (`pipeline/collect_*.py`): faltas mensais, listas de proposições e transcrições de votações nominais.
2. **Trava de qualidade** (`pipeline/validate.py`): compara com a última versão boa guardada em `baseline/`.
   Reprova, e **nada é publicado**, se, por exemplo: faltar algum mês que já existia; o último mês vier com poucos vereadores;
   alguma lista de propostas encolher mais de 0,5% ou crescer mais de 10% de uma vez; as moções não baterem com o maior número oficial;
   mais de 3% das propostas ficarem sem autor reconhecido; as votações já publicadas vierem diferentes (>2%) ou sumirem;
   aparecer um vereador desconhecido; o total de faltas não bater (`Total = Faltas − Abonadas`).
3. **Gera o site** (`pipeline/build.py`) e **abre num navegador de verdade** (`tests/smoke.py`): 60 nomes, abas, busca, nenhum erro.
4. **Publica** no GitHub Pages e grava a coleta como nova "última versão boa".

Se qualquer passo falhar, o fluxo fica vermelho (o GitHub manda e-mail) e o site continua exatamente como estava.
O relatório da conferência aparece no resumo de cada execução.

## Configuração única

*Settings → Pages → Build and deployment → Source: **GitHub Actions**.*

## Quando o robô bloquear

Abra a execução em *Actions*, leia o relatório. Se a Câmara só mudou o jeito de publicar e o dado novo está certo,
ajuste os limites no topo de `pipeline/validate.py` (ou rode à mão marcando **aceitar**, que só relaxa a comparação de votos).
Um vereador novo (suplente que assume) precisa ser acrescentado em `baseline/canon.json`.

## Regras de agrupamento das propostas

Estão em `pipeline/classify.py` (igual para todos os vereadores) e descritas no próprio site em "Como agrupamos".
Rua e bairro são extraídos do texto da proposta por `pipeline/ext.py` (aproximado).

## Testes

```
pip install -r requirements.txt && python -m playwright install chromium
python tests/test_parsers.py
python pipeline/build.py <pasta com presenca.json, props.json, votos.json> _site && python tests/smoke.py _site
```
