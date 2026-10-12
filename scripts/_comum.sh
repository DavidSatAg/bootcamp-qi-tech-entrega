# Funções e variáveis comuns aos scripts. Não rode este arquivo direto:
# ele é carregado (source) pelos outros.

set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RAIZ"

# Portas do sistema ligado (as mesmas do README).
PARTY_PORT=3001
CONTRACT_PORT=3002
LEDGER_PORT=3003

passo() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
erro() { printf '\n\033[1;31mERRO: %s\033[0m\n' "$*" >&2; exit 1; }

confere_submodulos() {
    for svc in party-api contract-api ledger-api; do
        [ -f "$svc/docker-compose.yml" ] || erro "a pasta $svc está vazia. Rode: git submodule update --init"
    done
}

confere_docker() {
    command -v docker >/dev/null 2>&1 || erro "docker não encontrado no PATH"
    docker info >/dev/null 2>&1 || erro "o Docker não está rodando (abra o Docker Desktop e espere ele ficar pronto)"
    docker compose version >/dev/null 2>&1 || erro "o plugin 'docker compose' (v2) não está instalado"
}

# Acha um Python 3.11+ (a versão dos três serviços) e cria, uma vez, o venv
# .venv na raiz. Com 3.10, testes do Ledger quebram: o datetime.fromisoformat
# do 3.10 não lê datas terminadas em "Z".
prepara_venv() {
    if [ -x .venv/bin/python ]; then
        PY=.venv/bin/python
    elif [ -x .venv/Scripts/python.exe ]; then
        PY=.venv/Scripts/python.exe
    fi
    if [ -n "${PY:-}" ] && ! "$PY" -c 'import sys; assert sys.version_info >= (3, 11)' >/dev/null 2>&1; then
        erro "o .venv foi criado com um Python mais velho que 3.11. Apague a pasta .venv e rode de novo"
    fi
    if [ -z "${PY:-}" ]; then
        local base=""
        for cand in python3.11 "py -3.11" python3 python "py -3"; do
            if $cand -c 'import sys; assert sys.version_info >= (3, 11)' >/dev/null 2>&1; then
                base="$cand"
                break
            fi
        done
        [ -n "$base" ] || erro "Python 3.11 ou mais novo não encontrado (python3.11, py -3.11, python3 ou python)"
        passo "criando o venv .venv com: $base"
        $base -m venv .venv
        if [ -x .venv/bin/python ]; then PY=.venv/bin/python; else PY=.venv/Scripts/python.exe; fi
    fi
    if ! "$PY" -c 'import pytest, requests, sqlalchemy, dotenv, psycopg2' >/dev/null 2>&1; then
        passo "instalando as dependências de teste no .venv"
        "$PY" -m pip install --quiet --upgrade pip
        "$PY" -m pip install --quiet -r requirements-dev.txt
    fi
}

# Espera um GET responder 2xx (até 90 s).
espera_http() {
    local url="$1" nome="$2"
    for _ in $(seq 1 90); do
        if curl -fsS -o /dev/null --max-time 2 "$url"; then
            echo "   $nome respondeu em $url"
            return 0
        fi
        sleep 1
    done
    erro "$nome não respondeu em $url"
}
