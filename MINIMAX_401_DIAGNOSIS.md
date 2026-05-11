# MiniMax 401 Diagnosis — Corrected

## Summary

The previous diagnosis was too strong. It claimed that `sk-cp-` Token Plan keys cannot be used from this repo or from direct HTTP calls. MiniMax's current Token Plan documentation says otherwise: Token Plan keys are intended for custom OpenAI-compatible and Anthropic-compatible endpoints.

What was actually wrong in this repo:

- `.env` was never loaded, so `quant analyze` usually ran with no key.
- The MiniMax call used the lowercase model id `minimax-m2.7`; MiniMax documents `MiniMax-M2.7`.
- The code sent whichever key it found to both MiniMax and OpenRouter, so a MiniMax key could be tried against OpenRouter.
- The OpenAI-compatible MiniMax path only checked `HTTP 200`, but MiniMax can return an error in `base_resp` inside a 200 response.
- Provider errors were swallowed and replaced with a generic mock response, hiding the real failure.

Those issues are now fixed in `quant/decide.py`.

## What MiniMax Documents

MiniMax documents two usable protocol surfaces for Token Plan keys:

- OpenAI-compatible: `https://api.minimax.io/v1`, model `MiniMax-M2.7` or `MiniMax-M2.7-highspeed`
- Anthropic-compatible: `https://api.minimax.io/anthropic`, model `MiniMax-M2.7` or `MiniMax-M2.7-highspeed`

Official references checked on 2026-05-08:

- `https://platform.minimax.io/docs/token-plan/other-tools`
- `https://platform.minimax.io/docs/token-plan/codex-cli`
- `https://platform.minimax.io/docs/api-reference/text-anthropic-api`
- `https://platform.minimax.io/docs/token-plan/faq`

The FAQ still says Token Plan and pay-as-you-go Open Platform keys are not interchangeable. That means a Token Plan key is not the same billing product as a standard API key; it does not mean Token Plan keys are unusable from external tooling.

## Current Local Result

Using the current key in `.env`, sanitized direct checks reached MiniMax but MiniMax rejected the key:

- `https://api.minimax.io/anthropic/v1/messages` -> `401 authentication_error`
- `https://api.minimax.io/v1/chat/completions` -> `401 authorized_error`
- `https://www.minimax.io/v1/token_plan/remains` -> `base_resp.status_code=1004`

The error text was:

```text
login fail: Please carry the API secret key in the 'Authorization' field of the request header
```

That message appears even when the request includes an `Authorization: Bearer ...` header, so in this case it means MiniMax did not accept the supplied key value for the tested account/region/product, not that the repo omitted the header.

## Current Code Behavior

`quant analyze` now:

1. Loads `.env` automatically.
2. Uses `MINIMAX_API_KEY` only for MiniMax.
3. Tries MiniMax's Anthropic-compatible endpoint first.
4. Falls back to MiniMax's OpenAI-compatible endpoint.
5. Uses OpenRouter only if a separate `OPENROUTER_API_KEY` exists.
6. Includes the real provider error in the mock fallback.

Example current output:

```text
Mock response — MiniMax Anthropic HTTP 401: login fail: Please carry the API secret key in the 'Authorization' field of the request header; MiniMax OpenAI HTTP 401: login fail: Please carry the API secret key in the 'Authorization' field of the request header (1004)
```

## Remaining Issue

The integration is now wired for MiniMax Token Plan correctly, but the current `.env` key is not accepted by MiniMax from this environment. The next thing to verify outside the repo is whether the copied key is still active, complete, and from the same MiniMax account/region as the Token Plan subscription.
