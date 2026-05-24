class ApplicationError(Exception):
    pass


class BatchTooLargeError(ApplicationError):
    def __init__(self, max_size: int) -> None:
        super().__init__(f"Batch size exceeds max={max_size}")
        self.max_size = max_size


class JobNotFoundError(ApplicationError):
    pass


class ForbiddenError(ApplicationError):
    pass


class InvalidWebhookError(ApplicationError):
    pass
