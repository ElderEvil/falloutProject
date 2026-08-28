# Pydantic AI Gateway Setup

Use Pydantic AI Gateway for Fallout Shelter chat and agent requests. OpenAI image generation, text-to-speech, and
transcription remain direct OpenAI integrations, so they continue to need an OpenAI API key.

This guide covers local development and the Hetzner Kubernetes deployment. Gateway setup is managed through the
Logfire organization; see the [official Gateway guide](https://pydantic.dev/docs/ai/overview/gateway/) for provider
and billing options.

## Credentials: Keep the Two Keys Separate

| Credential | Format | Where it belongs | Purpose |
|---|---|---|---|
| OpenAI provider key | `sk-...` | Gateway provider configuration and `OPENAI_API_KEY` | Pays for and enables OpenAI requests; still required for images and audio. |
| Gateway API key | `pylf_v...` | `PYDANTIC_AI_GATEWAY_API_KEY` | Authenticates this backend to the Pydantic AI Gateway. |

Never commit either key. Revoke and replace a key if it is pasted into chat, source code, a ticket, or logs.

## 1. Configure OpenAI in the Gateway

In the Logfire organization that owns the Gateway:

1. Open **Gateway settings** and activate the Gateway if it is not already active.
2. Add a provider with these values:

   | Field | Value |
   |---|---|
   | Provider type | `OpenAI` |
   | Route | A stable, unique identifier, for example `elder-openai-provider` |
   | Base URL | `https://api.openai.com/v1` |
   | API key | The OpenAI `sk-...` provider key |

3. Save the provider.
4. In **Gateway settings**, create a Gateway API key for the backend. Copy it once and store it as a secret.

The `Route` is not the model name. It identifies the Gateway provider or routing group and must match
`PYDANTIC_AI_GATEWAY_ROUTE` exactly.

## 2. Configure Local Development

Add these values to `backend/.env` (the file is gitignored):

```env
PYDANTIC_AI_GATEWAY_API_KEY=pylf_v...
PYDANTIC_AI_GATEWAY_ROUTE=elder-openai-provider
PYDANTIC_AI_GATEWAY_BASE_URL=https://gateway-eu.pydantic.dev/proxy

AI_PROVIDER=openai
AI_MODEL=gpt-4o-mini
OPENAI_API_KEY=sk-...
```

Use the regional proxy that matches the Logfire organization. For an EU organization, use
`https://gateway-eu.pydantic.dev/proxy`.

Restart the backend after changing `.env`.

### Check Configuration Without a Model Request

Run this from `backend/`. It initializes the configured model but does not send an inference request:

```bash
uv run python -c "from app.core.config import settings; from app.services.ai_service import get_ai_service; service = get_ai_service(); print({'mode': settings.ai_provider_mode, 'route': settings.PYDANTIC_AI_GATEWAY_ROUTE, 'base_url': settings.PYDANTIC_AI_GATEWAY_BASE_URL, 'using_gateway': service.using_gateway, 'model_available': service.is_available()})"
```

Expected values include `mode: 'gateway'`, `using_gateway: True`, and `model_available: True`.

### Make One Minimal End-to-End Request

This request uses the real provider and incurs its normal small request cost. It also emits a Logfire agent trace
when the local Logfire profile or `LOGFIRE_TOKEN` is configured:

```bash
uv run python -c "import asyncio; from app.core.logfire_config import configure_logfire; from app.services.ai_service import get_ai_service; configure_logfire(); result = asyncio.run(get_ai_service().chat_completion_with_usage([{'role': 'user', 'content': 'Reply with exactly: gateway-local-test'}])); print(result.text)"
```

The output should be `gateway-local-test`, and startup logs should include:

```text
AI initialized via Gateway (openai/gpt-4o-mini) via elder-openai-provider
```

## 3. Configure Hetzner

The Hetzner K3s backend imports the `backend-env` Secret in the `fallout` namespace. Patch only the Gateway keys so
existing secret values are preserved, then restart the backend and worker:

```bash
kubectl -n fallout patch secret backend-env --type merge \
  -p '{"stringData":{"PYDANTIC_AI_GATEWAY_API_KEY":"<gateway-key>","PYDANTIC_AI_GATEWAY_ROUTE":"elder-openai-provider","PYDANTIC_AI_GATEWAY_BASE_URL":"https://gateway-eu.pydantic.dev/proxy"}}'
kubectl -n fallout rollout restart deployment/backend deployment/dramatiq-worker
```

Confirm the rollout before sending application traffic:

```bash
kubectl -n fallout rollout status deployment/backend
kubectl -n fallout logs deployment/backend --tail=100 | grep 'AI initialized'
```

## Repeatable Local API Check

With the local API already running, use the smoke-test script instead of repeating the login and chat calls manually:

```bash
cd backend
uv run fo-cli ops check-ai
```

It uses the default user from `backend/.env`, selects that user's first local dweller, and sends one chat request to
`POST /api/v1/chat/{dweller_id}`. The output reports HTTP statuses, the selected AI mode, Gateway route/proxy, whether
the required keys are configured, and response/action metadata—but never keys, access tokens, dweller IDs, or chat
content. The request creates one local chat-history entry and incurs one normal provider request cost.

For a free readiness check that stops before contacting a model, use:

```bash
uv run fo-cli ops check-ai --skip-chat
```

Use an exact-response assertion only when testing a deterministic provider/model configuration:

```bash
uv run fo-cli ops check-ai --expect gateway-api-check
```

## Troubleshooting

| Symptom | Check |
|---|---|
| `AI initialized with direct OpenAI API (deprecated)` | `PYDANTIC_AI_GATEWAY_API_KEY` is absent or blank in the running backend. |
| A Gateway authentication or route error | Confirm the `pylf_v...` key, exact route name, and regional proxy URL. |
| Gateway works locally but not on Hetzner | Confirm the three Gateway keys are present in `backend-env`, then restart both deployments. |
| Images, TTS, or transcription fail after Gateway setup | `OPENAI_API_KEY` is missing; those features still call native OpenAI APIs directly. |
| No Logfire trace | Confirm the local checkout is associated with the Logfire project or set `LOGFIRE_TOKEN`; then make an agent request. |
