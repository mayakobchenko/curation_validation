import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import settings
from . import auth
from .routes import validation, export_routes

app = FastAPI(title="EBRAINS Curation Validator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(validation.router)
app.include_router(export_routes.router)


@app.get("/health")
async def health():
    return {"status": "ok"}


# In production the container serves the built React app directly (same
# single-container pattern as updated-metadata-wizard), mounted last so it
# never shadows the /api or /auth routes above.
_STATIC_DIR = os.getenv("FRONTEND_DIST_DIR", "/usr/src/app/frontend_dist")
if os.path.isdir(_STATIC_DIR):
    app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True), name="frontend")
