class ClientConfig {
  const ClientConfig({required this.coreBaseUrl, required this.avatarRenderer, this.clientToken, this.wakeWordEnabled = false});
  final String coreBaseUrl;
  final String avatarRenderer;
  final String? clientToken;
  final bool wakeWordEnabled;
  factory ClientConfig.fromEnvironment() {
    const value = String.fromEnvironment('JARVIS_CORE_URL', defaultValue: 'http://127.0.0.1:8000');
    const renderer = String.fromEnvironment('JARVIS_AVATAR_RENDERER', defaultValue: 'placeholder');
    const token = String.fromEnvironment('JARVIS_CLIENT_TOKEN');
    const wakeWord = String.fromEnvironment('JARVIS_WAKE_WORD_ENABLED', defaultValue: 'false');
    return ClientConfig(
      coreBaseUrl: value.replaceAll(RegExp(r'\/$'), ''),
      avatarRenderer: renderer,
      clientToken: token.isEmpty ? null : token,
      wakeWordEnabled: wakeWord.toLowerCase() == 'true',
    );
  }
}
