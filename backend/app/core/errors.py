class ApiError(Exception):
    def __init__(self, message: str, code: str = 'VALIDATION', status: int = 400):
        self.message, self.code, self.status = message, code, status
