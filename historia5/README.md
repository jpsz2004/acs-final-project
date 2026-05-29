# Historia 5 — Notificaciones en tiempo real (WebSockets + EventBus + JWT + PostgreSQL)

Sistema de procesamiento concurrente productor-consumidor que notifica
automáticamente al cliente cuando un `Job` finaliza, eliminando la necesidad
de polling.

---

## Arquitectura

```
historia5/
├── app/
│   ├── domain/
│   │   ├── models.py          # User, Job, Text, Email, Password, enums
│   │   ├── events.py          # JobCompletedEvent
│   │   └── commands.py        # TextAnalysisCommand
│   │
│   ├── application/
│   │   ├── dtos.py            # Request/Response DTOs (Pydantic)
│   │   ├── errors.py          # Errores de dominio tipados
│   │   ├── event_bus.py       # EventBus pub/sub thread-safe
│   │   ├── handlers.py        # JobCompletedHandler
│   │   ├── ports.py           # Interfaces (Protocol): repos, analyzer, notifier
│   │   └── services.py        # JobService, AuthService, JwtService, WebhookService
│   │
│   ├── infrastructure/
│   │   ├── analyzer.py        # SimpleTextAnalyzer (sentiment + score)
│   │   ├── circuit_breaker.py # CircuitBreaker para webhooks externos
│   │   ├── database.py        # SQLAlchemy engine + scoped_session factory
│   │   ├── hasher.py          # BcryptHasher
│   │   ├── models.py          # ORM: UserModel, JobModel (notified), TextModel
│   │   ├── notification_service.py  # NotificationServiceImpl (WS + Webhook)
│   │   ├── repositories.py    # InMemory* y Postgres* repos
│   │   ├── webhook_client.py  # HttpxWebhookClient
│   │   └── worker.py          # Worker (Thread) + WorkerPool
│   │
│   ├── presentation/
│   │   ├── api.py             # Endpoints REST + WebSocket
│   │   ├── app_factory.py     # create_app() — composición de dependencias
│   │   ├── auth.py            # HTTPBearer dependency → user_id
│   │   └── websocket_manager.py  # WebSocketManager (asyncio.Lock)
│   │
│   └── main.py
│
├── alembic/
│   ├── env.py
│   └── versions/
│       └── 0001_create_tables.py
│
├── tests/
│   └── test_ws_notification.py
│
├── alembic.ini
├── Dockerfile
├── docker-compose.yml
├── entrypoint.sh
├── requirements.txt
└── .env
```

---

## Patrones usados

| Patrón | Dónde | Por qué |
|---|---|---|
| **Producer-Consumer** | `POST /jobs` → `queue.Queue` → `Worker` threads | Desacopla llegada de requests del procesamiento |
| **Observer / Event-Driven** | `EventBus.publish()` → `JobCompletedHandler` | El worker no sabe cómo se notifica al cliente |
| **Repository** | `InMemory*` / `Postgres*` | Abstrae el almacenamiento; intercambiable sin tocar dominio |
| **Strategy** | `TextAnalyzer` Protocol | Permite cambiar el algoritmo de análisis sin modificar workers |
| **Circuit Breaker** | `CircuitBreaker` en webhooks | Evita saturar endpoints externos caídos |
| **Singleton** | `WebSocketManager` (una instancia en `app_factory`) | Centraliza todas las conexiones WS activas |
| **Factory** | `create_app()` | Compone el grafo de dependencias según entorno |

---

## Concurrencia

| Primitiva | Dónde | Para qué |
|---|---|---|
| `queue.Queue` | `JobService` → `Worker` | Cola thread-safe productor-consumidor |
| `threading.Thread` | `Worker` | Procesamiento paralelo de textos |
| `threading.Event` | `WorkerPool.stop()` | Shutdown cooperativo de workers |
| `threading.Lock` | Repos in-memory, `EventBus`, repos webhooks | Exclusión mutua en secciones críticas |
| `asyncio.Lock` | `WebSocketManager` | Protección del dict de conexiones en el event loop |
| `asyncio.run_coroutine_threadsafe` | `NotificationServiceImpl` | Puente entre hilos OS y el event loop de asyncio |
| `UPDATE WHERE notified=false` (SQL atómico) | `PostgresJobRepository.try_mark_notified` | Garantía exactly-once del evento en Postgres |

---

## Variables de entorno

| Variable | Default | Descripción |
|---|---|---|
| `DATABASE_URL` | — | URL Postgres. Si está vacío usa repos in-memory |
| `PORT` | `8005` | Puerto de uvicorn |
| `WORKERS_COUNT` | `4` | Número de worker threads |
| `PROCESSING_DELAY_MS` | `50` | Simulación de latencia en análisis |
| `QUEUE_MAXSIZE` | `0` | Límite de la cola (0 = ilimitado) |
| `JWT_SECRET` | `supersecret...` | Secreto para firmar tokens JWT |
| `JWT_ALGORITHM` | `HS256` | Algoritmo JWT |
| `JWT_EXPIRATION_SECONDS` | `3600` | TTL del token |
| `PUBLIC_BASE_URL` | — | Base URL para `results_url` en notificaciones WS |
| `WEBHOOK_MAX_RETRIES` | `3` | Reintentos para webhooks fallidos |
| `WEBHOOK_BACKOFF_BASE_MS` | `200` | Base del backoff exponencial |
| `CB_FAILURE_THRESHOLD` | `3` | Fallos antes de abrir el circuit breaker |
| `CB_COOLDOWN_S` | `30` | Segundos de cooldown del circuit breaker |

---

## Ejecución local (sin Docker)

```bash
cd historia5

# Crear entorno virtual
python -m venv .venv
source .venv/bin/activate     # Linux/Mac
.venv\Scripts\activate        # Windows

pip install -r requirements.txt

# Sin base de datos (modo in-memory):
uvicorn app.main:app --host 0.0.0.0 --port 8005

# Con PostgreSQL:
export DATABASE_URL=postgresql://user:pass@localhost:5432/historia5db
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8005
```

---

## Ejecución con Docker

```bash
cd historia5

# 1. Crear .env desde el ejemplo
cp env.example .env

# 2. Construir imagen
docker compose build

# 3. Levantar postgres + api (migraciones se ejecutan solas)
docker compose up

# 4. Correr tests (in-memory, no necesita postgres)
docker compose run --rm tests

# 5. Apagar y limpiar
docker compose down -v
```

---

## Endpoints

### Autenticación

| Método | Ruta | Body | Descripción |
|---|---|---|---|
| `POST` | `/register` | `{"email":"...","password":"..."}` | Registra usuario, retorna JWT |
| `POST` | `/login` | `{"email":"...","password":"..."}` | Login, retorna JWT |

Todos los demás endpoints requieren: `Authorization: Bearer <token>`

### Jobs

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/jobs` | Crea job con lote de textos (máx 100). Retorna `{job_id, status:"pending"}` |
| `GET` | `/jobs/{job_id}` | Estado del job y resultados por texto |

### Webhooks

| Método | Ruta | Body | Descripción |
|---|---|---|---|
| `POST` | `/webhooks` | `{"callback_url":"https://..."}` | Registra URL para notificación HTTP |

### WebSocket

```
WS /ws/jobs/{user_id}?token=<jwt>
```

El `user_id` en el path debe coincidir con el `sub` del token JWT.
Si no hay token o no coincide, el servidor cierra con código `1008 Policy Violation`.

Mensaje que recibe el cliente cuando su job termina:

```json
{
  "type": "job_completed",
  "job_id": "...",
  "results_url": "/jobs/..."
}
```

---

## Flujo completo de ejemplo (curl)

```bash
# 1. Registrar usuario
TOKEN=$(curl -s -X POST http://localhost:8005/register \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"secret123"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# 2. Crear un job
JOB=$(curl -s -X POST http://localhost:8005/jobs \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"texts":["hola mundo","este texto es genial","awful bad text"]}')
echo $JOB
JOB_ID=$(echo $JOB | python -c "import sys,json; print(json.load(sys.stdin)['job_id'])")

# 3. Consultar estado
curl -s http://localhost:8005/jobs/$JOB_ID \
  -H "Authorization: Bearer $TOKEN"

# 4. Conectar WebSocket (en otra terminal — requiere wscat o similar)
# USER_ID se obtiene decodificando el JWT (campo 'sub')
# wscat -c "ws://localhost:8005/ws/jobs/$USER_ID?token=$TOKEN"
```

---

## Tests

```bash
# Local
pytest tests/ -v

# Docker (in-memory, sin postgres)
docker compose run --rm tests
```

### Cobertura de tests

| Clase | Tests | Qué verifica |
|---|---|---|
| `TestAuth` | 5 | Registro, login, duplicado, contraseña incorrecta, endpoint sin token |
| `TestJobs` | 4 | Lote > 100, creación, procesamiento en background, scope por usuario |
| `TestWebSocketAuth` | 3 | Sin token, token inválido, user_id no coincide |
| `TestWebSocketNotifications` | 3 | Notificación correcta, exactly-once, desconexión sin crash |

**Total: 15 tests.**