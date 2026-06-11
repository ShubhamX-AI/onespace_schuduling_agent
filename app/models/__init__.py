from app.models.schedule import Schedule

__all__ = ["Schedule", "DOCUMENT_MODELS"]

# Registered with Beanie on startup.
DOCUMENT_MODELS = [Schedule]
