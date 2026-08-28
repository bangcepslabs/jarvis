import 'dart:convert';
import 'dart:typed_data';
import 'package:http/http.dart' as http;
class JarvisApiClient {
  JarvisApiClient(this.baseUrl, {this.clientToken, http.Client? client}) : _client = client ?? http.Client();
  final String baseUrl; final String? clientToken; final http.Client _client;
  Map<String, String> _headers([Map<String, String>? extra]) => {...?extra, if (clientToken != null) 'authorization': 'Bearer $clientToken'};
  Future<String> transcribe(Uint8List bytes) async { final r = http.MultipartRequest('POST', Uri.parse('$baseUrl/api/stt/transcribe')); r.headers.addAll(_headers()); r.files.add(http.MultipartFile.fromBytes('file', bytes, filename: 'recording.wav')); final s = await _client.send(r).timeout(const Duration(seconds: 60)); final b = await s.stream.bytesToString(); if (s.statusCode != 200) throw Exception(b); return ((jsonDecode(b) as Map<String,dynamic>)['text'] as String? ?? '').trim(); }
  Future<String> chat(String message, String conversationId, {String responseMode = 'text'}) async { final r = await _client.post(Uri.parse('$baseUrl/api/chat'), headers: _headers({'content-type':'application/json'}), body: jsonEncode({'message':message,'conversation_id':conversationId,'response_mode':responseMode})).timeout(const Duration(seconds: 60)); if (r.statusCode != 200) throw Exception(r.body); return (jsonDecode(r.body) as Map<String,dynamic>)['reply'] as String; }
  Future<Uint8List> synthesize(String text) async { final r = await _client.post(Uri.parse('$baseUrl/api/tts/synthesize'), headers: _headers({'content-type':'application/json'}), body: jsonEncode({'text':text,'language':'ko'})).timeout(const Duration(seconds: 60)); if (r.statusCode != 200) throw Exception(r.body); return r.bodyBytes; }
  void dispose() => _client.close();
}
