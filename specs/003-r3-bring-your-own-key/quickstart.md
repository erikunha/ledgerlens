# The live mode in five minutes: bring your own key

This is the quickstart of the live mode of LedgerLens. It is written for a reader who has never seen the
repository: it says how to run one case with a key of your own on a machine of your own, and how to take that key
back afterwards.

The live mode is the branch of the demo where the visitor brings the key of a model provider. Everything else of the
demo (the replay and the deterministic sandbox) keeps working with no key at all.

What the mode promises, in one paragraph: the key arrives once, over one request, and lives in the memory of the
server until the session ends, until you forget it, until its time to live passes or until the server restarts. It is
never written to a file, a log or a trace, and it never travels back to the client. What the run costs is what your
provider charges you, inside the caps that the request carries.

The binding documents are [the specification](spec.md), [the task list](tasks.md) and
[ADR-035, the facade of the live mode](../../docs/decisions/ADR-035-the-facade-of-the-live-mode.md).

## 1. What you need

- Python 3.12 (the repository pins it in `.python-version`) and [uv](https://docs.astral.sh/uv/).
- `curl` and `python3` for the commands below.
- A key of a model provider, and an account that may pay for the calls. The server accepts the providers it
  publishes: `openai`, `anthropic`, `google` and `local`.

## 2. Install

From a clone of the repository:

```bash
uv sync --extra api --extra dev --extra app
```

The `api` extra carries `fastapi`, `uvicorn` and `jsonschema`, and the routes of the live mode need all three. The
`dev` extra carries `pytest` and `ruff`, which the gate of the repository runs, and the `app` extra carries
`streamlit`, which the interface of the demo uses. In this repository the command above changes nothing: the
lockfile is already resolved with the three extras.

## 3. Start the live mode

The live mode has no console script in this milestone. `ledgerlens-api` serves the sandbox of the demo, not the
live mode. The honest way to serve the live mode is the factory of `uvicorn` over the `create_app` of
`ledgerlens/api/byok.py`:

```bash
uv run uvicorn ledgerlens.api.byok:create_app --factory --port 8010
```

Every argument of that factory is optional (`vault`, `registry`, `session_issuer`, `runtime_dir`, `coordinator`,
`adapter_factory`, `executor`, `clock`, `call_timeout`), so the application you start owns a vault and a registry of
its own. Nothing else has to be wired for a local run.

The server answers on `http://127.0.0.1:8010`. The answer that proves it is up is the catalogue, which needs no key
and no network:

```bash
curl -sS http://127.0.0.1:8010/v1/models
```

```json
{"models":[{"profile_id":"openai-gpt-4.1-mini","provider":"openai","model_id":"gpt-4.1-mini","display_name":"GPT-4.1 mini","capabilities":["chat","tool_calling"],"status":"tested","enabled_in_public_demo":true,"pricing":{"source":"manual","last_verified":"2026-11-08","input_per_1m_usd":"0.40","output_per_1m_usd":"1.60"}}]}
```

Make sure the product does not run offline. `LEDGERLENS_OFFLINE=1` refuses the live mode with a readable reason
(the section [the offline state](#the-offline-state) says exactly how), so if your `.env` carries it, start the
server with `LEDGERLENS_OFFLINE=0 uv run uvicorn ...` instead. The process environment wins over the `.env` file.

## 4. The session

The live mode has its own application, its own router and its own session issuer. The visitor is anonymous, and the
session is what decides what the visitor may read: a run belongs to the session that started it.

```bash
curl -sS -i -c jar.txt -X POST http://127.0.0.1:8010/v1/sessions
```

```http
HTTP/1.1 201 Created
set-cookie: ledgerlens_session=sess_ab8965e2ce7c42fa5bdbc5fe57bcc0b0.1794761731.bf173b5ea658462eda750fa3ddfe0da8; HttpOnly; Max-Age=14400; Path=/; SameSite=lax

{"id":"sess_ab8965e2ce7c42fa5bdbc5fe57bcc0b0","expires_at":"2026-11-15T16:55:31.022216+00:00","mode_capabilities":["deterministic_sandbox","live_agent","recorded_replay"]}
```

The file `jar.txt` is the cookie jar of `curl`. Every later command carries it with `-b jar.txt`, and the session
cookie is what ties the key, the run and the cost report to you.

Two facts about this cookie, because they surprise people:

- The cookie of the live mode and the cookie of the sandbox have the same name (`ledgerlens_session`) but they are
  signed with different keys by default: the live mode reads `data/runtime/live-session.key` and the sandbox reads
  `data/runtime/sandbox-session.key`. The two facades are the same visitor only when the deployment gives them the
  same session issuer and the same vault, and that wiring is a decision of the deployment
  ([ADR-035](../../docs/decisions/ADR-035-the-facade-of-the-live-mode.md)). Out of the box they are two visitors, and
  a handle of one session is refused in the other.
- That key file holds the signing key of the cookie, not your provider key. Your provider key never reaches the
  disk.

## 5. The catalogue and the price

The catalogue is the only list of models the visitor may pick. It shows the models the server really tested, with
their capabilities and their price.

```bash
curl -sS http://127.0.0.1:8010/v1/models
```

```json
{"models":[{"profile_id":"openai-gpt-4.1-mini","provider":"openai","model_id":"gpt-4.1-mini","display_name":"GPT-4.1 mini","capabilities":["chat","tool_calling"],"status":"tested","enabled_in_public_demo":true,"pricing":{"source":"manual","last_verified":"2026-11-08","input_per_1m_usd":"0.40","output_per_1m_usd":"1.60"}}]}
```

Only a profile whose tool calling was really exercised and that is enabled in the public demo enters that list. A
model of the allowlist that was not tested is not in the catalogue, and the server refuses it by itself when a
request names it.

The price of one model, with its provenance and the day it was last checked:

```bash
curl -sS http://127.0.0.1:8010/v1/models/openai-gpt-4.1-mini
```

```json
{"model":{"profile_id":"openai-gpt-4.1-mini","provider":"openai","model_id":"gpt-4.1-mini","display_name":"GPT-4.1 mini","capabilities":["chat","tool_calling"],"status":"tested","enabled_in_public_demo":true,"pricing":{"source":"manual","last_verified":"2026-11-08","input_per_1m_usd":"0.40","output_per_1m_usd":"1.60"}},"price_known":true,"price_note":"the price was verified on 2026-11-08 and comes from manual"}
```

A model whose price was never verified shows no amount at all, never a guess:

```bash
curl -sS http://127.0.0.1:8010/v1/models/openai-gpt-4.1
```

```json
{"model":{"profile_id":"openai-gpt-4.1","provider":"openai","model_id":"gpt-4.1","display_name":"GPT-4.1","capabilities":["chat"],"status":"experimental","enabled_in_public_demo":false,"pricing":{"source":"unknown","last_verified":null,"input_per_1m_usd":null,"output_per_1m_usd":null}},"price_known":false,"price_note":"the price of this model is unknown, so no amount is shown"}
```

## 6. Hand the key over, without putting it anywhere it should not be

The key may not sit in a URL, in a command line that ends in a shell history, in a file that outlives the session or
in a log. The commands below read the key from the keyboard without echoing it, and pass it to the server through
the standard input of `curl`. The key is never in the arguments of a process, so it never shows up in the process
list. The shell hands it on through a temporary file of its own, which bash removes as soon as the command is over,
and the variable that holds it is unset right after the call.

```bash
read -rs -p "paste the provider key: " KEY; echo
python3 -c 'import json,sys; json.dump({"provider":"openai","api_key":sys.stdin.read().strip()}, sys.stdout)' <<< "$KEY" \
  | curl -sS -b jar.txt -c jar.txt -H 'Content-Type: application/json' --data-binary @- http://127.0.0.1:8010/v1/credentials \
  | tee credential.json
unset KEY
```

The answer carries the handle, the provider and the expiry, and never the key:

```json
{"handle":"fP_QoGm3PnTLnpz3lHV3m1IRGLgqjifw0t3nb4p8vfM","provider":"openai","created_at":"2026-11-15T12:55:31.185377+00:00","expires_at":"2026-11-15T13:55:31.185377+00:00"}
```

The handle is what the rest of the flow uses. The file `credential.json` holds only the handle, the provider and
two dates, so it is safe to keep for the length of the session.

Two things to know about that answer:

- Accepting a key does not call the provider. The route checks the shape of the key and the name of the provider,
  and it hands out a handle. The provider sees your key for the first time in the run. A key that does not work is
  refused by the provider during the run, and the answer of the run says so.
- The headers of that answer say what the product does with the key: `X-LedgerLens-Key-Storage` says that the key
  is not stored and that the credential is dropped when the session ends, `X-LedgerLens-Key-Erasure` says that no
  runtime can promise that no copy of the text of the key survives in the memory of the interpreter or in a swap of
  the operating system, and `X-LedgerLens-Billing-Disclosure` says that your provider may charge you for the calls.

## 7. Run a case

A run carries a model, a question, a scenario, four caps (the calls of the models, the output tokens, the calls of
the tools and the wall clock) and a cap of money. The body is the published contract of the request
([live-run-request.schema.json](contracts/live-run-request.schema.json)), and the server checks it before it does
anything.

```bash
HANDLE=$(python3 -c 'import json; print(json.load(open("credential.json"))["handle"])')

cat > run.json <<JSON
{
  "mode": "live_agent",
  "scenario_id": "S01",
  "sandbox_id": "local",
  "expected_revision": 0,
  "account_id": "C-0001",
  "question": "Why was my card payment of 120,50 BRL reversed on 2026-11-03?",
  "variant": "A",
  "model_profile_id": "openai-gpt-4.1-mini",
  "credential_handle": "$HANDLE",
  "limits": {
    "max_model_calls": 2,
    "max_tool_calls": 4,
    "max_wall_seconds": 60,
    "max_output_tokens": 512,
    "max_estimated_usd": "0.50"
  }
}
JSON

RUN=$(curl -sS -b jar.txt -H 'Content-Type: application/json' --data-binary @run.json http://127.0.0.1:8010/v1/live-runs \
  | tee run-start.json | python3 -c 'import json,sys; print(json.load(sys.stdin)["run_id"])')

echo "run: $RUN"
```

The answer names the run and the mode:

```json
{"run_id":"run_f6db6c7ba5bf80d4","status":"running","mode":"live_agent"}
```

What each field of the body means:

- `mode` is `live_agent` for a live run. The route of the live mode refuses `deterministic_sandbox`, because the
  sandbox has its own route.
- `model_profile_id` is a `profile_id` of the catalogue. A name that is not in the allowlist of the server is
  refused, and a profile whose status is not `tested` is refused with the reason.
- `variant` is the architecture of the case. `A` runs without the tools of the agent, `B` and `C` need a model that
  calls tools natively, and `D` needs the strict requirement. A model that lacks the capability is refused with the
  capability named, and it is never replaced by another model.
- `scenario_id`, `sandbox_id`, `expected_revision` and `account_id` identify the case. The facade carries them into
  the trace of the run. In this milestone they are not checked against the sandbox store, so any value that matches
  the shape of the contract works.
- `limits` are the caps of the run. They are checked before the money of the visitor is spent, and the cap of the
  money is checked against the worst case that the other caps allow.

The body may never carry a raw key. The route takes the handle of a credential and nothing else.

## 8. Follow the run and read what it cost

The state of the run:

```bash
curl -sS -b jar.txt http://127.0.0.1:8010/v1/live-runs/$RUN
```

```json
{"run_id":"run_f6db6c7ba5bf80d4","status":"completed","answer":"the payment was reversed by the issuer, not by the merchant","error":null,"best_effort":false,"cancel_requested":false,"provider":"openai","model_profile_id":"openai-gpt-4.1-mini","model_id":"gpt-4.1-mini"}
```

The trace of the run, as a stream of events that ends with the terminal event:

```bash
curl -sS -N -b jar.txt http://127.0.0.1:8010/v1/live-runs/$RUN/events
```

```text
event: run.started
event: span.started
event: span.ended
event: run.status
event: run.completed
```

Every run ends with exactly one terminal event: `run.completed`, `run.failed` or `run.cancelled`. Whatever happened,
the partial trace stays visible.

The cost of the run:

```bash
curl -sS -b jar.txt http://127.0.0.1:8010/v1/live-runs/$RUN/cost
```

```json
{"run_id":"run_f6db6c7ba5bf80d4","status":"completed","model_calls":1,"tool_calls":0,"calls_by_model":{"gpt-4.1-mini":1},"input_tokens":120,"output_tokens":24,"elapsed_seconds":0.002,"observed_cost_usd":"0.0000864","estimated_cost_usd":"0.0008252","price_known":true,"money_cap_authoritative":true,"cut_by":null,"usage_without_reservation":[],"note":"the observed cost and the estimated cost are two numbers: the first is what the provider reported and the second is what the run planned"}
```

The observed cost and the estimated cost are two numbers and never one. The observed one is what the provider
counted, the estimated one is what the run planned. A run whose model has no verified price shows no amount at all
and says that the price is unknown.

To stop a run that is still going:

```bash
curl -sS -b jar.txt -X POST http://127.0.0.1:8010/v1/live-runs/$RUN/cancel
```

The calls that had not started never start, and the answer says that the cancellation of a call that was already at
the provider is a best effort and not a guarantee.

## 9. Revoke the key

There are two ways, and both take effect at once.

Forget one credential, with its handle:

```bash
cat > forget.json <<JSON
{"handle": "$HANDLE"}
JSON

curl -sS -b jar.txt -H 'Content-Type: application/json' --data-binary @forget.json http://127.0.0.1:8010/v1/credentials/forget
```

```json
{"forgotten":true,"message":"the key is gone"}
```

Forget every credential of the session, by ending the session:

```bash
curl -sS -o /dev/null -w "%{http_code}\n" -b jar.txt -X DELETE http://127.0.0.1:8010/v1/sessions/current
```

```text
204
```

The answer of the forgetting is the same when there was no key to forget, so the route never tells a visitor
whether a handle of another session exists:

```json
{"forgotten":false,"message":"there was no key to forget"}
```

The key also dies when the time to live of the credential passes (one hour by default, and never longer than the
session that holds it) and when the server restarts, because the key lives in the memory of the process and
nowhere else. The vault is bounded: 64 credentials at the same time by default, and a credential that fails three
times is dropped.

When you are done, remove the files that hold the handle and the cookie:

```bash
rm -f jar.txt credential.json run.json run-start.json forget.json
```

## 10. The eleven routes

| Route | What it does |
| --- | --- |
| `POST /v1/sessions` | Issues the session of the visitor and sets the cookie. |
| `DELETE /v1/sessions/current` | Ends the session and drops every credential of that session. |
| `POST /v1/credentials` | Accepts the key of the visitor and answers with a handle. |
| `POST /v1/credentials/forget` | Drops one credential at once. |
| `GET /v1/models` | The catalogue of the models the visitor may pick. |
| `GET /v1/models/{profile_id}` | The price of one model, with its provenance. |
| `POST /v1/live-runs` | Starts a live run and answers with its identifier. |
| `GET /v1/live-runs/{run_id}` | The state of a run, its answer and the reason it ended. |
| `GET /v1/live-runs/{run_id}/events` | The trace of the run, until the terminal event. |
| `POST /v1/live-runs/{run_id}/cancel` | Cancels a run that is still going. |
| `GET /v1/live-runs/{run_id}/cost` | What the run consumed, and the two costs. |

A run belongs to the session that started it. A run of another session answers `404` with the code `NOT_FOUND`,
exactly like a run that never existed, so a visitor cannot learn that a run of another visitor exists.

## The offline state

With `LEDGERLENS_OFFLINE=1` the whole product runs with no key and no network: the replay and the deterministic
sandbox keep working exactly as before. The live mode is refused with a readable reason, because a run that cannot
call a provider would be a run that lies about its own mode.

Start the server offline and ask for a key:

```bash
LEDGERLENS_OFFLINE=1 uv run uvicorn ledgerlens.api.byok:create_app --factory --port 8011
```

```bash
curl -sS -i -b jar.txt -H 'Content-Type: application/json' --data-binary @run.json http://127.0.0.1:8011/v1/live-runs
```

```http
HTTP/1.1 503 Service Unavailable

{"code":"LIVE_MODE_OFFLINE","message":"the live mode is off because the product runs offline (LEDGERLENS_OFFLINE=1); the replay and the sandbox keep working exactly as before","retryable":false,"request_id":"req_f63f3bd3f27c995e"}
```

The routes that hold or spend a credential answer `503` with the code `LIVE_MODE_OFFLINE`: that is
`POST /v1/credentials` and `POST /v1/live-runs`. The routes that hold nothing and spend nothing keep answering:
`GET /v1/models`, `GET /v1/models/{profile_id}`, `POST /v1/credentials/forget` and `DELETE /v1/sessions/current`.

```bash
curl -sS http://127.0.0.1:8011/v1/models
curl -sS -b jar.txt -H 'Content-Type: application/json' --data-binary @forget.json http://127.0.0.1:8011/v1/credentials/forget
```

## Appendix A: the whole flow without a key and without a network

The live mode refuses to run offline, so the flow above cannot be rehearsed with `LEDGERLENS_OFFLINE=1`. It can be
rehearsed with a scripted provider: the application accepts an `adapter_factory`, and the fake adapter of the
repository answers what the script tells it to answer and never opens a socket. Nothing is billed and no key is
needed, and the shape of every answer is the shape of the live one.

Save this as `ledgerlens_fake_live.py`:

```python
from ledgerlens.api.byok import create_app
from ledgerlens.byok.adapter import FakeProviderAdapter


def fake_adapter(provider: str, api_key: str) -> FakeProviderAdapter:
    return FakeProviderAdapter(provider=provider, api_key=api_key).script_answer(
        "the payment was reversed by the issuer, not by the merchant",
        input_tokens=120,
        output_tokens=24,
    )


app = create_app(adapter_factory=fake_adapter)
```

Start it on another port:

```bash
uv run uvicorn --app-dir . ledgerlens_fake_live:app --port 8114
```

Then follow the sections 4 to 9 with the port `8114` instead of `8010`, and paste a key that cannot be mistaken for
one (the fake provider never reads it). The answers of that run are the ones quoted above, with the numbers of the
scripted provider: one model call, 120 input tokens, 24 output tokens, an observed cost of `0.0000864` US$ and an
estimated cost of `0.0008252` US$.

The fake is a test double, not the product. It proves the shape of the flow; it does not prove that a real provider
answers.

## Appendix B: check a body before you send it

The published contract of the request is a file of the repository, so a body can be checked without a server, without
a key and without a network:

```bash
uv run python - <<'PY'
import json
from pathlib import Path
from jsonschema import Draft202012Validator

schema = json.loads(Path("specs/003-r3-bring-your-own-key/contracts/live-run-request.schema.json").read_text())
body = json.loads(Path("run.json").read_text())
errors = sorted(Draft202012Validator(schema).iter_errors(body), key=lambda e: list(e.absolute_path))
print("errors:", len(errors))
for error in errors:
    print(" -", list(error.absolute_path), error.message)
PY
```

```text
errors: 0
```

## Appendix C: the endpoints the server may call

The server calls only the endpoints its providers publish, and in public mode it refuses the addresses that reach
the machine itself: the link-local range, where the metadata of a cloud machine lives, and the loopback range,
where the services of the host live. The check is a pure function of the text of the endpoint, so it can be read
without a network:

```bash
uv run python - <<'PY'
from ledgerlens.byok.adapter import ALLOWED_ENDPOINTS, endpoint_verdict

for provider, endpoints in ALLOWED_ENDPOINTS.items():
    print(provider, endpoints)

for provider, endpoint in [
    ("openai", "https://api.openai.com/v1"),
    ("openai", "https://169.254.169.254/v1"),
    ("openai", "http://127.0.0.1:11434/v1"),
    ("openai", "https://api.openai.com/v1/chat"),
]:
    verdict = endpoint_verdict(provider, endpoint)
    print(provider, endpoint, "->", "allowed" if verdict is None else f"{verdict.code}: {verdict.message}")
PY
```

```text
openai ('https://api.openai.com/v1',)
anthropic ('https://api.anthropic.com/v1',)
google ('https://generativelanguage.googleapis.com/v1beta',)
local ('http://127.0.0.1:11434/v1', 'http://localhost:11434/v1')
openai https://api.openai.com/v1 -> allowed
openai https://169.254.169.254/v1 -> link_local: the endpoint 'https://169.254.169.254/v1' points to the link-local address 169.254.169.254, which the public demo refuses because it reaches the machine itself
openai http://127.0.0.1:11434/v1 -> loopback: the endpoint 'http://127.0.0.1:11434/v1' points to the loopback address 127.0.0.1, which the public demo refuses because it reaches the machine itself
openai https://api.openai.com/v1/chat -> not_published: the endpoint 'https://api.openai.com/v1/chat' is not an allowed endpoint of the provider 'openai', whose published endpoints are: https://api.openai.com/v1
```

In this milestone the visitor never chooses an endpoint: the request of a run carries no endpoint, and the adapter
uses the default endpoint of the provider. The check above is what a deployment that points the adapter at an
endpoint of its own gets.

## What is promised and what is not

Promised, and covered by the tests of the repository:

- The key never reaches a file, a log, a trace, an error message or an answer. The adapter scrubs it out of the
  error of the provider, and the coordinator scrubs everything it writes with the secret of the run, at every depth
  of a payload.
- The key lives in the memory of the process and nowhere else, and it is dropped when the session ends, when you
  forget it, when its time to live passes, when it fails too often or when the server restarts.
- The answer of the credential route never carries the key. It carries the handle, the provider and the expiry.
- A handle of another session is refused with the same answer as a handle that never existed.
- The catalogue shows only the models that were really tested, and the price of a model that was never verified is
  absent and never a guess.
- Every run ends with exactly one terminal event, and no run passes the cap of the calls, the cap of the tokens or
  the cap of the wall clock.
- The money of a run comes out of the code and never out of the model. It is a `Decimal` from the request to the
  report, and the report carries it as text.

Not promised, and said out loud by the product itself:

- No runtime can promise that the memory of the machine is erased. The server drops the key when the credential
  ends, but a copy of the text of the key may survive in the memory of the interpreter or in a swap of the
  operating system. The answer of every route that describes a run carries the header `X-LedgerLens-Key-Erasure`
  that says so.
- The key of the visitor is the money of the visitor. LedgerLens never makes a financial operation, in any mode, and
  the bill of the run comes from your provider.

## The codes you may see

| Code | Status | What it means |
| --- | --- | --- |
| `LIVE_MODE_OFFLINE` | 503 | The product runs offline, so the live mode is off. |
| `SESSION_REQUIRED` | 401 | No valid session cookie, or the session is not yours. |
| `UNKNOWN_PROVIDER` | 422 | The provider is not one the live mode publishes. |
| `CREDENTIAL_REFUSED` | 422 | The key is empty or too long. |
| `MODEL_NOT_ALLOWED` | 422 | The model is not in the allowlist, or its status is not `tested`. |
| `CAPABILITY_MISSING` | 422 | The model lacks the capability the architecture needs. |
| `WRONG_MODE` | 422 | The body asked for the deterministic sandbox on the route of the live mode. |
| `MODE_NOT_ALLOWED` | 403 | The session may not run the live mode. |
| `INVALID_REQUEST` | 422 | The body does not match the published contract. |
| `NOT_FOUND` | 404 | No such run, no such model, or a run of another session. |
| `RUN_RUNNING` | 409 | The run is still running, so it has no cost report yet. |
| `CONTRACT_UNAVAILABLE` | 503 | The deployment lacks `jsonschema`, so the server cannot check a body. |

A refusal of the facade never repeats a value of the visitor. The name of the model, the name of the provider and
the value of any field of the body are never quoted back, because the visitor may have put the key of their
provider in any of them.
