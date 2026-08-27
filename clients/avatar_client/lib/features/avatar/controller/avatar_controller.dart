import 'dart:async';

import 'package:audioplayers/audioplayers.dart';
import 'package:cross_file/cross_file.dart';
import 'package:flutter/foundation.dart';
import 'package:record/record.dart';
import '../../../core/network/jarvis_api_client.dart';
import '../domain/avatar_state.dart';
import '../lip_sync/lip_sync_analyzer.dart';
import '../lip_sync/lip_sync_playback_controller.dart';
import '../../voice/wake_word_detector.dart';

class AvatarController extends ChangeNotifier {
  AvatarController(this.api, {WakeWordDetector? detector}) {
    _wakeWordDetector = detector;
    _lipSync.mouthOpen.addListener(_onMouthOpenChanged);
    final configuredDetector = _wakeWordDetector;
    if (configuredDetector != null) {
      _wakeWordSubscription = configuredDetector.events.listen(_onWakeWordEvent);
      _armWakeWord();
    }
  }
  final JarvisApiClient api;
  late final WakeWordDetector? _wakeWordDetector;
  final AudioRecorder _recorder = AudioRecorder();
  final AudioPlayer _player = AudioPlayer();
  final LipSyncAnalyzer _lipSyncAnalyzer = const LipSyncAnalyzer();
  late final LipSyncPlaybackController _lipSync = LipSyncPlaybackController(
    _AudioPlayerLipSyncSource(_player),
  );
  AvatarState state = AvatarState.idle;
  String conversationId = 'avatar-${DateTime.now().millisecondsSinceEpoch}';
  String reply = '';
  String? errorMessage;
  bool _recording = false;
  bool _wakeWordArmed = false;
  StreamSubscription<WakeWordEvent>? _wakeWordSubscription;
  bool get isRecording => _recording;
  double get mouthOpen => _lipSync.mouthOpen.value;

  void _onMouthOpenChanged() => notifyListeners();

  Future<void> _armWakeWord() async {
    if (_wakeWordDetector == null || _wakeWordArmed || _recording || state != AvatarState.idle) return;
    try {
      await _wakeWordDetector.start();
      _wakeWordArmed = true;
    } on Object catch (error) {
      _wakeWordArmed = false;
      errorMessage = 'Wake word unavailable: $error';
      notifyListeners();
    }
  }

  Future<void> _pauseWakeWord() async {
    _wakeWordArmed = false;
    await _wakeWordDetector?.stop();
  }

  Future<void> _onWakeWordEvent(WakeWordEvent event) async {
    if (event is WakeWordError || event is! WakeWordDetected || !_wakeWordArmed) return;
    await _pauseWakeWord();
    await _startRecording();
  }

  Future<void> toggleRecording() async {
    if (_recording) {
      final path = await _recorder.stop();
      _recording = false;
      notifyListeners();
      if (path != null) await _run(await XFile(path).readAsBytes());
      return;
    }
    await _pauseWakeWord();
    await _startRecording();
  }

  Future<void> _startRecording() async {
    if (!await _recorder.hasPermission()) return _fail('Microphone permission required');
    state = AvatarState.listening;
    _recording = true;
    errorMessage = null;
    notifyListeners();
    await _recorder.start(
      const RecordConfig(encoder: AudioEncoder.wav, sampleRate: 16000, numChannels: 1),
      path: 'recording.wav',
    );
  }

  Future<void> sendText(String text) async {
    if (text.trim().isNotEmpty) await _run(Uint8List(0), typed: text.trim());
  }

  Future<void> _run(Uint8List bytes, {String? typed}) async {
    try {
      state = AvatarState.thinking;
      notifyListeners();
      final text = typed ?? await api.transcribe(bytes);
      if (text.isEmpty) return _fail('No speech detected');
      reply = await api.chat(text, conversationId);
      final audio = await api.synthesize(reply);
      final envelope = _lipSyncAnalyzer.analyzeWav(audio);
      state = AvatarState.speaking;
      notifyListeners();
      final completion = _player.onPlayerComplete.first;
      await _lipSync.play(envelope: envelope, audioBytes: audio);
      await completion;
      state = AvatarState.idle;
      notifyListeners();
    } catch (error) {
      _fail(error.toString().replaceFirst('Exception: ', ''));
    } finally {
      await _armWakeWord();
    }
  }

  void _fail(String message) {
    state = AvatarState.error;
    errorMessage = message;
    _recording = false;
    notifyListeners();
  }

  @override
  void dispose() {
    _recorder.dispose();
    _wakeWordSubscription?.cancel();
    _wakeWordDetector?.dispose();
    _lipSync.mouthOpen.removeListener(_onMouthOpenChanged);
    _lipSync.dispose();
    _player.dispose();
    api.dispose();
    super.dispose();
  }
}

final class _AudioPlayerLipSyncSource implements LipSyncPlaybackSource {
  const _AudioPlayerLipSyncSource(this.player);

  final AudioPlayer player;

  @override
  Stream<Duration> get positionStream => player.onPositionChanged;

  @override
  Stream<void> get completionStream => player.onPlayerComplete.map((_) {});

  @override
  Future<void> play(Uint8List audioBytes) => player.play(BytesSource(audioBytes));

  @override
  Future<void> stop() => player.stop();
}




