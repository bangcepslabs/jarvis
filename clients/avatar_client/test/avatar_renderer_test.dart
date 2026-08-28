import 'package:flutter_test/flutter_test.dart';
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
  });
}
