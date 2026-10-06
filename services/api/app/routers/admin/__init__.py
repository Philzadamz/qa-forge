from fastapi import APIRouter

from app.routers.admin import audit, defaults, report_defaults, templates, types, users

router = APIRouter(prefix="/admin")
router.include_router(types.router)
router.include_router(defaults.router)
router.include_router(users.router)
router.include_router(templates.router)
router.include_router(report_defaults.router)
router.include_router(audit.router)
