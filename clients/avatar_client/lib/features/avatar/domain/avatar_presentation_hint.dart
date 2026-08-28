enum AvatarEmotion { neutral, happy, excited, surprised, concerned, thinking, playful }
enum AvatarMotionIntent { none, subtle, positive, reaction }
enum AvatarAttitude { neutral, friendly, playful, supportive, curious, serious, confident }
enum AvatarReaction { none, acknowledge, agree, disagree, celebrate, surprise, worry, think, tease, encourage }
enum AvatarReactionDuration { short, normal, hold }

class AvatarPresentationHint {
  const AvatarPresentationHint({
    this.emotion = AvatarEmotion.neutral,
    this.intensity = .3,
    this.motionIntent = AvatarMotionIntent.none,
    this.attitude = AvatarAttitude.neutral,
    this.reaction = AvatarReaction.none,
    this.duration = AvatarReactionDuration.normal,
  });

  final AvatarEmotion emotion;
  final double intensity;
  final AvatarMotionIntent motionIntent;
  final AvatarAttitude attitude;
  final AvatarReaction reaction;
  final AvatarReactionDuration duration;

  Map<String, Object> toJson() => {'emotion': emotion.name, 'intensity': intensity, 'motion_intent': motionIntent.name, 'attitude': attitude.name, 'reaction': reaction.name, 'duration': duration.name};

  factory AvatarPresentationHint.fromJson(Object? value) {
    if (value is! Map) return const AvatarPresentationHint();
    final emotionMatches = AvatarEmotion.values.where((item) => item.name == value['emotion']);
    final motionMatches = AvatarMotionIntent.values.where((item) => item.name == value['motion_intent']);
    final emotion = emotionMatches.isEmpty ? null : emotionMatches.first;
    final motion = motionMatches.isEmpty ? null : motionMatches.first;
    final attitudeMatches = AvatarAttitude.values.where((item) => item.name == value['attitude']);
    final reactionMatches = AvatarReaction.values.where((item) => item.name == value['reaction']);
    final durationMatches = AvatarReactionDuration.values.where((item) => item.name == value['duration']);
    final rawIntensity = value['intensity'];
    final parsedIntensity = rawIntensity is num ? rawIntensity.toDouble().clamp(0.0, 1.0) : .3;
    return AvatarPresentationHint(
      emotion: emotion ?? AvatarEmotion.neutral,
      intensity: parsedIntensity,
      motionIntent: motion ?? AvatarMotionIntent.none,
      attitude: attitudeMatches.isEmpty ? AvatarAttitude.neutral : attitudeMatches.first,
      reaction: reactionMatches.isEmpty ? AvatarReaction.none : reactionMatches.first,
      duration: durationMatches.isEmpty ? AvatarReactionDuration.normal : durationMatches.first,
    );
  }
}
