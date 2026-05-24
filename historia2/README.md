# Historia 2 — Producer/Consumer (FastAPI + Queue + Workers)

Sistema para recibir un lote de textos, encolarlos y procesarlos concurrentemente en segundo plano.

## Arquitectura

- `app/domain`: entidades (`Job`, `Text`) y comandos (`TextAnalysisCommand`).
- `app/application`: DTOs, puertos y `JobService` (caso de uso CreateJob).
- `app/infrastructure`: repositorio in-memory con `threading.Lock`, analizador simple y `WorkerPool`.
- `app/presentation`: API FastAPI + autenticación básica por headers.

## Concurrencia

- Producer: `POST /jobs` valida y encola `TextAnalysisCommand` por cada texto.
- Consumer: `WorkerPool` mantiene N threads esperando en `queue.Queue`.
- Apagado ordenado: `threading.Event` para detener los workers en el lifespan.

## Variables de entorno

- `WORKERS_COUNT` (default `4`)
- `PROCESSING_DELAY_MS` (default `50`) — simula el procesamiento con `time.sleep`.
- `QUEUE_MAXSIZE` (default `0`) — 0 significa sin límite.
- `API_KEY` (opcional) — si está definido, se requiere header `X-API-Key`.

## Ejecución local

Desde la carpeta `historia2/`:

```bash
python -m venv .venv
source .venv/bin/activate  # en Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8002
```

## Autenticación

- Header obligatorio: `X-User-Id: <user_id>`
- Si `API_KEY` está configurada: `X-API-Key: <api_key>`

## Endpoints

### POST /jobs

Request:

```json
{ "texts": ["texto1", "texto2"] }
```

Regla: máximo 100 textos por lote (si se excede, retorna 400).

Response (202):

```json
{ "job_id": "...", "status": "pending" }
```

### GET /jobs/{job_id}

Retorna estado del job y resultados por texto.

## Tests

Desde `historia2/`:

```bash
pytest -q
```
