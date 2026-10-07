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
    IAM_BASE_URL: str = os.getenv("IAM_BASE_URL", "https://iam.ebrains.eu/auth")
    IAM_REALM: str = os.getenv("IAM_REALM", "hbp")
    OIDC_CLIENT_ID: str = os.getenv("CURATION_VALIDATOR_OIDC_CLIENT_ID", "")
    OIDC_CLIENT_SECRET: str = os.getenv("CURATION_VALIDATOR_OIDC_CLIENT_SECRET", "")
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
    KG_API_BASE: str = os.getenv("KG_API_BASE", "https://core.kg.ebrains.eu/v3")
    KG_STAGE: str = os.getenv("KG_STAGE", "IN_PROGRESS")

    # --- Session ---
    SESSION_SECRET: str = os.getenv("SESSION_SECRET", "dev-insecure-secret-change-me")
    FRONTEND_ORIGIN: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")

    # --- Storage for completed validation runs (used for the docx export +
    # a simple history list; swap for a real DB later if needed) ---
    DATA_DIR: str = os.getenv("DATA_DIR", "/usr/src/app/data")


settings = Settings()
