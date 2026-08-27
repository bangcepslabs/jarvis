import 'dart:typed_data';

Uint8List pcm16MonoToWav(Uint8List pcm, {int sampleRate = 16000}) {
  final out = ByteData(44 + pcm.length);
  out.setUint32(0, 0x52494646, Endian.big);
  out.setUint32(4, 36 + pcm.length, Endian.little);
  out.setUint32(8, 0x57415645, Endian.big);
  out.setUint32(12, 0x666d7420, Endian.big);
  out.setUint32(16, 16, Endian.little);
  out.setUint16(20, 1, Endian.little);
  out.setUint16(22, 1, Endian.little);
  out.setUint32(24, sampleRate, Endian.little);
  out.setUint32(28, sampleRate * 2, Endian.little);
  out.setUint16(32, 2, Endian.little);
  out.setUint16(34, 16, Endian.little);
  out.setUint32(36, 0x64617461, Endian.big);
  out.setUint32(40, pcm.length, Endian.little);
  out.buffer.asUint8List().setRange(44, 44 + pcm.length, pcm);
  return out.buffer.asUint8List();
}
