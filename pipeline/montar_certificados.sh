#!/usr/bin/env bash
# Os servidores da Câmara enviam a cadeia de certificados incompleta (falta o intermediário).
# Navegadores completam sozinhos; curl e Python não. Aqui buscamos o intermediário no endereço
# oficial indicado no próprio certificado (AIA) e montamos um pacote de confiança = certifi + intermediários.
# A verificação continua LIGADA: o intermediário só vale se encadear numa autoridade raiz conhecida.
set -u
OUT="${1:-ca-camara.pem}"
WORK="$(mktemp -d)"
ROOTS="$(python3 -c 'import certifi;print(certifi.where())')"
cp "$ROOTS" "$OUT"
for H in www.camara.rio aplicnt.camara.rj.gov.br; do
  openssl s_client -connect "$H:443" -servername "$H" </dev/null 2>/dev/null | openssl x509 > "$WORK/$H.0.pem" 2>/dev/null || { echo "sem certificado de $H"; continue; }
  for N in 0 1 2 3; do
    URL=$(openssl x509 -in "$WORK/$H.$N.pem" -noout -text | grep -A1 'CA Issuers' | grep -o 'http[^ ]*' | head -1)
    [ -z "$URL" ] && break
    curl -sS -m 20 -o "$WORK/$H.$N.der" "$URL" || break
    if openssl x509 -inform DER -in "$WORK/$H.$N.der" -out "$WORK/$H.$((N+1)).pem" 2>/dev/null; then :; \
    elif openssl x509 -in "$WORK/$H.$N.der" -out "$WORK/$H.$((N+1)).pem" 2>/dev/null; then :; else break; fi
    cat "$WORK/$H.$((N+1)).pem" >> "$OUT"
    echo "intermediário de $H: $(openssl x509 -in "$WORK/$H.$((N+1)).pem" -noout -subject)"
  done
done
echo "pacote: $OUT"
