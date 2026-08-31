import 'package:flutter_test/flutter_test.dart';
import 'package:flutter/widgets.dart';
import 'package:avatar_client/features/avatar/domain/avatar_presentation_hint.dart';
import 'package:avatar_client/features/avatar/domain/avatar_profile.dart';
import 'package:avatar_client/features/avatar/domain/avatar_state.dart';
import 'package:avatar_client/features/avatar/presentation/avatar_renderer.dart';

void main() {
  test('Live2D update payload carries runtime state and presentation values', () {
    final hint = AvatarPresentationHint.fromJson(const {
      'emotion': 'happy',
      'intensity': 0.8,
      'motion_intent': 'positive',
      'reaction': 'acknowledge',
    });

    final payload = live2DUpdateParams(
      AvatarRendererConfig(
        kind: AvatarRendererKind.live2d,
        modelAsset: 'assets/model.model3.json',
        expression: 'happy.exp3.json',
        profile: AvatarProfiles.ellenDev,
      ),
      AvatarState.speaking,
      hint,
      0.65,
    );

    expect(payload['state'], 'speaking');
    expect(payload['expression'], 'happy.exp3.json');
    expect(payload['emotion'], 'happy');
    expect(payload['motionIntent'], 'positive');
    expect(payload['reaction'], 'acknowledge');
    expect(payload['mouthOpen'], 0.65);
    expect(payload['mouthMaxOpen'], 0.72);
    expect(payload['mouthNoiseGate'], 0.04);
  });

  test('Live2D lifecycle payload marks only resumed as active', () {
    expect(
      live2DHostLifecycleParams(AppLifecycleState.resumed),
      const {'resumed': true},
    );
    expect(
      live2DHostLifecycleParams(AppLifecycleState.paused),
      const {'resumed': false},
    );
  });

  test('Ellen profile maps supported emotional expressions and motions', () {
    final payload = live2DUpdateParams(
      AvatarRendererConfig(
        kind: AvatarRendererKind.live2d,
        modelAsset: 'assets/model.model3.json',
        expression: 'shuiyin',
        profile: AvatarProfiles.ellenDev,
      ),
      AvatarState.speaking,
      const AvatarPresentationHint(
        emotion: AvatarEmotion.surprised,
        motionIntent: AvatarMotionIntent.reaction,
      ),
      0,
    );

    expect(payload['expression'], 'shock');
    expect(payload['motion'], 'idle2');
  });

  test('Emilia payload uses verified motion names and skips unavailable expressions', () {
    final payload = live2DUpdateParams(
      AvatarRendererConfig(
        kind: AvatarRendererKind.live2d,
        modelAsset: AvatarProfiles.emiliaMagical.modelAsset,
        expression: 'shuiyin',
        profile: AvatarProfiles.emiliaMagical,
      ),
      AvatarState.speaking,
      const AvatarPresentationHint(
        emotion: AvatarEmotion.happy,
        intensity: .8,
        motionIntent: AvatarMotionIntent.positive,
      ),
      0,
    );

    expect(payload['expression'], '');
    expect(payload['motion'], 'act_egao02');
    expect(payload['motionCandidates'], contains('act_egao'));
    expect(payload['ambientMotions'], ['select_idle', 'select_idle02']);
    expect(payload['avatarProfile'], 'emilia_magical');
    expect(payload['fallbackModelAsset'], AvatarProfiles.ellenDev.modelAsset);
  });

  test('Emilia neutral speech uses its body-motion pool and reduced mouth cap', () {
    final payload = live2DUpdateParams(
      AvatarRendererConfig(
        kind: AvatarRendererKind.live2d,
        modelAsset: AvatarProfiles.emiliaMagical.modelAsset,
        expression: 'shuiyin',
        profile: AvatarProfiles.emiliaMagical,
      ),
      AvatarState.speaking,
      const AvatarPresentationHint(),
      .8,
    );

    expect(payload['motionCandidates'], contains('act_normal03'));
    expect(payload['mouthMaxOpen'], .50);
    expect(payload['mouthNoiseGate'], .06);
  });
}
