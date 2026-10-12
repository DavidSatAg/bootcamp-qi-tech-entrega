# Bootcamp QI Tech — Conta com Propósito: entrega

Este repositório junta os três serviços do projeto e prova que eles
funcionam **juntos**: sobe os três ligados entre si, na ordem certa, e roda
os testes de ponta a ponta (e2e) contra eles.

| Pasta | Serviço | O que faz |
|---|---|---|
| `party-api/` | **Cadastro** | pessoas e empresas (partes), clientes, verificação no bureau de crédito |
| `contract-api/` | **Contrato** | contratos de locação, a divisão (split) de cada aluguel, ativação, reajuste e encerramento |
| `ledger-api/` | **Ledger** | o livro-razão em partidas dobradas: entrada por Pix, divisão, repasse, carteira, estorno, MED, extrato e integridade |

Cada pasta é um **submódulo Git**, ou seja, o repositório do próprio
serviço, fixado no commit que foi testado (ver `VERSIONS.md`). Este
repositório não tem código de produto: só os scripts para subir e testar,
os testes e2e e a RFC (`docs/rfc-conta-com-proposito.md`).

Quem chama quem:

```
                 ┌──────────────┐
   avaliador ──▶ │   Contrato   │ :3002
                 └──┬────────┬──┘
                    │        │ ativa o contrato: provisiona as contas
     confere partes │        ▼
                    │   ┌──────────┐      provedor Pix (mock) :8082
                    │   │  Ledger  │ :3003 ───▶ trilho externo
                    │   └────┬─────┘
                    ▼        │ confere o dono antes de repasse/carteira
                 ┌──────────┐◀┘
                 │ Cadastro │ :3001 ───▶ bureau de crédito (mock) :8081
                 └──────────┘            trilho externo
```

Nada é mock entre os três serviços. Só o bureau de crédito e o provedor
Pix são mocks (WireMock), porque são sistemas de fora.

---

## O que o avaliador precisa fazer

```bash
git clone --recurse-submodules git@github.com:DavidSatAg/bootcamp-qi-tech-entrega.git
cd bootcamp-qi-tech-entrega
./scripts/up.sh          # sobe Cadastro, Ledger e Contrato, nessa ordem
./scripts/test-e2e.sh    # roda os testes e2e: esperado "9 passed"
./scripts/down.sh        # derruba tudo
```

O resto deste README explica cada passo, o que esperar e o que fazer se
algo der errado.

---

## 0. Pré-requisitos

| Ferramenta | Versão | Para quê |
|---|---|---|
| Git | qualquer recente | clonar com os submódulos |
| Docker, com o `docker compose` v2 | Docker Desktop 4.x ou Docker Engine 24+ | subir as APIs, os bancos e os mocks |
| Python | 3.10 ou mais novo | rodar os testes (o script cria um venv sozinho) |
| Bash e `curl` | — | rodar os scripts |

- **Windows:** rode tudo no **Git Bash**, que já vem com o Git for
  Windows. PowerShell e CMD não rodam os scripts `.sh`. O Docker Desktop
  precisa estar aberto e mostrar "Engine running".
- **Linux:** o seu usuário precisa poder rodar `docker` sem `sudo`.
- **macOS:** Docker Desktop aberto. Num Mac M1, M2 ou M3 funciona do mesmo jeito.

**Portas livres.** O sistema usa estas portas da sua máquina. Se alguma
estiver ocupada, veja a seção 6.

| Porta | Serviço |
|---|---|
| 3001, 5433 | Cadastro (API e banco) |
| 3002, 5434 | Contrato (API e banco) |
| 3003, 5435 | Ledger (API e banco) |
| 8081 | mock do bureau de crédito |
| 8082 | mock do provedor Pix |

---

## 1. Clonar

```bash
git clone --recurse-submodules git@github.com:DavidSatAg/bootcamp-qi-tech-entrega.git
cd bootcamp-qi-tech-entrega
```

O `--recurse-submodules` já traz os três serviços. **Clonou sem ele?** As
pastas `party-api/`, `contract-api/` e `ledger-api/` ficam vazias. Rode:

```bash
git submodule update --init
```

**Acesso.** Os quatro repositórios (este e os três serviços) estão no
GitHub. O clone acima usa SSH, então a sua chave SSH precisa estar
cadastrada no GitHub e com acesso aos quatro. Prefere HTTPS? Antes do clone, rode:

```bash
git config --global url."https://github.com/".insteadOf git@github.com:
git clone --recurse-submodules https://github.com/DavidSatAg/bootcamp-qi-tech-entrega.git
```

A primeira linha faz o Git trocar SSH por HTTPS também nos submódulos.

---

## 2. Subir os três serviços

```bash
./scripts/up.sh
```

Na primeira vez demora alguns minutos, porque o Docker baixa as imagens e
constrói as três APIs. Nas próximas, leva segundos.

### O que o script faz, e em que ordem

A ordem importa: **o Ledger chama o Cadastro, e o Contrato chama os dois.**
Por isso o script sobe um de cada vez e só passa para o próximo quando o
anterior responde no `/health_check`.

| # | Serviço | Porta | Sobe junto | Chama |
|---|---|---|---|---|
| 1 | Cadastro | 3001 | banco (5433) e mock do bureau (8081) | o bureau (mock) |
| 2 | Ledger | 3003 | banco (5435) e mock do provedor Pix (8082) | o **Cadastro real** e o provedor (mock) |
| 3 | Contrato | 3002 | banco (5434) | o **Cadastro real** e o **Ledger real** |

Cada serviço é um projeto Docker separado (`e2e-party`, `e2e-ledger` e
`e2e-contract`). As ligações entre eles mudam só por variável de ambiente;
**nenhum arquivo dos serviços é alterado.** Dentro de um container, o
endereço da sua máquina é `host.docker.internal`: é por ele que um serviço
acha a porta publicada do outro.

<details>
<summary>Os mesmos passos, comando a comando (sem o script)</summary>

Rode na raiz do repositório, **um bloco de cada vez e na ordem**. Os
comandos já trazem os valores que o script usa.

```bash
# 1. Cadastro. BUREAU_API_TIMEOUT=1 é o que faz o caso "bureau fora do ar" do e2e virar "pending".
API_PORT=3001 DB_PORT=5433 BUREAU_API_TIMEOUT=1 \
  docker compose -p e2e-party -f party-api/docker-compose.yml up -d --build --wait db bureau-mock
API_PORT=3001 DB_PORT=5433 BUREAU_API_TIMEOUT=1 \
  docker compose -p e2e-party -f party-api/docker-compose.yml up -d --build --wait --no-deps api

# 2. Ledger, apontando para o Cadastro real (sem o party-mock dele)
API_PORT=3003 DB_PORT=5435 PROVIDER_MOCK_PORT=8082 \
  PARTY_API_URL=http://host.docker.internal:3001 PARTY_API_TIMEOUT=3 \
  docker compose -p e2e-ledger -f ledger-api/docker-compose.yml up -d --build --wait db provider-mock
API_PORT=3003 DB_PORT=5435 PROVIDER_MOCK_PORT=8082 \
  PARTY_API_URL=http://host.docker.internal:3001 PARTY_API_TIMEOUT=3 \
  docker compose -p e2e-ledger -f ledger-api/docker-compose.yml up -d --build --wait --no-deps api

# 3. Contrato, apontando para o Cadastro e o Ledger reais (sem os mocks dele)
API_PORT=3002 DB_PORT=5434 \
  PARTY_API_URL=http://host.docker.internal:3001 LEDGER_API_URL=http://host.docker.internal:3003 \
  docker compose -p e2e-contract -f contract-api/docker-compose.yml -f compose/contract-api.e2e.yml \
  up -d --build --wait db
API_PORT=3002 DB_PORT=5434 \
  PARTY_API_URL=http://host.docker.internal:3001 LEDGER_API_URL=http://host.docker.internal:3003 \
  docker compose -p e2e-contract -f contract-api/docker-compose.yml -f compose/contract-api.e2e.yml \
  up -d --build --wait --no-deps api
```

- O `--no-deps` sobe a API sem os mocks que o compose do serviço declara
  como dependência: no sistema ligado, quem responde são os serviços reais.
- O `compose/contract-api.e2e.yml` só acrescenta `host.docker.internal` ao
  Contrato. No Linux, sem ele, o nome não existe. O Cadastro e o Ledger já
  trazem essa linha no compose deles.

</details>

### Conferir que subiu

O script termina listando oito containers, todos `healthy`:

```
e2e-party-api-1, e2e-party-db-1, e2e-party-bureau-mock-1,
e2e-ledger-api-1, e2e-ledger-db-1, e2e-ledger-provider-mock-1,
e2e-contract-api-1, e2e-contract-db-1
```

Cada API responde na raiz:

```bash
curl http://localhost:3001/    # Cadastro
curl http://localhost:3002/    # Contrato
curl http://localhost:3003/    # Ledger
```

---

## 3. Rodar os testes e2e (o que o avaliador precisa rodar)

Com os três de pé:

```bash
./scripts/test-e2e.sh
```

Na primeira vez, o script cria o venv `.venv/` na raiz e instala as
dependências de teste (`requirements-dev.txt`). Depois roda
`pytest e2e -v`. A bateria leva cerca de um minuto.

**O resultado esperado** é um teste por fase, todos `PASSED`:

```
e2e/test_tres_apis.py::test_fase[cadastro] PASSED
e2e/test_tres_apis.py::test_fase[onboarding] PASSED
e2e/test_tres_apis.py::test_fase[dinheiro] PASSED
e2e/test_tres_apis.py::test_fase[carteira] PASSED
e2e/test_tres_apis.py::test_fase[med] PASSED
e2e/test_tres_apis.py::test_fase[vida] PASSED
e2e/test_tres_apis.py::test_fase[falhas] PASSED
e2e/test_tres_apis.py::test_fase[extras] PASSED
e2e/test_tres_apis.py::test_fase[pendente] PASSED
RESUMO: 91/91 checagens passaram (run ......)
========== 9 passed in ...s ==========
```

### O que as fases provam

Os testes seguem o caso do contrato 42 da Imobiliária Alfa (a Ana é a
locadora, o Bruno o locatário). Cada fase usa o que a anterior criou, por
isso **elas rodam em ordem e dependem umas das outras.**

| Fase | O que acontece |
|---|---|
| `cadastro` | cria as partes (pessoas e empresas) e o cliente Imobiliária Alfa no Cadastro real; um documento reprovado no bureau vira parte `rejected` |
| `onboarding` | cria e ativa o contrato no Contrato real; a ativação confere as partes no Cadastro e provisiona as contas do split no Ledger |
| `dinheiro` | o Pix do aluguel entra, a competência é dividida entre as contas, o repasse sai por Pix e a liquidação volta pelo webhook do provedor; os saldos e a integridade fecham |
| `carteira` | abre as carteiras (o Ledger confere no Cadastro se a parte está `active`), deposita, paga o aluguel com a carteira e repassa o aluguel para a carteira da Ana |
| `med` | a devolução do Pix por fraude (MED) estorna a entrada, e a Alfa devolve a taxa dela; a integridade continua fechando |
| `vida` | encerrar com saldo é recusado, o reajuste cria a versão 2 do split, encerrar sem saldo fecha as contas no Ledger, e o mesmo `trace_id` aparece nos bancos do Contrato e do Ledger |
| `falhas` | partes recusadas ou inexistentes barram a ativação; depois **para** a API do Ledger e a do Cadastro (`docker stop`): quem depende responde `503` sem gravar nada, e a mesma requisição passa depois do `docker start` |
| `extras` | pagamento parcial, entrada sem identificação (suspense) e alocação, estornos, extrato com hash e verificação pública, saque |
| `pendente` | com o bureau fora do ar, a parte nasce `pending`; o Ledger e o Contrato a recusam até a repescagem dela ficar `active` |

Se uma fase falha, a mensagem lista cada checagem que deu errado, com o
status HTTP e o corpo da resposta. O registro completo de cada execução
fica em `e2e/resultados/e2e_tres_apis-<run>.json`.

**Atenção:** a fase `falhas` derruba e sobe de novo os containers das
APIs. Não rode outra coisa contra o sistema enquanto o e2e roda.

### Variações

```bash
./scripts/test-e2e.sh -k dinheiro      # argumentos extras vão para o pytest
python e2e/e2e_tres_apis.py            # o mesmo roteiro sem pytest (use o python do .venv)
```

Rodar o e2e de novo, sem derrubar, funciona: cada execução cria partes e
contratos novos. Para começar com os bancos vazios:
`./scripts/down.sh && ./scripts/up.sh`.

---

## 4. Derrubar

```bash
./scripts/down.sh
```

Derruba os três serviços e **apaga os bancos deles** (`down -v`).

---

## 5. Testes de integração de cada serviço (opcional)

Além do e2e, cada serviço tem a própria suíte de testes de integração.
Ela fala HTTP com a API do serviço, que fica de pé no Docker, e troca as
dependências pelos **mocks** dele. Assim, cada serviço é testado sozinho,
sem os outros dois.

```bash
./scripts/test-integration.sh                 # os três, um depois do outro
./scripts/test-integration.sh ledger-api      # só um
```

Para cada serviço, o script:
1. cria o `.env` a partir do `.env.example`, se ele ainda não existir;
2. sobe a pilha do serviço (API, banco e mocks);
3. roda o `pytest`;
4. derruba a pilha, com os volumes.

Estas suítes usam as **mesmas portas** do sistema ligado. Por isso o
script começa rodando o `./scripts/down.sh`. Para voltar ao sistema
ligado depois: `./scripts/up.sh`.

**O resultado esperado:**

| Serviço | Resultado | Tempo aproximado |
|---|---|---|
| `party-api` | `177 passed` | 1 min |
| `contract-api` | `214 passed` | 3 min |
| `ledger-api` | `226 passed, 60 skipped` | 4 a 8 min |

Os 60 pulados do Ledger são os testes de `ledger-api/tests/e2e/`. Eles
repetem a suíte contra o Cadastro **real** e só rodam com `E2E=1`: veja
o `ledger-api/README.md`, seção 10.

<details>
<summary>Os mesmos passos, à mão, para um serviço</summary>

```bash
./scripts/down.sh                       # libera as portas
cd ledger-api                           # ou party-api, ou contract-api
cp .env.example .env                    # se ainda não existir
docker compose up -d --build --wait
../.venv/bin/python -m pytest           # no Windows: ../.venv/Scripts/python.exe -m pytest
docker compose down -v
```

O venv `.venv/` é criado pelo `./scripts/test-e2e.sh` ou pelo
`./scripts/test-integration.sh`. Para criá-lo à mão, na raiz:
`python -m venv .venv` e depois `.venv/bin/python -m pip install -r requirements-dev.txt`.

A suíte do Contrato recria a API dele apontando para os mocks e, no fim,
restaura a configuração. Por isso ela tem de rodar **sozinha**, nunca em
paralelo com outra.

</details>

---

## 6. Quando dá errado

**`port is already allocated` / `Bind for 0.0.0.0:3001 failed`.** Outro
programa, ou um container antigo, está usando a porta. Veja quem é:

```bash
docker ps --format "table {{.Names}}\t{{.Ports}}"
```

Se for um container deste projeto, `./scripts/down.sh` resolve. Se for
outro, pare esse container ou o programa, e rode o `./scripts/up.sh` de novo.

**`ERRO: o Docker não está rodando`.** Abra o Docker Desktop e espere
aparecer "Engine running".

**`ERRO: a pasta party-api está vazia`.** O clone foi feito sem
`--recurse-submodules`. Rode `git submodule update --init`.

**`Permission denied (publickey)` no clone.** A sua chave SSH não tem
acesso aos repositórios. Use HTTPS (seção 1) ou peça acesso.

**`$'\r': command not found` ao rodar um script.** O script foi salvo com
quebra de linha do Windows. Rode `git config core.autocrlf input` e depois
`git checkout -- scripts/`. O `.gitattributes` já evita isso num clone novo.

**`ERRO: Python 3.10 ou mais novo não encontrado`.** Instale o Python
(python.org). No Windows, marque "Add python.exe to PATH" no instalador.

**Um teste e2e falhou com `503` ou `Connection refused`.** Confira se os
oito containers estão `healthy` (`docker ps`). Se a fase `falhas` foi
interrompida no meio (Ctrl+C), uma API pode ter ficado parada. Rode
`./scripts/down.sh && ./scripts/up.sh` e o e2e de novo.

**Linux: o Contrato não acha o Cadastro (`503 QIT003...`).** Confira se
você subiu pelo `./scripts/up.sh`, ou com o `-f compose/contract-api.e2e.yml`
da seção 2: é ele que cria o `host.docker.internal` no container do Contrato.

---

## 7. Documentação

- **A RFC do projeto:** [`docs/rfc-conta-com-proposito.md`](docs/rfc-conta-com-proposito.md).
  Ela traz o problema, a solução, as rotas, o diagrama do banco, os fluxos
  e as peças que cada serviço acrescentou à base, com a justificativa de cada uma.
- **Cada serviço** tem o próprio README, com as rotas, os códigos de erro e
  exemplos com `curl`:
  [`party-api/README.md`](party-api/README.md),
  [`contract-api/README.md`](contract-api/README.md) e
  [`ledger-api/README.md`](ledger-api/README.md).
- **Versões testadas juntas:** [`VERSIONS.md`](VERSIONS.md).

### Estrutura deste repositório

```
bootcamp-qi-tech-entrega/
├── README.md                    ← este guia
├── VERSIONS.md                  ← os commits de cada serviço que foram testados juntos
├── party-api/                   ← submódulo: o Cadastro
├── contract-api/                ← submódulo: o Contrato
├── ledger-api/                  ← submódulo: o Ledger
├── scripts/
│   ├── up.sh                    ← sobe os três ligados, na ordem
│   ├── test-e2e.sh              ← roda os testes e2e
│   ├── test-integration.sh      ← roda a suíte de cada serviço contra os mocks dele
│   ├── down.sh                  ← derruba tudo e apaga os bancos
│   └── _comum.sh                ← funções usadas pelos outros scripts
├── compose/contract-api.e2e.yml ← host.docker.internal para o Contrato no Linux
├── e2e/
│   ├── test_tres_apis.py        ← os testes e2e: uma fase do roteiro por teste
│   └── e2e_tres_apis.py         ← o roteiro (9 fases, 91 checagens)
├── docs/rfc-conta-com-proposito.md
└── requirements-dev.txt         ← dependências de teste (versões fixas)
```
