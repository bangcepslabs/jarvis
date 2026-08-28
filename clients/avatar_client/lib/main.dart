import 'package:flutter/material.dart';
import 'core/config/client_config.dart';
import 'core/network/jarvis_api_client.dart';
import 'features/avatar/controller/avatar_controller.dart';
import 'features/avatar/presentation/avatar_screen.dart';
import 'features/avatar/presentation/avatar_renderer.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  final config = ClientConfig.fromEnvironment();
  runApp(MaterialApp(
    debugShowCheckedModeBanner: false,
    title: 'JARVIS Avatar',
    theme: ThemeData(
      colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xff62d8ff), brightness: Brightness.dark),
      useMaterial3: true,
    ),
    home: AvatarScreen(
      controller: AvatarController(JarvisApiClient(config.coreBaseUrl, clientToken: config.clientToken)),
      rendererConfig: AvatarRendererConfig.fromEnvironment(),
    ),
  ));
}
