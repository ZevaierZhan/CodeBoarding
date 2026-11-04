class ModelError(Exception):
    def __init__(self, code: str, location: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.location = location

    def as_dict(self) -> dict:
        return {"code": self.code, "location": self.location, "message": str(self)}
