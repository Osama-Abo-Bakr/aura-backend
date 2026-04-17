from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    ENVIRONMENT: str = "development"
    FRONTEND_URL: str = "http://localhost:3000"

    # Supabase
    SUPABASE_URL: str
    SUPABASE_SERVICE_ROLE_KEY: str
    SUPABASE_JWT_SECRET: str

    # Gemini
    GEMINI_API_KEY: str

    # Stripe
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRICE_ID_PREMIUM: str = ""  # Set in Stripe dashboard, e.g. price_xxx

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # Sentry
    SENTRY_DSN: str = ""

    # Admin
    ADMIN_EMAILS: str = ""  # Comma-separated admin emails

    class Config:
        env_file = ".env"


settings = Settings()
