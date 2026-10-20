# Service Rulebook

## Logging
- LOG-1: Every HTTP handler MUST log the incoming request, including headers.
- LOG-2: Services MUST NOT log authorization tokens or card numbers.

## HTTP
- HTTP-1: All outbound HTTP calls MUST set an explicit timeout.
- HTTP-2: Handlers MUST validate request bodies before use.

## Dependencies
- DEP-1: Services may only use approved libraries.
- DEP-2: The `request` npm package MUST NOT be used.

## Config
- CFG-1: Secrets MUST be read from environment variables, never hard-coded.
