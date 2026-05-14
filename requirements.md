# Organización General del Proyecto

El proyecto se dividirá en tres ejercicios independientes:

```text
acs-final/
│
├── historia2/
├── historia5/
├── historia8/
└── README.md
```

Cada historia funcionará como un mini-proyecto autónomo, con:

- estructura propia
- Dockerfile propio
- dependencias propias
- README propio
- configuración propia
- tests propios

No existirá una aplicación principal que unifique las historias.

---

# Distribución de Responsabilidades

## Responsabilidades de Tomás

Tomás será responsable de:

- Implementación completa de la Historia 2
- Implementación completa de la Historia 5
- Arquitectura interna de dichas historias
- Desarrollo de lógica de negocio
- Desarrollo de concurrencia
- Desarrollo de endpoints
- Desarrollo de WebSockets
- Desarrollo de workers
- Desarrollo de pruebas

Tomás NO será responsable de:

- Dockerización
- Orquestación con Docker Compose
- Infraestructura de despliegue
- Redes Docker
- Configuración de contenedores
- Integración DevOps

---

## Responsabilidades de Juan Pablo

Juan Pablo será responsable de:

- Implementación completa de la Historia 8
- Dockerización de Historia 2
- Dockerización de Historia 5
- Dockerización de Historia 8
- Configuración de Docker Compose
- Configuración de variables de entorno
- Configuración de PostgreSQL
- Validación de ejecución en contenedores
- Configuración de redes y puertos
- Validación final de despliegue
- Estructuración técnica del repositorio
- Integración de infraestructura

Juan Pablo NO modificará la lógica interna desarrollada por Tomás salvo que sea estrictamente necesario para compatibilidad Docker.

---

# Reglas Globales del Proyecto

## Regla 1 — Cada historia debe funcionar de manera independiente

Cada historia debe poder ejecutarse individualmente.

Ejemplo:

```bash
cd historia2
docker compose up
```

Debe iniciar correctamente sin depender de ninguna otra historia.

---

## Regla 2 — No compartir dependencias entre historias

Cada historia debe tener:

- `requirements.txt`
- `.env`
- `Dockerfile`
- `docker-compose.yml`
- `README.md`

propios.

---

## Regla 3 — No acoplar historias

Está prohibido:

- importar módulos entre historias
- reutilizar código cruzado
- compartir estados
- compartir bases de datos
- compartir colas

Cada historia debe ser completamente autónoma.

---

## Regla 4 — Estructura obligatoria

Todas las historias deben seguir una estructura similar.

Ejemplo:

```text
historiaX/
│
├── app/
│   ├── domain/
│   ├── application/
│   ├── infrastructure/
│   ├── presentation/
│   └── main.py
│
├── tests/
│
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env
└── README.md
```

---

## Regla 5 — Variables de entorno obligatorias

Está prohibido hardcodear:

- puertos
- rutas
- secretos
- hosts
- credenciales
- URLs de base de datos

Todo debe obtenerse mediante:

```python
os.getenv()
```

---

## Regla 6 — Compatibilidad Docker obligatoria

Toda aplicación debe ejecutarse usando:

```text
0.0.0.0
```

Nunca:

```text
127.0.0.1
localhost
```

---

## Regla 7 — No usar SQLite

La persistencia debe ser compatible con PostgreSQL desde el inicio.

---

## Regla 8 — Requirements limpios

Cada historia debe mantener actualizado:

```text
requirements.txt
```

---

## Regla 9 — Tests independientes

Cada historia debe tener sus propios tests dentro de:

```text
tests/
```

---

## Regla 10 — Documentación obligatoria

Cada historia debe incluir:

- descripción
- arquitectura
- patrones usados
- concurrencia usada
- instrucciones de ejecución
- endpoints
- pruebas realizadas

---

# Responsabilidades Técnicas — Historia 2

## Objetivo

Implementar un sistema Productor-Consumidor usando FastAPI, Queue y Workers concurrentes.

---

## Responsabilidades de Tomás

### Arquitectura

Implementar:

```text
domain/
application/
infrastructure/
presentation/
```

---

### API

Crear endpoint:

```text
POST /jobs
```

---

### DTOs

Definir:

- `CreateJobRequestDTO`
- `CreateJobResponseDTO`

---

### Queue

Implementar:

```python
queue.Queue()
```

thread-safe.

---

### Worker Pool

Implementar:

- clase `Worker`
- clase `WorkerPool`

---

### Procesamiento

Simular procesamiento concurrente usando:

```python
time.sleep()
```

---

### Estados

Implementar estados:

```text
pending
processing
completed
failed
```

---

### Repositorio

El acceso compartido debe protegerse usando:

```python
threading.Lock()
```

---

### Tests

Deben probarse:

- múltiples workers
- múltiples jobs
- queue concurrente
- procesamiento paralelo

---

## Restricciones Técnicas para Dockerización

Tomás debe garantizar:

### Uso de variables de entorno

Ejemplo:

```python
DATABASE_URL = os.getenv("DATABASE_URL")
```

---

### No usar rutas locales absolutas

Prohibido:

```python
C:/Users/...
```

---

### No asumir puertos fijos

Todo configurable.

---

### No crear archivos fuera del proyecto

Toda persistencia debe permanecer dentro del contenedor o BD.

---

### Punto de entrada único

Debe existir:

```text
app/main.py
```

---

# Responsabilidades Técnicas — Historia 5

## Objetivo

Implementar sistema de notificaciones concurrentes usando WebSockets y EventBus.

---

## Responsabilidades de Tomás

### WebSocket endpoint

Implementar:

```text
/ws/jobs/{user_id}
```

---

### EventBus

Implementar:

```python
publish()
subscribe()
```

---

### Eventos

Definir:

```text
JobCompletedEvent
```

---

### NotificationService

Debe existir un servicio desacoplado de los workers.

---

### WebSocketManager

Debe:

- mantener conexiones activas
- manejar desconexiones
- soportar múltiples clientes

---

### Thread Safety

El manejo de conexiones debe protegerse usando:

```python
threading.Lock()
```

---

### Tests

Deben probarse:

- múltiples clientes
- desconexiones
- eventos concurrentes
- envío correcto de notificaciones

---

## Restricciones Técnicas para Dockerización

Tomás debe garantizar:

### Host configurable

La aplicación debe ejecutarse en:

```text
0.0.0.0
```

---

### Variables de entorno obligatorias

Toda configuración debe obtenerse desde `.env`.

---

### No asumir entorno local

No utilizar:

```text
localhost
```

en conexiones internas.

---

### Compatibilidad FastAPI + WebSocket

La aplicación debe iniciar correctamente mediante:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8005
```

---

# Responsabilidades Técnicas — Historia 8

## Objetivo

Implementar problemas clásicos de concurrencia usando threading.

---

## Responsabilidades de Juan Pablo

---

## Parte 1 — Producer Consumer

Implementar:

- Queue
- productores
- consumidores
- workers
- sincronización

---

## Parte 2 — Readers Writers

Implementar:

- `ReadWriteLock`
- prioridad a escritores
- exclusión mutua

Métodos obligatorios:

```python
acquire_read()
release_read()
acquire_write()
release_write()
```

---

## Parte 3 — Barrier

Implementar:

```python
threading.Barrier
```

---

## Logs Concurrentes

Deben visualizarse claramente:

- entrada de lectores
- salida de lectores
- espera de escritores
- escritura activa

---

## Estadísticas

Implementar:

- tiempo total
- throughput
- validación de starvation

---

# Responsabilidades DevOps — Juan Pablo

## Dockerización de Historia 2

Crear:

- Dockerfile
- docker-compose.yml
- configuración de PostgreSQL
- variables de entorno
- validación de networking

---

## Dockerización de Historia 5

Crear:

- Dockerfile
- docker-compose.yml
- networking WebSocket
- configuración de puertos
- validación de conexiones

---

## Dockerización de Historia 8

Crear:

- Dockerfile
- configuración de ejecución
- automatización de pruebas

---

# Reglas de Calidad de Código

## Regla 1 — No lógica en endpoints

Los endpoints solo deben:

```text
request → service → response
```

---

## Regla 2 — Separación por capas

- Presentación no accede directamente a infraestructura
- Dominio no depende de FastAPI
- Application contiene casos de uso
- Infrastructure contiene detalles técnicos

---

## Regla 3 — Uso de typing

Debe utilizarse tipado explícito.

---

## Regla 4 — Logging

Usar:

```python
logging
```

en lugar de `print`, excepto en simulaciones académicas.

---

## Regla 5 — Código desacoplado

Workers, servicios y repositorios deben poder probarse individualmente.

---

# Flujo de Trabajo en Equipo

## Git

Ramas obligatorias:

```text
main
develop
feature/historia2
feature/historia5
feature/historia8
feature/docker
```

---

## Integración

Los cambios deben integrarse continuamente.

No esperar al final del proyecto.

---

## Validaciones antes de merge

Antes de fusionar cambios:

- ejecutar tests
- verificar funcionamiento local
- verificar imports
- verificar dependencias

---

## Reuniones Técnicas

Realizar revisiones frecuentes para:

- validar estructura
- validar compatibilidad Docker
- evitar retrabajo
- validar endpoints
- validar configuraciones

---

# Objetivo Final del Proyecto

Cada historia debe sentirse como:

```text
un mini proyecto profesional y desacoplado
```

y no como:

```text
un script académico improvisado
```

El objetivo técnico es demostrar:

- arquitectura limpia
- concurrencia
- desacoplamiento
- diseño profesional
- capacidad de despliegue
- capacidad de contenerización
- buenas prácticas de ingeniería de software