import 'package:flutter_test/flutter_test.dart';
import 'package:avatar_client/features/avatar/domain/avatar_profile.dart';
import 'package:avatar_client/features/avatar/domain/avatar_presentation_hint.dart';

void main() {
  test('unknown profile safely falls back to placeholder', () {
    expect(AvatarProfiles.byId('missing').id, 'placeholder');
  });

  test('unverified expression mappings are a safe no-op', () {
    expect(AvatarProfiles.ellenDev.expressionFor(AvatarEmotion.happy), isNull);
    expect(AvatarProfiles.ellenDev.expressionFor(AvatarEmotion.neutral), isNull);
  });

  test('Ellen development profile preserves known framing and mouth defaults', () {
    expect(AvatarProfiles.ellenDev.framing.scale, 2.95);
    expect(AvatarProfiles.ellenDev.framing.offsetY, -0.30);
    expect(AvatarProfiles.ellenDev.mouthOpenParameter, 'ParamMouthOpenY');
  });
}
