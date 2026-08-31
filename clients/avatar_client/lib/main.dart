import 'package:flutter/material.dart';
import 'core/config/client_config.dart';
import 'core/network/jarvis_api_client.dart';
import 'features/avatar/controller/avatar_controller.dart';
import 'features/avatar/presentation/avatar_screen.dart';
import 'features/avatar/presentation/avatar_renderer.dart';
import 'features/voice/wake_word/wake_word_engine.dart';
import 'features/voice/wake_word/wake_word_controller.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  final config = ClientConfig.fromEnvironment();
  final avatarController = AvatarController(JarvisApiClient(config.coreBaseUrl, clientToken: config.clientToken));
  final wakeController = WakeWordController(
    config.wakeWordEnabled && config.wakeWordEngine == 'openwakeword'
        ? OpenWakeWordEngine(modelAsset: config.wakeWordModelAsset, threshold: config.wakeWordThreshold)
        : UnavailableWakeWordEngine('wake word is disabled'),
    onDetected: avatarController.onWakeWordDetected,
  );
  avatarController.attachWakeWordController(wakeController);
  if (config.wakeWordEnabled) wakeController.arm();
  runApp(MaterialApp(
    debugShowCheckedModeBanner: false,
    title: 'JARVIS Avatar',
    theme: ThemeData(
      colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xff62d8ff), brightness: Brightness.dark),
      useMaterial3: true,
    ),
    home: AvatarScreen(
      controller: avatarController,
      rendererConfig: AvatarRendererConfig.fromEnvironment(),
    ),
  ));
}
