from fastapi import APIRouter

from app.schemas.health import HealthResponse
from app.services.health_service import HealthService

router = APIRouter(tags=["health"])
health_service = HealthService()


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    return health_service.get_health()
