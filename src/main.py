from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from src.auth.router import router as auth_router
from src.cards.router import public_router, router as cards_router
from src.contacts.router import router as contacts_router
from src.core.config import settings
from src.core.exceptions import register_exception_handlers
from src.core.rate_limit import limiter
from src.database import connect_db, create_indexes, disconnect_db
from src.enrichment.router import router as enrichment_router
from src.events.router import router as events_router
from src.scans.router import router as scans_router
from src.tags.router import router as tags_router
from src.uploads.router import router as uploads_router
from src.users.router import router as users_router
from src.activity.router import router as activity_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    await create_indexes()
    yield
    await disconnect_db()


app = FastAPI(
    title="Cardly API",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)


@app.get("/health", tags=["health"])
async def health_check() -> JSONResponse:
    from src.database import get_database
    try:
        await get_database().command("ping")
        db_status = "connected"
    except Exception:
        db_status = "unavailable"
    status = "ok" if db_status == "connected" else "degraded"
    return JSONResponse(
        status_code=200 if status == "ok" else 503,
        content={"status": status, "db": db_status},
    )


PREFIX = "/api/v1"
app.include_router(auth_router, prefix=PREFIX)
app.include_router(contacts_router, prefix=PREFIX)
app.include_router(tags_router, prefix=PREFIX)
app.include_router(events_router, prefix=PREFIX)
app.include_router(activity_router, prefix=PREFIX)
app.include_router(scans_router, prefix=PREFIX)
app.include_router(enrichment_router, prefix=PREFIX)
app.include_router(cards_router, prefix=PREFIX)
app.include_router(public_router, prefix=PREFIX)
app.include_router(users_router, prefix=PREFIX)
app.include_router(uploads_router, prefix=PREFIX)
