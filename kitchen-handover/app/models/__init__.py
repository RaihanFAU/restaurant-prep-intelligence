"""Import every model here so Base.metadata is fully populated — this is
what lets Alembic autogenerate see all tables, and what lets relationship()
string references (e.g. "Section") resolve correctly.
"""

from app.models.station import Station
from app.models.section import Section
from app.models.storage_location import StorageLocation
from app.models.worker import Worker
from app.models.prepared_product import PreparedProduct
from app.models.preparation_task import PreparationTask
from app.models.product_location_history import ProductLocationHistory

__all__ = [
    "Station",
    "Section",
    "StorageLocation",
    "Worker",
    "PreparedProduct",
    "PreparationTask",
    "ProductLocationHistory",
]
