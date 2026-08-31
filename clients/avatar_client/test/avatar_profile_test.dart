import 'package:flutter_test/flutter_test.dart';
import 'package:avatar_client/features/avatar/domain/avatar_profile.dart';
import 'package:avatar_client/features/avatar/domain/avatar_presentation_hint.dart';
import 'package:avatar_client/features/avatar/domain/avatar_state.dart';

void main() {
  test('unknown profile safely falls back to placeholder', () {
    expect(AvatarProfiles.byId('missing').id, 'placeholder');
  });

  test('Ellen maps expressions present in its model registry', () {
    expect(AvatarProfiles.ellenDev.expressionFor(AvatarEmotion.happy), 'red');
    expect(AvatarProfiles.ellenDev.expressionFor(AvatarEmotion.surprised), 'shock');
    expect(AvatarProfiles.ellenDev.expressionFor(AvatarEmotion.neutral), isNull);
  });

  test('Ellen development profile preserves known framing and mouth defaults', () {
    expect(AvatarProfiles.ellenDev.framing.scale, 2.95);
    expect(AvatarProfiles.ellenDev.framing.offsetY, -0.30);
    expect(AvatarProfiles.ellenDev.mouthOpenParameter, 'ParamMouthOpenY');
  });

  test('Emilia profile uses verified Cubism motion names and mouth parameter', () {
    final selection = AvatarProfiles.emiliaMagical.motionSelectionFor(
      AvatarState.speaking,
      const AvatarPresentationHint(
        emotion: AvatarEmotion.surprised,
        intensity: .8,
      ),
    );

    expect(AvatarProfiles.byId('emilia_magical').id, 'emilia_magical');
    expect(AvatarProfiles.emiliaMagical.modelAsset, endsWith('Emilia (Magical).model3.json'));
    expect(AvatarProfiles.emiliaMagical.mouthOpenParameter, 'ParamMouthOpenY');
    expect(AvatarProfiles.emiliaMagical.ambientMotions, ['select_idle', 'select_idle02']);
    expect(selection.motion, 'act_bikkuri02');
    expect(selection.candidates, contains('act_bikkuri'));
    expect(AvatarProfiles.emiliaMagical.supportsExpressions, isFalse);
  });

  test('Emilia gives neutral speaking a rotating verified body-motion pool', () {
    final selection = AvatarProfiles.emiliaMagical.motionSelectionFor(
      AvatarState.speaking,
      const AvatarPresentationHint(),
    );

    expect(selection.candidates, containsAll([
      'act_normal03', 'act_unazuku', 'act_hohoemu', 'act_doya',
    ]));
    expect(AvatarProfiles.emiliaMagical.mouthMaxOpen, .50);
  });
}
