from app.core.exceptions import JarvisError


class STTError(JarvisError):
    pass


class STTDisabledError(STTError):
    pass


class UnsupportedAudioError(STTError):
    pass


class AudioTooLargeError(STTError):
    pass


class STTTimeoutError(STTError):
    pass


class STTProviderError(STTError):
    pass


class NoSpeechDetected(STTError):
    pass
