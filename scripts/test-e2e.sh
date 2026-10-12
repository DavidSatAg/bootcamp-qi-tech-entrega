#!/usr/bin/env bash
# Roda os testes de ponta a ponta (e2e/) contra as três APIs de pé.
# Antes: ./scripts/up.sh
#
# Argumentos extras vão direto para o pytest. Exemplo, só uma fase:
#   ./scripts/test-e2e.sh -k dinheiro
source "$(dirname "$0")/_comum.sh"

prepara_venv

for par in "Cadastro:$PARTY_PORT" "Contrato:$CONTRACT_PORT" "Ledger:$LEDGER_PORT"; do
    nome="${par%%:*}"; porta="${par##*:}"
    curl -fsS -o /dev/null --max-time 3 "http://localhost:$porta/health_check" \
        || erro "$nome não responde na porta $porta. Suba o sistema antes: ./scripts/up.sh"
done

passo "testes e2e contra Cadastro :$PARTY_PORT, Contrato :$CONTRACT_PORT e Ledger :$LEDGER_PORT"
"$PY" -m pytest e2e -v "$@"
