import math

from app.auth import require_api_key
from app.db import get_db
from app.discovery import (
    DiscoveryFilter,
    DiscoveryProviderError,
    DiscoveryService,
    ProviderStatusResponse,
    create_default_registry,
)
from app.models.core import PlatformChannel
from app.models.discovery import DiscoveredVideo, DiscoveryRun, LiveSession
from app.schemas import (
    DiscoveredVideoOut,
    DiscoveryRunOut,
    DiscoveryTriggerRequest,
    LiveSessionOut,
    PaginatedResponse,
    PlatformChannelOut,
)
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

router = APIRouter(prefix="/discovery", tags=["discovery"])
_registry = create_default_registry()
_service = DiscoveryService(_registry)


@router.get("/status", response_model=list[ProviderStatusResponse])
def get_discovery_status() -> list[ProviderStatusResponse]:
    """Inspect configured discovery adapters and their availability status."""
    return _registry.list_statuses()


@router.post(
    "/run", response_model=DiscoveryRunOut, status_code=status.HTTP_202_ACCEPTED
)
def trigger_discovery(
    request: DiscoveryTriggerRequest,
    db: Session = Depends(get_db),
    _api_key: str = Depends(require_api_key),
) -> DiscoveryRun:
    """
    Manually triggers a discovery run for YouTube or Twitch.
    Requires authentication via X-API-Key or Authorization Bearer header.
    """
    if not _registry.is_supported(request.provider):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Provider '{request.provider}' is unsupported.",
        )

    provider = _registry.get(request.provider)
    if not provider or not provider.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Provider '{request.provider}' is not configured with required API credentials.",
        )

    flt = DiscoveryFilter(
        query=request.query,
        is_live_only=request.is_live_only,
        max_results=request.max_results,
    )

    try:
        run_record = _service.run_provider_discovery(
            db=db,
            provider_name=request.provider,
            filter_params=flt,
            trigger_type="manual",
        )
        return run_record
    except DiscoveryProviderError as exc:
        raise HTTPException(
            status_code=exc.status_code or status.HTTP_502_BAD_GATEWAY,
            detail=f"Discovery failed: {exc.message}",
        ) from exc


@router.get("/videos", response_model=PaginatedResponse[DiscoveredVideoOut])
def list_discovered_videos(
    platform: str | None = Query(None, description="Filter by platform"),
    is_live: bool | None = Query(None, description="Filter by live status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
) -> PaginatedResponse[DiscoveredVideoOut]:
    """Lists discovered video metadata with pagination and platform filters."""
    query = select(DiscoveredVideo)
    count_query = select(func.count(DiscoveredVideo.id))

    if platform:
        query = query.where(DiscoveredVideo.platform == platform.lower())
        count_query = count_query.where(DiscoveredVideo.platform == platform.lower())
    if is_live is not None:
        query = query.where(DiscoveredVideo.is_live == is_live)
        count_query = count_query.where(DiscoveredVideo.is_live == is_live)

    total = db.scalar(count_query) or 0
    pages = math.ceil(total / page_size) if total > 0 else 1

    query = query.order_by(
        DiscoveredVideo.published_at.desc().nullslast(), DiscoveredVideo.id.desc()
    )
    query = query.offset((page - 1) * page_size).limit(page_size)
    items = list(db.scalars(query).all())

    return PaginatedResponse(
        items=[DiscoveredVideoOut.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/streams", response_model=PaginatedResponse[LiveSessionOut])
def list_live_streams(
    platform: str | None = Query(None, description="Filter by platform"),
    is_active: bool | None = Query(True, description="Filter by active status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
) -> PaginatedResponse[LiveSessionOut]:
    """Lists discovered live stream sessions."""
    query = select(LiveSession)
    count_query = select(func.count(LiveSession.id))

    if platform:
        query = query.where(LiveSession.platform == platform.lower())
        count_query = count_query.where(LiveSession.platform == platform.lower())
    if is_active is not None:
        query = query.where(LiveSession.is_active == is_active)
        count_query = count_query.where(LiveSession.is_active == is_active)

    total = db.scalar(count_query) or 0
    pages = math.ceil(total / page_size) if total > 0 else 1

    query = query.order_by(
        LiveSession.viewer_count.desc().nullslast(), LiveSession.id.desc()
    )
    query = query.offset((page - 1) * page_size).limit(page_size)
    items = list(db.scalars(query).all())

    return PaginatedResponse(
        items=[LiveSessionOut.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/channels", response_model=PaginatedResponse[PlatformChannelOut])
def list_channels(
    platform: str | None = Query(None, description="Filter by platform"),
    is_live: bool | None = Query(None, description="Filter by currently live status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
) -> PaginatedResponse[PlatformChannelOut]:
    """Lists tracked creator/streamer platform channels."""
    query = select(PlatformChannel)
    count_query = select(func.count(PlatformChannel.id))

    if platform:
        query = query.where(PlatformChannel.platform == platform.lower())
        count_query = count_query.where(PlatformChannel.platform == platform.lower())
    if is_live is not None:
        query = query.where(PlatformChannel.is_live == is_live)
        count_query = count_query.where(PlatformChannel.is_live == is_live)

    total = db.scalar(count_query) or 0
    pages = math.ceil(total / page_size) if total > 0 else 1

    query = query.order_by(
        PlatformChannel.last_seen_at.desc(), PlatformChannel.id.desc()
    )
    query = query.offset((page - 1) * page_size).limit(page_size)
    items = list(db.scalars(query).all())

    return PaginatedResponse(
        items=[PlatformChannelOut.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/runs", response_model=PaginatedResponse[DiscoveryRunOut])
def list_discovery_runs(
    provider: str | None = Query(None, description="Filter by provider"),
    status: str | None = Query(None, description="Filter by run status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
) -> PaginatedResponse[DiscoveryRunOut]:
    """Lists discovery execution run history and metrics."""
    query = select(DiscoveryRun)
    count_query = select(func.count(DiscoveryRun.id))

    if provider:
        query = query.where(DiscoveryRun.provider == provider.lower())
        count_query = count_query.where(DiscoveryRun.provider == provider.lower())
    if status:
        query = query.where(DiscoveryRun.status == status.lower())
        count_query = count_query.where(DiscoveryRun.status == status.lower())

    total = db.scalar(count_query) or 0
    pages = math.ceil(total / page_size) if total > 0 else 1

    query = query.order_by(DiscoveryRun.started_at.desc(), DiscoveryRun.id.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    items = list(db.scalars(query).all())

    return PaginatedResponse(
        items=[DiscoveryRunOut.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )
