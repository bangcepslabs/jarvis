class LLMProviderError(Exception):
    """Safe, provider-independent error raised by an LLM adapter."""


class LLMRateLimitError(LLMProviderError):
    def __init__(self, message: str = "The AI service is temporarily rate limited.", rate_limit=None) -> None:
        super().__init__(message)
        self.rate_limit = rate_limit
