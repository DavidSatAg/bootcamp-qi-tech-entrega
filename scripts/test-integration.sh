#!/usr/bin/env bash
# Roda a suíte de integração de cada serviço, sozinho, contra os mocks dele.
# Um serviço por vez: sobe a pilha dele, roda o pytest e derruba (com -v).
#
# Estas suítes usam as mesmas portas do sistema ligado, por isso o script
# derruba o sistema ligado antes. Depois, para voltar a ele: ./scripts/up.sh
#
# Para rodar só um serviço:  ./scripts/test-integration.sh ledger-api
source "$(dirname "$0")/_comum.sh"

confere_submodulos
confere_docker
prepara_venv
PY_ABS="$RAIZ/$PY"

"$RAIZ/scripts/down.sh"

servicos=("$@")
[ ${#servicos[@]} -gt 0 ] || servicos=(party-api contract-api ledger-api)

resumo=()
for svc in "${servicos[@]}"; do
    [ -f "$svc/docker-compose.yml" ] || erro "serviço desconhecido: $svc"
    passo "$svc: subindo a pilha dele (API, banco e mocks)"
    (
        cd "$svc"
        # O .env é local e fica fora do Git; sem ele, a suíte não acha as portas.
        [ -f .env ] || cp .env.example .env
        docker compose up -d --build --wait
        set +e
        "$PY_ABS" -m pytest -q -p no:cacheprovider
        status=$?
        set -e
        docker compose down -v --remove-orphans
        exit $status
    ) && resumo+=("$svc: verde") || resumo+=("$svc: FALHOU")
done

passo "resumo"
printf '   %s\n' "${resumo[@]}"
printf '%s\n' "${resumo[@]}" | grep -q FALHOU && exit 1 || exit 0
