/// A single time-stamped mouth-open value produced by the audio analyzer.
class LipSyncFrame {
  const LipSyncFrame({required this.timestamp, required this.mouthOpen});

  final Duration timestamp;
  final double mouthOpen;
}

/// Ephemeral, renderer-independent mouth animation data for one WAV clip.
class LipSyncEnvelope {
  LipSyncEnvelope({required this.duration, required List<LipSyncFrame> frames})
    : frames = List.unmodifiable(frames);

  final Duration duration;
  final List<LipSyncFrame> frames;

  /// Returns a clamped, linearly interpolated value at [position].
  ///
  /// Values at or after the audio duration are silent so a completed clip
  /// cannot leave the avatar's mouth open.
  double valueAt(Duration position) {
    if (position.isNegative || frames.isEmpty) {
      return 0;
    }
    if (position >= duration) {
      return 0;
    }
    if (position <= frames.first.timestamp) {
      return _clamp(frames.first.mouthOpen);
    }

    for (var index = 1; index < frames.length; index++) {
      final right = frames[index];
      if (position <= right.timestamp) {
        final left = frames[index - 1];
        final span =
            right.timestamp.inMicroseconds - left.timestamp.inMicroseconds;
        if (span <= 0) {
          return _clamp(right.mouthOpen);
        }
        final progress =
            (position.inMicroseconds - left.timestamp.inMicroseconds) / span;
        return _clamp(
          left.mouthOpen + (right.mouthOpen - left.mouthOpen) * progress,
        );
      }
    }
    return 0;
  }

  static double _clamp(double value) {
    if (!value.isFinite || value <= 0) return 0;
    if (value >= 1) return 1;
    return value;
  }
}
