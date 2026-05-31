# Deployment Guide

This guide walks through deploying ClassiRoute to production. It covers three hosting options:

- **Render** for the Python/FastAPI backend
- **Vercel** for the React/TypeScript frontend
- **Neon** (or any PostgreSQL 16+) for the database

Plus a self-hosted Docker option if you prefer to run everything yourself.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Before You Start](#2-before-you-start)
3. [Database Setup (Neon)](#3-database-setup-neon)
4. [Environment Configuration](#4-environment-configuration)
5. [Backend Deployment (Render)](#5-backend-deployment-render)
6. [Frontend Deployment (Vercel)](#6-frontend-deployment-vercel)
7. [Docker Deployment (Self-Hosted)](#7-docker-deployment-self-hosted)
8. [Post-Deployment Verification](#8-post-deployment-verification)
9. [Monitoring Setup](#9-monitoring-setup)
10. [Updating](#10-updating)
11. [Troubleshooting](#11-troubleshooting)

---

## 1. Architecture Overview

```
┌──────────────────────────────────────────────────────┐
│                     Vercel                            │
│  ┌────────────────────────────────────────────────┐  │
│  │  React SPA (TypeScript / Vite)                  │  │
│  │  Build: npm run build → dist/                   │  │
│  │  Rewrites all routes to index.html (SPA)        │  │
│  └────────────────┬───────────────────────────────┘  │
└───────────────────┼──────────────────────────────────┘
                    │  HTTP API calls
                    ▼
┌──────────────────────────────────────────────────────┐
│                      Render                           │
│  ┌────────────────────────────────────────────────┐  │
│  │  FastAPI (Python 3.13)                         │  │
│  │  Port: $PORT (assigned by Render)              │  │
│  │  Health: GET /health                           │  │
│  │  Schema: Alembic auto-migrate on startup       │  │
│  └────────────────┬───────────────────────────────┘  │
└───────────────────┼──────────────────────────────────┘
                    │  SQL (asyncpg)
                    ▼
┌──────────────────────────────────────────────────────┐
│                   Neon (PostgreSQL 16)                 │
│  ┌────────────────────────────────────────────────┐  │
│  │  Serverless Postgres                           │  │
│  │  Schema: classiroute (default)                 │  │
│  └────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────┘
```

The frontend is a single-page app served by Vercel's edge network. It talks to the backend API on Render. The backend connects to a PostgreSQL 16 database (Neon recommended, but any PG 16 provider works). Alembic handles schema migrations automatically when the app starts.

---

## 2. Before You Start

### What you need

- A GitHub account (to connect Render and Vercel repos)
- A Render account ([render.com](https://render.com))
- A Vercel account ([vercel.com](https://vercel.com))
- A Neon account ([neon.tech](https://neon.tech)) or any PostgreSQL 16 host
- Your repo pushed to GitHub

### Repo structure

```
classiroute/
├── backend/              # FastAPI app (Python 3.13)
│   ├── main.py           # Entry point
│   ├── Dockerfile        # Multi-stage Docker build
│   ├── docker-entrypoint.sh
│   ├── requirements.txt
│   ├── pyproject.toml
│   └── alembic/          # Database migrations
├── frontend/             # React app (TypeScript / Vite)
│   ├── vercel.json
│   └── package.json
├── render.yaml           # Render blueprint
└── docker-compose.yml    # Self-hosted deployment
```

---

## 3. Database Setup (Neon)

Neon is the recommended PostgreSQL provider because it's serverless, has a free tier, and supports PG 16 natively.

### Step-by-step

1. **Create a Neon account**
   Go to [neon.tech](https://neon.tech) and sign up. The free tier gives you 0.5 GB storage, enough to start.

2. **Create a project**
   - Click "Create a project"
   - Name it `classiroute` (or whatever you like)
   - Select **PostgreSQL 16** (required)
   - Choose the region closest to your Render deployment

3. **Get your connection string**
   - Once the project is created, Neon shows a "Connection details" panel
   - Copy the connection string. It looks like this:
     ```
     postgresql://user:pass@ep-xxxx.us-east-2.aws.neon.tech/classiroute?sslmode=require
     ```
   - Save this for the `DATABASE_URL` environment variable

4. **Set up the schema (optional)**
   You can leave the schema as `public` (the default). If you want a custom schema, set `DB_SCHEMA` to whatever you like. The app creates tables automatically on first startup.

### Alternative: Any PostgreSQL 16 provider

If you're not using Neon, any PG 16 host works. You just need a connection string in the same format:

```
postgresql://user:password@host:5432/database_name
```

Supported providers include:
- AWS RDS for PostgreSQL
- Google Cloud SQL for PostgreSQL
- Supabase (managed Postgres)
- A VPS running PostgreSQL 16

The app uses asyncpg, so make sure your provider allows async connections.

---

## 4. Environment Configuration

ClassiRoute uses these environment variables. Required ones will crash the app if missing.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | - | Full PostgreSQL connection string. For Neon, include `?sslmode=require` |
| `DB_SCHEMA` | No | `public` | Database schema name |
| `JWT_SECRET` | Yes | - | At least 64 random characters. Generate with `openssl rand -base64 48` |
| `JWT_ALGORITHM` | No | `HS256` | JWT signing algorithm |
| `JWT_EXPIRE_DAYS` | No | `30` | How long tokens stay valid |
| `ENCRYPTION_KEY` | Yes | - | Fernet key for encrypting API credentials. Generate with the command below |
| `CORS_ORIGINS` | Yes | - | Comma-separated list of allowed origins (e.g., `https://your-app.vercel.app`) |
| `APP_ENV` | No | `development` | Set to `production` in production |
| `POSTHOG_API_KEY` | No | - | PostHog project API key (for product analytics) |
| `POSTHOST_HOST` | No | `https://app.posthog.com` | PostHog instance URL |
| `SENTRY_DSN` | No | - | Sentry DSN for error tracking |

### Generating secrets

**JWT_SECRET:**
```bash
openssl rand -base64 48
```

**ENCRYPTION_KEY:**
```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### CORS_ORIGINS format

For production, set it to your Vercel deployment domain:

```
https://classiroute.vercel.app
```

If you have a custom domain, add that too:

```
https://classiroute.vercel.app,https://classiroute.com
```

No spaces around the commas.

---

## 5. Backend Deployment (Render)

### Option A: Deploy from render.yaml (blueprint)

The repo includes a `render.yaml` that defines the web service. This is the easiest path.

1. **Connect your repo**
   - Log into [dashboard.render.com](https://dashboard.render.com)
   - Click "New +" > "Blueprint"
   - Select your GitHub repo
   - Render reads `render.yaml` and creates a "ClassiRoute API" web service

2. **Set secret environment variables**
   In the Render dashboard, navigate to your web service > "Environment" tab. You need to add values for these secrets (marked `sync: false` in render.yaml because they should not be committed):
   - `DATABASE_URL` -- your Neon connection string
   - `JWT_SECRET` -- the 64+ char secret you generated
   - `ENCRYPTION_KEY` -- the Fernet key
   - `CORS_ORIGINS` -- your frontend URL

3. **Verify the remaining env vars**
   Render auto-fills the ones with default values (JWT_ALGORITHM, JWT_EXPIRE_DAYS, DB_SCHEMA, APP_ENV), but double check that `APP_ENV` is set to `production`.

4. **Set up the health check**
   Under your web service settings, check that the health check path is `/health`. Render uses this to know when your app is ready. If the health check fails 3 times, Render restarts the service.

5. **First deploy**
   After the blueprint is created, Render starts the first deploy automatically. Watch the logs (they stream in the dashboard). The first build takes about 2-3 minutes:
   - Build phase: `pip install -r requirements.txt`
   - Start phase: `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - Health check pings `/health` once the app starts

   When you see "Your service is live", the backend is running.

### Option B: Manual web service setup

If you'd rather not use the blueprint:

1. **Create a new Web Service**
   - Click "New +" > "Web Service"
   - Connect your repo
   - Set **Root Directory** to `backend`
   - Set **Runtime** to `Python 3`
   - Set **Build Command** to `pip install -r requirements.txt`
   - Set **Start Command** to `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - Set **Health Check Path** to `/health`

2. **Add all environment variables** (required + optional) from the table in section 4.

3. **Deploy** and watch the logs.

### Render pricing notes

- The free tier spins down after 15 minutes of inactivity. The first request after idle takes a few seconds to wake up. For production, use the Starter tier ($7/month) or higher to keep it always on.
- Database connections on the free tier are limited. If you hit connection limits, upgrade your Render plan.

---

## 6. Frontend Deployment (Vercel)

The `frontend/vercel.json` is already configured for SPA routing. It rewrites all paths to `index.html` so React Router works on page reload.

### Step-by-step

1. **Import your repo**
   - Log into [vercel.com](https://vercel.com)
   - Click "Add New..." > "Project"
   - Select your GitHub repo
   - Vercel auto-detects the Vite framework

2. **Configure the project**
   - **Framework Preset**: Vite (auto-detected)
   - **Root Directory**: `frontend` (important -- the frontend code is in a subdirectory)
   - **Build Command**: `npm run build` (pulls from vercel.json)
   - **Output Directory**: `dist` (pulls from vercel.json)
   - **Install Command**: `npm ci` (clean install, pulls from vercel.json)

3. **Add environment variables (optional)**
   If your frontend needs an API URL at build time, add it under Environment Variables:
   - `VITE_API_URL` -- set to your Render backend URL, e.g., `https://classiroute-api.onrender.com`
   - Click "Deploy"

4. **First deploy**
   Vercel clones the repo, installs dependencies with `npm ci`, runs `npm run build` (which runs `tsc -b && vite build`), and deploys the `dist/` folder. The whole process takes about 1-2 minutes.

5. **Get your URL**
   Vercel assigns a `.vercel.app` domain. Yours will be something like:
   ```
   https://classiroute-xxxxx.vercel.app
   ```
   You can add a custom domain under "Domains" in the project settings.

### SPA routing

The `vercel.json` rewrites file handles SPA routing:

```json
{
  "rewrites": [
    { "source": "/(.*)", "destination": "/index.html" }
  ]
}
```

This means any route like `/dashboard` or `/settings` serves `index.html` and lets React Router handle the client-side navigation.

---

## 7. Docker Deployment (Self-Hosted)

If you prefer to run everything on your own server (VPS, dedicated machine), use the included Docker setup.

### What you get

- **PostgreSQL 16** (Alpine image) in one container
- **ClassiRoute API** (multi-stage build) in another container
- A shared network so containers can talk to each other
- A persistent volume for database data
- A persistent volume for ML model files

### Prerequisites

- Docker Engine 24+ and Docker Compose v2
- A server with at least 2 GB RAM (more if you run ML inference)

### Step-by-step

1. **Clone the repo on your server**
   ```bash
   git clone https://github.com/your-org/classiroute.git
   cd classiroute
   ```

2. **Set environment variables**
   Create a `.env` file in the project root:
   ```bash
   cat > .env << EOF
   JWT_SECRET=$(openssl rand -base64 48)
   ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
   POSTGRES_PASSWORD=choose-a-strong-password
   APP_ENV=production
   EOF
   ```

   Note: The `docker-compose.yml` reads `JWT_SECRET` and `ENCRYPTION_KEY` from the `.env` file automatically. If either is missing, Docker refuses to start (the `:?` syntax enforces this).

3. **Start the services**
   ```bash
   docker compose up -d
   ```
   This builds the backend image and starts both containers. The first build takes longer (5-10 minutes) because it compiles Python dependencies.

4. **Check that everything is running**
   ```bash
   docker compose ps
   ```
   You should see both `db` and `app` with state "Up".

5. **Verify the health check**
   ```bash
   curl http://localhost:8000/health
   ```
   Expected response:
   ```json
   {"status": "healthy"}
   ```

6. **Stop and clean up**
   ```bash
   docker compose down           # stops containers
   docker compose down -v        # stops and removes volumes (database wipe)
   ```

### Dockerfile breakdown

The Dockerfile uses a multi-stage build to keep the final image small.

**Stage 1: Builder**
- Starts from `python:3.13-slim`
- Installs `gcc`, `g++`, `build-essential` for compiling native deps (psycopg2, scikit-learn, xgboost)
- Copies `uv` from the official Astral image
- Runs `uv sync --frozen --no-dev --no-editable` to install production dependencies into a virtual environment

**Stage 2: Runtime**
- Starts from a fresh `python:3.13-slim` (no build tools)
- Installs only `curl` (for the health check)
- Copies the `.venv` from builder
- Sets `PATH` to include the virtual environment
- Copies the app code
- Exposes port 8000
- Sets `HEALTHCHECK` to ping `/health` every 30 seconds
- Uses `docker-entrypoint.sh` as the entrypoint

### docker-entrypoint.sh

This script runs before the app starts. It:

1. Parses the host and port from `DATABASE_URL`
2. Polls the database port in a Python loop until it's reachable
3. Runs `exec "$@"` to start uvicorn

The polling loop prevents the app from crashing if the database container is still starting up. It's not a replacement for a proper connection retry, but it handles the common case.

### docker-compose.yml details

| Service | Image/Port | Volumes | Healthcheck |
|---------|-----------|---------|-------------|
| `db` | postgres:16-alpine, :5432 | `pgdata` (persistent) | `pg_isready` every 5s |
| `app` | built from ./backend, :8000 | `modeldata` (ML models) | depends on db |

The `app` service has `depends_on: db: condition: service_healthy`, so Docker waits for PostgreSQL to be ready before starting the app.

---

## 8. Post-Deployment Verification

After deploying, run through these checks to confirm everything works.

### 1. Health check

```bash
# Render or Docker
curl https://classiroute-api.onrender.com/health

# Expected:
{"status": "healthy"}
```

### 2. Test a simple API call

```bash
curl https://classiroute-api.onrender.com/api/v1/status

# Expected (or similar):
{"status": "running", "version": "0.1.0"}
```

### 3. Test database connectivity

The health endpoint checks the database connection. If the database is down, the health check returns a 503 status and Render restarts the service.

### 4. Verify the database schema

Connect to your Neon database and check that tables exist:

```bash
psql "$DATABASE_URL" -c "\dt"
```

You should see tables like `users`, `conversations`, `llm_configs`, `prompts`, `routing_decisions` (or similar). If tables are missing, the Alembic auto-migrate may have failed. Run it manually:

```bash
uv run alembic upgrade head
```

### 5. Load the frontend

Open your Vercel URL in a browser. The app should load without console errors. If the frontend can't reach the backend, check:
- CORS_ORIGINS on the backend includes the frontend URL
- The frontend's API URL points to the correct Render backend
- Both services are in the "live" or "ready" state

### 6. Run the smoke test suite

If you have smoke tests in the repo:

```bash
cd backend
URL=https://classiroute-api.onrender.com pytest tests/smoke/ -v
```

---

## 9. Monitoring Setup

### PostHog (product analytics)

PostHog tracks usage, events, and user behavior. It's fully optional.

1. Create a project at [posthog.com](https://posthog.com) (or self-host)
2. Get your Project API Key from "Project Settings" > "API Keys"
3. Set the environment variables:
   - `POSTHOG_API_KEY` -- your project API key (phc_...)
   - `POSTHOG_HOST` -- defaults to `https://app.posthog.com`
4. Restart the service

When enabled, the app captures events like:
- User login/signup
- Prompt submission
- Routing decisions
- Error events

The dashboards in PostHog show you which models are used most, how the classifier performs, and where users hit errors.

### Sentry (error tracking)

Sentry captures unhandled exceptions and performance traces.

1. Create a project at [sentry.io](https://sentry.io)
2. Choose "FastAPI" as the platform
3. Copy the DSN (starts with `https://...@...ingest.sentry.io/...`)
4. Set `SENTRY_DSN` environment variable
5. Restart the service

When enabled, Sentry:
- Captures all unhandled 500 errors with stack traces
- Records slow API calls (configurable threshold)
- Shows error trends and affected users

### Render built-in monitoring

Render provides basic monitoring out of the box:
- **Metrics**: CPU, memory, network
- **Logs**: streamed in real time, searchable
- **Alerts**: configure notification thresholds (CPU > 80%, memory > 80%)
- **Cron jobs**: available if you need periodic tasks

To set up alerts:
1. Go to your web service > "Settings" > "Alert Settings"
2. Choose metric and threshold
3. Add notification channels (email, Slack)

### Docker monitoring (self-hosted)

For Docker deployments, use standard Docker tooling:

```bash
# Live logs
docker compose logs -f app

# Resource usage
docker stats

# Container health
docker compose ps
```

For production self-hosted setups, consider:
- [Prometheus](https://prometheus.io) + [Grafana](https://grafana.com) for metrics
- [Loki](https://grafana.com/oss/loki/) for log aggregation
- [Docker healthchecks](https://docs.docker.com/engine/reference/builder/#healthcheck) are already configured in the Dockerfile

---

## 10. Updating

### Backend (Render)

Render auto-deploys when you push to the connected branch. To trigger a manual deploy:

1. In the Render dashboard, go to your web service
2. Click "Manual Deploy" > "Deploy latest commit"
3. Watch the logs for build and start

If you need to change environment variables:
1. Go to "Environment" tab
2. Update the values
3. Render restarts the service automatically

### Frontend (Vercel)

Same pattern. Push to the connected branch triggers a deploy. For a manual deploy:

1. In the Vercel dashboard, go to your project
2. Click "Deployments"
3. Find the latest commit and click "..."

Alternatively, use the Vercel CLI:

```bash
vercel --prod
```

### Docker (self-hosted)

```bash
git pull origin main
docker compose down
docker compose up -d --build
```

The `--build` flag forces a fresh image build. If you only changed environment variables in `.env`, you can skip the build and just restart:

```bash
docker compose down
docker compose up -d
```

### Database migrations

When you deploy a new version that changes the database schema, Alembic runs migrations automatically on app startup. This happens before the health check passes, so there's a brief window where the app starts but isn't healthy yet.

To run migrations manually (if auto-migrate is disabled):

```bash
# Render: open a shell from the dashboard
cd backend
uv run alembic upgrade head

# Docker
docker compose exec app alembic upgrade head
```

If a migration fails:
1. Check the logs for the specific error
2. Roll back with `alembic downgrade -1`
3. Fix the migration file
4. Run `alembic upgrade head` again

---

## 11. Troubleshooting

### Backend won't start on Render

**"No module named 'main'"**
Make sure the root directory is set to `backend` in your Render service. The `main.py` file lives there.

**Health check failing**
- Check the logs for traceback
- Verify `DATABASE_URL` is correct (Neon connections need `?sslmode=require`)
- Make sure the database server is accepting connections
- If the database is fine, check that `uvicorn` starts without errors

**"Address already in use"**
Render sets `$PORT` automatically. Don't hardcode port 8000 in the start command. The render.yaml uses `$PORT` correctly.

### Frontend shows blank page on Vercel

**Check the build output**
Go to the deployment page in Vercel and look at the build logs. If `tsc -b` fails with type errors, the build fails. Fix the errors and push again.

**API calls fail**
Open the browser's developer console (F12). Look for CORS errors. If you see them:
- Verify `CORS_ORIGINS` on the backend includes your Vercel domain exactly
- Restart the backend service
- Refresh the frontend

**SPA routes 404 on reload**
Make sure `vercel.json` has the rewrites configured. If you deployed without it, any route other than `/` returns a 404. Vercel reads `vercel.json` automatically -- just commit the file and redeploy.

### Docker containers crash

**App container exits immediately**
- Check logs: `docker compose logs app`
- Common cause: missing `JWT_SECRET` or `ENCRYPTION_KEY` in `.env`
- Another cause: database not reachable. The entrypoint waits for the port, but if the credentials are wrong, the app crashes after connecting.

**Database container fails**
- Check logs: `docker compose logs db`
- If the data volume is corrupted, stop everything and remove the volume: `docker compose down -v`
- Warning: this wipes all data. Make sure you have backups.

### Performance issues

**First request is slow on Render free tier**
Render free tier spins down after inactivity. The first request takes 5-10 seconds to wake up. Upgrade to a paid plan for always-on service.

**ML model loading is slow**
The routing classifier models load into memory on first request. Subsequent requests are faster. If you restart the service, the first request again loads the model. Consider:
- Increasing the Render instance RAM (at least 2 GB)
- Using a smaller model for faster loading

### Getting help

- Check existing docs in the `docs/` directory
- Open a GitHub issue in the repo
- Check Render's status page: [status.render.com](https://status.render.com)
- Check Vercel's status page: [vercel-status.com](https://vercel-status.com)

---

## Appendix: Quick Reference

### Secret generation commands

```bash
# JWT secret (64+ chars)
openssl rand -base64 48

# Fernet encryption key
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Render.yaml (for reference)

```yaml
services:
  - type: web
    name: classiroute-api
    env: python
    rootDir: backend
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn main:app --host 0.0.0.0 --port $PORT
    healthCheckPath: /health
    envVars:
      - key: DATABASE_URL
        sync: false
      - key: JWT_SECRET
        sync: false
      - key: ENCRYPTION_KEY
        sync: false
      - key: CORS_ORIGINS
        sync: false
      # ... defaults omitted for brevity
```

### Vercel.json (for reference)

```json
{
  "framework": "vite",
  "buildCommand": "npm run build",
  "outputDirectory": "dist",
  "installCommand": "npm ci",
  "rewrites": [
    { "source": "/(.*)", "destination": "/index.html" }
  ]
}
```

### docker-compose.yml (for reference)

```yaml
services:
  db:
    image: postgres:16-alpine
    restart: unless-stopped
    volumes:
      - pgdata:/var/lib/postgresql/data
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-classiroute}
      POSTGRES_DB: classiroute
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d classiroute"]
      interval: 5s
      timeout: 5s
      retries: 5

  app:
    build: ./backend
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql://postgres:${POSTGRES_PASSWORD:-classiroute}@db:5432/classiroute
      JWT_SECRET: ${JWT_SECRET:?JWT_SECRET is required}
      JWT_ALGORITHM: HS256
      JWT_EXPIRE_DAYS: 30
      ENCRYPTION_KEY: ${ENCRYPTION_KEY:?ENCRYPTION_KEY is required}
      APP_ENV: ${APP_ENV:-production}
    depends_on:
      db:
        condition: service_healthy
    volumes:
      - modeldata:/app/models

volumes:
  pgdata:
  modeldata:
```
