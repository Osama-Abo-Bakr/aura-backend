from fastapi import APIRouter

from app.api.v1.analysis import router as analysis_router
from app.api.v1.auth import router as auth_router
from app.api.v1.chat import router as chat_router
from app.api.v1.health_log import router as health_log_router
from app.api.v1.subscriptions import router as subscriptions_router
from app.api.v1.wellness import router as wellness_router

router = APIRouter(prefix="/api/v1")
router.include_router(auth_router, tags=["auth"])
router.include_router(analysis_router, tags=["analysis"])
router.include_router(chat_router, tags=["chat"])
router.include_router(subscriptions_router, tags=["subscriptions"])
router.include_router(health_log_router, tags=["health-log"])
router.include_router(wellness_router, tags=["wellness"])
