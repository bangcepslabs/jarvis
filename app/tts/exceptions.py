from app.core.exceptions import JarvisError


class TTSError(JarvisError):
    pass


class TTSEnabledError(TTSError):
    pass


class TTSTextValidationError(TTSError):
    pass


class TTSTimeoutError(TTSError):
    pass


class TTSProviderError(TTSError):
    pass
