> Nota de tradução: este arquivo é a tradução em português brasileiro do original em inglês [`docs/roadmap-v3.md`](../roadmap-v3.md). O texto em inglês é a fonte da verdade: em caso de divergência entre os dois, prevalece o texto em inglês, conforme o [ADR-016](../decisions/ADR-016-brazilian-portuguese-translation-layer.md).

# Roadmap v3: o LedgerLens como laboratório público de engenharia de IA aplicada

Este documento é o plano de trabalho a partir de 2026-11-11. A decisão que o ancora é o
[ADR-011](../decisions/ADR-011-v3-roadmap-in-verifiable-slices.md). A especificação detalhada de cada release vive em
[`specs/`](../../specs/), escrita com o toolkit de especificação, e o pacote de design que dirige o ciclo inteiro é
versionado em [`docs/v3/`](../v3/ORIGEM.md).

## A decisão

O LedgerLens é um **laboratório público de engenharia de IA aplicada** que usa operações de pagamento como um domínio
rico em restrições. Não é uma fintech, não é um produto bancário, não é um SaaS e nunca vai movimentar dinheiro real.
Quem visita o repositório ou o site encontra uma máquina de engenharia que pode ser inspecionada, não uma promessa.

Três resultados a otimizar, nesta ordem:

1. **Engenharia**: profundidade real em frontend, Python, agentes, ferramentas, dados, segurança, testes, evals,
   observabilidade e custo.
2. **Demonstração**: qualquer pessoa pode experimentar sem chave e sem login, e entender o resultado com evidência.
3. **Carreira**: material verificável para mostrar a engenheiros, entrevistadores, gestores e fundadores. Sem promessa
   de retorno financeiro.

## As linhas vermelhas

1. Nunca forjar uma execução ao vivo, um valor recuperado, um resultado de benchmark ou um certificado.
2. Nunca disponibilizar movimentação de dinheiro real. Toda mudança é um evento do sandbox.
3. Nunca vazar a chave de um visitante que traz a própria, nem em um log, nem em um trace, nem em um replay.
4. Nunca afirmar que múltiplos agentes são melhores sem um teste comparativo pareado.
5. Nunca simplificar um problema financeiro a ponto de esconder sua dificuldade.
6. Nunca chamar de "ao vivo" o que é um replay ou uma simulação.

## O ciclo

Uma tarefa por commit. O gate do repositório verde antes de cada commit. Cada fatia entrega evidência que um terceiro
pode reexecutar: um hash de origem, um teste, um fixture ou um trace, e o comando exato.

O que conta como evidência vem do próprio pacote de design: para as tarefas de engenharia, "teste reprodutível +
trace/fixture + link da fonte"; para as econômicas, "oráculo econômico/funcional + teste pareado + premissas".

## R0: congelar a verdade

Sem isso, nada depois dela é comparável. Nenhuma mudança de comportamento entra nesta fase.

| ID | Tarefa | Evidência | Estado |
|---|---|---|---|
| LL-V3-R0-01 | Congelar o commit, o lockfile e o hash dos cenários | [`verification/baseline.md`](../../verification/baseline.md) | feito |
| LL-V3-R0-02 | Executar os testes offline e registrar a saída exata | [`verification/baseline.md`](../../verification/baseline.md) | feito |
| LL-V3-R0-03 | Normalizar o `Span` atual no esquema público `TraceEvent` | [`ledgerlens/observability/trace_event.py`](../../ledgerlens/observability/trace_event.py) e [`tests/observability/test_trace_event.py`](../../tests/observability/test_trace_event.py) | feito |
| LL-V3-R0-04 | Capturar e sanitizar o bundle canônico de replay | [`data/eval/replay/s01`](../../data/eval/replay/s01) e [`tests/replay/test_bundle.py`](../../tests/replay/test_bundle.py) | feito |
| LL-V3-R0-05 | Reconciliar a divergência entre os 30 e os 43 casos do verificador | [`docs/verification_sets.md`](../verification_sets.md) e [`tests/verify/test_verification_sets.py`](../../tests/verify/test_verification_sets.py) | feito |
| LL-V3-R0-06 | `RunContext` em Python, sem estado global por visitante | [`ledgerlens/run_context.py`](../../ledgerlens/run_context.py) e [`tests/agents/test_run_context.py`](../../tests/agents/test_run_context.py) | feito |
| LL-V3-R0-07 | Documentar a guarda de SQL e o isolamento de contas | [`docs/tools.md`](../tools.md) e [`docs/architecture.md`](../architecture.md) | feito |

O `TraceEvent` público é o contrato de `contracts/schemas/trace-event.schema.json` do pacote, implementado em
[`ledgerlens/observability/trace_event.py`](../../ledgerlens/observability/trace_event.py) com a decisão no
[ADR-013](../decisions/ADR-013-public-trace-as-a-versioned-contract.md): `schema_version`, `run_id`, `seq`, `at`,
`event_type`, `span_id`, `parent_span_id`, `payload`, `snapshot_sha256` e `mode`, com `mode` em `recorded_replay`,
`deterministic_sandbox` ou `live_agent`.

## R1: o visitante sem chave

A especificação está em [`specs/001-r1-public-replay/`](../../specs/001-r1-public-replay/).

| ID | Tarefa | Estado |
|---|---|---|
| LL-V3-R1-01 | Shell Next.js e tokens de design responsivos | pendente |
| LL-V3-R1-02 | Galeria de cenários sem autenticação, com procedência | pendente |
| LL-V3-R1-03 | Renderizar o trace gravado, passo a passo | pendente |
| LL-V3-R1-04 | Explorador de registros de pagamento | pendente |
| LL-V3-R1-05 | Inspetor vinculado de afirmação, veredito e evidência | pendente |
| LL-V3-R1-06 | Explorador de arquitetura com âncoras na fonte | pendente |
| LL-V3-R1-07 | Testes automatizados de acessibilidade e mobile | pendente |

O frontend consome esquemas de API versionados e nunca reimplementa uma regra de domínio. O Python continua sendo a
autoridade.

## R2: o sandbox

A especificação está em [`specs/002-r2-visitor-sandbox/`](../../specs/002-r2-visitor-sandbox/).

| ID | Tarefa | Estado |
|---|---|---|
| LL-V3-R2-01 | Comandos de mutação tipados para o sandbox | pendente |
| LL-V3-R2-02 | Fork do snapshot base imutável por sessão | pendente |
| LL-V3-R2-03 | Append e projeção idempotentes | pendente |
| LL-V3-R2-04 | Pré-visualização e diff das mutações | pendente |
| LL-V3-R2-05 | Recalcular o oráculo do cenário após a mutação | pendente |
| LL-V3-R2-06 | Reset, consistência de hash e tempo de vida | pendente |
| LL-V3-R2-07 | Isolamento ponta a ponta entre dois visitantes, e o caso de conflito | pendente |

A base pública é imutável: cada visitante recebe um branch isolado e pode resetar de forma determinística. Nada escreve
direto na tabela de domínio; um evento é escrito e o projetor recalcula.

## R3: traga a sua própria chave, por último

A especificação está em [`specs/003-r3-bring-your-own-key/`](../../specs/003-r3-bring-your-own-key/).

| ID | Tarefa | Estado |
|---|---|---|
| LL-V3-R3-01 | Registro de provedores e a lista de capacidades testadas | pendente |
| LL-V3-R3-02 | Handle efêmero de segredo, com o caminho de exclusão | pendente |
| LL-V3-R3-03 | Coordenador de execução com orçamento estrito | pendente |
| LL-V3-R3-04 | Server-sent events tipados e cancelamento | pendente |
| LL-V3-R3-05 | Seletor de modelo e um consentimento transparente | pendente |
| LL-V3-R3-06 | Teste de conformidade de tool calling para o provedor | pendente |
| LL-V3-R3-07 | Sanitização da chave e do trace em caso de falha | pendente |

O BYOK só chega depois que os testes de isolamento por sessão e os testes de sanitização estiverem verdes. A chave fica
no servidor, na sessão, e desaparece na saída.

## Depois do R3

O R4 traz os experimentos comparáveis e a reconciliação do verificador com os denominadores certos; o R5 traz o
deployment com um fallback estático, o hardening de segurança e a medição real de latência e custo. Do R6 em diante são
trilhas de pesquisa: multiagente, memória versionada, execução durável, digital twin, multimodalidade e causalidade,
cada uma com o gate de prova que o pacote define.

## Onde está o pacote de design

O pacote com o atlas de 234 capacidades, os 161 novos ids, as 34 telas, as 19 especificações de componentes e os 7
esquemas é versionado em [`docs/v3/`](../v3/ORIGEM.md), importado por `scripts/import_v3_pack.py`. São 125 arquivos,
sha256 `4bf1cb2402ac7b31d85244e9ec7e4970c1db5ab63f17361d43471e102a2cbad1` sobre o caminho relativo e os bytes, o mesmo
digest do ADR-011.

A importação é mecânica: o travessão vira um hífen, a palavra que a guarda de contexto proíbe vira o sinônimo em
inglês, a cedilha de "facade" cai, e os dois documentos que existem apenas em português brasileiro são traduzidos para
o inglês. Nenhuma afirmação do pacote foi reescrita. O pacote é material de terceiros e está em inglês; o plano que
dirige o trabalho é este documento, na voz do projeto. A procedência está no
[ADR-012](../decisions/ADR-012-v3-package-versioned-in-docs-v3.md).

## Como o plano é especificado

Cada release tem uma pasta de especificação em [`specs/`](../../specs/), escrita com o toolkit de especificação e
seguindo a mesma estrutura:

- `spec.md`: as histórias de usuário com prioridades, os requisitos funcionais, as entidades e os critérios de sucesso
- `plan.md`: o contexto técnico, a checagem da constituição e a estrutura de arquivos
- `tasks.md`: a lista ordenada de tarefas, mapeada para as histórias de usuário, com os checkpoints

A constituição vive na pasta `memory` do toolkit de especificação e guarda os princípios que toda fatia obedece. A
ferramenta que gera as pastas está na pasta `scripts` do mesmo toolkit.

## O que não foi medido

O número econômico central do projeto, o custo por caso resolvido corretamente, **não tem medição**. Todo valor do
pacote é uma premissa, um perfil simulado, ou está rotulado como tal. Antes de qualquer número de custo ou economia ser
publicado, tem que existir uma medição com o denominador certo e uma premissa declarada.

Os números de qualidade que o repositório publica vêm de execuções reais. A reconciliação dos denominadores é a
LL-V3-R0-05 e está feita: a acurácia NLI combinada de 0.786 é medida sobre 70 casos de NLI, os 30 casos de texto do
conjunto de verificação mais os 40 ao vivo, e não sobre os 43 registros do conjunto de verificação. Cada número diz o
que conta em [`docs/verification_sets.md`](../verification_sets.md).
