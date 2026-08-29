import 'package:audioplayers/audioplayers.dart';
import 'package:cross_file/cross_file.dart';
import 'dart:io';
import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:record/record.dart';
import '../../../core/network/jarvis_api_client.dart';
import '../domain/avatar_state.dart';
import '../domain/avatar_presentation_hint.dart';
import '../domain/character_reaction_policy.dart';
import '../lip_sync/lip_sync_analyzer.dart';
import '../lip_sync/lip_sync_playback_controller.dart';
import '../voice/voice_activity_detector.dart';

class AvatarController extends ChangeNotifier {
  AvatarController(this.api) {
    _lipSync = LipSyncPlaybackController(_AudioPlayerLipSyncSource(_player));
  }
  final JarvisApiClient api;
  final AudioRecorder _recorder = AudioRecorder();
  final AudioPlayer _player = AudioPlayer();
  late final LipSyncPlaybackController _lipSync;
  final LipSyncAnalyzer _lipSyncAnalyzer = const LipSyncAnalyzer();
  AvatarState state = AvatarState.idle;
  String conversationId = 'avatar-${DateTime.now().millisecondsSinceEpoch}';
  String reply = '';
  String? errorMessage;
  AvatarPresentationHint presentationHint = const AvatarPresentationHint();
  final CharacterReactionPolicy reactionPolicy = const CharacterReactionPolicy();
  int _presentationGeneration = 0;
  bool _recording = false;
  bool _stopInProgress = false;
  StreamSubscription<Amplitude>? _amplitudeSubscription;
  Stopwatch? _recordingElapsed;
  VoiceActivityDetector? _voiceActivityDetector;
  bool get isRecording => _recording;
  ValueListenable<double> get mouthOpen => _lipSync.mouthOpen;

  Future<void> toggleRecording() async {
    if (_recording) {
      await _stopRecording(submit: true);
      return;
    }
    if (!await _recorder.hasPermission()) return _fail('Microphone permission required');
    state = AvatarState.listening;
    _recording = true;
    _stopInProgress = false;
    _voiceActivityDetector = VoiceActivityDetector();
    _recordingElapsed = Stopwatch()..start();
    errorMessage = null;
    notifyListeners();
    try {
      final path = '${Directory.systemTemp.path}${Platform.pathSeparator}jarvis-recording-${DateTime.now().microsecondsSinceEpoch}.wav';
      await _recorder.start(
        const RecordConfig(encoder: AudioEncoder.wav, sampleRate: 16000, numChannels: 1),
        path: path,
      );
      _amplitudeSubscription = _recorder
          .onAmplitudeChanged(const Duration(milliseconds: 100))
          .listen(_handleAmplitude, onError: (_) => _stopRecording(submit: false));
    } catch (error) {
      _recording = false;
      _recordingElapsed?.stop();
      _recordingElapsed = null;
      _fail('녹음에 실패했어요: ${error.toString().replaceFirst('Exception: ', '')}');
    }
  }

  void _handleAmplitude(Amplitude amplitude) {
    if (!_recording || _stopInProgress || _recordingElapsed == null || _voiceActivityDetector == null) return;
    final decision = _voiceActivityDetector!.process(amplitude.current, _recordingElapsed!.elapsed);
    if (decision.event == VoiceActivityEvent.speechStarted) {
      // Keep the existing recording UI; the separate detector state is not AvatarState.
      notifyListeners();
    } else if (decision.event == VoiceActivityEvent.speechEnded || decision.event == VoiceActivityEvent.maximumDurationReached) {
      unawaited(_stopRecording(submit: decision.speechDetected));
    }
  }

  Future<void> _stopRecording({required bool submit}) async {
    if (!_recording || _stopInProgress) return;
    _stopInProgress = true;
    await _amplitudeSubscription?.cancel();
    _amplitudeSubscription = null;
    _recordingElapsed?.stop();
    _recordingElapsed = null;
    try {
      final turnTimer = Stopwatch()..start();
      final path = await _recorder.stop();
      _recording = false;
      _stopInProgress = false;
      notifyListeners();
      if (!submit) {
        state = AvatarState.idle;
        notifyListeners();
        return;
      }
      final recorderStopElapsed = turnTimer.elapsed;
      if (path == null) return _fail('음성 녹음 파일이 생성되지 않았어요.');
      final file = File(path);
      if (!await file.exists()) return _fail('음성 녹음 파일을 찾을 수 없어요.');
      try {
        await _run(
          await XFile(path).readAsBytes(),
          turnTimer: turnTimer,
          recorderStopElapsed: recorderStopElapsed,
          recordingFinalizeElapsed: turnTimer.elapsed,
        );
      } finally {
        try {
          await file.delete();
        } catch (_) {
          // Temporary recording cleanup must not mask the conversation result.
        }
      }
    } catch (error) {
      _recording = false;
      _stopInProgress = false;
      _fail('Recording failed: ${error.toString().replaceFirst('Exception: ', '')}');
    }
  }

  Future<void> sendText(String text) async {
    if (text.trim().isNotEmpty) await _run(Uint8List(0), typed: text.trim());
  }

  Future<void> _run(
    Uint8List bytes, {
    String? typed,
    Stopwatch? turnTimer,
    Duration? recorderStopElapsed,
    Duration? recordingFinalizeElapsed,
  }) async {
    final generation = ++_presentationGeneration;
    final totalTimer = turnTimer ?? (Stopwatch()..start());
    Duration? sttElapsed;
    Map<String, int> sttServerTiming = const {};
    Duration? chatElapsed;
    Duration? ttsElapsed;
    int? serverTtsMs;
    Duration? processingElapsed;
    Duration? playbackStartElapsed;
    await _lipSync.stop();
    try {
      state = AvatarState.thinking;
      notifyListeners();
      String text;
      if (typed != null) {
        text = typed;
      } else {
        final timer = Stopwatch()..start();
        final transcription = await api.transcribe(bytes);
        timer.stop();
        sttElapsed = timer.elapsed;
        sttServerTiming = transcription.timing;
        text = transcription.text;
      }
      if (generation != _presentationGeneration) return;
      if (text.isEmpty) return _fail('음성을 인식하지 못했어요. 다시 말씀해 주세요.');
      final chatTimer = Stopwatch()..start();
      final chat = await api.chat(text, conversationId, responseMode: typed == null ? 'voice' : 'text');
      chatTimer.stop();
      chatElapsed = chatTimer.elapsed;
      if (generation != _presentationGeneration) return;
      reply = chat.reply;
      presentationHint = chat.presentationHint;
      final plan = reactionPolicy.plan(presentationHint, AvatarState.speaking);
      final ttsTimer = Stopwatch()..start();
      final audioFuture = api.synthesize(reply, presentationHint: presentationHint).then((result) {
        ttsTimer.stop();
        ttsElapsed = ttsTimer.elapsed;
        processingElapsed = totalTimer.elapsed;
        serverTtsMs = result.serverTtsMs;
        return result;
      });
      if (plan.preSpeechDelay > Duration.zero) await Future<void>.delayed(plan.preSpeechDelay);
      if (generation != _presentationGeneration) return;
      final synthesis = await audioFuture;
      if (generation != _presentationGeneration) return;
      state = AvatarState.speaking;
      notifyListeners();
      playbackStartElapsed = await _playAudioWithLipSync(synthesis.audio, totalTimer);
      if (generation != _presentationGeneration) return;
      if (plan.tailDuration > Duration.zero) await Future<void>.delayed(plan.tailDuration);
      if (generation != _presentationGeneration) return;
      state = AvatarState.idle;
      notifyListeners();
    } catch (error) {
      if (generation == _presentationGeneration) _fail(error.toString().replaceFirst('Exception: ', ''));
    } finally {
      totalTimer.stop();
      if (kDebugMode) {
        final playbackStartDelay = playbackStartElapsed != null && processingElapsed != null
            ? playbackStartElapsed - processingElapsed!
            : null;
        debugPrint(
          '[voice_latency] recorder_stop=${_formatDuration(recorderStopElapsed)} '
          'recording_finalize=${_formatDuration(recordingFinalizeElapsed)} '
          'stt=${_formatDuration(sttElapsed)} '
          'stt_server=${_formatTiming(sttServerTiming)} '
          'chat=${_formatDuration(chatElapsed)} '
          'tts=${_formatDuration(ttsElapsed)} '
          'tts_server=${serverTtsMs == null ? 'unknown' : '${serverTtsMs}ms'} '
          'processing=${_formatDuration(processingElapsed)} '
          'time_to_first_audio=${_formatDuration(playbackStartElapsed)} '
          'playback_start_delay=${_formatDuration(playbackStartDelay)} '
          'total=${_formatDuration(totalTimer.elapsed)}',
        );
      }
    }
  }

  String _formatDuration(Duration? duration) =>
      duration == null ? 'skipped' : '${duration.inMilliseconds}ms';

  String _formatTiming(Map<String, int> timing) => timing.isEmpty
      ? 'unavailable'
      : timing.entries
          .map(
            (entry) => entry.key == 'model_reused'
                ? '${entry.key}=${entry.value == 1}'
                : '${entry.key}=${entry.value}ms',
          )
          .join(',');

  Future<Duration?> _playAudioWithLipSync(Uint8List audio, Stopwatch turnTimer) async {
    final playbackStarted = _player.onPlayerStateChanged
        .where((state) => state == PlayerState.playing)
        .first;
    try {
      final envelope = _lipSyncAnalyzer.analyzeWav(audio);
      await _lipSync.play(envelope: envelope, audioBytes: audio);
    } catch (error) {
      debugPrint('JARVIS_LIPSYNC analyzer/playback bridge skipped: $error');
      await _lipSync.stop();
      await _player.play(BytesSource(audio));
    }
    try {
      await playbackStarted.timeout(const Duration(seconds: 2));
      return turnTimer.elapsed;
    } catch (_) {
      return null;
    }
  }

  void _fail(String message) {
    _lipSync.reset();
    state = AvatarState.error;
    errorMessage = message;
    _recording = false;
    _stopInProgress = false;
    _amplitudeSubscription?.cancel();
    _amplitudeSubscription = null;
    notifyListeners();
  }

  @override
  void dispose() {
    _presentationGeneration++;
    _lipSync.dispose();
    _recorder.dispose();
    _amplitudeSubscription?.cancel();
    _player.dispose();
    api.dispose();
    super.dispose();
  }
}

class _AudioPlayerLipSyncSource implements LipSyncPlaybackSource {
  const _AudioPlayerLipSyncSource(this.player);

  final AudioPlayer player;

  @override
  Stream<Duration> get positionStream => player.onPositionChanged;

  @override
  Stream<void> get completionStream => player.onPlayerComplete.map<void>((_) {});

  @override
  Future<void> play(Uint8List audioBytes) => player.play(BytesSource(audioBytes));

  @override
  Future<void> stop() => player.stop();
}




