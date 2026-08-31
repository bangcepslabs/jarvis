import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:avatar_client/features/voice/wake_word/wake_word_controller.dart';
import 'package:avatar_client/features/voice/wake_word/wake_word_engine.dart';

void main() {
  late FakeWakeWordEngine engine;
  late WakeWordController controller;
  late int detected;

  setUp(() {
    engine = FakeWakeWordEngine();
    detected = 0;
    controller = WakeWordController(engine, onDetected: () async => detected++);
  });

  tearDown(() => controller.dispose());

  test('arms engine and forwards one detection', () async {
    await controller.arm();
    expect(engine.starts, 1);
    engine.emit(const WakeWordDetected(name: 'Hey Jarvis', score: .8));
    await Future<void>.delayed(Duration.zero);
    expect(detected, 1);
    expect(engine.stops, 1);
    expect(controller.state, WakeWordControllerState.suspended);
  });

  test('duplicate detection while suspended is ignored', () async {
    await controller.arm();
    engine.emit(const WakeWordDetected(name: 'Hey Jarvis', score: .8));
    engine.emit(const WakeWordDetected(name: 'Hey Jarvis', score: .9));
    await Future<void>.delayed(const Duration(milliseconds: 10));
    expect(detected, 1);
  });

  test('unavailable engine is safe', () async {
    final unavailable = WakeWordController(UnavailableWakeWordEngine('missing'));
    await unavailable.arm();
    expect(unavailable.state, WakeWordControllerState.unavailable);
    unavailable.dispose();
  });

  test('dispose prevents restart', () async {
    controller.dispose();
    await controller.arm();
    expect(engine.starts, 0);
    expect(controller.state, WakeWordControllerState.disposed);
  });

  test('old async arm completion cannot overwrite suspend', () async {
    final started = Completer<void>();
    engine.startHook = () => started.future;
    final arm = controller.arm();
    await Future<void>.delayed(Duration.zero);
    await controller.suspend();
    started.complete();
    await arm;
    expect(controller.state, WakeWordControllerState.suspended);
  });
}
