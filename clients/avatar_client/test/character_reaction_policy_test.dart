import 'package:flutter_test/flutter_test.dart';
import 'package:avatar_client/features/avatar/domain/avatar_presentation_hint.dart';
import 'package:avatar_client/features/avatar/domain/avatar_state.dart';
import 'package:avatar_client/features/avatar/domain/character_reaction_policy.dart';

void main() {
  const policy = CharacterReactionPolicy();

  test('strong reactions get a short pre-speech lead', () {
    final plan = policy.plan(const AvatarPresentationHint(reaction: AvatarReaction.celebrate), AvatarState.speaking);
    expect(plan.preSpeechDelay, const Duration(milliseconds: 200));
  });

  test('duration maps to a bounded semantic tail', () {
    final plan = policy.plan(const AvatarPresentationHint(duration: AvatarReactionDuration.hold), AvatarState.speaking);
    expect(plan.tailDuration, const Duration(milliseconds: 1500));
  });

  test('system states take priority over response reaction', () {
    final plan = policy.plan(const AvatarPresentationHint(reaction: AvatarReaction.celebrate), AvatarState.listening);
    expect(plan.preSpeechDelay, Duration.zero);
    expect(plan.tailDuration, Duration.zero);
  });
}
