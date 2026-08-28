enum AvatarEmotion { neutral, happy, excited, surprised, concerned, thinking, playful }
enum AvatarMotionIntent { none, subtle, positive, reaction }

class AvatarPresentationHint {
  const AvatarPresentationHint({
    this.emotion = AvatarEmotion.neutral,
    this.intensity = .3,
    this.motionIntent = AvatarMotionIntent.none,
  });

  final AvatarEmotion emotion;
  final double intensity;
  final AvatarMotionIntent motionIntent;

  factory AvatarPresentationHint.fromJson(Object? value) {
    if (value is! Map) return const AvatarPresentationHint();
    final emotionMatches = AvatarEmotion.values.where((item) => item.name == value['emotion']);
    final motionMatches = AvatarMotionIntent.values.where((item) => item.name == value['motion_intent']);
    final emotion = emotionMatches.isEmpty ? null : emotionMatches.first;
    final motion = motionMatches.isEmpty ? null : motionMatches.first;
    final rawIntensity = value['intensity'];
    final parsedIntensity = rawIntensity is num ? rawIntensity.toDouble().clamp(0.0, 1.0) : .3;
    return AvatarPresentationHint(
      emotion: emotion ?? AvatarEmotion.neutral,
      intensity: parsedIntensity,
      motionIntent: motion ?? AvatarMotionIntent.none,
    );
  }
}
