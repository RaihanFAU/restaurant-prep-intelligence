from fastapi import FastAPI

app = FastAPI(title="Kitchen Prep Handover & Location Tracker")


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check only — no real routes exist yet (see docs/mvp/kitchen-handover.md,
    implementation order: this is step 1, skeleton + models only)."""
    return {"status": "ok"}
