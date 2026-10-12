"""Os testes de ponta a ponta: o roteiro do contrato 42 (remodelagem/05)
contra o Cadastro, o Contrato e o Ledger reais, de pé pelo scripts/up.sh.

Cada fase do roteiro é um teste, e as fases rodam na ordem abaixo: uma usa
o que a anterior criou (partes, contrato, contas). Uma fase passa quando
todas as checagens dela passam; a falha mostra cada checagem que deu errado,
com o status e o corpo da resposta.

O roteiro em si está em e2e_tres_apis.py (também roda sozinho:
`python e2e/e2e_tres_apis.py`).

Atenção: a fase "falhas" para e volta a subir os containers da API do
Ledger e da API do Cadastro (docker stop/start), para provar o 503 e a
retomada. Não rode outra coisa contra eles ao mesmo tempo.
"""
import json
import os

import pytest

import e2e_tres_apis as roteiro

ORDEM = ["cadastro", "onboarding", "dinheiro", "carteira", "med", "vida", "falhas", "extras", "pendente"]
assert set(ORDEM) == set(roteiro.FASES), "a lista de fases mudou no roteiro"


@pytest.fixture(scope="module", autouse=True)
def grava_resultado():
    """Grava o JSON do run em e2e/resultados/, como faz o roteiro sozinho."""
    yield
    os.makedirs(roteiro.OUT_DIR, exist_ok=True)
    caminho = os.path.join(roteiro.OUT_DIR, f"e2e_tres_apis-{roteiro.RUN}.json")
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump({"run": roteiro.RUN, "estado": roteiro.estado, "resultados": roteiro.resultados},
                  f, ensure_ascii=False, indent=1)
    ok = sum(1 for r in roteiro.resultados if r[2])
    print(f"\nRESUMO: {ok}/{len(roteiro.resultados)} checagens passaram (run {roteiro.RUN}) -> {caminho}")


@pytest.mark.parametrize("fase", ORDEM)
def test_fase(fase):
    antes = len(roteiro.resultados)
    roteiro.FASES[fase]()
    desta_fase = roteiro.resultados[antes:]
    falhas = [f"{cid} {desc}: {detalhe}" for cid, desc, ok, detalhe in desta_fase if not ok]
    assert desta_fase, f"a fase {fase} não fez nenhuma checagem"
    assert not falhas, f"{len(falhas)} de {len(desta_fase)} checagens falharam:\n" + "\n".join(falhas)
