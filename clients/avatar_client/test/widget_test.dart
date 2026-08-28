import 'package:flutter_test/flutter_test.dart';
import 'package:avatar_client/features/avatar/domain/avatar_state.dart';
import 'package:avatar_client/features/avatar/presentation/avatar_renderer.dart';

void main() {
  test('avatar starts idle and exposes the five foundation states', () {
    expect(AvatarState.idle.label, 'Idle');
    expect(AvatarState.values, hasLength(5));
  });

  test('base build keeps Live2D renderer optional', () {
    final config = AvatarRendererConfig.fromEnvironment();
    expect(config.kind, AvatarRendererKind.placeholder);
  });
}
