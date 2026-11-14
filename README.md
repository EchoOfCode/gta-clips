# GTA VI Clip Engine — Production Home-Server Engine

A reliable, permission-first media workflow engine engineered to run on a single Ubuntu Server 26.04.1 LTS home server. It provides official YouTube Data API and Twitch Helix metadata discovery, background task execution with Redis/RQ, strict creator and commercial rights validation, safe Alembic database migrations, and production-grade private remote access via host-managed Tailscale Serve.

---

## Host Architecture & Coexistence Invariants

The application runs on a shared home server alongside existing services (`outreach-engine` on `127.0.0.1:8000`, `Beszel` on `0.0.0.0:8090`, `Immich` on `0.0.0.0:2283`, `cape-mongodb`, and the Beszel agent).

| Component | Target Budget | Placement | Host Network Exposure |
| :--- | :--- | :--- | :--- |
| **FastAPI Backend (`api`)** | 0.5 CPU / 512 MB RAM | SSD | `127.0.0.1:18090` (Container port 8000) |
| **PostgreSQL 17 (`db`)** | 0.5 CPU / 768 MB RAM | SSD (`./state/postgres`) | **None** (Internal bridge network only) |
| **Redis 7 (`redis`)** | 0.2 CPU / 256 MB RAM | SSD (`redis_data` volume) | **None** (Internal bridge network only) |
| **RQ Worker (`worker`)** | 1.0 CPU / 2048 MB RAM | SSD | **None** (1 worker maximum initially) |
| **Media Storage** | Up to 867 GB free | HDD (`/mnt/data/gta-clip-engine`) | Bind-mounted into API and worker containers |

### Core Safety Rules
1. **No Port Collisions**: The starter defaulted to host port 8090, which collided with Beszel listening on `0.0.0.0:8090`. The GTA API is bound strictly to `127.0.0.1:18090`.
2. **Loopback Isolation**: Never publish API, PostgreSQL, or Redis ports to `0.0.0.0` or local LAN interfaces.
3. **Storage Partitioning**: Database persistence and container runtimes live on SSD. Heavy media assets, logs, and database backups live on the mounted HDD at `/mnt/data/gta-clip-engine`.
4. **Data Preservation**: Never delete `state/postgres`, drop tables, or re-initialize an existing database. All database evolutions use Alembic with baseline adoption.
5. **Rights Gate**: Discovered public streams are **metadata only**. No third-party footage may be ingested or published without active, verified creator permissions, commercial rights, and game-content clearance.

---

## 1. Preflight the Host Server

Run the preflight check on your Ubuntu server to verify hardware, mount points, and open ports:

```bash
bash scripts/host-preflight.sh
```

Ensure `/mnt/data` is mounted to the physical HDD (`/dev/sdX` or UUID), and confirm port 18090 is available on `127.0.0.1`.

---

## 2. Prepare Storage Layout

Confirm the HDD mount, create project subdirectories, and set ownership for the container non-root UID/GID (`10001:10001`):

```bash
# Create dedicated media subdirectories on HDD (never chown entire /mnt/data)
sudo mkdir -p /mnt/data/gta-clip-engine/{incoming,processing,rendered,thumbnails,archive,logs,backups}
sudo chown -R 10001:10001 /mnt/data/gta-clip-engine
sudo chmod -R 770 /mnt/data/gta-clip-engine

# Create database state directory on SSD (if not already present)
mkdir -p state/postgres
```

---

## 3. Configure Secrets (`.env`)

Copy the template and configure your secrets:

```bash
cp .env.example .env
nano .env
chmod 600 .env
```

### Environment Variable Reference

| Variable | Description | Example / Default |
| :--- | :--- | :--- |
| `POSTGRES_DB` | Database name | `gta_clip_engine` |
| `POSTGRES_USER` | Database username | `gta_clip` |
| `POSTGRES_PASSWORD` | Database user password | *(Long random password)* |
| `API_PORT` | Host loopback binding port | `18090` |
| `INTERNAL_API_KEY` | Admin API key for write operations | *(Long random string)* |
| `YOUTUBE_API_KEY` | Google Cloud API key for YouTube Data API v3 | `AIzaSy...` (Optional) |
| `TWITCH_CLIENT_ID` | Twitch Developer Application Client ID | `gp762...` (Optional) |
| `TWITCH_CLIENT_SECRET` | Twitch Developer Application Client Secret | `k9z21...` (Optional) |
| `MEDIA_ROOT` | Host storage path for media assets | `/mnt/data/gta-clip-engine` |
| `TZ` | Server timezone | `Asia/Kolkata` |

### Setting Up Official Provider APIs

#### Google Cloud YouTube Data API v3
1. Navigate to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create or select a project (e.g., `gta-clip-engine`).
3. Enable the **YouTube Data API v3** in *APIs & Services > Library*.
4. Go to *APIs & Services > Credentials* and click **Create Credentials > API Key**.
5. Restrict the key's API scope to **YouTube Data API v3** only.
6. Set `YOUTUBE_API_KEY=your_key_here` in `.env`.

#### Twitch Developer Console Helix API
1. Navigate to the [Twitch Developer Console](https://dev.twitch.tv/console).
2. Register an Application:
   - **Name**: `GTA VI Clip Engine Discovery`
   - **OAuth Redirect URLs**: `http://localhost` (or leave default)
   - **Category**: *Website Integration* or *Analytics Tool*
3. Click **Manage** to view your **Client ID**.
4. Click **New Secret** to generate a **Client Secret**.
5. Set `TWITCH_CLIENT_ID` and `TWITCH_CLIENT_SECRET` in `.env`.
   *(The engine automatically manages the OAuth2 Client Credentials flow, token caching, and automatic token refresh)*.

---

## 4. Deploy Docker Compose Services

Validate and start the service stack:

```bash
# Validate Compose configuration syntax and resource limits
docker compose config

# Build and start services in background
docker compose up -d --build

# Verify container health and status
docker compose ps
```

Verify local loopback health:

```bash
# Test API liveness
curl http://127.0.0.1:18090/health

# Test dependency readiness (PostgreSQL + Redis)
curl http://127.0.0.1:18090/ready
```

---

## 5. Safe Database Migration & Baseline Adoption

The repository includes an Alembic migration suite that supports zero-downtime upgrades without destroying existing data.

Run the adoption script:

```bash
bash scripts/migrate-db.sh
```

### How Baseline Adoption Works
- If `state/postgres` was already initialized using `001_schema.sql`, the script detects existing tables and runs `alembic stamp 0001_baseline`. This prevents Alembic from attempting to re-create existing tables or failing.
- It then executes `alembic upgrade head`, which applies revision `0002_discovery` to create the discovery engine tables (`discovery_runs`, `discovered_videos`, `live_sessions`, indexes, and foreign keys).
- **Existing records in `creators`, `rights_grants`, `platform_channels`, and `media_assets` are completely preserved.**

---

## 6. Tailscale Serve Integration (Host-Managed)

Tailscale is installed and managed directly on the host (not inside Docker) to leverage native kernel networking, host systemd lifecycle, and automatic MagicDNS HTTPS certificates.

### 6.1 Check Tailscale & API Status
```bash
bash scripts/tailscale-status.sh
```
This inspects host Tailscale connectivity, retrieves your node's MagicDNS domain name, displays active Serve mappings, and verifies local API health.

### 6.2 Enable Tailscale Serve Safely
```bash
bash scripts/tailscale-serve-enable.sh --yes
```

#### Strict Safety Invariants:
- Verifies local API liveness on `127.0.0.1:18090` before enabling.
- Inspects existing Serve configuration before modifying anything.
- **Refuses to overwrite an existing unrelated Serve configuration** (e.g., if another service is already using port 443).
- **NEVER enables Tailscale Funnel** (your API remains private to your tailnet only, never public).
- **NEVER executes `tailscale serve reset`** (protecting other services).
- Dynamically resolves and prints the HTTPS MagicDNS URL: `https://your-server.tailnet.ts.net/`.

### 6.3 Disable Tailscale Serve Safely
```bash
bash scripts/tailscale-serve-disable.sh
```
Selectively turns off only the GTA Clip Engine endpoint (port 18090) without resetting other host services or disconnecting Tailscale.

### 6.4 Connecting from Laptops, Windows, and Mobile Devices
1. Install Tailscale on your client device (Windows, macOS, iOS, Android, Linux).
2. Sign in to the same tailnet account.
3. Open `https://<YOUR-SERVER-NAME>.<YOUR-TAILNET>.ts.net/health` or `/docs` in your browser.
4. Let's Encrypt certificates are automatically handled by the host Tailscale daemon; no self-signed certificate warnings will appear.

---

## 7. API Reference & Authentication Layer

Tailnet membership provides encrypted network transport, but **write and administrative operations require explicit application-level authentication**.

Pass your `INTERNAL_API_KEY` via either:
- Header: `X-API-Key: YOUR_INTERNAL_KEY`
- Header: `Authorization: Bearer YOUR_INTERNAL_KEY`

### Endpoint Catalog

| Method | Endpoint | Access Level | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/health` | Public / Tailnet | Liveness probe (200 OK) |
| `GET` | `/ready` | Public / Tailnet | Readiness probe checking database & Redis |
| `GET` | `/discovery/status` | Public / Tailnet | Inspect configured discovery providers & availability |
| `GET` | `/discovery/videos` | Public / Tailnet | Paginated listing of discovered videos (`platform`, `is_live`, `page`, `page_size`) |
| `GET` | `/discovery/streams` | Public / Tailnet | Paginated listing of active live streams (`platform`, `is_active`, `page`, `page_size`) |
| `GET` | `/discovery/channels`| Public / Tailnet | Paginated listing of tracked creator channels |
| `GET` | `/discovery/runs` | Public / Tailnet | Paginated history of discovery runs and metrics |
| `GET` | `/rights/verify-clip/{id}` | Public / Tailnet | Verify creator permissions, commercial rights, and game clearance for a clip |
| `POST`| `/discovery/run` | **Authenticated (`X-API-Key`)** | Trigger a manual discovery run (`youtube` or `twitch`) |
| `POST`| `/jobs/smoke-test` | **Authenticated (`X-API-Key`)** | Enqueue a verification job to the background RQ worker |
| `GET` | `/jobs/{job_id}` | Public / Tailnet | Check status and result of a background job |

### Example API Commands

```bash
# 1. Inspect discovery adapter status
curl -s http://127.0.0.1:18090/discovery/status

# 2. Trigger YouTube GTA VI discovery (Authenticated)
curl -X POST http://127.0.0.1:18090/discovery/run \
  -H "X-API-Key: YOUR_INTERNAL_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"provider": "youtube", "query": "Grand Theft Auto VI", "max_results": 20}'

# 3. Trigger Twitch Live Streams discovery (Authenticated)
curl -X POST http://127.0.0.1:18090/discovery/run \
  -H "X-API-Key: YOUR_INTERNAL_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"provider": "twitch", "query": "Grand Theft Auto VI", "is_live_only": true}'

# 4. List discovered videos (Paginated)
curl -s "http://127.0.0.1:18090/discovery/videos?platform=youtube&page=1&page_size=10"

# 5. List active live streams
curl -s "http://127.0.0.1:18090/discovery/streams?is_active=true"
```

---

## 8. Rights Clearance Model (Phase C)

The application enforces a strict legal clearance gate for all content.

### Database Trigger: `trg_enforce_publish_rights_gate`
Before any row in `publishing_jobs` can transition to `approved`, `scheduled`, `uploading`, or `published`, PostgreSQL executes `enforce_publish_rights_gate()`:
1. Validates that an active `rights_grants` record exists for the clip's parent `media_assets` and `creators`.
2. Validates `creator_footage_allowed = TRUE`.
3. Validates `commercial_use_allowed = TRUE`.
4. Validates `game_content_clearance = 'approved'`.
5. Validates `revoked_at IS NULL`.
6. Validates `expires_at IS NULL OR expires_at > NOW()`.

### Application Validation Layer
The application layer (`app.rights.verify_clip_for_publishing`) performs identical checks before database operations and returns structured explanations if a clip is blocked.

---

## 9. Backups and Restore Testing

### Creating a Verified Backup
```bash
./scripts/backup-db.sh
```
Writes a custom-format dump (`.dump`) to `/mnt/data/gta-clip-engine/backups/`, sets `chmod 600`, and verifies dump integrity.

### Testing Restore in an Isolated Database
```bash
./scripts/restore-db.sh /mnt/data/gta-clip-engine/backups/postgres-YYYYMMDD-HHMMSS.dump
```
Safely restores into a temporary database (`gta_restore_test`), verifies table counts and creator records, and prompts for cleanup. Production data is never touched during restore testing.

---

## 10. Operational Troubleshooting

| Symptom | Diagnosis | Solution |
| :--- | :--- | :--- |
| **API container stops immediately** | Port collision on host port 8090 | Verify `docker-compose.yml` uses `127.0.0.1:${API_PORT:-18090}:8000`. Check `ss -tuln \| grep 18090`. |
| **Readiness probe (`/ready`) returns 503** | PostgreSQL or Redis not healthy | Run `docker compose ps` to inspect container health checks. Check `docker compose logs db redis`. |
| **Tailscale Serve enable fails with exit code 5** | Unrelated service already bound on port 443 | Inspect mappings with `tailscale serve status`. Do not force overwrite. |
| **`/discovery/run` returns 401 Unauthorized** | Missing or incorrect `X-API-Key` | Verify `INTERNAL_API_KEY` in `.env` matches the request header. |
| **YouTube returns `quotaExceeded`** | Daily YouTube Data API limit reached | Check Google Cloud Console quota dashboard. YouTube search calls consume 100 units each. |
| **Twitch returns 401 Unauthorized** | Expired client secret | Verify `TWITCH_CLIENT_ID` and `TWITCH_CLIENT_SECRET` in `.env`. The provider automatically re-authenticates on next run. |

---

## Useful Day-to-Day Commands

```bash
# View real-time container logs
docker compose logs -f api worker

# Restart API and worker containers cleanly
docker compose restart api worker

# Check Tailscale status and endpoints
bash scripts/tailscale-status.sh

# Run full automated test suite
python -m pytest backend/tests -v
```
