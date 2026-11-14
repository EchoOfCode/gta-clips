# Architecture decisions

## Single-server design

The home server is the only application host. Docker Compose runs PostgreSQL, Redis, FastAPI, and one RQ worker. The initial design uses one worker to protect the CPU and avoid competing with existing home-server services.

## Storage placement

- SSD: source code, Docker configuration, PostgreSQL data, Redis persistence.
- HDD: authorized media, rendered clips, thumbnails, logs, and database backups.

Verify the HDD mount before starting containers. The Compose file bind-mounts `MEDIA_ROOT` into the API and worker containers.

## Security

- API published on host loopback only (`127.0.0.1`).
- No host ports published for PostgreSQL or Redis.
- Remote access via SSH tunnel initially; Tailscale Serve can be configured later.
- `.env` is not committed.
- Media directories are writable by a dedicated non-root container UID/GID (10001 by default).
- No media is accepted for processing unless a verified rights record exists.
- The database trigger is a second line of defence, not a substitute for application-level authorization and legal review.

## CPU budget

- One media-processing worker initially.
- No continuous full-stream decoding.
- Discovery uses platform metadata APIs.
- Analyze only creator-authorized assets.
- Add CPU transcription and visual analysis after the infrastructure is stable.
