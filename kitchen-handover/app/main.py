from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.core.csrf import CSRFCookieMiddleware
from app.routes import (
    admin,
    admin_products,
    admin_sections,
    admin_stations,
    admin_tasks,
    admin_users,
    auth,
    pages,
    products,
    stations,
    tasks,
)
from app.services.errors import CSRFError, ForbiddenError, InactiveProductError, LoginRequiredError, NotFoundError

app = FastAPI(title="Kitchen Prep Handover & Location Tracker")

app.add_middleware(CSRFCookieMiddleware)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(auth.router)
app.include_router(pages.router)
app.include_router(products.router)
app.include_router(stations.router)
app.include_router(tasks.router)
app.include_router(admin.router)
app.include_router(admin_products.router)
app.include_router(admin_stations.router)
app.include_router(admin_sections.router)
app.include_router(admin_users.router)
app.include_router(admin_tasks.router)


@app.exception_handler(NotFoundError)
async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(InactiveProductError)
async def inactive_product_handler(request: Request, exc: InactiveProductError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(LoginRequiredError)
async def login_required_handler(request: Request, exc: LoginRequiredError) -> RedirectResponse:
    return RedirectResponse(url=f"/login?next={exc.next_path}", status_code=303)


@app.exception_handler(ForbiddenError)
async def forbidden_handler(request: Request, exc: ForbiddenError) -> JSONResponse:
    return JSONResponse(status_code=403, content={"detail": "Forbidden — admin access required."})


@app.exception_handler(CSRFError)
async def csrf_error_handler(request: Request, exc: CSRFError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
