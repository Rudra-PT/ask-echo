class IngestionError(Exception):
    pass

class CorruptDocumentError(IngestionError):
    pass

class EmptyExtractionError(IngestionError):
    pass

class UnsupportedMimeError(IngestionError):
    pass

class VisionExtractionError(IngestionError):
    pass

class EmbeddingError(IngestionError):
    pass
