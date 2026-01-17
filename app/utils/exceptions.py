"""
Custom exception classes for the application.

Provides specific exception types for different error scenarios.
"""


class LegalAIException(Exception):
    """Base exception for all application errors."""
    
    def __init__(self, message: str, details: dict = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class RetrievalError(LegalAIException):
    """Raised when document retrieval fails."""
    pass


class LLMError(LegalAIException):
    """Raised when LLM generation fails."""
    pass


class VectorDBError(LegalAIException):
    """Raised when vector database operations fail."""
    pass


class RateLimitExceeded(LegalAIException):
    """Raised when rate limit is exceeded."""
    pass


class InvalidSessionError(LegalAIException):
    """Raised when session ID is invalid."""
    pass