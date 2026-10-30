# app/src/config/api_config.py
# Static structural constants for the FastAPI server.
# Never changes between dev and production.
# settings.py owns the runtime values (port, CORS, rate limits).

from dataclasses import dataclass


# ─────────────────────────────────────────────────────────────────────────────
# DATA STRUCTURE
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class APIMetadata:
    title:          str
    description:    str
    version:        str
    docs_url:       str
    redoc_url:      str
    openapi_url:    str


@dataclass(frozen=True)
class APIRoutes:
    prefix:  str
    chat:    str
    health:  str

    @property
    def full_chat(self) -> str:
        return f"{self.prefix}{self.chat}"

    @property
    def full_health(self) -> str:
        return f"{self.prefix}{self.health}"


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

APP_METADATA = APIMetadata(
    title        = "Cipher Agent API",
    description  = "Coding agent backend — hexagonal architecture",
    version      = "1.0.0",
    docs_url     = "/docs",
    redoc_url    = "/redoc",
    openapi_url  = "/openapi.json",
)

API_ROUTES = APIRoutes(
    prefix  = "/api/v1",
    chat    = "/chat",
    health  = "/health",
)

# ── standard error messages ───────────────────────────────────────────────────
class ErrorMessages:
    INTERNAL_ERROR    = "An internal error occurred"
    TOOL_NOT_FOUND    = "Requested tool not found"
    MODEL_NOT_FOUND   = "Requested model not found"
    TIMEOUT           = "Request timed out"
    RATE_LIMIT        = "Too many requests"
    PAYLOAD_TOO_LARGE = "Request body too large"
    INVALID_REQUEST   = "Invalid request body"


# ── standard response keys ────────────────────────────────────────────────────
class ResponseKeys:
    STATUS     = "status"
    MESSAGE    = "message"
    DATA       = "data"
    ERROR      = "error"
    REQUEST_ID = "request_id"


# ─────────────────────────────────────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def get_app_metadata() -> APIMetadata:
    return APP_METADATA


def get_routes() -> APIRoutes:
    return API_ROUTES


def get_full_route(route: str) -> str:
    return f"{API_ROUTES.prefix}{route}"