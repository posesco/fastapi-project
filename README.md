# Movie API: an SRE learning lab built with FastAPI

This repository is a living, exploratory lab for learning backend development from an SRE perspective. It uses a Movie API to connect application design with authentication, persistence, caching, storage, migrations, container operations, observability, and load testing.

The project is intentionally a work in progress. It is useful for experimentation and study, but it is not presented as a production-ready reference architecture.

## What works today

- Async HTTP endpoints built with FastAPI and SQLModel.
- PostgreSQL persistence with Alembic migrations.
- Redis-backed token revocation and login rate limiting.
- OAuth2 password flow with JWT access and refresh tokens.
- Role-based user operations and audit records.
- Movie CRUD, category queries, and image uploads.
- Selectable S3-compatible storage (MinIO locally) or local filesystem storage.
- Optional OpenTelemetry export for logs, metrics, and traces.
- Docker Compose definitions for the API and supporting infrastructure.
- Isolated pytest resources with fail-closed safety checks.
- k6 scenarios for the public movie read endpoints.

The current application configuration targets PostgreSQL. Although additional database drivers exist in `requirements.txt`, MariaDB and SQLite are not configured or supported execution paths.

## Quick start with Docker

### Prerequisites

- Docker Engine
- Docker Compose with support for the Compose `include` directive
- Git

### Start the API

```bash
git clone https://github.com/posesco/fastapi-project.git
cd fastapi-project
cp .env.example .env
docker compose up -d --build app nginx postgres redis minio minio-init
```

This command starts only the application path and its required local dependencies. Alembic migrations run when the application container starts.

| Resource | URL |
|---|---|
| API entry point | <http://localhost> |
| OpenAPI UI | <http://localhost/docs> |
| ReDoc | <http://localhost/redoc> |
| Detailed application status | <http://localhost/_status/> |
| Liveness check | <http://localhost/health-check/> |
| MinIO console | <http://localhost:9001> |

Check service state and application logs:

```bash
docker compose ps
docker compose logs -f app
```

Stop the stack without deleting persisted data:

```bash
docker compose down
```

Before using shared or public environments, replace the example credentials and JWT secret in `.env`. The supplied configuration is for local experimentation.

## API capabilities

All business endpoints use the `/api/v1` prefix. The generated OpenAPI documentation is the source of truth for request and response schemas.

| Area | Current behavior |
|---|---|
| Movies | List, retrieve, filter by category, create, update, and delete movies |
| Users | Register, authenticate, refresh and revoke tokens, update profiles, and administer roles |
| Authorization | JWT authentication with role checks for privileged operations |
| Audit | Records selected user and movie mutations |
| Uploads | Accepts JPEG, PNG, and WebP files through an authenticated endpoint |
| Storage | Uses S3-compatible storage by default; local filesystem storage is selectable with `STORAGE_BACKEND=local` |

Useful public read endpoints include:

```text
GET /api/v1/movies/
GET /api/v1/movies/categories
GET /api/v1/movies/{id}
GET /api/v1/movies/category/?category=Drama
```

Authentication, mutation payloads, and role requirements are easiest to explore through `/docs`.

## Safe, isolated tests

The test suite is destructive by design inside its dedicated resources: it recreates the PostgreSQL schema and flushes its Redis database. It must never point at application data.

The safety checks fail closed before connecting unless all of these conditions are true:

- `.env.test` or equivalent explicit test environment variables provide both resource URLs.
- PostgreSQL uses the reserved database name `fastapi_test` through `postgresql+asyncpg`.
- The test database is different from the configured application database.
- Redis uses the reserved database number `15` with no query-string override.
- Redis DB 15 is different from the configured application Redis database.

### Prepare test resources

Start PostgreSQL and Redis, create the dedicated database, and copy the test template:

```bash
docker compose up -d postgres redis
cp .env.test.example .env.test
docker compose exec postgres sh -c 'createdb -U "$POSTGRES_USER" fastapi_test'
```

`createdb` reports an error if the database already exists; no additional action is required in that case. If you changed credentials in `.env`, update `.env.test` to match.

### Run tests on the host

With the project dependencies installed in a local Python environment:

```bash
pytest
```

The example test URLs use `localhost`, so they are suitable for host execution. Pytest was not available on the host used for the latest repository inspection; that is an environment state, not a project requirement.

### Run tests in Docker

The development image includes the dependencies from `requirements.txt`. Use Compose service names instead of `localhost` from inside the container:

```bash
docker compose run --rm \
  -e TEST_DATABASE_URL='postgresql+asyncpg://admin:nimda@postgres:5432/fastapi_test' \
  -e TEST_REDIS_URL='redis://:changeme@redis:6379/15' \
  app pytest
```

The credentials above match `.env.example`. Change both URLs if you customized the PostgreSQL or Redis credentials.

## Architecture

The codebase uses a pragmatic layered structure with FastAPI dependency injection. Routers depend on services and repositories supplied by `src/api/deps.py`; SQLModel models and Pydantic schemas represent persistence and API data respectively.

```text
src/
├── api/
│   ├── deps.py              # Dependency providers and authorization helpers
│   └── v1/                  # Versioned routers and HTTP endpoints
├── core/                    # Settings, database, Redis, security, and telemetry
├── middlewares/             # Error handling and response behavior
├── models/                  # SQLModel persistence models
├── repositories/            # Database access
├── schemas/                 # Request and response models
├── services/                # Application logic, audit, auth, and storage
└── main.py                  # FastAPI application and lifecycle
```

A typical request follows this path:

```text
HTTP request -> router -> injected service -> repository -> PostgreSQL
                         -> Redis / storage when required
```

This separation improves navigation and testability, but it is not strict Clean Architecture and the repository does not claim complete SOLID compliance. Infrastructure and framework concerns still cross some layer boundaries, which is acceptable for the lab's current stage and remains open to refinement.

## Compose topology

`compose.yml` is the unified entry point. It includes four files:

| File | Services |
|---|---|
| `compose.app.yml` | FastAPI application, configured with four development replicas |
| `compose.required.yml` | Nginx, PostgreSQL, Redis, MinIO, and bucket initialization |
| `compose.optional.yml` | DbGate |
| `compose.monitoring.yml` | Grafana stack, exporters, Alertmanager, and SonarQube |

Because all four files are currently included without Compose profiles, an unrestricted `docker compose up` attempts to start every service. Prefer explicit service lists unless you intentionally want the larger lab environment.

The four application replicas and Nginx upstream are useful for local scaling experiments. They do not establish high availability, production/staging parity, or production readiness. Compose files and optional component configuration may temporarily drift as the lab evolves.

### Optional database UI

```bash
docker compose up -d dbgate
```

DbGate is then available at <http://localhost:18581>.

### Observability lab

The application can emit logs, metrics, and traces over OTLP when `OTEL_ENABLED=True`. The local observability stack is optional and includes Alloy, Prometheus, Grafana, Loki, Tempo, Alertmanager, service exporters, and Tempo Vulture.

Start it after the core services:

```bash
docker compose up -d \
  alloy prometheus grafana loki tempo alertmanager \
  nginx_exporter redis_exporter vulture
```

| Component | Local URL | Purpose |
|---|---|---|
| Grafana | <http://localhost:3000> | Dashboards and data exploration |
| Prometheus | <http://localhost:9090> | Metrics storage and queries |
| Alertmanager | <http://localhost:9093> | Alert routing experiments |
| Alloy | <http://localhost:12345> | Telemetry collection and processing |
| Loki | <http://localhost:3100> | Log backend |
| Tempo | <http://localhost:3200> | Trace backend |

Enable telemetry in `.env` only when the collector is running. The stack is a local learning environment, not a validated production observability deployment.

SonarQube and its dedicated PostgreSQL database are defined separately because they require more resources:

```bash
docker compose up -d sonarqube-db sonarqube
```

SonarQube is exposed at <http://localhost:9100>.

## Load testing with k6

The scripts in `tests/performance/` exercise the public movie read endpoints. Start the core stack first, then run a scenario from an ephemeral k6 container on the Compose network:

```bash
docker run --rm -i \
  --network fastapi_net \
  -v "$(pwd)/tests/performance:/tests:ro" \
  grafana/k6:1.7.1 run \
  -e BASE_URL=http://nginx:80 \
  /tests/get_movies.js
```

Run every scenario sequentially:

```bash
for file in tests/performance/*.js; do
  docker run --rm -i \
    --network fastapi_net \
    -v "$(pwd)/tests/performance:/tests:ro" \
    grafana/k6:1.7.1 run \
    -e BASE_URL=http://nginx:80 \
    "/tests/$(basename "$file")"
done
```

| Script | Endpoint |
|---|---|
| `get_categories.js` | `GET /api/v1/movies/categories` |
| `get_movies.js` | `GET /api/v1/movies/` |
| `get_movie_by_id.js` | `GET /api/v1/movies/{id}` |
| `get_movies_by_category.js` | `GET /api/v1/movies/category/?category=...` |

Each scenario ramps to 20 virtual users and checks a `p95 < 500 ms` request-duration threshold with an error rate below 1%. These are lab assertions, not a production capacity claim.

## Current limitations and roadmap

- **Baseline CI:** make pull-request checks reliable and provide isolated PostgreSQL and Redis services before treating CI as a merge gate.
- **API hardening:** continue strengthening secrets, token semantics, endpoint behavior, and automated coverage.
- **Operational alignment:** reconcile Compose, container runtime, monitoring configuration, and deployment artifacts.
- **Frontend:** build a client only after the API contract and backend baseline are stable.
- **AWS:** evaluate and implement cloud infrastructure after local operational behavior is understood; AWS deployment is not available today.

The repository also contains Kubernetes and CI artifacts under active exploration. Their presence does not imply a supported deployment target.

## Contributing

Issues, focused pull requests, and technical feedback are welcome. Please keep changes small, explain the learning or operational outcome, include tests when behavior changes, and avoid presenting experimental paths as production guarantees.

## License

This project is licensed under the [GNU General Public License v3.0](./LICENSE).
