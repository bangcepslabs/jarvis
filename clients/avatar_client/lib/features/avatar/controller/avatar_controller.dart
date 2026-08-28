import 'package:audioplayers/audioplayers.dart';
import 'package:cross_file/cross_file.dart';
import 'package:flutter/foundation.dart';
import 'package:record/record.dart';
import '../../../core/network/jarvis_api_client.dart';
import '../domain/avatar_state.dart';
import '../domain/avatar_presentation_hint.dart';
import '../domain/character_reaction_policy.dart';

class AvatarController extends ChangeNotifier {
  AvatarController(this.api);
  final JarvisApiClient api;
  final AudioRecorder _recorder = AudioRecorder();
  final AudioPlayer _player = AudioPlayer();
  AvatarState state = AvatarState.idle;
  String conversationId = 'avatar-${DateTime.now().millisecondsSinceEpoch}';
  String reply = '';
  String? errorMessage;
  AvatarPresentationHint presentationHint = const AvatarPresentationHint();
  final CharacterReactionPolicy reactionPolicy = const CharacterReactionPolicy();
  int _presentationGeneration = 0;
  bool _recording = false;
  bool get isRecording => _recording;

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
      await _player.play(BytesSource(audio));
      if (generation != _presentationGeneration) return;
      if (plan.tailDuration > Duration.zero) await Future<void>.delayed(plan.tailDuration);
      if (generation != _presentationGeneration) return;
      state = AvatarState.idle;
      notifyListeners();
    } catch (error) {
      if (generation == _presentationGeneration) _fail(error.toString().replaceFirst('Exception: ', ''));
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
    _presentationGeneration++;
    _recorder.dispose();
    _player.dispose();
    api.dispose();
    super.dispose();
  }
}




