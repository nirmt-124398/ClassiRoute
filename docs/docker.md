# Docker — ClassiRoute

## Files

| File | Purpose |
|---|---|
| `Dockerfile` | Multi-stage build: builder compiles deps with `uv`, runtime ships only what's needed. Exposes `:8000`. Healthcheck on `/health`. |
| `docker-compose.yml` | Orchestrates `app` + `db` (PostgreSQL 16-alpine). Volumes for PG data & models. Env vars via `${VAR:?}` (fail if missing). |
| `docker-entrypoint.sh` | Entrypoint: waits for PG port via Python socket, then `exec "$@"` (uvicorn). |
| `.env.example` | Template — copy to `.env` and fill secrets. |
| `.dockerignore` | Excludes `.venv`, `__pycache__`, `.git`, `.env`, etc. from build context. |

## Commands

### Build

```bash
docker build -t classiroute-app:latest .
```

### Run (dev — one-off)

```bash
# Start PG first
docker run -d --name classiroute-db \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=classiroute \
  -e POSTGRES_DB=classiroute \
  -p 5432:5432 \
  postgres:16-alpine

# Start app
docker run -d --name classiroute-app \
  -e DATABASE_URL=postgresql://postgres:classiroute@host.docker.internal:5432/classiroute \
  -e DB_SCHEMA=public \
  -e JWT_SECRET="<your-secret>" \
  -e JWT_ALGORITHM=HS256 \
  -e JWT_EXPIRE_DAYS=30 \
  -e ENCRYPTION_KEY="<your-fernet-key>" \
  -e APP_ENV=development \
  -p 8000:8000 \
  classiroute-app:latest
```

### Run (recommended — compose)

```bash
cp .env.example .env     # edit .env with real secrets
docker compose up        # builds + starts both containers
docker compose up -d     # detached mode
docker compose logs -f   # tail logs
docker compose down      # stop + remove containers
docker compose down -v   # + delete volumes (wipes DB)
```

### Rebuild after code changes

```bash
docker compose build     # rebuild image
docker compose up -d     # restart with new image
```

### Push to registry (cloud / public fetch)

```bash
# Tag for your registry
docker tag classiroute-app:latest ghcr.io/<org>/classiroute-app:latest
docker tag classiroute-app:latest ghcr.io/<org>/classiroute-app:v1.0.0

# Push
docker push ghcr.io/<org>/classiroute-app:latest
docker push ghcr.io/<org>/classiroute-app:v1.0.0

# On server (pull + run)
docker pull ghcr.io/<org>/classiroute-app:latest
docker compose -f docker-compose.yml up -d

# Or via docker stack / swarm
docker stack deploy -c docker-compose.yml classiroute
```

Registries: Docker Hub (`docker.io/<user>/classiroute-app`), GitHub Container Registry (`ghcr.io/<org>/classiroute-app`), AWS ECR, GCP Artifact Registry.

### Health check

```bash
curl http://localhost:8000/health
# → {"status":"ok","model_loaded":false}
```

## Required env vars

| Variable | Source |
|---|---|
| `JWT_SECRET` | Random 64+ char string |
| `ENCRYPTION_KEY` | `python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `DATABASE_URL` | Set automatically by `docker-compose.yml` (points to `db` service) |

## Notes

- `model_loaded: false` in health response is expected unless a trained XGBoost model is mounted at `/app/models/`. Not required for API operation.
- Entrypoint uses Python for DB wait — no `nc` / `netcat` dependency.
- HEALTHCHECK uses `docker` format (suppressed as warning on podman/OCI — works on real Docker).
- The `uv.lock` file must be kept in sync with `pyproject.toml` for reproducible builds.
