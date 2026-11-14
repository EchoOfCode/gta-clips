# ADR 0001: Provider-Adapter Discovery Engine, Storage Topology, Alembic Baseline Adoption, and Host-Managed Tailscale Serve

- **Status**: Accepted
- **Date**: 2026-11-15
- **Author**: Principal Backend Engineer & Infrastructure Architect

---

## Context

The GTA VI Clip Engine starter repository is being evolved into a production-grade backend running on a dedicated home server (Ubuntu Server 26.04.1 LTS, 4 logical CPUs, 14 GiB RAM, 4 GiB swap).

### Environmental Constraints & Pre-Existing Workloads
1. **Host Services**: The home server already hosts unrelated Docker workloads:
   - `outreach-engine` on `127.0.0.1:8000`
   - `Beszel` on `0.0.0.0:8090`
   - `Immich` on `0.0.0.0:2283`
   - `cape-mongodb` and `Beszel agent`
2. **Port Collision**: The starter repository configured its API host binding to `127.0.0.1:${API_PORT:-8090}:8000`. Because Beszel listens on `0.0.0.0:8090`, Docker's port mapping failed with `bind: address already in use`, causing the API container to stop or fail to start while `db`, `redis`, and `worker` (which have no host port exposure) continued running.
3. **Storage Partitioning**: The host has two physical drives:
   - 238.5 GB SSD (~151 GB free)
   - 931.5 GB HDD mounted at `/mnt/data` (~867 GB free)
4. **Data Preservation**: Existing database records and state in `state/postgres` must never be dropped, reset, or lost. The starter relied solely on `database/init/001_schema.sql` (which only executes when the PostgreSQL data directory is completely empty).
5. **Platform Discovery**: The application must discover public GTA VI video and stream metadata from YouTube and Twitch using official APIs without scraping, cookie extraction, or DRM bypass, while respecting rate limits and quotas.
6. **Remote Access**: Secure, private remote access is required over Tailscale with HTTPS MagicDNS certificates without containerizing Tailscale or exposing ports to the public internet.

---

## Architectural Decisions

### 1. Host Port Binding Hardening
- **Decision**: Change the default host binding of the GTA API container to `127.0.0.1:18090` (container port 8000).
- **Rationale**: Eliminates the port collision with Beszel (8090) and outreach-engine (8000), keeps the API private on loopback, and prevents accidental exposure to the LAN.
- **Rules**: Database and Redis ports are never mapped to the host; all internal communication takes place over the isolated Docker bridge network `internal`.

### 2. Bounded Resource Budgets
- **Decision**: Enforce CPU and memory limits on every Compose service:
  - `db`: `cpus: 0.50`, `mem_limit: 768M`
  - `redis`: `cpus: 0.20`, `mem_limit: 256M`
  - `api`: `cpus: 0.50`, `mem_limit: 512M`
  - `worker`: `cpus: 1.00`, `mem_limit: 2048M` (strictly 1 worker process)
- **Rationale**: Protects co-located workloads (Immich, Beszel) from memory exhaustion or CPU starvation during batch processing.

### 3. Dual-Tier Storage Architecture
- **Decision**:
  - **SSD**: Application source code, Docker configs, PostgreSQL data (`state/postgres`), and Redis append-only persistence (`redis_data`).
  - **HDD (`/mnt/data`)**: Media storage mounted at `/mnt/data/gta-clip-engine` with subdirectories `incoming`, `processing`, `rendered`, `thumbnails`, `archive`, `logs`, and `backups`.
- **Permissions**: Ownership set to dedicated container non-root UID/GID `10001:10001` (`app:app`). Scripts verify `/mnt/data` is an active non-root mount before creating directories.

### 4. Alembic Migrations with Safe Baseline Adoption
- **Decision**: Introduce Alembic with a two-phase revision strategy:
  1. `0001_baseline`: Represents the existing 001 schema (`creators`, `platform_channels`, `rights_grants`, `media_assets`, `candidate_moments`, `edited_clips`, `publishing_jobs`, trigger).
  2. `0002_discovery`: Adds Phase B tables (`discovery_runs`, `discovered_videos`, `live_sessions`, indexes, and foreign keys).
- **Baseline Adoption Script (`scripts/migrate-db.sh`)**: If tables already exist in PostgreSQL, Alembic safely stamps revision `0001_baseline` before executing `upgrade head`. This completely prevents destructive re-creation while adopting migration tracking.

### 5. Provider-Adapter Discovery Engine
- **Decision**: Implement a typed, modular provider architecture in `app.discovery`:
  - `DiscoveryProvider`: Abstract base class enforcing `discover_videos()`, `discover_live_streams()`, `test_connection()`, and `get_status()`.
  - `YouTubeDiscoveryProvider`: Official YouTube Data API v3 adapter using `/search` and `/videos` endpoints, ISO 8601 duration parsing, quota accounting, and exponential backoff with jitter.
  - `TwitchDiscoveryProvider`: Official Twitch Helix API adapter using OAuth2 Client Credentials (`/oauth2/token`), token caching and auto-refresh, game ID resolution (`/games`), live stream discovery (`/streams`), and clip metadata (`/clips`).
  - `ProviderRegistry`: Central registry managing supported adapters and exposing status (`configured`, `not_configured`, `unsupported`, `error`) for active and future platforms (e.g., Kick).
  - `DiscoveryService`: Idempotent persistence layer performing safe upserts into PostgreSQL (`platform_channels`, `discovered_videos`, `live_sessions`) and recording execution metrics in `discovery_runs`.

### 6. Multi-Layer Rights Clearance Gate
- **Decision**: Enforce creator authorization at both application and database layers:
  - **Database Layer**: Trigger `trg_enforce_publish_rights_gate` blocks publishing status transitions (`approved`, `scheduled`, `uploading`, `published`) unless `rights_grants` is active, unexpired, unrevoked, with `creator_footage_allowed = TRUE`, `commercial_use_allowed = TRUE`, and `game_content_clearance = 'approved'`.
  - **Application Layer**: `app.rights.verify_clip_for_publishing` validates the complete chain before scheduling or dispatching, returning clear diagnostic explanations.
- **Invariant**: Discovered public streams are stored as **metadata only**. Public discovery does not equal authorization to reuse footage.

### 7. Host-Managed Tailscale Serve Integration
- **Decision**: Manage Tailscale on the host OS via shell automation (`scripts/tailscale-status.sh`, `scripts/tailscale-serve-enable.sh`, `scripts/tailscale-serve-disable.sh`) rather than embedding Tailscale inside a Docker container.
- **Strict Invariants**:
  - `tailscale serve --bg 18090` is enabled only after verifying local API health.
  - **Never run `tailscale serve reset`**, which would delete unrelated user serve mappings.
  - **Never enable Tailscale Funnel**; keep traffic strictly within the private tailnet.
  - Inspect existing serve configuration and refuse to overwrite unrelated endpoints automatically.
  - Dynamically parse MagicDNS domain from `tailscale status --json` without hardcoding tailnet domains.

### 8. Application-Level Authentication
- **Decision**: Introduce `app.auth.require_api_key` for all mutation/write endpoints (`POST /discovery/run`, `POST /jobs/smoke-test`).
- **Rationale**: Tailnet membership provides network transport encryption, but cannot be assumed as sufficient application-level authorization. Write endpoints require `INTERNAL_API_KEY` passed via `X-API-Key` or `Authorization: Bearer <token>`.

---

## Consequences

### Positive
- **Home Server Stability**: Neighboring services (`Beszel`, `outreach-engine`, `Immich`) operate completely unaffected.
- **Zero Port Conflict**: API listens cleanly on `127.0.0.1:18090`.
- **Zero Data Loss**: Database schema migrations are version-controlled with zero table resets.
- **Legal & Platform Compliance**: Only official APIs are used; rights verification is enforced prior to publishing.
- **Secure Remote Access**: Automatic HTTPS certificates over Tailscale with fine-grained endpoint authorization.

### Operational Notes & Future Milestones
- Public discovery endpoints are read-only; media asset downloading and automatic publishing remain disabled for this milestone until creator upload portal workflows are active.
- YouTube API quota is consumed conservatively (100 units per search, 1 unit per 50 video details).
