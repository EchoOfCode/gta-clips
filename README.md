# GTA VI Clip Engine — home-server starter

A single-node, Docker Compose foundation for a permission-first gaming media workflow. This starter intentionally provides infrastructure, health checks, a background-job smoke test, and an initial rights-aware database schema. It does **not** scrape streams, download third-party videos, or publish automatically.

## Target host

Designed for Ubuntu Server 24.04 LTS on a modest CPU-only home server. The API is bound to `127.0.0.1` only. PostgreSQL and Redis are not published to the host network.

## 1. Preflight the server

Run this on the Ubuntu home server:

```bash
bash scripts/host-preflight.sh
```

Confirm `/mnt/data` is actually mounted on the 1 TB HDD before creating media directories. Do not proceed if it points to the root filesystem unexpectedly.

## 2. Prepare storage

After confirming the mount:

```bash
sudo mkdir -p /mnt/data/gta-clip-engine/{incoming,processing,rendered,thumbnails,archive,logs,backups}
sudo chown -R 10001:10001 /mnt/data/gta-clip-engine
mkdir -p state/postgres
```

## 3. Configure secrets

```bash
cp .env.example .env
nano .env
chmod 600 .env
```

Replace `POSTGRES_PASSWORD` with a long, unique random value. Do not commit `.env`, OAuth credentials, or API tokens to Git.

## 4. Start the services

Docker Engine and the Compose plugin must already be installed.

```bash
docker compose config
docker compose up -d --build
docker compose ps
```

Check the API:

```bash
curl http://127.0.0.1:8090/health
curl http://127.0.0.1:8090/ready
```

Test the background queue:

```bash
curl -X POST http://127.0.0.1:8090/jobs/smoke-test
```

Copy the returned `job_id` and check it:

```bash
curl http://127.0.0.1:8090/jobs/JOB_ID_HERE
```

Worker logs:

```bash
docker compose logs -f worker
```

## 5. Remote access

For a temporary SSH tunnel from your laptop:

```bash
ssh -L 8090:127.0.0.1:8090 YOUR_SERVER_USER@YOUR_SERVER_TAILSCALE_IP
```

Then open `http://127.0.0.1:8090/health` on the laptop. We will configure Tailscale Serve for a more convenient private dashboard later. Do not expose the API, database, or Redis directly to the public internet.

## 6. Backups

```bash
./scripts/backup-db.sh
```

The backup is written to the HDD backup directory. A separate scheduled backup and restore test will be configured after the first successful deployment.

## Useful commands

```bash
docker compose ps
docker compose logs -f api
docker compose logs -f worker
docker compose restart api worker
docker compose down
```

`docker compose down` preserves named volumes and bind-mounted database data. Do not use `docker compose down -v` unless you deliberately intend to delete the Redis volume.

## Important database note

Files under `database/init/` are executed only when PostgreSQL initializes an empty data directory. If the database has already been initialized, later schema changes must use migrations. Never delete `state/postgres` to apply a schema change.

## Current scope

- FastAPI service and liveness/readiness endpoints.
- PostgreSQL schema for creators, channels, rights grants, media assets, candidate moments, clips, and publishing jobs.
- A database trigger that blocks publishing states unless creator footage permission, commercial use, game-content clearance, and grant validity all pass.
- Redis-backed RQ worker and a smoke-test job.
- FFmpeg installed inside the backend/worker image.
- Local disk storage mounted from the HDD.

Not yet implemented: platform discovery connectors, OAuth flows, creator upload portal, transcription, visual moment scoring, editing presets, review dashboard, YouTube publishing, or analytics ingestion.
