"""Roteiro do contrato 42 (remodelagem/05) contra os tres servicos REAIS.

Cadastro :3001, Contrato :3002, Ledger :3003 (projeto docker e2e-ledger,
apontando para o Cadastro real). Nenhum mock entre os servicos; o bureau
e o provedor Pix continuam mocks (sao trilhos externos).

Uso: pytest e2e (test_tres_apis.py), ou python e2e_tres_apis.py [fase ...] (padrao: todas)

Enderecos e nomes de container vem do ambiente; o padrao e o do scripts/up.sh:
  E2E_PARTY_URL      http://localhost:3001     (Cadastro)
  E2E_CONTRACT_URL   http://localhost:3002     (Contrato)
  E2E_LEDGER_URL     http://localhost:3003     (Ledger)
  E2E_BUREAU_URL     http://localhost:8081     (mock do bureau do Cadastro)
  E2E_TOKEN          default_token
  E2E_PARTY_API      e2e-party-api-1           (container parado na fase 7)
  E2E_LEDGER_API     e2e-ledger-api-1          (idem)
  E2E_CONTRACT_DB    e2e-contract-db-1         (psql do CU-K12)
  E2E_LEDGER_DB      e2e-ledger-db-1           (idem)
  E2E_OUT_DIR        e2e/resultados            (onde grava o JSON do run)
"""
import json
import os
import random
import subprocess
import sys
import uuid

import requests

PARTY = os.environ.get("E2E_PARTY_URL", "http://localhost:3001")
CONTRACT = os.environ.get("E2E_CONTRACT_URL", "http://localhost:3002")
LEDGER = os.environ.get("E2E_LEDGER_URL", "http://localhost:3003")
BUREAU = os.environ.get("E2E_BUREAU_URL", "http://localhost:8081")
TOKEN = os.environ.get("E2E_TOKEN", "default_token")
PARTY_API_CT = os.environ.get("E2E_PARTY_API", "e2e-party-api-1")
LEDGER_API_CT = os.environ.get("E2E_LEDGER_API", "e2e-ledger-api-1")
CONTRACT_DB_CT = os.environ.get("E2E_CONTRACT_DB", "e2e-contract-db-1")
LEDGER_DB_CT = os.environ.get("E2E_LEDGER_DB", "e2e-ledger-db-1")
OUT_DIR = os.environ.get("E2E_OUT_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "resultados"))
RUN = uuid.uuid4().hex[:6]

resultados = []  # (id, descricao, ok, detalhe)
estado = {}


def headers(idem=None, rid=None):
    h = {"INTERNAL-TOKEN": TOKEN, "X-Request-ID": rid or str(uuid.uuid4()),
         "Content-Type": "application/json"}
    if idem:
        h["Idempotency-Key"] = idem
    return h


def call(method, url, body=None, idem=None, timeout=15, rid=None):
    r = requests.request(method, url, headers=headers(idem, rid),
                         data=None if body is None else json.dumps(body), timeout=timeout)
    try:
        js = r.json()
    except ValueError:
        js = None
    return r.status_code, js


def check(cid, desc, cond, detalhe=""):
    resultados.append((cid, desc, bool(cond), detalhe))
    print(f"[{'PASS' if cond else 'FAIL'}] {cid} {desc}  {detalhe}")
    return bool(cond)


def code_of(js):
    if isinstance(js, dict):
        return js.get("code") or (js.get("detail") or {}).get("code") if isinstance(js.get("detail"), dict) else js.get("code")
    return None


def short(js):
    s = json.dumps(js, ensure_ascii=False)
    return s if len(s) < 300 else s[:300] + "..."


# ---------- documentos validos ----------
def _dv(nums, pesos):
    s = sum(n * p for n, p in zip(nums, pesos)) % 11
    return 0 if s < 2 else 11 - s


def cpf():
    while True:
        b = [random.randint(0, 9) for _ in range(9)]
        d1 = _dv(b, range(10, 1, -1))
        d2 = _dv(b + [d1], range(11, 1, -1))
        doc = "".join(map(str, b + [d1, d2]))
        if doc[-2:] not in ("00", "97", "98", "99") and len(set(doc)) > 1:
            return doc


def cnpj(final=None):
    while True:
        b = [random.randint(0, 9) for _ in range(8)] + [0, 0, 0, 1]
        d1 = _dv(b, [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
        d2 = _dv(b + [d1], [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
        doc = "".join(map(str, b + [d1, d2]))
        if final is None and doc[-2:] not in ("00", "97", "98", "99"):
            return doc
        if final is not None and doc.endswith(final):
            return doc


def cpf_final(final):
    while True:
        b = [random.randint(0, 9) for _ in range(9)]
        d1 = _dv(b, range(10, 1, -1))
        d2 = _dv(b + [d1], range(11, 1, -1))
        doc = "".join(map(str, b + [d1, d2]))
        if doc.endswith(final):
            return doc


def docker(*args):
    return subprocess.run(["docker", *args], capture_output=True, text=True)


def psql(container, sql):
    r = docker("exec", container, "psql", "-U", "bootcamp", "-d", "bootcamp", "-tAc", sql)
    return r.stdout.strip() if r.returncode == 0 else f"ERRO {r.stderr.strip()}"


def espera(url):
    import time
    for _ in range(40):
        try:
            if requests.get(f"{url}/health_check", timeout=2).status_code in (200, 204):
                return True
        except requests.RequestException:
            pass
        time.sleep(1)
    return False


# ---------- helpers de dominio ----------
def nova_parte(nome, doc, pix=None):
    body = {"name": nome, "document_number": doc, "actor": "erp-alfa"}
    if pix:
        body["pix_key"] = pix
    return call("POST", f"{PARTY}/parties", body)


def contas(filtro, valor):
    st, js = call("GET", f"{LEDGER}/ledger_accounts?{filtro}={valor}&limit=100")
    return st, (js or {}).get("data", [])


def saldo(key):
    st, js = call("GET", f"{LEDGER}/ledger_accounts/{key}")
    return (js or {}).get("balance_in_cents")


def conta_por(lista, purpose):
    for c in lista:
        if c["purpose_code"] == purpose:
            return c["ledger_account_key"]
    return None


def contrato_body(client_key, ext, p, rent=500000):
    return {
        "client_key": client_key, "external_reference": ext, "property_reference": "APT-101",
        "start_date": "2026-09-01", "rent_amount_in_cents": rent,
        "parties": [{"party_key": p["bruno"], "role": "tenant"},
                    {"party_key": p["ana"], "role": "landlord"},
                    {"party_key": p["alfa"], "role": "administrator"},
                    {"party_key": p["pref"], "role": "provider"},
                    {"party_key": p["cond"], "role": "provider"},
                    {"party_key": p["agua"], "role": "provider"},
                    {"party_key": p["luz"], "role": "provider"}],
        "split": [{"purpose_code": "RENT", "party_key": p["ana"], "role": "landlord", "type": "remainder"},
                  {"purpose_code": "OWN", "party_key": p["alfa"], "role": "administrator", "type": "percentage", "value": "10.0000"},
                  {"purpose_code": "IPTU", "party_key": p["pref"], "role": "provider", "type": "fixed", "value": 30000},
                  {"purpose_code": "CONDO", "party_key": p["cond"], "role": "provider", "type": "fixed", "value": 80000},
                  {"purpose_code": "WATER", "party_key": p["agua"], "role": "provider", "type": "fixed", "value": 12000},
                  {"purpose_code": "ELECTRICITY", "party_key": p["luz"], "role": "provider", "type": "fixed", "value": 18000}],
        "actor": "erp-alfa"}


# =================== FASES ===================
def fase_cadastro():
    print("\n== 1. Cadastro real (onboarding de partes e cliente) ==")
    p = {}
    for nome, chave, doc, pix in [("Imobiliaria Alfa", "alfa", cnpj(), "alfa@example.com"),
                                  ("Ana Locadora", "ana", cpf(), "ana.locadora@example.com"),
                                  ("Bruno Locatario", "bruno", cpf(), None),
                                  ("Prefeitura", "pref", cnpj(), None),
                                  ("Condominio Ed. Aurora", "cond", cnpj(), "condominio@example.com"),
                                  ("Companhia de agua", "agua", cnpj(), None),
                                  ("Companhia de luz", "luz", cnpj(), None)]:
        st, js = nova_parte(nome, doc, pix)
        p[chave] = (js or {}).get("party_key")
        check("CAD-01", f"POST /parties {chave} -> 201 active", st == 201 and (js or {}).get("status") == "active", f"{st} {short(js)}")
    estado["p"] = p
    st, js = nova_parte("Fulano Recusado", cpf_final("00"))
    estado["rejeitado"] = (js or {}).get("party_key")
    check("CAD-02", "POST /parties doc final 00 -> rejected (bureau)", st == 201 and (js or {}).get("status") == "rejected", f"{st} {short(js)}")
    st, js = call("POST", f"{PARTY}/clients", {"party_key": p["alfa"], "platform_fee_percentage": "1.0000", "actor": "erp-alfa"})
    estado["client"] = (js or {}).get("client_key")
    check("CAD-03", "POST /clients Alfa (1%) -> 201", st == 201 and estado["client"], f"{st} {short(js)}")
    st, js = call("GET", f"{PARTY}/clients/{estado['client']}")
    check("CAD-04", "GET /clients/{key} -> 200 (o que o Contrato le)", st == 200, f"{st} {short(js)}")
    st, js = call("GET", f"{PARTY}/parties/{p['ana']}")
    check("CAD-05", "GET /parties/{ana} -> 200 com pix_key (o que o Ledger le)", st == 200 and (js or {}).get("pix_key"), f"{st} {short(js)}")


def fase_onboarding():
    print("\n== 2. Contrato real -> Cadastro real -> Ledger real (ativacao) ==")
    p = estado["p"]
    st, js = call("POST", f"{CONTRACT}/contracts", contrato_body(estado["client"], f"ALFA-{RUN}-42", p))
    estado["c42"] = (js or {}).get("contract_key")
    check("ONB-01", "POST /contracts -> 201 draft", st == 201 and estado["c42"], f"{st} {short(js)}")
    st, js = call("POST", f"{CONTRACT}/contracts/{estado['c42']}/activation", {"actor": "erp-alfa", "reason": "inicio da locacao"})
    check("ONB-02", "POST /activation -> 200 active (provisiona no Ledger real)", st == 200 and (js or {}).get("status") == "active", f"{st} {short(js)}")
    st, lst = contas("contract_key", estado["c42"])
    purposes = sorted(c["purpose_code"] for c in lst)
    check("ONB-03", "Ledger tem os 6 earmarks do contrato", purposes == sorted(["COLLECTION", "RENT", "IPTU", "CONDO", "WATER", "ELECTRICITY"]), f"{st} {purposes}")
    ana_rent = [c for c in lst if c["purpose_code"] == "RENT"]
    check("ONB-04", "C42-RENT tem dono = Ana (party_key real do Cadastro)", ana_rent and ana_rent[0]["owner_party_key"] == p["ana"], short(ana_rent))
    st, livros = contas("client_key", estado["client"])
    tipos = sorted({c["purpose_code"] for c in livros if not c.get("contract_key")})
    check("ONB-05", "Livros da Alfa abertos (CASH, UNALLOCATED, TRANSIT, OWN, PLATFORM_FEE)", tipos == sorted(["CASH", "UNALLOCATED", "TRANSIT", "OWN", "PLATFORM_FEE"]), f"{st} {tipos}")
    estado["acc"] = {c["purpose_code"]: c["ledger_account_key"] for c in lst}
    estado["acc"].update({c["purpose_code"]: c["ledger_account_key"] for c in livros if not c.get("contract_key")})
    st, js = call("POST", f"{CONTRACT}/contracts/{estado['c42']}/activation", {"actor": "erp-alfa", "reason": "repeticao"})
    check("ONB-06", "Ativacao repetida -> 200 (idempotente ponta a ponta)", st == 200, f"{st} {short(js)}")
    st, lst2 = contas("contract_key", estado["c42"])
    check("ONB-07", "Repeticao nao duplicou contas no Ledger", len(lst2) == 6, f"{len(lst2)} contas")


def fase_dinheiro():
    print("\n== 3. Dinheiro: entrada, divisao, repasse Pix, liquidacao ==")
    a, c42 = estado["acc"], estado["c42"]
    e2e = f"E0000000020260905{RUN}"
    estado["e2e"] = e2e
    body = {"contract_key": c42, "period_reference": "2026-09", "payer_party_key": estado["p"]["bruno"],
            "end_to_end_id": e2e, "amount_in_cents": 640000, "value_date": "2026-09-05T14:22:00Z", "actor": "erp-alfa"}
    st, js = call("POST", f"{LEDGER}/transfers/inflow", body, idem=e2e)
    estado["tx1"] = (js or {}).get("ledger_transaction_key")
    check("DIN-01", "TX1 inflow 640000 -> 201", st == 201, f"{st} {short(js)}")
    st, js = call("POST", f"{LEDGER}/transfers/inflow", body, idem=e2e)
    check("DIN-02", "TX1 reenviada (mesma chave) -> replay, mesma transacao", st in (200, 201) and (js or {}).get("ledger_transaction_key") == estado["tx1"], f"{st}")
    check("DIN-03", "C42-COL = 640000", saldo(a["COLLECTION"]) == 640000, str(saldo(a["COLLECTION"])))
    st, js = call("POST", f"{LEDGER}/transfers/split", {"contract_key": c42, "period_reference": "2026-09", "actor": "erp-alfa", "reason": "divisao 09/2026"}, idem=f"split-{RUN}-09")
    check("DIN-04", "TX2 split -> 201, split_version 1", st == 201 and (js or {}).get("split_version") == 1, f"{st} {short(js)}")
    esperado = {"COLLECTION": 0, "RENT": 450000, "OWN": 45000, "IPTU": 30000, "CONDO": 80000, "WATER": 12000, "ELECTRICITY": 18000, "PLATFORM_FEE": 5000}
    reais = {k: saldo(a[k]) for k in esperado}
    check("DIN-05", "Saldos apos a divisao = remodelagem/05 (OWN 45000 = 50000 - 5000 da plataforma)", reais == esperado, str(reais))
    st, js = call("POST", f"{LEDGER}/transfers/split", {"contract_key": c42, "period_reference": "2026-09", "actor": "erp-alfa", "reason": "divisao 09/2026 de novo"}, idem=f"split-{RUN}-09-b")
    check("DIN-06", "Segunda divisao da competencia -> 409 QIT001036", st == 409 and "QIT001036" in json.dumps(js), f"{st} {short(js)}")
    st, js = call("POST", f"{LEDGER}/transfers/payout", {"source_account_key": a["RENT"], "amount_in_cents": 450000, "destination": "pix", "period_reference": "2026-09", "actor": "erp-alfa", "reason": "repasse aluguel 09/2026"}, idem=f"payout-{RUN}-ana")
    estado["tx3"], estado["outbox"] = (js or {}).get("ledger_transaction_key"), ((js or {}).get("outbox") or {}).get("outbox_key")
    estado["benef"] = ((js or {}).get("outbox") or {}).get("beneficiary_party_key")
    check("DIN-07", "TX3 payout Pix p/ Ana -> 202, outbox sent, beneficiario = Ana", st == 202 and estado["outbox"] and estado["benef"] == estado["p"]["ana"], f"{st} {short(js)}")
    st, js = call("POST", f"{LEDGER}/webhooks/provider", {"provider_reference": f"PRV-{RUN}-SETTLED", "event_type": "settlement_confirmed", "outbox_key": estado["outbox"], "value_date": "2026-09-06T10:00:00Z"})
    check("DIN-08", "TX4 webhook settlement_confirmed -> 204", st == 204, f"{st} {short(js)}")
    st, js = call("POST", f"{LEDGER}/webhooks/provider", {"provider_reference": f"PRV-{RUN}-SETTLED", "event_type": "settlement_confirmed", "outbox_key": estado["outbox"], "value_date": "2026-09-06T10:00:00Z"})
    check("DIN-09", "Webhook reenviado -> 204 sem novo lancamento", st == 204 and saldo(a["CASH"]) == 640000 - 450000, f"{st} CASH={saldo(a['CASH'])}")
    st, js = call("POST", f"{LEDGER}/transfers/payout", {"source_account_key": a["CONDO"], "amount_in_cents": 80000, "destination": "pix", "period_reference": "2026-09", "actor": "erp-alfa", "reason": "condominio 09/2026"}, idem=f"payout-{RUN}-cond")
    ob = ((js or {}).get("outbox") or {}).get("outbox_key")
    check("DIN-10", "TX5 payout condominio -> 202", st == 202, f"{st} {short(js)}")
    st, _ = call("POST", f"{LEDGER}/webhooks/provider", {"provider_reference": f"PRV-{RUN}-COND", "event_type": "settlement_confirmed", "outbox_key": ob, "value_date": "2026-09-10T10:00:00Z"})
    check("DIN-11", "TX6 liquidacao condominio -> 204; EXT-ALFA = 110000 (05 'saldos depois da TX6')", st == 204 and saldo(a["CASH"]) == 110000, f"{st} CASH={saldo(a['CASH'])}")
    st, js = call("POST", f"{LEDGER}/transfers/payout", {"source_account_key": a["IPTU"], "amount_in_cents": 30000, "destination": "pix", "period_reference": "2026-09", "actor": "erp-alfa", "reason": "iptu"}, idem=f"payout-{RUN}-iptu")
    check("DIN-12", "Payout p/ Prefeitura sem pix_key -> 422 QIT001039 (dado do Cadastro real)", st == 422 and "QIT001039" in json.dumps(js), f"{st} {short(js)}")
    st, js = call("POST", f"{LEDGER}/transfers/internal", {"source_account_key": a["RENT"], "gross_amount_in_cents": 1, "allocations": [{"target_account_key": a["IPTU"], "type": "remainder"}], "actor": "erp-alfa", "reason": "tentativa"}, idem=f"int-{RUN}-x")
    check("DIN-13", "RENT -> IPTU -> 422 QIT001008 (nao-contaminacao)", st == 422 and "QIT001008" in json.dumps(js), f"{st} {short(js)}")
    st, js = call("GET", f"{LEDGER}/transfers/{estado['tx3']}/trace")
    txt = json.dumps(js)
    check("DIN-14", "Trace da TX3: cadeia mostra Bruno como pagador e Ana como dona", st == 200 and estado["p"]["bruno"] in txt and estado["p"]["ana"] in txt, f"{st} {len(txt)} bytes")
    st, js = call("GET", f"{LEDGER}/integrity?client_key={estado['client']}")
    check("DIN-15", "GET /integrity do livro da Alfa -> fecha", st == 200, f"{st} {short(js)}")


def fase_carteira():
    print("\n== 4. Carteira (tudo interno) com partes do Cadastro real ==")
    p, a, c42 = estado["p"], estado["acc"], estado["c42"]
    st, js = call("POST", f"{LEDGER}/wallets", {"party_key": p["bruno"], "actor": "erp-alfa"})
    wb = (js or {}).get("ledger_account_key")
    check("CAR-01", "POST /wallets Bruno -> 201 (Ledger conferiu 'active' no Cadastro real)", st == 201 and wb, f"{st} {short(js)}")
    st, js = call("POST", f"{LEDGER}/wallets", {"party_key": p["ana"], "actor": "erp-alfa"})
    wa = (js or {}).get("ledger_account_key")
    check("CAR-02", "POST /wallets Ana -> 201", st == 201 and wa, f"{st}")
    st, js = call("POST", f"{LEDGER}/wallets", {"party_key": estado["rejeitado"], "actor": "erp-alfa"})
    check("CAR-03", "POST /wallets parte rejected -> 409 QIT001038", st == 409 and "QIT001038" in json.dumps(js), f"{st} {short(js)}")
    e2e = f"E0000000020261001{RUN}"
    st, js = call("POST", f"{LEDGER}/transfers/inflow", {"wallet_key": wb, "end_to_end_id": e2e, "amount_in_cents": 640000, "actor": "erp-alfa"}, idem=e2e)
    check("CAR-04", "Deposito Pix na carteira de Bruno -> 201", st == 201 and saldo(wb) == 640000, f"{st} WAL-BRUNO={saldo(wb)}")
    st, js = call("POST", f"{LEDGER}/transfers/inflow", {"contract_key": c42, "period_reference": "2026-10", "source_wallet_key": wb, "amount_in_cents": 640000, "actor": "erp-alfa"}, idem=f"wpay-{RUN}")
    check("CAR-05", "Bruno paga out/2026 com a carteira -> 201; carteira 0; COL 640000", st == 201 and saldo(wb) == 0 and saldo(a["COLLECTION"]) == 640000, f"{st} {short(js)}")
    st, js = call("POST", f"{LEDGER}/transfers/inflow", {"contract_key": c42, "period_reference": "2026-11", "source_wallet_key": wb, "amount_in_cents": 1, "actor": "erp-alfa"}, idem=f"wpay2-{RUN}")
    check("CAR-06", "Pagar com carteira vazia -> 422 QIT001009", st == 422 and "QIT001009" in json.dumps(js), f"{st} {short(js)}")
    st, js = call("POST", f"{LEDGER}/transfers/split", {"contract_key": c42, "period_reference": "2026-10", "actor": "erp-alfa", "reason": "divisao 10/2026"}, idem=f"split-{RUN}-10")
    check("CAR-07", "Divisao out/2026 -> 201", st == 201, f"{st}")
    st, js = call("POST", f"{LEDGER}/transfers/payout", {"source_account_key": a["RENT"], "amount_in_cents": 450000, "destination": "wallet", "period_reference": "2026-10", "actor": "erp-alfa", "reason": "aluguel na carteira"}, idem=f"pw-{RUN}")
    check("CAR-08", "Repasse do RENT para a carteira de Ana -> 201; WAL-ANA 450000", st == 201 and saldo(wa) == 450000, f"{st} WAL-ANA={saldo(wa)}")
    st, js = call("GET", f"{LEDGER}/integrity")
    check("CAR-09", "GET /integrity global -> 200 (Alfa + plataforma fecham)", st == 200, f"{st} {short(js)}")


def fase_med():
    print("\n== 5. MED da TX1 ==")
    a = estado["acc"]
    st, js = call("POST", f"{LEDGER}/webhooks/provider", {"provider_reference": f"MED-{RUN}", "event_type": "med_return", "end_to_end_id": estado["e2e"], "amount_in_cents": 640000, "value_date": "2026-09-08T12:00:00Z"})
    check("MED-01", "webhook med_return -> 204", st == 204, f"{st} {short(js)}")
    col = saldo(a["COLLECTION"])
    check("MED-02", "C42-COL = -640000 (estava 0 depois das duas divisoes)", col == -640000, f"COL={col}")
    st, js = call("GET", f"{LEDGER}/integrity?client_key={estado['client']}")
    check("MED-03", "Integridade continua fechando (negativo legitimo)", st == 200, f"{st} {short(js)}")
    # FIN-5 / CU-F8 = TX8 do remodelagem/05: a Alfa devolve a propria taxa (45000) ao C42-COL.
    # A taxa da plataforma (PLATFORM_FEE) nao volta (05 "E a taxa da plataforma?").
    own0, fee0 = saldo(a["OWN"]), saldo(a["PLATFORM_FEE"])
    st, js = call("POST", f"{LEDGER}/transfers/internal", {"source_account_key": a["OWN"], "gross_amount_in_cents": 45000, "allocations": [{"target_account_key": a["COLLECTION"], "type": "remainder"}], "actor": "gerente-financeiro@alfa", "reason": "devolucao de taxa - MED 09/2026"}, idem=f"tx8-{RUN}")
    check("CU-F8", "TX8: OWN-ALFA -> C42-COL 45000 (internal) -> 201", st == 201 and (js or {}).get("ledger_transaction_type") == "internal", f"{st} {short(js)}")
    col, own1, fee1 = saldo(a["COLLECTION"]), saldo(a["OWN"]), saldo(a["PLATFORM_FEE"])
    check("CU-F8b", "C42-COL -640000 -> -595000; OWN-ALFA -45000; PLATFORM_FEE intacta", col == -595000 and own1 == own0 - 45000 and fee1 == fee0, f"COL={col} OWN {own0}->{own1} FEE {fee0}->{fee1}")
    st, js = call("GET", f"{LEDGER}/integrity?client_key={estado['client']}")
    check("CU-F8c", "Integridade da Alfa fecha depois da TX8 (difference 0)", st == 200 and (js or {}).get("difference_in_cents") == 0, f"{st} {short(js)}")


def fase_ciclo_de_vida():
    print("\n== 6. Encerramento e reajuste pelo Contrato real ==")
    st, js = call("POST", f"{CONTRACT}/contracts/{estado['c42']}/termination", {"actor": "erp-alfa", "reason": "fim"})
    check("VID-01", "Encerrar contrato com saldo retido -> 409 QIT003013", st == 409 and "QIT003013" in json.dumps(js), f"{st} {short(js)}")
    st, js = call("GET", f"{CONTRACT}/contracts/{estado['c42']}")
    check("VID-02", "Contrato continua active", (js or {}).get("status") == "active", f"{st} {(js or {}).get('status')}")
    body = contrato_body(estado["client"], "x", estado["p"], rent=530000)
    st, js = call("POST", f"{CONTRACT}/contracts/{estado['c42']}/split_versions", {"rent_amount_in_cents": 530000, "split": body["split"], "actor": "erp-alfa", "reason": "reajuste"})
    check("VID-03", "Reajuste: split_versions -> 201 version 2 (provisionada no Ledger)", st == 201 and (js or {}).get("split_version") == 2, f"{st} {short(js)}")
    # contrato vazio: encerra
    st, js = call("POST", f"{CONTRACT}/contracts", contrato_body(estado["client"], f"ALFA-{RUN}-77", estado["p"]))
    c77 = (js or {}).get("contract_key")
    call("POST", f"{CONTRACT}/contracts/{c77}/activation", {"actor": "erp-alfa", "reason": "x"})
    rid = f"e2e-k12-{RUN}"
    st, js = call("POST", f"{CONTRACT}/contracts/{c77}/termination", {"actor": "erp-alfa", "reason": "distrato"}, rid=rid)
    check("VID-04", "Encerrar contrato sem saldo -> 200 terminated", st == 200 and (js or {}).get("status") == "terminated", f"{st} {short(js)}")
    st, lst = contas("contract_key", c77)
    check("VID-05", "Ledger fechou os 6 earmarks (closed)", lst and all(c["status"] == "closed" for c in lst), str(sorted({c['status'] for c in lst})))
    # FIN-2 / CU-K12: o X-Request-ID do encerramento vira trace_id nos dois bancos (08:109).
    c_ev = psql(CONTRACT_DB_CT, "select string_agg(s.enumerator, ',') from contract_status_event e "
                "join contract c on c.id = e.contract_id join contract_status s on s.id = e.to_status_id "
                f"where e.trace_id = '{rid}' and c.contract_key = '{c77}'")
    check("CU-K12", f"contract_status_event do C77 com trace_id {rid} -> terminated", c_ev == "terminated", f"contrato: {c_ev}")
    l_ev = psql(LEDGER_DB_CT, "select count(*) || ':' || coalesce(string_agg(distinct s.enumerator, ','), '') "
                "from ledger_account_status_event e join ledger_account a on a.id = e.ledger_account_id "
                f"join ledger_account_status s on s.id = e.to_status_id where e.trace_id = '{rid}' and a.contract_key = '{c77}'")
    check("CU-K12b", "...o mesmo trace_id nos 6 ledger_account_status_event (closed) do Ledger", l_ev == "6:closed", f"ledger: {l_ev}")


def fase_falhas():
    print("\n== 7. Falhas entre servicos ==")
    p = estado["p"]
    # parte rejected no contrato
    body = contrato_body(estado["client"], f"ALFA-{RUN}-rej", p)
    body["parties"][0]["party_key"] = estado["rejeitado"]
    st, js = call("POST", f"{CONTRACT}/contracts", body)
    crej = (js or {}).get("contract_key")
    st2, js2 = call("POST", f"{CONTRACT}/contracts/{crej}/activation", {"actor": "erp-alfa", "reason": "x"}) if crej else (st, js)
    check("FAL-01", "Contrato com locatario rejected: ativacao recusada 409 QIT003007", st2 == 409 and "QIT003007" in json.dumps(js2), f"create={st} act={st2} {short(js2)}")
    body = contrato_body(estado["client"], f"ALFA-{RUN}-inex", p)
    body["parties"][0]["party_key"] = str(uuid.uuid4())
    st, js = call("POST", f"{CONTRACT}/contracts", body)
    cin = (js or {}).get("contract_key")
    st2, js2 = call("POST", f"{CONTRACT}/contracts/{cin}/activation", {"actor": "erp-alfa", "reason": "x"}) if cin else (st, js)
    check("FAL-02", "Parte inexistente no Cadastro: 422 QIT003008", st2 == 422 and "QIT003008" in json.dumps(js2), f"create={st} act={st2} {short(js2)}")
    # Ledger fora do ar
    st, js = call("POST", f"{CONTRACT}/contracts", contrato_body(estado["client"], f"ALFA-{RUN}-down", p))
    cdown = (js or {}).get("contract_key")
    docker("stop", LEDGER_API_CT)
    st, js = call("POST", f"{CONTRACT}/contracts/{cdown}/activation", {"actor": "erp-alfa", "reason": "x"}, timeout=30)
    check("FAL-03", "Ledger fora: ativacao -> 503 QIT003010", st == 503 and "QIT003010" in json.dumps(js), f"{st} {short(js)}")
    st, js = call("GET", f"{CONTRACT}/contracts/{cdown}")
    check("FAL-04", "...e o contrato continua draft", (js or {}).get("status") == "draft", f"{(js or {}).get('status')}")
    docker("start", LEDGER_API_CT)
    import time
    for _ in range(40):
        try:
            if requests.get(f"{LEDGER}/health_check", timeout=2).status_code in (200, 204):
                break
        except requests.RequestException:
            pass
        time.sleep(1)
    st, js = call("POST", f"{CONTRACT}/contracts/{cdown}/activation", {"actor": "erp-alfa", "reason": "retomada"})
    check("FAL-05", "Ledger de volta: mesma ativacao -> 200 active", st == 200 and (js or {}).get("status") == "active", f"{st} {short(js)}")
    # Cadastro fora do ar
    st, js = call("POST", f"{CONTRACT}/contracts", contrato_body(estado["client"], f"ALFA-{RUN}-pdown", p))
    cpd = (js or {}).get("contract_key")
    docker("stop", PARTY_API_CT)
    st, js = call("POST", f"{CONTRACT}/contracts/{cpd}/activation", {"actor": "erp-alfa", "reason": "x"}, timeout=30)
    check("FAL-06", "Cadastro fora: ativacao -> 503 QIT003010", st == 503 and "QIT003010" in json.dumps(js), f"{st} {short(js)}")
    st, js = call("POST", f"{LEDGER}/wallets", {"party_key": p["cond"], "actor": "erp-alfa"}, timeout=30)
    check("FAL-07", "Cadastro fora: POST /wallets no Ledger -> 503 QIT001040", st == 503 and "QIT001040" in json.dumps(js), f"{st} {short(js)}")
    # FIN-3 / CU-S8: repasse Pix com o Cadastro fora -> 503 QIT001040, nada gravado (S09 CA-08).
    a = estado["acc"]
    condo0, transit0 = saldo(a["CONDO"]), saldo(a["TRANSIT"])
    s8 = {"source_account_key": a["CONDO"], "amount_in_cents": 80000, "destination": "pix", "period_reference": "2026-10", "actor": "erp-alfa", "reason": "condominio 10/2026"}
    st, js = call("POST", f"{LEDGER}/transfers/payout", s8, idem=f"s8-{RUN}", timeout=30)
    condo1, transit1 = saldo(a["CONDO"]), saldo(a["TRANSIT"])
    check("CU-S8", "Cadastro fora: payout Pix do C42-CONDO -> 503 QIT001040", st == 503 and "QIT001040" in json.dumps(js), f"{st} {short(js)}")
    check("CU-S8b", "...nada gravado: C42-CONDO e TRANSIT intactos", condo0 == 80000 and condo1 == condo0 and transit1 == transit0, f"CONDO {condo0}->{condo1} TRANSIT {transit0}->{transit1}")
    docker("start", PARTY_API_CT)
    for _ in range(40):
        try:
            if requests.get(f"{PARTY}/health_check", timeout=2).status_code in (200, 204):
                break
        except requests.RequestException:
            pass
        time.sleep(1)
    st, js = call("POST", f"{LEDGER}/transfers/payout", s8, idem=f"s8-{RUN}")
    check("CU-S8c", "Cadastro de volta: a mesma chave de idempotencia -> 202 (o 503 nao gravou nada)", st == 202 and saldo(a["CONDO"]) == 0, f"{st} CONDO={saldo(a['CONDO'])} {short(js)}")


def fase_pendente():
    print("\n== 9. Parte pending: CU-P5 (Cadastro) + CU-K6 (Contrato) ==")
    p = estado["p"]
    # final 98 = scenario bureau-instavel: 1a chamada atrasa 2 s (fora do ar), as seguintes aprovam.
    # So vira pending se o Cadastro tiver BUREAU_API_TIMEOUT=1 (00 sec. 2; party-api/00-sumario L4).
    requests.post(f"{BUREAU}/__admin/scenarios/reset", timeout=5)
    st, js = nova_parte("Fulano Pendente", cpf_final("98"), "fulano@example.com")
    pk = (js or {}).get("party_key")
    check("CU-P5", "POST /parties com bureau fora (final 98) -> 201 pending", st == 201 and (js or {}).get("status") == "pending", f"{st} {short(js)}")
    st, js = call("POST", f"{LEDGER}/wallets", {"party_key": pk, "actor": "erp-alfa"})
    check("CU-P5b", "Ledger: POST /wallets de parte pending -> 409 QIT001038 (01b sec. 4)", st == 409 and "QIT001038" in json.dumps(js), f"{st} {short(js)}")
    body = contrato_body(estado["client"], f"ALFA-{RUN}-pend", p)
    body["parties"][0]["party_key"] = pk
    st, js = call("POST", f"{CONTRACT}/contracts", body)
    cp = (js or {}).get("contract_key")
    st2, js2 = call("POST", f"{CONTRACT}/contracts/{cp}/activation", {"actor": "erp-alfa", "reason": "inicio"}) if cp else (st, js)
    check("CU-K6", "Ativar contrato com locatario pending -> 409 QIT003007", st2 == 409 and "QIT003007" in json.dumps(js2), f"create={st} act={st2} {short(js2)}")
    _, jc = call("GET", f"{CONTRACT}/contracts/{cp}")
    _, lst = contas("contract_key", cp)
    check("CU-K6b", "...continua draft e nada foi provisionado no Ledger", (jc or {}).get("status") == "draft" and len(lst) == 0, f"{(jc or {}).get('status')} contas={len(lst)}")
    st, js = call("POST", f"{PARTY}/parties/{pk}/verification", {"actor": "erp-alfa"})
    check("CU-P5c", "Repescagem POST /parties/{key}/verification -> 200 active", st == 200 and (js or {}).get("status") == "active", f"{st} {short(js)}")
    st, js = call("POST", f"{CONTRACT}/contracts/{cp}/activation", {"actor": "erp-alfa", "reason": "parte verificada"})
    _, lst = contas("contract_key", cp)
    check("CU-K6c", "Parte agora active: a mesma ativacao -> 200 active, 6 earmarks no Ledger", st == 200 and (js or {}).get("status") == "active" and len(lst) == 6, f"{st} contas={len(lst)} {short(js)}")


def fase_extras():
    print("\n== 8. Casos de uso complementares (contrato 88, novo) ==")
    import datetime
    p, cli = estado["p"], estado["client"]
    st, js = call("POST", f"{CONTRACT}/contracts", contrato_body(cli, f"ALFA-{RUN}-88", p))
    c88 = (js or {}).get("contract_key")
    call("POST", f"{CONTRACT}/contracts/{c88}/activation", {"actor": "erp-alfa", "reason": "x"})
    st, lst = contas("contract_key", c88)
    a = {c["purpose_code"]: c["ledger_account_key"] for c in lst}
    a.update({k: v for k, v in estado["acc"].items() if k in ("CASH", "UNALLOCATED", "TRANSIT", "OWN", "PLATFORM_FEE")})

    e1 = f"E8800000020260905{RUN}"
    call("POST", f"{LEDGER}/transfers/inflow", {"contract_key": c88, "period_reference": "2026-09", "payer_party_key": p["bruno"], "end_to_end_id": e1, "amount_in_cents": 320000, "actor": "erp-alfa"}, idem=e1)
    st, js = call("POST", f"{LEDGER}/transfers/split", {"contract_key": c88, "period_reference": "2026-09", "actor": "erp-alfa", "reason": "divisao 09/2026"}, idem=f"s88a-{RUN}")
    check("CU-S3", "Divisao com pagamento parcial (320000) -> 422 QIT001009", st == 422 and "QIT001009" in json.dumps(js), f"{st} {short(js)}")
    st, js = call("POST", f"{LEDGER}/transfers/payout", {"source_account_key": a["COLLECTION"], "amount_in_cents": 1000, "destination": "pix", "period_reference": "2026-09", "actor": "erp-alfa", "reason": "x"}, idem=f"p88col-{RUN}")
    check("CU-S7", "Repasse a partir de COLLECTION -> 422 QIT001008", st == 422 and "QIT001008" in json.dumps(js), f"{st} {short(js)}")
    e2 = f"E8800000020260906{RUN}"
    call("POST", f"{LEDGER}/transfers/inflow", {"contract_key": c88, "period_reference": "2026-09", "payer_party_key": p["bruno"], "end_to_end_id": e2, "amount_in_cents": 320000, "actor": "erp-alfa"}, idem=e2)
    st, js = call("POST", f"{LEDGER}/transfers/split", {"contract_key": c88, "period_reference": "2026-09", "actor": "erp-alfa", "reason": "divisao 09/2026"}, idem=f"s88b-{RUN}")
    tx_split = (js or {}).get("ledger_transaction_key")
    check("CU-S1/S2", "Resto chega (2a parcela) -> divisao 201 v1", st == 201 and (js or {}).get("split_version") == 1, f"{st}")

    st, js = call("POST", f"{LEDGER}/transfers/payout", {"source_account_key": a["RENT"], "amount_in_cents": 450000, "destination": "pix", "period_reference": "2026-09", "actor": "erp-alfa", "reason": "repasse"}, idem=f"p88ana-{RUN}")
    ob = ((js or {}).get("outbox") or {}).get("outbox_key")
    st, js = call("POST", f"{LEDGER}/webhooks/provider", {"provider_reference": f"PRV-{RUN}-88-FAIL", "event_type": "settlement_failed", "outbox_key": ob, "value_date": "2026-09-06T10:00:00Z"})
    check("CU-E5", "Webhook settlement_failed -> 204; dinheiro volta ao C88-RENT", st == 204 and saldo(a["RENT"]) == 450000, f"{st} RENT={saldo(a['RENT'])}")

    body = contrato_body(cli, "x", p, rent=530000)
    call("POST", f"{CONTRACT}/contracts/{c88}/split_versions", {"rent_amount_in_cents": 530000, "split": body["split"], "actor": "erp-alfa", "reason": "reajuste"})
    e3 = f"E8800000020261005{RUN}"
    _, jin = call("POST", f"{LEDGER}/transfers/inflow", {"contract_key": c88, "period_reference": "2026-10", "payer_party_key": p["bruno"], "end_to_end_id": e3, "amount_in_cents": 670000, "actor": "erp-alfa"}, idem=e3)
    tx_in = (jin or {}).get("ledger_transaction_key")
    st, js = call("POST", f"{LEDGER}/transfers/split", {"contract_key": c88, "period_reference": "2026-10", "actor": "erp-alfa", "reason": "divisao 10/2026"}, idem=f"s88c-{RUN}")
    check("CU-K9", "Reajuste: divisao seguinte grava split_version 2 (670000 esperado)", st == 201 and (js or {}).get("split_version") == 2, f"{st} {short(js)}")
    st, js = call("GET", f"{LEDGER}/transfers/{tx_split}/trace")
    check("CU-K9b", "...e a divisao antiga continua split_version 1", st == 200 and '"split_version": 1' in json.dumps(js), f"{st}")

    e4 = f"E8800000020261007{RUN}"
    st, js = call("POST", f"{LEDGER}/transfers/inflow", {"client_key": cli, "end_to_end_id": e4, "amount_in_cents": 5000, "actor": "erp-alfa"}, idem=e4)
    check("CU-B2", "Pix sem identificacao -> 201 no suspense", st == 201 and saldo(a["UNALLOCATED"]) == 5000, f"{st} SUS={saldo(a['UNALLOCATED'])}")
    st, js = call("POST", f"{LEDGER}/transfers/internal", {"source_account_key": a["UNALLOCATED"], "gross_amount_in_cents": 5000, "allocations": [{"target_account_key": a["COLLECTION"], "type": "remainder"}], "actor": "gerente@alfa", "reason": "identificado: Bruno"}, idem=f"alloc-{RUN}")
    check("CU-B3", "Alocar suspense -> COLLECTION -> 201", st == 201 and saldo(a["UNALLOCATED"]) == 0, f"{st} {short(js)}")
    st, js = call("POST", f"{LEDGER}/transfers/internal", {"source_account_key": a["UNALLOCATED"], "gross_amount_in_cents": 1, "allocations": [{"target_account_key": a["COLLECTION"], "type": "remainder"}], "actor": "gerente@alfa", "reason": "x"}, idem=f"alloc2-{RUN}")
    check("CU-B4", "Alocar mais que o suspense -> 422 QIT001009", st == 422 and "QIT001009" in json.dumps(js), f"{st} {short(js)}")

    st, js = call("POST", f"{LEDGER}/transfers/{tx_in}/reversal", {"amount_in_cents": 1000, "actor": "gerente@alfa", "reason": "ajuste"}, idem=f"rev-{RUN}")
    check("CU-F2", "Estorno parcial (1000) da entrada de out/2026 -> 201", st == 201, f"{st} {short(js)}")
    st, js = call("POST", f"{LEDGER}/transfers/{(js or {}).get('ledger_transaction_key')}/reversal", {"actor": "x", "reason": "x"}, idem=f"rev2-{RUN}")
    check("CU-F6", "Estornar um estorno -> 422 QIT001016", st == 422 and "QIT001016" in json.dumps(js), f"{st} {short(js)}")

    st, js = call("GET", f"{LEDGER}/transfers?payer_party_key={p['bruno']}&limit=100")
    check("CU-T2", "GET /transfers?payer_party_key=Bruno lista o que ele pagou", st == 200 and len((js or {}).get("data", [])) >= 3, f"{st} n={len((js or {}).get('data', []))}")
    st, lst = contas("owner_party_key", p["ana"])
    roles = sorted({str(c.get("owner_role")) for c in lst})
    check("CU-T3", "Contas de Ana: RENT (landlord) e WALLET (holder)", st == 200 and "landlord" in roles and "holder" in roles, f"{st} {roles}")
    check("CU-T4", "Receita da plataforma na REV-ALFA > 0", (saldo(a["PLATFORM_FEE"]) or 0) > 0, str(saldo(a["PLATFORM_FEE"])))

    agora = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    st, js = call("POST", f"{LEDGER}/statement", {"ledger_account_key": a["RENT"], "period_start": "2026-01-01T00:00:00Z", "period_end": agora, "actor": "erp-alfa"}, idem=f"stmt-{RUN}")
    h = (js or {}).get("content_hash")
    check("CU-G1", "POST /statement do C88-RENT -> 201 com content_hash", st == 201 and h, f"{st} {short(js)}")
    r = requests.post(f"{LEDGER}/statement/verify", json={"content_hash": h}, timeout=10)
    check("CU-G10", "POST /statement/verify SEM token -> 200 match", r.status_code == 200 and "true" in r.text.lower(), f"{r.status_code} {r.text[:200]}")

    st, lst = contas("owner_party_key", p["ana"])
    wa = conta_por(lst, "WALLET")
    st, js = call("POST", f"{LEDGER}/transfers/payout", {"source_account_key": wa, "amount_in_cents": 100000, "destination": "pix", "period_reference": "2026-10", "actor": "app-ana", "reason": "saque"}, idem=f"saque-{RUN}")
    ob = ((js or {}).get("outbox") or {}).get("outbox_key")
    st2, _ = call("POST", f"{LEDGER}/webhooks/provider", {"provider_reference": f"PRV-{RUN}-SAQUE", "event_type": "settlement_confirmed", "outbox_key": ob, "value_date": "2026-10-11T10:00:00Z"})
    check("CU-W9", "Saque da carteira de Ana -> 202 + liquidacao 204; WAL-ANA 350000", st == 202 and st2 == 204 and saldo(wa) == 350000, f"{st}/{st2} WAL={saldo(wa)} {short(js)}")
    st, js = call("POST", f"{LEDGER}/wallets", {"party_key": p["ana"], "actor": "erp-alfa"})
    check("CU-W2", "Reabrir carteira -> 200 mesma chave", st == 200 and (js or {}).get("ledger_account_key") == wa, f"{st}")
    st, js = call("POST", f"{LEDGER}/transfers/payout", {"source_account_key": a["CONDO"], "amount_in_cents": 80000, "destination": "wallet", "period_reference": "2026-09", "actor": "erp-alfa", "reason": "x"}, idem=f"pcw-{RUN}")
    check("CU-W5", "Repasse p/ carteira de dono sem carteira -> 404 QIT001041", st == 404 and "QIT001041" in json.dumps(js), f"{st} {short(js)}")
    st, js = call("GET", f"{LEDGER}/integrity")
    check("CU-H1/T5", "Integridade global no fim -> difference 0", st == 200 and (js or {}).get("difference_in_cents") == 0, f"{st} {short(js)}")


FASES = {"cadastro": fase_cadastro, "onboarding": fase_onboarding, "dinheiro": fase_dinheiro,
         "carteira": fase_carteira, "med": fase_med, "vida": fase_ciclo_de_vida, "falhas": fase_falhas,
         "extras": fase_extras, "pendente": fase_pendente}

if __name__ == "__main__":
    for nome in (sys.argv[1:] or list(FASES)):
        try:
            FASES[nome]()
        except Exception as exc:  # registra e segue
            check("ERRO", f"fase {nome} abortou", False, repr(exc))
    ok = sum(1 for r in resultados if r[2])
    print(f"\nRESUMO: {ok}/{len(resultados)} checagens passaram (run {RUN})")
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, f"e2e_tres_apis-{RUN}.json"), "w", encoding="utf-8") as f:
        json.dump({"run": RUN, "estado": estado, "resultados": resultados}, f, ensure_ascii=False, indent=1)
