import 'dart:convert';
import 'dart:typed_data';
import 'package:http/http.dart' as http;
class JarvisApiClient {
  JarvisApiClient(this.baseUrl, {http.Client? client}) : _client = client ?? http.Client();
  final String baseUrl; final http.Client _client;
  Future<String> transcribe(Uint8List bytes) async { final r = http.MultipartRequest('POST', Uri.parse('$baseUrl/api/stt/transcribe'))..files.add(http.MultipartFile.fromBytes('file', bytes, filename: 'recording.wav')); final s = await _client.send(r).timeout(const Duration(seconds: 60)); final b = await s.stream.bytesToString(); if (s.statusCode != 200) throw Exception(b); return ((jsonDecode(b) as Map<String,dynamic>)['text'] as String? ?? '').trim(); }
  Future<String> chat(String message, String conversationId) async { final r = await _client.post(Uri.parse('$baseUrl/api/chat'), headers: {'content-type':'application/json'}, body: jsonEncode({'message':message,'conversation_id':conversationId})).timeout(const Duration(seconds: 60)); if (r.statusCode != 200) throw Exception(r.body); return (jsonDecode(r.body) as Map<String,dynamic>)['reply'] as String; }
  Future<Uint8List> synthesize(String text) async { final r = await _client.post(Uri.parse('$baseUrl/api/tts/synthesize'), headers: {'content-type':'application/json'}, body: jsonEncode({'text':text,'language':'ko'})).timeout(const Duration(seconds: 60)); if (r.statusCode != 200) throw Exception(r.body); return r.bodyBytes; }
  void dispose() => _client.close();
}
