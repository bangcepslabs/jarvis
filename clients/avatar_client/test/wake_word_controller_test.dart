import 'package:flutter_test/flutter_test.dart';
import 'package:avatar_client/features/avatar/wake/wake_word_engine.dart';

class FakeWakeWordEngine implements WakeWordEngine {
  FakeWakeWordEngine(this.available);
  final bool available;
  WakeWordCallback? callback;
  @override bool get isAvailable => available;
  @override Future<void> start(WakeWordCallback onDetected) async => callback = onDetected;
  @override Future<void> pause() async {}
  @override Future<void> resume() async {}
  @override Future<void> stop() async {}
  @override Future<void> dispose() async {}
}

void main() {
  test('unavailable engine is safe', () async {
    final engine = FakeWakeWordEngine(false);
    var detected = 0;
    final controller = WakeWordController(engine: engine, onDetected: () => detected++);
    await controller.setEnabled(true);
    expect(controller.status, WakeWordStatus.unavailable);
    expect(detected, 0);
  });

  test('only listening events are forwarded', () async {
    final engine = FakeWakeWordEngine(true);
    var detected = 0;
    final controller = WakeWordController(engine: engine, onDetected: () => detected++);
    await controller.setEnabled(true);
    await engine.callback!();
    expect(detected, 1);
    await controller.pause();
    await engine.callback!();
    expect(detected, 1);
    await controller.resume();
    await engine.callback!();
    expect(detected, 2);
  });

  test('disable invalidates an in-flight event', () async {
    final engine = FakeWakeWordEngine(true);
    var detected = 0;
    final controller = WakeWordController(engine: engine, onDetected: () => detected++);
    await controller.setEnabled(true);
    final callback = engine.callback!;
    await controller.setEnabled(false);
    await callback();
    expect(detected, 0);
  });
}
