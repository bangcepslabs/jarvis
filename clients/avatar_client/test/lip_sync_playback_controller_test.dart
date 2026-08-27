import 'dart:async';
import 'dart:typed_data';

import 'package:avatar_client/features/avatar/lip_sync/lip_sync_envelope.dart';
import 'package:avatar_client/features/avatar/lip_sync/lip_sync_playback_controller.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  late FakePlaybackSource source;
  late LipSyncPlaybackController controller;
  final envelope = LipSyncEnvelope(
    duration: const Duration(milliseconds: 120),
    frames: const [
      LipSyncFrame(timestamp: Duration.zero, mouthOpen: 0.2),
      LipSyncFrame(timestamp: Duration(milliseconds: 60), mouthOpen: 0.8),
    ],
  );

  setUp(() {
    source = FakePlaybackSource();
    controller = LipSyncPlaybackController(source);
  });

  tearDown(() {
    controller.dispose();
    source.dispose();
  });

  test(
    'starts at zero before playback',
    () => expect(controller.mouthOpen.value, 0),
  );

  test('uses position lookup and interpolation', () async {
    await controller.play(envelope: envelope, audioBytes: Uint8List(0));
    source.emitPosition(Duration.zero);
    await pumpEventQueue();
    expect(controller.mouthOpen.value, closeTo(0.2, .001));
    source.emitPosition(const Duration(milliseconds: 30));
    await pumpEventQueue();
    expect(controller.mouthOpen.value, closeTo(0.5, .001));
    source.emitPosition(const Duration(milliseconds: 60));
    await pumpEventQueue();
    expect(controller.mouthOpen.value, closeTo(0.8, .001));
  });

  test('position after duration resets to zero', () async {
    await controller.play(envelope: envelope, audioBytes: Uint8List(0));
    source.emitPosition(const Duration(milliseconds: 121));
    await pumpEventQueue();
    expect(controller.mouthOpen.value, 0);
    expect(controller.isPlaying, isFalse);
  });

  test('completion resets to zero', () async {
    await controller.play(envelope: envelope, audioBytes: Uint8List(0));
    source.emitPosition(const Duration(milliseconds: 60));
    await pumpEventQueue();
    source.complete();
    await pumpEventQueue();
    expect(controller.mouthOpen.value, 0);
  });

  test('stop resets to zero', () async {
    await controller.play(envelope: envelope, audioBytes: Uint8List(0));
    source.emitPosition(const Duration(milliseconds: 60));
    await pumpEventQueue();
    await controller.stop();
    expect(controller.mouthOpen.value, 0);
  });

  test('position stream error resets to zero', () async {
    await controller.play(envelope: envelope, audioBytes: Uint8List(0));
    source.emitPosition(const Duration(milliseconds: 60));
    await pumpEventQueue();
    source.failPosition();
    await pumpEventQueue();
    expect(controller.mouthOpen.value, 0);
  });

  test('dispose resets to zero and rejects new playback', () async {
    await controller.play(envelope: envelope, audioBytes: Uint8List(0));
    source.emitPosition(const Duration(milliseconds: 60));
    await pumpEventQueue();
    controller.dispose();
    expect(controller.mouthOpen.value, 0);
    expect(
      () => controller.play(envelope: envelope, audioBytes: Uint8List(0)),
      throwsStateError,
    );
  });

  test('new playback replaces the previous envelope', () async {
    final replacement = LipSyncEnvelope(
      duration: const Duration(milliseconds: 120),
      frames: const [LipSyncFrame(timestamp: Duration.zero, mouthOpen: 0.9)],
    );
    await controller.play(envelope: envelope, audioBytes: Uint8List(0));
    source.emitPosition(const Duration(milliseconds: 60));
    await pumpEventQueue();
    await controller.play(envelope: replacement, audioBytes: Uint8List(0));
    source.emitPosition(Duration.zero);
    await pumpEventQueue();
    expect(controller.mouthOpen.value, closeTo(0.9, .001));
  });

  test('stale position from replaced playback is ignored', () async {
    await controller.play(envelope: envelope, audioBytes: Uint8List(0));
    final stalePosition = source.positions.listeners.last;
    await controller.play(envelope: envelope, audioBytes: Uint8List(0));
    source.emitPosition(const Duration(milliseconds: 60));
    await pumpEventQueue();
    final currentValue = controller.mouthOpen.value;
    stalePosition(Duration.zero);
    expect(controller.mouthOpen.value, currentValue);
  });

  test('stale completion from replaced playback is ignored', () async {
    await controller.play(envelope: envelope, audioBytes: Uint8List(0));
    final staleCompletion = source.completions.listeners.last;
    await controller.play(envelope: envelope, audioBytes: Uint8List(0));
    source.emitPosition(const Duration(milliseconds: 60));
    await pumpEventQueue();
    staleCompletion(null);
    expect(controller.mouthOpen.value, greaterThan(0));
    expect(controller.isPlaying, isTrue);
  });

  test('stale error from replaced playback is ignored', () async {
    await controller.play(envelope: envelope, audioBytes: Uint8List(0));
    final staleError = source.positions.errorListeners.last;
    await controller.play(envelope: envelope, audioBytes: Uint8List(0));
    source.emitPosition(const Duration(milliseconds: 60));
    await pumpEventQueue();
    staleError(Exception('stale error'));
    expect(controller.mouthOpen.value, greaterThan(0));
    expect(controller.isPlaying, isTrue);
  });

  test('current playback events are processed normally', () async {
    await controller.play(envelope: envelope, audioBytes: Uint8List(0));
    source.emitPosition(const Duration(milliseconds: 60));
    await pumpEventQueue();
    expect(controller.mouthOpen.value, closeTo(0.8, .001));
    source.complete();
    await pumpEventQueue();
    expect(controller.mouthOpen.value, 0);
  });

  test('published values stay clamped', () async {
    final extreme = LipSyncEnvelope(
      duration: const Duration(seconds: 1),
      frames: const [
        LipSyncFrame(timestamp: Duration.zero, mouthOpen: double.infinity),
      ],
    );
    await controller.play(envelope: extreme, audioBytes: Uint8List(0));
    source.emitPosition(Duration.zero);
    await pumpEventQueue();
    expect(controller.mouthOpen.value, inInclusiveRange(0, 1));
  });

  test('silence envelope remains zero', () async {
    final silence = LipSyncEnvelope(
      duration: const Duration(seconds: 1),
      frames: const [LipSyncFrame(timestamp: Duration.zero, mouthOpen: 0)],
    );
    await controller.play(envelope: silence, audioBytes: Uint8List(0));
    source.emitPosition(const Duration(milliseconds: 30));
    await pumpEventQueue();
    expect(controller.mouthOpen.value, 0);
  });

  test('playback failure resets to zero', () async {
    source.shouldFailPlay = true;
    await expectLater(
      controller.play(envelope: envelope, audioBytes: Uint8List(0)),
      throwsException,
    );
    expect(controller.mouthOpen.value, 0);
    expect(controller.isPlaying, isFalse);
  });
}

class FakePlaybackSource implements LipSyncPlaybackSource {
  final positions = StickyStream<Duration>();
  final completions = StickyStream<void>();
  bool shouldFailPlay = false;
  int playCount = 0;
  @override
  Stream<Duration> get positionStream => positions;
  @override
  Stream<void> get completionStream => completions;
  @override
  Future<void> play(Uint8List audioBytes) async {
    playCount++;
    if (shouldFailPlay) throw Exception('playback failed');
  }

  @override
  Future<void> stop() async {}
  void emitPosition(Duration position) => positions.emit(position);
  void complete() => completions.emit(null);
  void failPosition() => positions.error(Exception('position failed'));
  void dispose() {
    positions.clear();
    completions.clear();
  }
}

class StickyStream<T> extends Stream<T> {
  final listeners = <void Function(T)>[];
  final errorListeners = <void Function(Object)>[];

  @override
  StreamSubscription<T> listen(
    void Function(T)? onData, {
    Function? onError,
    void Function()? onDone,
    bool? cancelOnError,
  }) {
    final data = onData ?? (_) {};
    final error = onError == null
        ? (_) {}
        : (Object value) => Function.apply(onError, [value]);
    listeners.add(data);
    errorListeners.add(error);
    return _NoopSubscription<T>();
  }

  void emit(T value) {
    for (final listener in List.of(listeners)) {
      listener(value);
    }
  }

  void error(Object value) {
    for (final listener in List.of(errorListeners)) {
      listener(value);
    }
  }

  void clear() {
    listeners.clear();
    errorListeners.clear();
  }
}

class _NoopSubscription<T> implements StreamSubscription<T> {
  @override
  Future<void> cancel() async {}
  @override
  bool get isPaused => false;
  @override
  void onData(void Function(T)? handleData) {}
  @override
  void onDone(void Function()? handleDone) {}
  @override
  void onError(Function? handleError) {}
  @override
  void pause([Future<void>? resumeSignal]) {}
  @override
  void resume() {}
  @override
  Future<E> asFuture<E>([E? futureValue]) => Future<E>.value(futureValue);
}
