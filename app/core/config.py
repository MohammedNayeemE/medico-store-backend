from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = ""
    APP_VERSION: str = ""
    DB_URL: str = ""
    ACCESS_SECRET_TOKEN: str = ""
    REFRESH_SECRET_TOKEN: str = ""
    ALGORITHM: str = ""
    ACCESS_TOKEN_EXPIRES: int = 0
    REFRESH_TOKEN_EXPIRES: int = 0
    DEV: bool = True
    PRODUCTION_URL: str = ""
    DEBUG: bool = True
    MONGO_DB_URL: str = ""
    MONGO_DB_NAME: str = ""
    RECAPTCHA_SECRET_KEY: str = ""
    RECAPTCHA_SITE_KEY: str = ""
    CAPTCHA_BYPASS: bool = False
    MAIL_USERNAME: str = ""
    MAIL_PASSWORD: str = ""
    MAIL_FROM: str = ""
    MAIL_PORT: int = 587
    MAIL_SERVER: str = "smtp.gmail.com"
    BACKUP_DIR: str = ""
    RESTORE_DIR: str = ""
    POSTGRES_HOST: str = ""
    POSTGRES_USER: str = ""
    POSTGRES_DB: str = ""
    MONGO_URI: str = ""
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_PHONE_NUMBER: str = ""
    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()

allowed_origins = []
if settings.DEV:
    allowed_origins = ["*"]
else:
    allowed_origins = [settings.PRODUCTION_URL]
