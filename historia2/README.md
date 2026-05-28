# Historia 2 — Producer/Consumer (FastAPI + Queue + Workers)

Sistema para recibir un lote de textos, encolarlos y procesarlos concurrentemente en segundo plano.

## Arquitectura

- `app/domain`: entidades (`User`, `Job`, `Text`) y comandos (`TextAnalysisCommand`).
- `app/application`: DTOs, puertos, `AuthService`, `JwtService`, `JobService` y `ReportService`.
- `app/infrastructure`: repositorios (in-memory y Postgres), SQLAlchemy models, `BcryptHasher`, analizador simple y `WorkerPool`.
- `app/presentation`: API FastAPI con JWT bearer authentication.

## Concurrencia

- Producer: `POST /jobs` valida y encola un `TextAnalysisCommand` por cada texto.
- Consumer: `WorkerPool` mantiene N hilos (threads) que consumen de `queue.Queue`.
- Apagado ordenado: `threading.Event` en el `lifespan` de FastAPI para detener los workers.

## Variables de entorno importantes

- `WORKERS_COUNT` (default `4`)
- `PROCESSING_DELAY_MS` (default `50`) — simula el procesamiento con `time.sleep`.
- `QUEUE_MAXSIZE` (default `0`) — 0 significa sin límite.
- `DATABASE_URL` (opcional) — si está presente usa Postgres (SQLAlchemy + Alembic). Si no, usa repositorios in-memory.
- `JWT_SECRET` (obligatorio en producción) — secreto para firmar tokens JWT.
- `JWT_ALGORITHM` (default `HS256`)
- `JWT_EXPIRATION_SECONDS` (default `3600`)

## Ejecución local

Desde la carpeta `historia2/`:

```bash
python -m venv .venv
.venv\Scripts\activate    # Windows
# on Unix: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8002
```

Si usas Postgres (recomendado para integración):

```bash
export DATABASE_URL=postgresql://user:pass@localhost:5432/dbname
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8002
```

## Autenticación

- Ahora se usa JWT Bearer tokens en lugar de `X-User-Id` header.
- Endpoints públicos: `/register`, `/login` (devuelven `access_token`).
- Para llamadas protegidas añadir header: `Authorization: Bearer <access_token>`

## Endpoints

- POST `/register` — registra usuario: body `{ "email": "...", "password": "..." }`. Retorna `access_token`.
- POST `/login` — obtiene `access_token` con credenciales.
- POST `/jobs` — crea un job (protegido). Body: `{ "texts": ["...", "..."] }`. Máx 100 textos por solicitud.
- GET `/jobs/{job_id}` — estado del job y resultados agregados (protegido).
- GET `/jobs/{job_id}/results?limit=20&offset=0` — resultados paginados (protegido).
- GET `/jobs/{job_id}/report` — reporte estadístico (total, procesados, completados, fallidos, puntaje promedio) (protegido).

Notas:

- Cada `Text` ahora incluye un campo `score: float` en rango aproximado [-1.0, 1.0].
- Repositorios: hay implementaciones in-memory y `PostgresJobRepository`/`PostgresUserRepository` usando SQLAlchemy.

## Migraciones (Alembic)

- Archivo de configuración: `alembic/` y `alembic.ini` incluido.
- Crear/migrar esquema:

```bash
alembic upgrade head
```

## Tests

Desde `historia2/`:

```bash
pytest -q
```

Los tests actuales cubren registro/login, creación de jobs y scope por usuario.

## Quick Example (curl)

The following sequence shows how to register a user, obtain a JWT token, create a job and query results.
`jq` is optional but convenient for parsing JSON in the shell.

1) Register (creates user and returns access token):

```bash
curl -s -X POST http://localhost:8002/register \
	-H "Content-Type: application/json" \
	-d '{"email":"user@example.com","password":"secret123"}' | jq -r '.access_token'
```

2) Login (alternate way to obtain token):

```bash
TOKEN=$(curl -s -X POST http://localhost:8002/login \
	-H "Content-Type: application/json" \
	-d '{"email":"user@example.com","password":"secret123"}' | jq -r '.access_token')
echo "TOKEN=$TOKEN"
```

3) Create a job (use the `Authorization` header):

```bash
CREATE_RESP=$(curl -s -X POST http://localhost:8002/jobs \
	-H "Content-Type: application/json" \
	-H "Authorization: Bearer $TOKEN" \
	-d '{"texts":["hola","mundo"]}')
echo "$CREATE_RESP" | jq
JOB_ID=$(echo "$CREATE_RESP" | jq -r '.job_id')
```

4) Poll job status:

```bash
curl -s -X GET "http://localhost:8002/jobs/$JOB_ID" \
	-H "Authorization: Bearer $TOKEN" | jq
```

5) Get paginated results:

```bash
curl -s -X GET "http://localhost:8002/jobs/$JOB_ID/results?limit=10&offset=0" \
	-H "Authorization: Bearer $TOKEN" | jq
```

6) Get job report:

```bash
curl -s -X GET "http://localhost:8002/jobs/$JOB_ID/report" \
	-H "Authorization: Bearer $TOKEN" | jq
```

Replace `http://localhost:8002` and ports/host with your deployment settings as needed.
