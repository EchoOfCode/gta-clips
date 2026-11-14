# Platform integration notes

## YouTube

Use the YouTube Data API for supported metadata discovery and the authenticated upload API for our own channel. Public metadata lookup and channel uploads require different credential handling. Upload with OAuth 2.0 and the minimum `youtube.upload` scope. Respect current API quotas and developer policies. Do not use the API to download or copy third-party audiovisual content.

## Twitch

Use Twitch Helix for supported metadata and clip discovery. Download access for Twitch clips is permission- and authorization-dependent; obtain the relevant broadcaster/editor grant and scopes before ingestion. A public stream listing is not permission to reuse the stream.

## Other platforms

Add adapters only where an official, authorized API or creator-submission workflow exists. Never make scraping, session-cookie extraction, DRM circumvention, or platform-control bypass a dependency.

## Required publishing gate

Before a clip can be approved for publishing, verify:

1. The creator has granted the necessary rights to the specific footage, facecam, voice, and edits.
2. Commercial use is explicitly covered if the channel is monetized or otherwise commercial.
3. The underlying game footage is cleared for the planned use.
4. The grant is active, not expired, and not revoked.
5. Any music, overlays, third-party assets, privacy, spoiler, and moderation checks pass.
