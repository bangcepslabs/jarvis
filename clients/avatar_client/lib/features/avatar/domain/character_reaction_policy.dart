import 'avatar_presentation_hint.dart';
import 'avatar_state.dart';

class ReactionPlan {
  const ReactionPlan({required this.preSpeechDelay, required this.tailDuration, required this.resetToNeutral});
  final Duration preSpeechDelay;
  final Duration tailDuration;
  final bool resetToNeutral;
}

class CharacterReactionPolicy {
  const CharacterReactionPolicy();

  ReactionPlan plan(AvatarPresentationHint hint, AvatarState state) {
    if (state == AvatarState.error || state == AvatarState.listening || state == AvatarState.thinking) {
      return const ReactionPlan(preSpeechDelay: Duration.zero, tailDuration: Duration.zero, resetToNeutral: true);
    }
    final pre = hint.reaction == AvatarReaction.celebrate || hint.reaction == AvatarReaction.surprise
        ? const Duration(milliseconds: 200)
        : Duration.zero;
    final tail = switch (hint.duration) {
      AvatarReactionDuration.short => const Duration(milliseconds: 450),
      AvatarReactionDuration.normal => const Duration(milliseconds: 850),
      AvatarReactionDuration.hold => const Duration(milliseconds: 1500),
    };
    return ReactionPlan(preSpeechDelay: pre, tailDuration: tail, resetToNeutral: true);
  }
}
