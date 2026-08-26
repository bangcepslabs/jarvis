class ClientConfig {
  const ClientConfig({required this.coreBaseUrl, required this.avatarRenderer});
  final String coreBaseUrl;
  final String avatarRenderer;
  factory ClientConfig.fromEnvironment() {
    const value = String.fromEnvironment('JARVIS_CORE_URL', defaultValue: 'http://127.0.0.1:8000');
    const renderer = String.fromEnvironment('JARVIS_AVATAR_RENDERER', defaultValue: 'placeholder');
    return ClientConfig(coreBaseUrl: value.replaceAll(RegExp(r'\/$'), ''), avatarRenderer: renderer);
  }
}
