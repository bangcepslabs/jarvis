import 'dart:async';
import 'dart:typed_data';
import 'package:audioplayers/audioplayers.dart';
import 'package:cross_file/cross_file.dart';
import 'package:flutter/foundation.dart';
import 'package:record/record.dart';
import '../../../core/network/jarvis_api_client.dart';
import '../../voice/pcm_wav.dart';
import '../../voice/voice_activity_detector.dart';
import '../../voice/wake_word_detector.dart';
import '../domain/avatar_state.dart';
import '../lip_sync/lip_sync_analyzer.dart';
import '../lip_sync/lip_sync_playback_controller.dart';

enum VoiceMode { manual, continuous }

class ContinuousVoiceConfig {
  const ContinuousVoiceConfig({
    this.maxUtterance = const Duration(seconds: 30),
    this.idleTimeout = const Duration(seconds: 12),
    this.preroll = const Duration(milliseconds: 300),
    this.resumeCooldown = const Duration(milliseconds: 300),
  });
  final Duration maxUtterance, idleTimeout, preroll, resumeCooldown;
}

class AvatarController extends ChangeNotifier {
  AvatarController(
    this.api, {
    WakeWordDetector? detector,
    this.continuousConfig = const ContinuousVoiceConfig(),
  }) {
    _wakeWordDetector = detector;
    _lipSync.mouthOpen.addListener(_onMouthOpenChanged);
    if (detector != null) {
      _wakeWordSubscription = detector.events.listen(_onWakeWordEvent);
      _armWakeWord();
    }
  }
  final JarvisApiClient api;
  final ContinuousVoiceConfig continuousConfig;
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
  VoiceMode mode = VoiceMode.manual;
  bool continuousSessionActive = false;
  bool _recording = false, _processing = false, _wakeWordArmed = false;
  int _generation = 0;
  StreamSubscription<WakeWordEvent>? _wakeWordSubscription;
  StreamSubscription<Uint8List>? _pcmSubscription;
  Timer? _idleTimer, _maxUtteranceTimer;
  final VoiceActivityDetector _vad = VoiceActivityDetector();
  final List<int> _ring = [], _utterance = [];
  DateTime? _utteranceStarted;
  bool get isRecording => _recording;
  double get mouthOpen => _lipSync.mouthOpen.value;
  VoiceActivityDetector get vad => _vad;
  void _onMouthOpenChanged() => notifyListeners();

  Future<void> _armWakeWord() async {
    if (_wakeWordDetector == null ||
        _wakeWordArmed ||
        _recording ||
        state != AvatarState.idle ||
        continuousSessionActive)
      return;
    try {
      await _wakeWordDetector!.start();
      _wakeWordArmed = true;
    } on Object catch (e) {
      _wakeWordArmed = false;
      errorMessage = 'Wake word unavailable: $e';
      notifyListeners();
    }
  }

  Future<void> _pauseWakeWord() async {
    _wakeWordArmed = false;
    await _wakeWordDetector?.stop();
  }

  Future<void> _onWakeWordEvent(WakeWordEvent e) async {
    if (e is WakeWordError || e is! WakeWordDetected || !_wakeWordArmed) return;
    await _pauseWakeWord();
    await startContinuousConversation();
  }

  /// Preserves the existing one-shot recording behavior.
  Future<void> toggleRecording() async {
    if (continuousSessionActive) {
      await cancelContinuousConversation();
      return;
    }
    if (_recording) {
      final path = await _recorder.stop();
      _recording = false;
      notifyListeners();
      if (path != null) await _run(await XFile(path).readAsBytes());
      return;
    }
    await _pauseWakeWord();
    await _startManualRecording();
  }

  Future<void> _startManualRecording() async {
    if (!await _recorder.hasPermission())
      return _fail('Microphone permission required');
    mode = VoiceMode.manual;
    state = AvatarState.listening;
    _recording = true;
    errorMessage = null;
    notifyListeners();
    try {
      await _recorder.start(
        const RecordConfig(
          encoder: AudioEncoder.wav,
          sampleRate: 16000,
          numChannels: 1,
        ),
        path: 'recording.wav',
      );
    } on Object catch (e) {
      _recording = false;
      _fail(e.toString());
    }
  }

  Future<void> startContinuousConversation() async {
    if (continuousSessionActive || _processing) return;
    if (!await _recorder.hasPermission()) {
      _fail('Microphone permission required');
      return;
    }
    await _pauseWakeWord();
    mode = VoiceMode.continuous;
    continuousSessionActive = true;
    _generation++;
    errorMessage = null;
    _vad.reset();
    _ring.clear();
    _utterance.clear();
    _processing = false;
    state = AvatarState.listening;
    notifyListeners();
    await _startContinuousCapture(_generation);
  }

  Future<void> _startContinuousCapture(int generation) async {
    if (!continuousSessionActive || generation != _generation || _processing)
      return;
    _vad.reset();
    _ring.clear();
    _utterance.clear();
    _utteranceStarted = null;
    _armIdleTimeout(generation);
    try {
      final stream = await _recorder.startStream(
        const RecordConfig(
          encoder: AudioEncoder.pcm16bits,
          sampleRate: 16000,
          numChannels: 1,
          streamBufferSize: 640,
        ),
      );
      _recording = true;
      notifyListeners();
      _pcmSubscription = stream.listen(
        (c) => _onPcm(generation, c),
        onError: (Object e, StackTrace _) => _continuousError(generation, e),
      );
    } on Object catch (e) {
      _continuousError(generation, e);
    }
  }

  void _onPcm(int generation, Uint8List chunk) {
    if (!continuousSessionActive || generation != _generation || _processing)
      return;
    final wasSpeaking = _utteranceStarted != null;
    final maxRing = 16000 * continuousConfig.preroll.inMilliseconds ~/ 1000 * 2;
    _ring.addAll(chunk);
    if (_ring.length > maxRing) _ring.removeRange(0, _ring.length - maxRing);
    for (final event in _vad.process(chunk)) {
      if (event.type == VadEventType.speechStarted && !_processing) {
        _utterance.addAll(_ring);
        _utteranceStarted = DateTime.now();
        _idleTimer?.cancel();
        _maxUtteranceTimer = Timer(
          continuousConfig.maxUtterance,
          () => _finishUtterance(generation),
        );
        notifyListeners();
      }
      if (event.type == VadEventType.speechEnded)
        unawaited(_finishUtterance(generation));
    }
    // A native chunk can contain several VAD frames; append it once, not once
    // per event, otherwise audio is duplicated at chunk boundaries.
    if (wasSpeaking) _utterance.addAll(chunk);
  }

  Future<void> _finishUtterance(int generation) async {
    if (!continuousSessionActive ||
        generation != _generation ||
        _processing ||
        _utteranceStarted == null)
      return;
    _processing = true;
    _maxUtteranceTimer?.cancel();
    _idleTimer?.cancel();
    final pcm = Uint8List.fromList(_utterance);
    _utterance.clear();
    _utteranceStarted = null;
    await _stopCapture();
    if (pcm.length < 16000 * 2 * 0.2) {
      _processing = false;
      await _startContinuousCapture(generation);
      return;
    }
    state = AvatarState.thinking;
    notifyListeners();
    try {
      final text = (await api.transcribe(pcm16MonoToWav(pcm))).trim();
      if (text.isNotEmpty && text.length >= 2)
        await _completeTurn(text, generation);
      else if (continuousSessionActive && generation == _generation) {
        _processing = false;
        state = AvatarState.listening;
        notifyListeners();
        await _startContinuousCapture(generation);
      }
    } on Object catch (e) {
      _continuousError(generation, e);
    }
  }

  Future<void> _completeTurn(String text, int generation) async {
    if (!continuousSessionActive || generation != _generation) return;
    reply = await api.chat(text, conversationId);
    final audio = await api.synthesize(reply);
    if (!continuousSessionActive || generation != _generation) return;
    state = AvatarState.speaking;
    notifyListeners();
    final completion = _player.onPlayerComplete.first;
    await _lipSync.play(
      envelope: _lipSyncAnalyzer.analyzeWav(audio),
      audioBytes: audio,
    );
    await completion;
    _lipSync.mouthOpen.value = 0;
    if (continuousSessionActive && generation == _generation) {
      await Future<void>.delayed(continuousConfig.resumeCooldown);
      _processing = false;
      state = AvatarState.listening;
      notifyListeners();
      await _startContinuousCapture(generation);
    }
  }

  void _armIdleTimeout(int generation) {
    _idleTimer?.cancel();
    _idleTimer = Timer(
      continuousConfig.idleTimeout,
      () => cancelContinuousConversation(generation: generation),
    );
  }

  Future<void> cancelContinuousConversation({
    int? generation,
    bool preserveError = false,
  }) async {
    if (!continuousSessionActive ||
        (generation != null && generation != _generation))
      return;
    continuousSessionActive = false;
    _generation++;
    _processing = false;
    _idleTimer?.cancel();
    _maxUtteranceTimer?.cancel();
    await _stopCapture();
    _vad.reset();
    _utterance.clear();
    _ring.clear();
    _lipSync.mouthOpen.value = 0;
    state = preserveError ? AvatarState.error : AvatarState.idle;
    if (!preserveError) errorMessage = null;
    notifyListeners();
  }

  Future<void> _stopCapture() async {
    await _pcmSubscription?.cancel();
    _pcmSubscription = null;
    if (_recording) {
      await _recorder.stop();
      _recording = false;
    }
  }

  void _continuousError(int generation, Object e) {
    if (generation != _generation || !continuousSessionActive) return;
    errorMessage = e.toString().replaceFirst('Exception: ', '');
    unawaited(
      cancelContinuousConversation(generation: generation, preserveError: true),
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
      if (text.trim().isEmpty) return _fail('No speech detected');
      reply = await api.chat(text.trim(), conversationId);
      final audio = await api.synthesize(reply);
      state = AvatarState.speaking;
      notifyListeners();
      final completion = _player.onPlayerComplete.first;
      await _lipSync.play(
        envelope: _lipSyncAnalyzer.analyzeWav(audio),
        audioBytes: audio,
      );
      await completion;
      state = AvatarState.idle;
      notifyListeners();
    } on Object catch (e) {
      _fail(e.toString().replaceFirst('Exception: ', ''));
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
    _idleTimer?.cancel();
    _maxUtteranceTimer?.cancel();
    _pcmSubscription?.cancel();
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
  Stream<Duration> get positionStream => player.onPositionChanged;
  Stream<void> get completionStream => player.onPlayerComplete.map((_) {});
  Future<void> play(Uint8List audioBytes) =>
      player.play(BytesSource(audioBytes));
  Future<void> stop() => player.stop();
}
