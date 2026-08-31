import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'wake_word_engine.dart';

enum WakeWordControllerState { idle, armed, suspended, unavailable, disposed }

class WakeWordController extends ChangeNotifier {
  WakeWordController(this.engine, {this.onDetected}) { _subscription = engine.events.listen(_handle); }
  final WakeWordEngine engine;
  final Future<void> Function()? onDetected;
  StreamSubscription<WakeWordEvent>? _subscription;
  WakeWordControllerState state = WakeWordControllerState.idle;
  int _generation = 0;
  DateTime? _lastDetection;

  Future<void> arm() async {
    if (state == WakeWordControllerState.disposed || state == WakeWordControllerState.armed) return;
    final generation = ++_generation;
    try {
      await engine.start();
      if (generation != _generation || state == WakeWordControllerState.disposed) return;
      state = engine is UnavailableWakeWordEngine ? WakeWordControllerState.unavailable : WakeWordControllerState.armed;
    } on PlatformException {
      if (generation == _generation) state = WakeWordControllerState.unavailable;
    } catch (_) {
      if (generation == _generation) state = WakeWordControllerState.unavailable;
    } finally { notifyListeners(); }
  }

  Future<void> suspend() async {
    if (state == WakeWordControllerState.disposed) return;
    final generation = ++_generation;
    state = WakeWordControllerState.suspended;
    notifyListeners();
    await engine.stop();
    if (generation == _generation) notifyListeners();
  }

  Future<void> rearm() => arm();

  Future<void> _handle(WakeWordEvent event) async {
    if (event is WakeWordUnavailable) { if (state != WakeWordControllerState.disposed) { state = WakeWordControllerState.unavailable; notifyListeners(); } return; }
    if (event is WakeWordError || state != WakeWordControllerState.armed) return;
    final now = DateTime.now();
    if (_lastDetection != null && now.difference(_lastDetection!) < const Duration(seconds: 2)) return;
    _lastDetection = now;
    await suspend();
    if (state != WakeWordControllerState.suspended) return;
    await onDetected?.call();
  }

  @override
  void dispose() {
    if (state == WakeWordControllerState.disposed) return;
    ++_generation;
    state = WakeWordControllerState.disposed;
    unawaited(_subscription?.cancel());
    unawaited(engine.dispose());
    super.dispose();
  }
}
