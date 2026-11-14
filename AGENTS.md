# Repository instructions

- Keep this application deployable on one Ubuntu home server with modest CPU and 16 GB RAM.
- Prefer Docker Compose over Kubernetes or additional infrastructure.
- Default to one background worker; avoid parallel video workloads unless explicitly configured.
- Do not add scraping, DRM circumvention, cookie extraction, or unauthorized video download functionality.
- Every media asset must reference a rights grant. Publishing requires active creator-footage permission, commercial-use permission, and approved game-content clearance.
- Never store secrets in source control. Use environment variables or a secret manager.
- Do not expose PostgreSQL or Redis ports on the host.
- Keep the API bound to loopback until private Tailscale access is deliberately configured.
- Add migrations for schema changes; never instruct users to delete the PostgreSQL data directory to apply schema updates.
- Add health checks and bounded resource usage for new services.
