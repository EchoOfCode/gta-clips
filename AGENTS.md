# Repository instructions & Architectural Invariants

## Target Host Environment
- **Host**: Ubuntu Server 26.04.1 LTS, x86_64, 4 logical CPUs, 14 GiB RAM, 4 GiB swap.
- **Neighboring Services**: Unrelated host containers (`outreach-engine` on `127.0.0.1:8000`, `Beszel` on `0.0.0.0:8090`, `Immich` on `0.0.0.0:2283`, `cape-mongodb`, and Beszel agent) must **never** be stopped, renamed, deleted, recreated, modified, or interfered with.
- **Architecture**: Single-node Docker Compose foundation (no Kubernetes, no cloud processing, no GPU assumption).

## Networking & Port Safety
- **GTA API Host Port**: Bound strictly to `127.0.0.1:18090` (container port 8000). Avoid host port 8090 (used by Beszel) and 8000 (used by outreach-engine).
- **Internal Loopback**: Never expose the database, Redis, or internal microservices to `0.0.0.0` or local LAN interfaces.
- **Remote Access**: Managed via host-level Tailscale Serve with MagicDNS HTTPS certificates.

## Storage Invariants
- **SSD**: Application source code, Docker configs, PostgreSQL data (`state/postgres`), and Redis persistence (`redis_data`).
- **HDD (`/mnt/data`)**: Media storage mounted at `/mnt/data/gta-clip-engine` with subdirectories `incoming`, `processing`, `rendered`, `thumbnails`, `archive`, `logs`, and `backups`.
- **Mount Verification**: Always verify `/mnt/data` is the actual mounted HDD before writing.
- **Permissions**: Never recursively chown the entire `/mnt/data`. Grant permissions only to `/mnt/data/gta-clip-engine` for container UID/GID `10001:10001`.

## Resource Budgets & Workers
- **Single Worker**: Maximum of one RQ background worker initially to protect host CPU and RAM.
- **Resource Limits**: Every container must specify bounded CPU and memory limits:
  - PostgreSQL: 0.50 CPU, 768 MB RAM
  - Redis: 0.20 CPU, 256 MB RAM
  - API: 0.50 CPU, 512 MB RAM
  - Worker: 1.00 CPU, 2048 MB RAM
- **Log Rotation**: Bounded logging (`max-size: "10m"`, `max-file: "3"`).

## Database & Data Preservation
- **Never Reset Database**: Never delete `state/postgres`, drop production tables, or reset the database.
- **Alembic Migrations**: All schema updates must be managed via Alembic migrations.
- **Baseline Adoption**: Use safe baseline stamping (`0001_baseline`) when adopting existing database state, followed by `0002_discovery` upgrades.

## Tailscale Serve Invariants
- **Host Managed**: Tailscale is managed on the host OS, not inside Docker containers.
- **Never Run Destructive Commands**: Never execute `tailscale serve reset`, `tailscale down`, or modify host ACLs.
- **No Funnel**: Never enable Tailscale Funnel. All access must remain private to the tailnet.
- **Preserve Existing Mappings**: Always inspect `tailscale serve status` before modifying. Refuse to overwrite unrelated active serve configurations.
- **Application Authorization**: Tailnet membership is transport encryption only. All write and administrative operations require explicit application authentication (`INTERNAL_API_KEY`).

## Legal & Rights Foundation
- **No Scraping or Bypass**: Use official APIs only (YouTube Data API v3, Twitch Helix). Never scrape, extract cookies, circumvent DRM, or download unauthorized content.
- **Public Streams != Rights**: A discovered public stream or video is metadata only and does not grant permission to reuse footage.
- **Publishing Gate**: Every publishing job is subject to database trigger `trg_enforce_publish_rights_gate` and application-level rights verification. Content must be covered by an active, unexpired, unrevoked grant with creator footage permission, commercial rights, and Rockstar game-content clearance.
