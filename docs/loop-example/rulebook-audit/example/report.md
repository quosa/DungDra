# Rulebook audit

12 findings (12 new since baseline). Rejected by evidence check: 1.

## Conflict (1)

### [high] LOG-1, LOG-2 — rulebook 🆕
CONFIRMED: RULEBOOK.md:4-5. LOG-1 requires logging headers with no carve-out, and LOG-2 forbids logging authorization tokens, which normally travel in the Authorization header. The rulebook has no precedence or redaction clause. orders/handler.js:5 shows the conflict in practice: it satisfies LOG-1 by logging all headers and so falls foul of LOG-2.

```
Every HTTP handler MUST log the incoming request, including headers.
```
<sub>confidence 0.90 · fp `ac3896515ccf4cc1`</sub>

## Gap (1)

### [high] DEP-1 — rulebook 🆕
CONFIRMED: I found no approved-library list anywhere in the repo. The only files are the rulebook, two service files, and the audit tooling. The rulebook defines no approval process or owner, so DEP-1 can't be enforced.

```
Services may only use approved libraries.
```
<sub>confidence 0.90 · fp `4632e72563567e8f`</sub>

## Ambiguity (2)

### [medium] HTTP-1 — rulebook 🆕
CONFIRMED: RULEBOOK.md:8 gives no bound and doesn't say which timeout it means. The ambiguity is real, but it is minor: both cited call sites are decided under either reading (2000ms in orders, no timeout in payments).

```
All outbound HTTP calls MUST set an explicit timeout.
```
<sub>confidence 0.55 · fp `a0732ed8db7b5941`</sub>

### [medium] HTTP-2 — rulebook 🆕
CONFIRMED: RULEBOOK.md:9 doesn't define 'validate'. This matters in practice: orders/handler.js:11-13 only checks that `b.items` exists, which passes the weak reading and fails the strong one.

```
Handlers MUST validate request bodies before use.
```
<sub>confidence 0.65 · fp `0a89f66ed09ef8ca`</sub>

## Violation (7)

### [high] LOG-2 — `services/orders/src/handler.js:5` 🆕
CONFIRMED: handler.js:5 logs the whole req.headers object. `./log` does not exist anywhere in the repo (Glob found no services/orders/src/log*), so no redaction is visible, and there is no middleware or config that redacts. Confidence stays below certain because the Authorization header only appears on authenticated calls, and because LOG-1 requires this logging (see the conflict finding).

```
log.info('request', { path: req.path, headers: req.headers });
```
<sub>confidence 0.80 · fp `6ebe3d606e8406cb`</sub>

### [high] HTTP-2 — `services/payments/src/charge.js:5` 🆕
CONFIRMED: card and amount go straight into the log and the outbound call with no checks. There is no validation middleware in the repo. This fails even the weakest reading of 'validate'.

```
const { card, amount } = req.body;
```
<sub>confidence 0.95 · fp `19ce9e3d9c211843`</sub>

### [high] CFG-1.a, CFG-1.b — `services/payments/src/charge.js:2` 🆕
CONFIRMED: charge.js:2 contains a literal live key, and process.env is never used. The rule ids CFG-1.a and CFG-1.b exist in .audit/rules.json, where CFG-1 is split into 'read from env' and 'never hard-coded'.

```
const API_KEY = "sk_live_51Habc123";
```
<sub>confidence 0.97 · fp `c51eaaa2c4444b15`</sub>

### [high] LOG-2 — `services/payments/src/charge.js:6` 🆕
CONFIRMED: `card` comes straight from req.body (line 5) and is logged unmasked through console.log, with no redaction layer. The only uncertainty is whether `card` holds a full PAN or a token, but in context it is the card data sent to the PSP.

```
console.log('charging card', card, amount);
```
<sub>confidence 0.90 · fp `375e5c0813951354`</sub>

### [medium] DEP-2 — rulebook 🆕
CONFIRMED: charge.js:1 does `require('request')`, which DEP-2 (RULEBOOK.md:13) bans outright. The file is live service code, not a test or vendored file.

```
services/payments/src/charge.js:1:const request = require('request');
```
<sub>confidence 1.00 · fp `d51af8e4e09aae47`</sub>

### [medium] LOG-1 — `services/payments/src/charge.js:6` 🆕
CONFIRMED: `charge(req, res)` is an HTTP handler. Its only log line (6) records card and amount, not the request or its headers. The repo has no middleware that does request logging.

```
console.log('charging card', card, amount);
```
<sub>confidence 0.85 · fp `dee2b21c5d1df3dd`</sub>

### [medium] HTTP-1 — `services/payments/src/charge.js:7` 🆕
CONFIRMED: the options object on line 7 has only url and json, with no timeout. There is no shared client or defaults call (request.defaults) anywhere in the repo.

```
request.post({ url: 'https://psp.example/charge', json: { card, amount, key: API_KEY } },
```
<sub>confidence 0.95 · fp `ad9cd9803dc93846`</sub>

## Unverifiable (1)

### [low] DEP-1 — `services/orders/src/handler.js:1` 🆕
CONFIRMED: the repo has no approved list and no package.json, so this can't be decided. It follows from the DEP-1 gap finding.

```
const axios = require('axios');
```
<sub>confidence 0.50 · fp `bb6cf6cae95a09bc`</sub>
