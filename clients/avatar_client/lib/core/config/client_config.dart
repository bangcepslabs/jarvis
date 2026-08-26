class ClientConfig {
  const ClientConfig({required this.coreBaseUrl});
  final String coreBaseUrl;
  factory ClientConfig.fromEnvironment() {
    const value = String.fromEnvironment('JARVIS_CORE_URL', defaultValue: 'http://127.0.0.1:8000');
    return ClientConfig(coreBaseUrl: value.replaceAll(RegExp(r'\/$'), ''));
  }
}
