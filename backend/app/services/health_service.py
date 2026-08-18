from app.core.config import settings
from app.schemas.health import HealthResponse


class HealthService:
    def get_health(self) -> HealthResponse:
        return HealthResponse(status="healthy", service=settings.app_name)
