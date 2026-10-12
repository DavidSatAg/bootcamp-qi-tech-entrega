#!/usr/bin/env bash
# Sobe as três APIs ligadas entre si, na ordem certa:
#   1. Cadastro (party-api)    :3001  — com o mock do bureau de crédito (trilho externo)
#   2. Ledger   (ledger-api)   :3003  — chama o Cadastro real; mock do provedor Pix (trilho externo)
#   3. Contrato (contract-api) :3002  — chama o Cadastro e o Ledger reais
#
# Nenhum mock fica entre os três serviços. Cada serviço é um projeto Docker
# próprio (e2e-party, e2e-ledger, e2e-contract), e as ligações mudam só por
# variável de ambiente: nenhum arquivo dos repositórios é alterado.
#
# Os bancos nascem vazios a cada `down.sh` + `up.sh`.
source "$(dirname "$0")/_comum.sh"

confere_submodulos
confere_docker

passo "1/3 Cadastro (party-api) na porta $PARTY_PORT"
# BUREAU_API_TIMEOUT=1: o caso "bureau fora do ar" do e2e (CU-P5) depende dele.
export API_PORT=$PARTY_PORT DB_PORT=5433 BUREAU_API_TIMEOUT=1
docker compose -p e2e-party -f party-api/docker-compose.yml up -d --build --wait db bureau-mock
docker compose -p e2e-party -f party-api/docker-compose.yml up -d --build --wait --no-deps api
unset API_PORT DB_PORT BUREAU_API_TIMEOUT
espera_http "http://localhost:$PARTY_PORT/health_check" "Cadastro"

passo "2/3 Ledger (ledger-api) na porta $LEDGER_PORT, chamando o Cadastro real"
export API_PORT=$LEDGER_PORT DB_PORT=5435 PROVIDER_MOCK_PORT=8082 \
    PARTY_API_URL=http://host.docker.internal:$PARTY_PORT PARTY_API_TIMEOUT=3
docker compose -p e2e-ledger -f ledger-api/docker-compose.yml up -d --build --wait db provider-mock
docker compose -p e2e-ledger -f ledger-api/docker-compose.yml up -d --build --wait --no-deps api
unset API_PORT DB_PORT PROVIDER_MOCK_PORT PARTY_API_URL PARTY_API_TIMEOUT
espera_http "http://localhost:$LEDGER_PORT/health_check" "Ledger"

passo "3/3 Contrato (contract-api) na porta $CONTRACT_PORT, chamando o Cadastro e o Ledger reais"
export API_PORT=$CONTRACT_PORT DB_PORT=5434 \
    PARTY_API_URL=http://host.docker.internal:$PARTY_PORT \
    LEDGER_API_URL=http://host.docker.internal:$LEDGER_PORT
CONTRATO=(-p e2e-contract -f contract-api/docker-compose.yml -f compose/contract-api.e2e.yml)
docker compose "${CONTRATO[@]}" up -d --build --wait db
# --no-deps: o compose do Contrato declara os mocks dele como dependência da
# api; aqui eles não sobem, porque quem responde são os serviços reais.
docker compose "${CONTRATO[@]}" up -d --build --wait --no-deps api
unset API_PORT DB_PORT PARTY_API_URL LEDGER_API_URL
espera_http "http://localhost:$CONTRACT_PORT/health_check" "Contrato"

passo "Pronto. Containers de pé:"
docker ps --filter "name=e2e-" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo
echo "Agora rode os testes de ponta a ponta:  ./scripts/test-e2e.sh"
