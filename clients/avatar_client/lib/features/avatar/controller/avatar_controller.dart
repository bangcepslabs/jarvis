import 'package:audioplayers/audioplayers.dart';
import 'package:cross_file/cross_file.dart';
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
  bool get isRecording => _recording;
  ValueListenable<double> get mouthOpen => _lipSync.mouthOpen;

  Future<void> toggleRecording() async {
    if (_recording) {
      final path = await _recorder.stop();
      _recording = false;
      notifyListeners();
      if (path != null) await _run(await XFile(path).readAsBytes());
      return;
    }
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
    final generation = ++_presentationGeneration;
    await _lipSync.stop();
    try {
      state = AvatarState.thinking;
      notifyListeners();
      final text = typed ?? await api.transcribe(bytes);
      if (generation != _presentationGeneration) return;
      if (text.isEmpty) return _fail('No speech detected');
      final chat = await api.chat(text, conversationId, responseMode: typed == null ? 'voice' : 'text');
      if (generation != _presentationGeneration) return;
      reply = chat.reply;
      presentationHint = chat.presentationHint;
      final plan = reactionPolicy.plan(presentationHint, AvatarState.speaking);
      final audioFuture = api.synthesize(reply, presentationHint: presentationHint);
      if (plan.preSpeechDelay > Duration.zero) await Future<void>.delayed(plan.preSpeechDelay);
      if (generation != _presentationGeneration) return;
      final audio = await audioFuture;
      if (generation != _presentationGeneration) return;
      state = AvatarState.speaking;
      notifyListeners();
      await _playAudioWithLipSync(audio);
      if (generation != _presentationGeneration) return;
      if (plan.tailDuration > Duration.zero) await Future<void>.delayed(plan.tailDuration);
      if (generation != _presentationGeneration) return;
      state = AvatarState.idle;
      notifyListeners();
    } catch (error) {
      if (generation == _presentationGeneration) _fail(error.toString().replaceFirst('Exception: ', ''));
    }
  }

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




