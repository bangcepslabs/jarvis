enum VoiceActivityState { silence, speaking }

enum VoiceActivityEvent { none, speechStarted, speechEnded, maximumDurationReached }

class VoiceActivityConfig {
  const VoiceActivityConfig({
    this.amplitudeThresholdDb = -45.0,
    this.minimumSpeechDuration = const Duration(milliseconds: 300),
    this.silenceTimeout = const Duration(milliseconds: 800),
    this.maximumRecordingDuration = const Duration(seconds: 20),
  });

  final double amplitudeThresholdDb;
  final Duration minimumSpeechDuration;
  final Duration silenceTimeout;
  final Duration maximumRecordingDuration;
}

class VoiceActivityDecision {
  const VoiceActivityDecision(this.event, this.state, this.speechDetected);

  final VoiceActivityEvent event;
  final VoiceActivityState state;
  final bool speechDetected;
}

/// Lightweight dBFS VAD. It deliberately knows nothing about Android or STT.
class VoiceActivityDetector {
  VoiceActivityDetector({this.config = const VoiceActivityConfig()});

  final VoiceActivityConfig config;
  VoiceActivityState state = VoiceActivityState.silence;
  bool speechDetected = false;
  Duration? _speechCandidateStarted;
  Duration? _silenceStarted;

  VoiceActivityDecision process(double amplitudeDb, Duration elapsed) {
    if (elapsed >= config.maximumRecordingDuration) {
      return VoiceActivityDecision(VoiceActivityEvent.maximumDurationReached, state, speechDetected);
    }
    final isSpeech = amplitudeDb >= config.amplitudeThresholdDb;
    if (!speechDetected) {
      if (!isSpeech) {
        _speechCandidateStarted = null;
        return VoiceActivityDecision(VoiceActivityEvent.none, VoiceActivityState.silence, false);
      }
      _speechCandidateStarted ??= elapsed;
      if (elapsed - _speechCandidateStarted! >= config.minimumSpeechDuration) {
        speechDetected = true;
        state = VoiceActivityState.speaking;
        _silenceStarted = null;
        return VoiceActivityDecision(VoiceActivityEvent.speechStarted, state, true);
      }
      return VoiceActivityDecision(VoiceActivityEvent.none, VoiceActivityState.silence, false);
    }
    if (isSpeech) {
      _silenceStarted = null;
      state = VoiceActivityState.speaking;
      return VoiceActivityDecision(VoiceActivityEvent.none, state, true);
    }
    _silenceStarted ??= elapsed;
    if (elapsed - _silenceStarted! >= config.silenceTimeout) {
      state = VoiceActivityState.silence;
      return VoiceActivityDecision(VoiceActivityEvent.speechEnded, state, true);
    }
    return VoiceActivityDecision(VoiceActivityEvent.none, state, true);
  }
}
