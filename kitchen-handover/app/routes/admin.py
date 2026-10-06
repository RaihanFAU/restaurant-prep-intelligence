from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates

from app.core.auth import require_admin
from app.core.i18n import TEXTS
from app.models import Worker

router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory="app/templates")


@router.get("")
def admin_dashboard(request: Request, current_user: Worker = Depends(require_admin)):
    return templates.TemplateResponse(
        request, "admin/dashboard.html", {"t": TEXTS, "current_user": current_user}
    )
