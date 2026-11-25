"""
Central configuration, loaded from environment variables / Kubernetes secrets.
Mirrors the conventions used by updated-metadata-wizard (same IAM realm,
same KG API host) so the two apps can share OIDC client family and Harbor
project if desired.
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # --- EBRAINS IAM / Keycloak ---
    IAM_BASE_URL: str = os.getenv(
        "IAM_BASE_URL", "https://iam.ebrains.eu/auth")
    IAM_REALM: str = os.getenv("IAM_REALM", "hbp")
    OIDC_CLIENT_ID: str = os.getenv("CURATION_VALIDATOR_OIDC_CLIENT_ID", "")
    OIDC_CLIENT_SECRET: str = os.getenv(
        "CURATION_VALIDATOR_OIDC_CLIENT_SECRET", "")
    # Where Keycloak redirects back to after login (frontend route)
    OIDC_REDIRECT_URI: str = os.getenv(
        "OIDC_REDIRECT_URI", "http://localhost:5173/auth/callback"
    )

    @property
    def iam_issuer(self) -> str:
        return f"{self.IAM_BASE_URL}/realms/{self.IAM_REALM}"

    @property
    def iam_token_endpoint(self) -> str:
        return f"{self.iam_issuer}/protocol/openid-connect/token"

    @property
    def iam_auth_endpoint(self) -> str:
        return f"{self.iam_issuer}/protocol/openid-connect/auth"

    @property
    def iam_userinfo_endpoint(self) -> str:
        return f"{self.iam_issuer}/protocol/openid-connect/userinfo"

    @property
    def iam_certs_endpoint(self) -> str:
        return f"{self.iam_issuer}/protocol/openid-connect/certs"

    # --- EBRAINS Knowledge Graph ---
    KG_API_BASE: str = os.getenv(
        "KG_API_BASE", "https://core.kg.ebrains.eu/v3")
    KG_STAGE: str = os.getenv("KG_STAGE", "IN_PROGRESS")

    # Scope of the login. The Collab drive (data descriptor, metadata draft) needs "collab.drive": add it here once the
    # OIDC client of this app is allowed to ask for it.
    OIDC_SCOPE: str = os.getenv("OIDC_SCOPE", "openid profile email team roles group")

    # --- Collab drive and Data Proxy (read-only, with the curator's own token) ---
    DRIVE_BASE: str = os.getenv("DRIVE_BASE", "https://drive.ebrains.eu")
    DATA_PROXY_BASE: str = os.getenv("DATA_PROXY_BASE", "https://data-proxy.ebrains.eu/api/v1")

    # --- Language model for the review of the data descriptor (any service that speaks the OpenAI chat-completions
    # protocol, e.g. the university's GPT UiO). Empty LLM_BASE_URL or LLM_API_KEY switches the review off. The key is
    # a secret of the deployment (Vault), never sent to the browser.
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "")
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "")
    LLM_LABEL: str = os.getenv("LLM_LABEL", "Language model")
    LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "4000"))
    # "max_tokens", or "max_completion_tokens" for Azure GPT-5 style models
    LLM_MAX_TOKENS_PARAM: str = os.getenv("LLM_MAX_TOKENS_PARAM", "max_tokens")
    LLM_TIMEOUT: int = int(os.getenv("LLM_TIMEOUT", "180"))
    LLM_MAX_PROMPT_CHARS: int = int(os.getenv("LLM_MAX_PROMPT_CHARS", "120000"))
    # JSON object of extra request headers, e.g. {"api-key": "..."} for services that do not use a bearer token
    LLM_EXTRA_HEADERS: str = os.getenv("LLM_EXTRA_HEADERS", "")

    # --- Session ---
    SESSION_SECRET: str = os.getenv(
        "SESSION_SECRET", "dev-insecure-secret-change-me")
    FRONTEND_ORIGIN: str = os.getenv(
        "FRONTEND_ORIGIN", "http://localhost:5173")

    # --- Local development only ---
    # When true, /auth/login skips EBRAINS IAM entirely and logs in a fake
    # curator, so the UI can be clicked through before an OIDC client exists.
    # Never set this in a deployed environment — guarded again at call site.
    DEV_MODE: bool = os.getenv(
        "DEV_MODE", "false").lower() in ("1", "true", "yes")

    # --- Storage for completed validation runs (used for the docx export +
    # a simple history list; swap for a real DB later if needed) ---
    DATA_DIR: str = os.getenv("DATA_DIR", "/usr/src/app/data")


settings = Settings()
