#!/usr/bin/env bash
# Derruba as três APIs do sistema ligado e apaga os bancos delas (-v).
source "$(dirname "$0")/_comum.sh"

confere_docker

passo "derrubando Contrato, Ledger e Cadastro"
docker compose -p e2e-contract -f contract-api/docker-compose.yml -f compose/contract-api.e2e.yml down -v --remove-orphans
docker compose -p e2e-ledger -f ledger-api/docker-compose.yml down -v --remove-orphans
docker compose -p e2e-party -f party-api/docker-compose.yml down -v --remove-orphans
echo "   nada do sistema ligado ficou de pé"
