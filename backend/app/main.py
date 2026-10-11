"""FastAPI main application - РАЗРЯД Platform

Serves both API and frontend SPA with:
- OpenAPI documentation at /docs
- Health check at /health
- API endpoints at /api/v1
- SPA static files from frontend/dist
- RFC 9457 error handling
"""
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.core.db import engine, Base

# Import routers
from app.api import auth, profiles, companies, vacancies, applications, fsp

# Routers owned by other team members. They are discovered automatically so that
# testing-designer and matching-designer can ship their module WITHOUT editing this
# file (single-writer rule, brief §13.6). Create `app/api/<name>.py` exposing a
# module-level `router` and it is mounted automatically at /api/v1/<name>.
OPTIONAL_ROUTERS = ("assessment", "needs", "shortlists", "invitations", "search", "files")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown"""
    # Startup
    print(f"🚀 Starting {settings.APP_TITLE} v{settings.APP_VERSION}")
    print(f"📊 Database: {settings.DATABASE_URL}")
    print(f"🔧 Dev mode: {settings.DEV_MODE}")
    
    # In production, migrations should be run separately
    # For demo, we could optionally create tables here
    # Base.metadata.create_all(bind=engine)
    
    yield
    
    # Shutdown
    print("👋 Shutting down")
    engine.dispose()


app = FastAPI(
    title=settings.APP_TITLE,
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)


# ============================================================================
# CORS Middleware
# ============================================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# RFC 9457 Error Handlers (problem+json)
# ============================================================================

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle HTTP exceptions with RFC 9457 format"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "type": f"https://httpstatuses.com/{exc.status_code}",
            "title": exc.detail if isinstance(exc.detail, str) else "HTTP Error",
            "status": exc.status_code,
            "detail": exc.detail,
            "instance": str(request.url),
        },
        headers=exc.headers if hasattr(exc, "headers") else None,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors with RFC 9457 format"""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "type": "https://httpstatuses.com/422",
            "title": "Validation Error",
            "status": 422,
            "detail": "Request validation failed",
            "instance": str(request.url),
            "errors": [{"loc": e.get("loc"), "msg": e.get("msg"), "type": e.get("type")} for e in exc.errors()],
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions"""
    if settings.DEV_MODE:
        # In dev mode, return detailed error
        import traceback
        detail = f"{type(exc).__name__}: {str(exc)}\n\n{traceback.format_exc()}"
    else:
        # In production, hide details
        detail = "Internal server error"
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "type": "https://httpstatuses.com/500",
            "title": "Internal Server Error",
            "status": 500,
            "detail": detail,
            "instance": str(request.url),
        },
    )


# ============================================================================
# Health Check
# ============================================================================

@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": settings.APP_TITLE,
        "version": settings.APP_VERSION,
    }


# ============================================================================
# API Routes
# ============================================================================

# Include routers with /api/v1 prefix
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(profiles.router, prefix="/api/v1/profiles", tags=["Profiles"])
app.include_router(companies.router, prefix="/api/v1/companies", tags=["Companies"])
app.include_router(vacancies.router, prefix="/api/v1/vacancies", tags=["Vacancies"])
app.include_router(applications.router, prefix="/api/v1/applications", tags=["Applications"])
app.include_router(fsp.router, prefix="/api/v1/fsp", tags=["FSP Integration"])

# Auto-mount routers owned by other team members (see OPTIONAL_ROUTERS above).
# A module that does not exist yet is skipped, so this file never needs editing when
# a new router lands. A ModuleNotFoundError raised from INSIDE an existing module is
# re-raised: silently skipping a broken router would be very hard to debug.
import importlib

for _router_name in OPTIONAL_ROUTERS:
    try:
        _module = importlib.import_module(f"app.api.{_router_name}")
    except ModuleNotFoundError as exc:
        if exc.name != f"app.api.{_router_name}":
            raise
        continue
    if hasattr(_module, "router"):
        app.include_router(
            _module.router,
            prefix=f"/api/v1/{_router_name}",
            tags=[_router_name.replace("-", " ").title()],
        )


# ============================================================================
# Frontend SPA Serving
# ============================================================================

# Path to frontend build
FRONTEND_DIST = Path(__file__).parent.parent.parent / "frontend" / "dist"

if FRONTEND_DIST.exists() and FRONTEND_DIST.is_dir():
    # Mount static assets (JS, CSS, images)
    app.mount(
        "/assets",
        StaticFiles(directory=str(FRONTEND_DIST / "assets")),
        name="assets"
    )
    
    # Catch-all route for client-side routing
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve SPA for client-side routing, fallback to index.html"""
        # Неизвестный маршрут API обязан отвечать 404 в формате JSON, а не
        # отдавать HTML интерфейса. Иначе опечатка в адресе возвращает
        # «200 OK» и страницу вместо ошибки: клиент ломается на разборе JSON
        # и не понимает, что вызвал несуществующий эндпоинт. На это уже
        # наткнулся независимый тестировщик (звал /api/v1/vacancies без
        # завершающего слеша и получал HTML с кодом 200).
        if full_path.startswith("api/") or full_path == "api":
            return JSONResponse(
                status_code=404,
                content={
                    "type": "https://httpstatuses.com/404",
                    "title": "Not Found",
                    "status": 404,
                    "detail": f"Маршрут API не найден: /{full_path}",
                    "instance": f"/{full_path}",
                },
            )

        # Try to serve the requested file
        file_path = FRONTEND_DIST / full_path
        
        if file_path.is_file():
            return FileResponse(file_path)
        
        # Fallback to index.html for client-side routing
        index_path = FRONTEND_DIST / "index.html"
        if index_path.is_file():
            return FileResponse(index_path)
        
        # If index.html doesn't exist, return 404
        return JSONResponse(
            status_code=404,
            content={
                "type": "https://httpstatuses.com/404",
                "title": "Not Found",
                "status": 404,
                "detail": f"Frontend not built or path not found: {full_path}",
                "instance": f"/{full_path}",
            },
        )
else:
    print(f"⚠️  Frontend not found at {FRONTEND_DIST}")
    print("   Build frontend with: cd frontend && npm run build")
    
    @app.get("/")
    async def frontend_missing():
        """Placeholder when frontend is not built"""
        return {
            "message": "Frontend not built yet",
            "api_docs": "/docs",
            "health": "/health",
            "hint": "Run 'cd frontend && npm run build' to build the frontend"
        }
