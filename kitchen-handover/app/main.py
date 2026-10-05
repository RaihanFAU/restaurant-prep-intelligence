from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.routes import pages, products, stations, tasks, worker
from app.services.errors import InactiveProductError, NotFoundError

app = FastAPI(title="Kitchen Prep Handover & Location Tracker")

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(pages.router)
app.include_router(products.router)
app.include_router(stations.router)
app.include_router(tasks.router)
app.include_router(worker.router)


@app.exception_handler(NotFoundError)
async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(InactiveProductError)
async def inactive_product_handler(request: Request, exc: InactiveProductError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
