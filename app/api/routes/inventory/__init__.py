from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
from . import (
    alternates_routes,
    bacthes_routes,
    category_routes,
    gst_routes,
    medicine_routes,
    side_effects_routes,
    tags_routes,
    use_cases_routes,
)

router = APIRouter(prefix="/inventory" , dependencies=[Depends(RateLimiter(times=100 , seconds=60))])

#
# @router.get("/dev", description="Health check endpoint for Inventory routes")
# async def get_root_dev():
#     return JSONResponse(status_code=200, content={"msg": "this route is working"})


# Include all sub-routers
router.include_router(medicine_routes.router)
router.include_router(category_routes.router)
router.include_router(tags_routes.router)
router.include_router(alternates_routes.router)
router.include_router(bacthes_routes.router)
router.include_router(side_effects_routes.router)
router.include_router(gst_routes.router)
router.include_router(use_cases_routes.router)
