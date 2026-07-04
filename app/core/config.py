from typing import List, Union, Optional
# pyrefly: ignore [missing-import]
from pydantic import AnyHttpUrl, field_validator
# pyrefly: ignore [missing-import]
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App General Settings
    APP_NAME: str = "Prro Health Club ERP"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"

    # Security Settings
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Supabase Settings
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""

    # Database Settings
    DATABASE_URL: str = ""

    # CORS Settings
    CORS_ORIGINS: str = "*"

    # Timezone
    TIMEZONE: str = "Asia/Kolkata"

    # Server configuration
    PORT: int = 8000
    WORKERS: int = 2

    # Email Settings (Resend Integration)
    RESEND_API_KEY: str = ""
    FROM_EMAIL: str = "noreply@prrohealthclub.com"
    FROM_NAME: str = "Prro Health Club"
    ENABLE_EMAILS: bool = True        # set False locally to skip actual sending
    EMAIL_TIMEOUT: int = 15           # seconds before Resend call times out
    EMAIL_RETRY_COUNT: int = 3        # retry attempts on transient failures

    # PDF / Invoices
    PDF_STORAGE_PATH: str = "receipts"    # local fallback path (not used in prod yet)
    INVOICE_PREFIX: str = "PRRO"

    # Password Reset
    RESET_TOKEN_EXPIRY_MINUTES: int = 60

    # Frontend (for reset links)
    FRONTEND_URL: str = "http://localhost:4321"

    # Cron
    CRON_TIMEZONE: str = "Asia/Kolkata"

    # GST & Gym details
    GYM_GST_NUMBER: Optional[str] = None   # e.g. "27XXXXX" — None means GST not applicable
    GYM_GST_PERCENT: float = 0.0           # e.g. 18.0 for 18% GST
    GYM_ADDRESS: str = "Mumbai, Maharashtra, India"
    GYM_PHONE: str = ""
    GYM_EMAIL: str = "info@prrohealthclub.com"

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def cors_origins_list(self) -> List[str]:
        if not self.CORS_ORIGINS:
            return []
        val = self.CORS_ORIGINS.strip()
        if val.startswith("[") and val.endswith("]"):
            import json
            try:
                parsed = json.loads(val)
                if isinstance(parsed, list):
                    return [str(item).strip() for item in parsed]
            except Exception:
                pass
        return [i.strip() for i in val.split(",")]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
