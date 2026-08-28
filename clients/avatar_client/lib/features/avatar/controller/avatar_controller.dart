import 'package:audioplayers/audioplayers.dart';
import 'package:cross_file/cross_file.dart';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:record/record.dart';
import '../../../core/network/jarvis_api_client.dart';
import '../domain/avatar_state.dart';
import '../domain/avatar_presentation_hint.dart';
import '../domain/character_reaction_policy.dart';
import '../lip_sync/lip_sync_analyzer.dart';
import '../lip_sync/lip_sync_playback_controller.dart';

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
  DateTime? _recordingStartedAt;
  bool get isRecording => _recording;
  ValueListenable<double> get mouthOpen => _lipSync.mouthOpen;

  Future<void> toggleRecording() async {
    if (_recording) {
      try {
        final path = await _recorder.stop();
        _recording = false;
        notifyListeners();
        final recordingElapsed = _recordingStartedAt == null
            ? null
            : DateTime.now().difference(_recordingStartedAt!);
        _recordingStartedAt = null;
        if (path == null) return _fail('음성 녹음 파일이 생성되지 않았어요.');
        final file = File(path);
        if (!await file.exists()) return _fail('음성 녹음 파일을 찾을 수 없어요.');
        try {
          await _run(
            await XFile(path).readAsBytes(),
            recordingElapsed: recordingElapsed,
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
        _fail('Recording failed: ${error.toString().replaceFirst('Exception: ', '')}');
      }
      return;
    }
    if (!await _recorder.hasPermission()) return _fail('Microphone permission required');
    state = AvatarState.listening;
    _recording = true;
    errorMessage = null;
    notifyListeners();
    try {
      final path = '${Directory.systemTemp.path}${Platform.pathSeparator}jarvis-recording-${DateTime.now().microsecondsSinceEpoch}.wav';
      await _recorder.start(
        const RecordConfig(encoder: AudioEncoder.wav, sampleRate: 16000, numChannels: 1),
        path: path,
      );
      _recordingStartedAt = DateTime.now();
    } catch (error) {
      _recording = false;
      _fail('녹음에 실패했어요: ${error.toString().replaceFirst('Exception: ', '')}');
    }
  }

  Future<void> sendText(String text) async {
    if (text.trim().isNotEmpty) await _run(Uint8List(0), typed: text.trim());
  }

  Future<void> _run(Uint8List bytes, {String? typed, Duration? recordingElapsed}) async {
    final generation = ++_presentationGeneration;
    final totalTimer = Stopwatch()..start();
    Duration? sttElapsed;
    Duration? chatElapsed;
    Duration? ttsElapsed;
    Duration? lipSyncElapsed;
    await _lipSync.stop();
    try {
      state = AvatarState.thinking;
      notifyListeners();
      String text;
      if (typed != null) {
        text = typed;
      } else {
        final timer = Stopwatch()..start();
        text = await api.transcribe(bytes);
        timer.stop();
        sttElapsed = timer.elapsed;
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
      final audioFuture = api.synthesize(reply, presentationHint: presentationHint);
      if (plan.preSpeechDelay > Duration.zero) await Future<void>.delayed(plan.preSpeechDelay);
      if (generation != _presentationGeneration) return;
      final ttsTimer = Stopwatch()..start();
      final audio = await audioFuture;
      ttsTimer.stop();
      ttsElapsed = ttsTimer.elapsed;
      if (generation != _presentationGeneration) return;
      state = AvatarState.speaking;
      notifyListeners();
      final lipSyncTimer = Stopwatch()..start();
      await _playAudioWithLipSync(audio);
      lipSyncTimer.stop();
      lipSyncElapsed = lipSyncTimer.elapsed;
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
        debugPrint(
          '[voice_latency] recording_finalize=${_formatDuration(recordingElapsed)} '
          'stt=${_formatDuration(sttElapsed)} '
          'chat=${_formatDuration(chatElapsed)} '
          'tts=${_formatDuration(ttsElapsed)} '
          'time_to_first_audio=${_formatDuration(lipSyncElapsed)} '
          'processing=${_formatDuration(totalTimer.elapsed)}',
        );
      }
    }
  }

  String _formatDuration(Duration? duration) =>
      duration == null ? 'skipped' : '${duration.inMilliseconds}ms';

  Future<void> _playAudioWithLipSync(Uint8List audio) async {
    try {
      final envelope = _lipSyncAnalyzer.analyzeWav(audio);
      await _lipSync.play(envelope: envelope, audioBytes: audio);
    } catch (error) {
      debugPrint('JARVIS_LIPSYNC analyzer/playback bridge skipped: $error');
      await _lipSync.stop();
      await _player.play(BytesSource(audio));
    }
  }

  void _fail(String message) {
    _lipSync.reset();
    state = AvatarState.error;
    errorMessage = message;
    _recording = false;
    notifyListeners();
  }

  @override
  void dispose() {
    _presentationGeneration++;
    _lipSync.dispose();
    _recorder.dispose();
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




