import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import '../../features/avatar/domain/avatar_presentation_hint.dart';

class JarvisChatResult {
  const JarvisChatResult({required this.reply, required this.presentationHint});
  final String reply;
  final AvatarPresentationHint presentationHint;
}

class JarvisTranscriptionResult {
  const JarvisTranscriptionResult({required this.text, this.timing = const {}});
  final String text;
  final Map<String, int> timing;
}

class JarvisSynthesisResult {
  const JarvisSynthesisResult({required this.audio, this.serverTtsMs});
  final Uint8List audio;
  final int? serverTtsMs;
}

class JarvisApiClient {
  JarvisApiClient(this.baseUrl, {this.clientToken, http.Client? client}) : _client = client ?? http.Client();
  final String baseUrl; final String? clientToken; final http.Client _client;
  Map<String, String> _headers([Map<String, String>? extra]) => {...?extra, if (clientToken != null) 'authorization': 'Bearer $clientToken'};
  Future<JarvisTranscriptionResult> transcribe(Uint8List bytes) async {
    final request = http.MultipartRequest('POST', Uri.parse('$baseUrl/api/stt/transcribe'));
    request.headers.addAll(_headers());
    request.files.add(http.MultipartFile.fromBytes('file', bytes, filename: 'recording.wav'));
    final response = await _client.send(request).timeout(const Duration(seconds: 60));
    final body = await response.stream.bytesToString();
    if (kDebugMode) {
      final decodedForLog = _tryDecodeMap(body);
      debugPrint('[stt_http] status=${response.statusCode} response_bytes=${body.length} keys=${decodedForLog?.keys.join(',') ?? 'non_json'}');
    }
    if (response.statusCode != 200) throw Exception(body);
    final decoded = jsonDecode(body) as Map<String, dynamic>;
    final timing = <String, int>{};
    final rawTiming = decoded['_timing'];
    if (rawTiming is Map) {
      for (final entry in rawTiming.entries) {
        if (entry.value is num) timing[entry.key.toString()] = (entry.value as num).round();
      }
    }
    return JarvisTranscriptionResult(
      text: (decoded['text'] as String? ?? '').trim(),
      timing: timing,
    );
  }
  Map<String, dynamic>? _tryDecodeMap(String body) {
    try {
      final value = jsonDecode(body);
      return value is Map<String, dynamic> ? value : null;
    } catch (_) {
      return null;
    }
  }
  Future<JarvisChatResult> chat(String message, String conversationId, {String responseMode = 'text'}) async { final r = await _client.post(Uri.parse('$baseUrl/api/chat'), headers: _headers({'content-type':'application/json'}), body: jsonEncode({'message':message,'conversation_id':conversationId,'response_mode':responseMode})).timeout(const Duration(seconds: 60)); if (r.statusCode != 200) throw Exception(r.body); final body = jsonDecode(r.body) as Map<String,dynamic>; return JarvisChatResult(reply: body['reply'] as String, presentationHint: AvatarPresentationHint.fromJson(body['presentation_hint'])); }
  Future<JarvisSynthesisResult> synthesize(String text, {AvatarPresentationHint? presentationHint, String? voiceProfileId}) async {
    final body = <String,dynamic>{'text':text,'language':'ko', ...?presentationHint == null ? null : {'presentation_hint': presentationHint.toJson()}, ...?voiceProfileId == null ? null : {'voice_profile_id': voiceProfileId}};
    final response = await _client.post(Uri.parse('$baseUrl/api/tts/synthesize'), headers: _headers({'content-type':'application/json'}), body: jsonEncode(body)).timeout(const Duration(seconds: 60));
    if (response.statusCode != 200) throw Exception(response.body);
    final match = RegExp(r'tts;dur=(\\d+)').firstMatch(response.headers['server-timing'] ?? '');
    return JarvisSynthesisResult(audio: response.bodyBytes, serverTtsMs: int.tryParse(match?.group(1) ?? ''));
  }
  void dispose() => _client.close();
}
