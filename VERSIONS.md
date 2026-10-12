# Versões que compõem a entrega

Cada linha é uma combinação dos três serviços que foi testada junta. Os
submódulos deste repositório apontam exatamente para esses commits.

| Entrega | party-api (Cadastro) | contract-api (Contrato) | ledger-api (Ledger) | e2e |
|---|---|---|---|---|
| 2026-10-13 | `7706afd` | `d702828` | `f23110c` | 9/9 fases, 91/91 checagens |

Suítes de integração de cada serviço, nesta combinação:

| Serviço | Resultado |
|---|---|
| party-api | 177 passed |
| contract-api | 214 passed |
| ledger-api | 226 passed, 60 skipped (os 60 são os testes `tests/e2e` do Ledger, que pedem `E2E=1` e o Cadastro real) |

O texto da RFC em `docs/rfc-conta-com-proposito.md` é a versão `64215fa`
do repositório de documentação.
