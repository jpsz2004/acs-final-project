# Historia 5 — Notificaciones en tiempo real (WebSockets + EventBus)

Sistema de procesamiento concurrente (producer/consumer) que notifica automáticamente cuando un Job finaliza (completed), evitando polling.

## Arquitectura

- `app/domain`: entidades (`Job`, `Text`), comandos y evento `JobCompletedEvent`.
- `app/application`: `EventBus` (pub/sub), servicios (casos de uso) y handler de notificación.
- `app/infrastructure`: repo in-memory + workers + `NotificationService` (WebSocket + Webhook) + circuit breaker.
- `app/presentation`: API FastAPI, endpoint WebSocket y `WebSocketManager`.

## Concurrencia

- Producer: `POST /jobs` encola `TextAnalysisCommand`.
- Consumers: N threads `Worker` consumen la cola y actualizan el repositorio.
- Evento: cuando el job pasa a `completed`, se publica `JobCompletedEvent` **exactamente una vez por job**.
- Notificación: el handler delega a `NotificationService` (envía por WebSocket y opcionalmente por webhook).

## Variables de entorno

- `WORKERS_COUNT` (default `4`)
- `PROCESSING_DELAY_MS` (default `50`)
- `QUEUE_MAXSIZE` (default `0`)
- `API_KEY` (opcional) — si se define, se requiere `X-API-Key`.
- `PUBLIC_BASE_URL` (opcional) — se usa para construir `results_url` (si no, se envía `/jobs/{job_id}`).

Webhooks:

- `WEBHOOK_MAX_RETRIES` (default `3`)
- `WEBHOOK_BACKOFF_BASE_MS` (default `200`) — backoff exponencial.

Circuit breaker:

- `CB_FAILURE_THRESHOLD` (default `3`)
- `CB_COOLDOWN_S` (default `30`)

## Ejecución local

Desde la carpeta `historia5/`:

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8005
```

## Autenticación

- REST: header obligatorio `X-User-Id`.
- WebSocket: se requiere header `X-User-Id` igual al `{user_id}` del path.
- Si `API_KEY` está configurada, agregar `X-API-Key`.

## Endpoints

- `POST /jobs` → crea job, encola textos y retorna `202 {job_id, status:"pending"}`.
- `GET /jobs/{job_id}` → consulta estado/resultados.
- `POST /webhooks` → registra callback para el usuario: `{ "callback_url": "https://..." }`.
- `WS /ws/jobs/{user_id}` → recibe mensajes:

```json
{ "type": "job_completed", "job_id": "...", "results_url": "/jobs/..." }
```

## Tests

```bash
pytest -q
```
