class NotFoundError(Exception):
    """Base class: a referenced entity does not exist."""


class ProductNotFoundError(NotFoundError):
    def __init__(self, product_id: int):
        super().__init__(f"Prepared product {product_id} not found.")


class StationNotFoundError(NotFoundError):
    def __init__(self, station_id: int):
        super().__init__(f"Station {station_id} not found.")


class WorkerNotFoundError(NotFoundError):
    def __init__(self, worker_id: int):
        super().__init__(f"Worker {worker_id} not found.")


class TaskNotFoundError(NotFoundError):
    def __init__(self, task_id: int):
        super().__init__(f"Preparation task {task_id} not found.")


class InactiveProductError(Exception):
    """A preparation task cannot be created for a product that is no longer active."""

    def __init__(self, product_id: int):
        super().__init__(f"Prepared product {product_id} is inactive and cannot be scheduled for preparation.")
