# Fast local development (Docker hot reload)

The default `docker-compose.yml` is the production-style setup. For daily coding, use `docker-compose.dev.yml` **in addition** to the default file.

## Initial setup / switching from production-style containers

Keep your existing `.env` file. From the HRMS repository root:

```bash
git pull --ff-only origin feature/hrms-mvp
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build -d
```

The first dev-mode start installs dependencies in a separate frontend development image. After that, **do not use `--build` for normal source changes**.

Open http://localhost:3000 for Next.js and http://localhost:8000/docs for FastAPI.

## Daily workflow

Start (no rebuild):

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

Edit or pull changes to `frontend/app/*.tsx`, `frontend/app/*.css` or `backend/app/*.py`. Next.js Fast Refresh and Uvicorn reload will pick them up automatically. Refresh the browser if needed.

Follow live logs:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f web api
```

Stop without deleting database or uploads:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml down
```

### When to rebuild

If `frontend/package.json`, `frontend/Dockerfile.dev`, `backend/requirements.txt`, or Dockerfiles change:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build -d
```

Use the base command `docker compose up --build -d` **only** when testing the production-style build. Do not alternate between prod and dev commands without knowing which containers you are starting.

### Troubleshooting

- If a frontend dependency cannot be found after package changes: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm web npm install`, then restart the web service.
- PostgreSQL data stays in the existing `pgdata` named volume; employee uploads stay in `hrms_uploads`.
- Never run `docker compose down -v` during normal development: `-v` removes named volumes, including your database.
- Do not commit `.env` or real employee documents.

This configuration is for **local development only**. It enables code watching, verbose dev servers, and source bind mounts; do not use it for hosted production.
