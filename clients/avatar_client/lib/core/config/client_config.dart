class ClientConfig {
  const ClientConfig({required this.coreBaseUrl, required this.avatarRenderer, this.clientToken, this.wakeWordEnabled = false, this.wakeWordEngine = 'disabled', this.wakeWordModelAsset = 'wake_word/development/hey_jarvis.onnx', this.wakeWordThreshold = .5});
  final String coreBaseUrl;
  final String avatarRenderer;
  final String? clientToken;
  final bool wakeWordEnabled;
  final String wakeWordEngine;
  final String wakeWordModelAsset;
  final double wakeWordThreshold;
  factory ClientConfig.fromEnvironment() {
    const value = String.fromEnvironment('JARVIS_CORE_URL', defaultValue: 'http://127.0.0.1:8000');
    const renderer = String.fromEnvironment('JARVIS_AVATAR_RENDERER', defaultValue: 'placeholder');
    const token = String.fromEnvironment('JARVIS_CLIENT_TOKEN');
    const wakeEnabled = bool.fromEnvironment('JARVIS_WAKE_WORD_ENABLED', defaultValue: false);
    const wakeEngine = String.fromEnvironment('JARVIS_WAKE_WORD_ENGINE', defaultValue: 'disabled');
    const wakeModel = String.fromEnvironment('JARVIS_WAKE_WORD_MODEL_ASSET', defaultValue: 'wake_word/development/hey_jarvis.onnx');
    final wakeThreshold = double.tryParse(const String.fromEnvironment('JARVIS_WAKE_WORD_THRESHOLD', defaultValue: '0.5')) ?? .5;
    return ClientConfig(coreBaseUrl: value.replaceAll(RegExp(r'\/$'), ''), avatarRenderer: renderer, clientToken: token.isEmpty ? null : token, wakeWordEnabled: wakeEnabled, wakeWordEngine: wakeEngine, wakeWordModelAsset: wakeModel, wakeWordThreshold: wakeThreshold);
  }
}
