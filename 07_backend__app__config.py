import os
try:
    from dotenv import load_dotenv; load_dotenv()
except ImportError:
    pass
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./irrp.db")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")
ROUTING_API_URL = os.getenv("ROUTING_API_URL", "https://router.project-osrm.org").rstrip("/")
GEOCODING_API_URL = os.getenv("GEOCODING_API_URL", "https://nominatim.openstreetmap.org").rstrip("/")
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")]
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "lax")
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
