import json,re,unicodedata,collections
def U(s): return ''.join(c for c in unicodedata.normalize('NFD',s) if unicodedata.category(c)!='Mn').upper()
TYPES=r'(RUA|AVENIDA|AV|ESTRADA|ESTR|EST|TRAVESSA|TV|PRACA|LARGO|ALAMEDA|BECO|RODOVIA|LADEIRA|CAMINHO|VIELA|ESCADARIA|PASSAGEM)'
STREET=re.compile(r'\b'+TYPES+r'\.?\s+(.+?)(?=,|\s[-–]\s|\sN[º°O]\b|\sN\.|\sNUMERO|\sALTURA|\sPROXIMO|\sEM FRENTE|\sFRENTE|\sESQUINA|\sNO\s|\sNA\s|\sNAS\s|\sNOS\s|\sEM\s|\sPARA\s|\s\(|\sQD\b|\sLT\b|\sLOCALIZAD|\sENTRE|\sCOM\s|\s\d|\.|;|\sSENTIDO|\sAO\s|\sAOS\s|\sA\s|\sDA\s(COMUNIDADE|ALTURA)|\sE\s(RUA|AV|ESTRADA|TRAVESSA|PRACA)|\sDE\s(FRENTE|ACORDO)|$)')
NORMT={'AV':'AVENIDA','ESTR':'ESTRADA','EST':'ESTRADA','TV':'TRAVESSA'}
def streets(e):
    u=U(e);out=[]
    for m in STREET.finditer(u):
        t=NORMT.get(m.group(1),m.group(1));n=re.sub(r'\s+',' ',m.group(2)).strip(' -–')
        if len(n)<2 or len(n)>45: continue
        s=t+' '+n
        if s not in out: out.append(s)
    return out
BAIRRO=[re.compile(r'\bNO\s+(?:SUB-?)?BAIRRO\s+(?:DE|DO|DA|DOS|DAS)?\s*([A-Z0-9 \'-]{3,40}?)(?=,|\.|\s[-–]|\(|\sRIO DE JANEIRO|$)'),
        re.compile(r'(?:,|\s[-–]|\sEM|\sNA|\sNO)\s+(?:(?:NA|NO|NAS|NOS)\s+)?([A-Z][A-Z \'-]{2,35}?)\s*(?:\(.*\))?[\s./]*(?:RIO DE JANEIRO(?:\s*/\s*RJ)?)?[\s.]*$')]
def bairro(e):
    u=U(e).strip()
    for r in BAIRRO:
        m=r.search(u)
        if m:
            b=re.sub(r'\s+',' ',m.group(1)).strip(' -–.')
            b=re.sub(r'^(EM|NA|NO)\s+','',b)
            if ' EM ' in b: b=b.split(' EM ')[-1]
            b=re.sub(r'\s+(RIO DE JANEIRO|RJ)$','',b).strip()
            if 3<=len(b)<=35 and not re.search(r'\b(RUA|AVENIDA|ESTRADA|N[º°O]|NUMERO|ALTURA|ESCOLA|CRECHE|PRACA|QUADRA)\b',b): return b
    return ''

CATS=[("Buraco, asfalto e pavimentação",r"BURACO|ASFALT|PAVIMENT|RECAPE|AFUNDAMENTO DE PISTA|ASFALTO LISO|REPAVIMENT"),
("Poda de árvore e capina",r"PODA|ARVORE|AVORE|CAPINA|ROCAD|RACAO DE MATO"),
("Esgoto, ralo e drenagem",r"GRELHA|RALO|BUEIRO|MANILHA|DRENAGEM|ESGOTO|GALERIA|CAIXA COLETORA|DESOBSTRU|ALAGAMENT|\bVALA\b|CANAL"),
("Lixo e limpeza",r"LIXO|ENTULHO|LIMPEZA|COLETA|CACAMBA|COMLURB|RESIDUO|DESCARTE|VEICULO|CARCACA|ROEDORES|DEDETIZ|MOSQUITO|FOCOS"),
("Iluminação e fiação",r"ILUMINA|POSTE|LUMINARIA|RIOLUZ|CACA FIOS|CACA-FIOS|FIACAO|LAMPADA|FIOS"),
("Calçada, escada e obras",r"CALCADA|CALCAMENTO|MEIO-FIO|MEIO FIO|RAMPA|ACESSIBILIDADE|ESCADA|URBANIZA|CONTENCAO|MURO|OBRA|REFORMA|REVITALIZA|RECUPERA|PINTURA|MANUTENCAO"),
("Trânsito e transporte",r"SINALIZA|SEMAFORO|FAIXA|LOMBADA|REDUTOR|PONTO DE ONIBUS|ONIBUS|TRANSPORTE|TRANSITO|ESTACIONAMENTO|CICLOVIA|\bBRT\b|\bVAN\b|LINHA DE"),
("Praças, quadras e lazer",r"PRACA|QUADRA|ACADEMIA|PARQUE|PLAYGROUND|CAMPO|BRINQUEDO|ESPORT|LAZER|BANCOS"),
("Segurança",r"SEGURANCA|POLICIAMENTO|CAMERA|GUARDA|PATRULHA|VIGILANCIA"),
("Saúde e educação",r"SAUDE|HOSPITAL|CLINICA|\bUPA\b|POSTO DE SAUDE|ESCOLA|CRECHE|EDUCACAO|MEDIC|VACINA")]
CATRE=[(n,re.compile(p)) for n,p in CATS]
def cat(e):
    u=U(e)
    for i,(n,r) in enumerate(CATRE):
        if r.search(u): return i
    return len(CATS)
