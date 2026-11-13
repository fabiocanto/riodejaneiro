"""Regra única de agrupamento das propostas (igual para todos os vereadores)."""
import re
from ext import U

# índices das listas oficiais (scpro)
V_PL, V_PLC, V_ELO, V_PDL, V_PR, V_IND, V_MOC, V_RI, V_RQ = range(9)
VIEWS = ["LeiInt", "LeiCompInt", "EmendaInt", "DecretoInt", "ResolucaoInt",
         "IndInt", "mocaoInt", "ReqInfInt", "ReqInt"]
GROUPS = ["bairro", "perguntas", "homenagem", "lei", "outros"]

HOM = r'CONGRAT|LOUVOR|APLAUSO|RECONHECIMENTO|PESAR|HOMENAGEM|PARABENS|SAUDA|AGRADECIMENT|MEDALHA'
ASK = r'INFORMACO|ESCLARECIMENTO|DADOS|RELATORIO'
RE_HOM, RE_ASK = re.compile(HOM), re.compile(ASK)
RE_REQ_HOM = re.compile(HOM + r'|TITULO')
RE_PL_HOM = re.compile(r'CALENDARIO|^DA (?:O )?NOME\b|COMO LOGRADOURO PUBLICO,|DENOMINA')
RE_PR_HOM = re.compile(r'\bNOME\b|DENOMINA')
RE_PDL_HOM = re.compile(r'TITULO|MEDALHA')


def group(view, ementa):
    u = U(ementa)
    if view == V_IND: return 'bairro'
    if view == V_RI: return 'perguntas'
    if view == V_MOC: return 'homenagem' if RE_HOM.search(u) else 'outros'
    if view == V_RQ:
        if RE_ASK.search(u): return 'perguntas'
        return 'homenagem' if RE_REQ_HOM.search(u) else 'outros'
    if view == V_PDL: return 'homenagem' if RE_PDL_HOM.search(u) else 'outros'
    if view == V_PR: return 'homenagem' if RE_PR_HOM.search(u) else 'outros'
    if view == V_PL: return 'homenagem' if RE_PL_HOM.search(u) else 'lei'
    return 'lei'  # PLC e emenda à Lei Orgânica
