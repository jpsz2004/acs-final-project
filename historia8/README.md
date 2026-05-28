# Historia 8 — LMS Platform

Sistema de simulación de concurrencia clásica sobre una plataforma LMS (Learning Management System), implementado en Python puro con `threading`.

---

## Descripción

El proyecto implementa tres problemas clásicos de concurrencia, cada uno modelado dentro del contexto de una plataforma académica:

| Parte | Problema | Contexto LMS |
|-------|----------|--------------|
| 1 | Producer-Consumer | Estudiantes envían tareas → workers las califican |
| 2 | Readers-Writers | Estudiantes leen notas (lectores) / profesores las actualizan (escritores) |
| 3 | Barrier | Todos los estudiantes deben llegar antes de iniciar el examen |

---

## Arquitectura

```text
historia8/
│
├── app/
│   ├── domain/
│   │   └── models.py            # Entidades: Assignment, GradeRecord, ExchangeRate
│   │
│   ├── application/
│   │   └── services.py          # Casos de uso: ProducerConsumer-, ReadersWriters-, BarrierService
│   │
│   ├── infrastructure/
│   │   ├── locks.py             # ReadWriteLock con prioridad a escritores
│   │   ├── repositories.py      # GradeRepository, PaymentConfigRepository (thread-safe)
│   │   └── workers.py           # AssignmentWorker (threading.Thread)
│   │
│   └── main.py                  # Punto de entrada: ejecuta las 3 simulaciones
│
├── tests/
│   └── test_historia8.py        # 29 tests unitarios e integración
│
├── requirements.txt
├── .env.example
└── README.md
```

Estructura siguiendo **Clean Architecture**:
- `domain/` — entidades puras, sin dependencias externas.
- `application/` — casos de uso que orquestan la infraestructura.
- `infrastructure/` — implementaciones concretas de locks, repos y workers.
- No hay capa `presentation/` porque el proyecto es una simulación de consola, no una API.

---

## Patrones de diseño usados

### Parte 1 — Producer-Consumer
- **Producer-Consumer**: el endpoint productor (hilo de estudiante) introduce tareas en una `queue.Queue` bounded. Los `AssignmentWorker` las consumen concurrentemente.
- **Template Method**: `AssignmentWorker` hereda de `threading.Thread` y sobreescribe `run()`.
- **Repository**: `GradeRepository` abstrae el almacenamiento de notas con interfaz read/write.

### Parte 2 — Readers-Writers
- **ReadWriteLock personalizado** con prioridad a escritores mediante `threading.Condition` y contador `_writers_waiting`. Mientras haya escritores esperando, los nuevos lectores se bloquean.
- **Repository** con política de acceso controlada por el lock (no expuesto al cliente).

### Parte 3 — Barrier
- **Barrier** (`threading.Barrier`): sincronización de punto de encuentro. N hilos se bloquean hasta que todos llegan, y luego se liberan simultáneamente.

---

## Concurrencia usada

| Primitiva | Dónde se usa | Por qué |
|-----------|-------------|---------|
| `queue.Queue(maxsize=10)` | Parte 1 | Cola thread-safe con capacidad acotada; `put()` bloquea si llena |
| `threading.Thread` | Partes 1, 2, 3 | Unidad de ejecución concurrente |
| `threading.Event` | Parte 1 (shutdown) | Señal cooperativa para detener workers |
| `threading.Lock` | Repos, contadores | Exclusión mutua en secciones críticas simples |
| `threading.Condition` | `ReadWriteLock` | Espera condicional con notificación y prioridad a escritores |
| `threading.Barrier` | Parte 3 | Sincronización de punto de encuentro (rendezvous) |

---

## Instrucciones de ejecución

### Requisitos

- Python 3.11+
- Sin dependencias externas (solo biblioteca estándar + pytest para tests)

### Instalar dependencias de test

```bash
cd historia8
pip install -r requirements.txt
```

### Ejecutar simulación completa

```bash
python -m app.main
```

Control de verbosidad de logs:

```bash
LOG_LEVEL=DEBUG   python -m app.main    # Muestra cada evento de lock
LOG_LEVEL=INFO    python -m app.main    # Eventos por tarea (defecto)
LOG_LEVEL=WARNING python -m app.main    # Solo resumen final
```

---

## Endpoints

Esta historia no expone endpoints HTTP — es una simulación de consola pura.  
La salida estructurada por `main.py` equivale a la capa de presentación.

---

## Pruebas realizadas

### Ejecutar todos los tests

```bash
pytest tests/ -v
```

### Descripción de los tests

#### ReadWriteLock (6 tests)
- Adquisición y liberación de lectura individual.
- Múltiples lectores concurrentes no se bloquean entre sí.
- Un escritor activo bloquea a todos los lectores.
- Prioridad a escritores: nuevos lectores esperan mientras hay escritores en cola.
- `release_read()` con contador en 0 no lanza excepción.
- N escritores concurrentes se serializan sin condiciones de carrera.

#### GradeRepository (4 tests)
- Escritura y lectura básica.
- Lectura de clave inexistente retorna `None`.
- 100 escritores concurrentes no producen pérdida de datos.
- 20 lectores concurrentes terminan dentro de 1 s (sin serialización).

#### AssignmentWorker (3 tests)
- Un worker califica una sola tarea correctamente.
- 3 workers califican 15 tareas sin pérdida.
- El worker se detiene cuando `stop_event` se activa.

#### ProducerConsumerService (4 tests)
- Las 15 tareas se califican.
- El throughput es positivo.
- La suma de tareas por worker iguala el total.
- Todas las notas están en rango [0, 100].

#### PaymentConfigRepository (3 tests)
- Lectura de tasas iniciales correcta.
- Actualización y snapshot coherentes.
- 10 lectores + 2 escritores concurrentes no corrompen los datos.

#### ReadersWritersService (3 tests)
- Se completan exactamente 50 lecturas y 6 escrituras.
- No se detecta inanición de escritores.
- Cada escritor completa sus 3 escrituras.

#### BarrierService (5 tests)
- Se registran los 5 estudiantes.
- Todos comienzan dentro de 50 ms entre sí.
- Cada estudiante llega antes de comenzar.
- El último en llegar libera la barrera con espera < 50 ms.
- El primero en llegar espera > 0 s (la barrera lo bloqueó).

**Total: 28 tests, todos en verde.**

---

## Salida esperada

```
======================================================================
  Historia 8 — LMS Platform · Concurrency Simulations
  IS924 ACS — Universidad Tecnológica de Pereira
======================================================================

  PART 1 — Producer-Consumer (LMS Grading)
  ...
  Total assignments  : 15
  Graded assignments : 15
  Throughput         : ~2.1 assignments/s

  PART 2 — Readers-Writers (Grade Access Control)
  ...
  Total reads     : 50
  Total writes    : 6
  Starvation detected: ✓  No writer starvation detected

  PART 3 — Barrier (Synchronised Exam Start)
  ...
  Simultaneous start : ✓  All students started within 50 ms
```
