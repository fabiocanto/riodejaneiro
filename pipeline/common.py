import re, unicodedata, time, requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

APL = "https://aplicnt.camara.rj.gov.br/APL/Legislativos/"
UA = "riodejaneiro-dados/1.0 (+https://github.com/fabiocanto/riodejaneiro; leitura de dados publicos)"


def sessao():
    s = requests.Session()
    s.headers['User-Agent'] = UA
    r = Retry(total=3, connect=2, read=2, backoff_factor=1.5, status_forcelist=(429, 500, 502, 503, 504), allowed_methods=("GET",))
    s.mount('https://', HTTPAdapter(max_retries=r, pool_maxsize=16))
    return s


def get(s, url, tries=3):
    """GET com tentativas; devolve texto. Levanta erro se não conseguir (a coleta então falha e não publica)."""
    last = None
    for k in range(tries):
        try:
            r = s.get(url, timeout=(10, 45))
            if r.status_code == 200:
                return decodificar(r.content)
            last = 'HTTP %s' % r.status_code
        except requests.RequestException as e:
            last = str(e)
        time.sleep(2 * (k + 1))
    raise RuntimeError('falha ao baixar %s: %s' % (url, last))


def decodificar(b):
    try:
        return b.decode('utf-8')
    except UnicodeDecodeError:
        return b.decode('cp1252', errors='replace')


def norm_name(s):
    s = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
    s = re.sub(r'^(VEREADOR(?:A)?\s+)', '', s.strip().upper())
    return re.sub(r'\s+', ' ', s)
