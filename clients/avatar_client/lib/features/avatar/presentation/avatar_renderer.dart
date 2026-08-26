import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../domain/avatar_state.dart';

enum AvatarRendererKind { placeholder, live2d }

class AvatarRendererConfig {
  const AvatarRendererConfig({
    required this.kind,
    required this.modelAsset,
    required this.expression,
  });

  final AvatarRendererKind kind;
  final String modelAsset;
  final String expression;

  factory AvatarRendererConfig.fromEnvironment() {
    const renderer = String.fromEnvironment(
      'JARVIS_AVATAR_RENDERER',
      defaultValue: 'placeholder',
    );
    const model = String.fromEnvironment(
      'JARVIS_LIVE2D_MODEL_ASSET',
      defaultValue:
          'assets/avatars/development/ellen_workshop/免费模型艾莲.model3.json',
    );
    const expression = String.fromEnvironment(
      'JARVIS_LIVE2D_EXPRESSION',
      defaultValue: '',
    );
    return AvatarRendererConfig(
      kind: renderer.toLowerCase() == 'live2d'
          ? AvatarRendererKind.live2d
          : AvatarRendererKind.placeholder,
      modelAsset: model,
      expression: expression,
    );
  }
}

abstract interface class AvatarRenderer {
  Widget build(BuildContext context, AvatarState state, double size);
}

class PlaceholderAvatarRenderer implements AvatarRenderer {
  @override
  Widget build(BuildContext context, AvatarState state, double size) =>
      AnimatedContainer(
        duration: const Duration(milliseconds: 300),
        width: size,
        height: size,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          color: const Color(0xff102b43),
          border: Border.all(
            color: state == AvatarState.error
                ? Colors.redAccent
                : const Color(0xff62d8ff),
            width: 3,
          ),
          boxShadow: [
            BoxShadow(
              color: const Color(0xff1596bd).withValues(alpha: .25),
              blurRadius: state == AvatarState.thinking ? 36 : 18,
            ),
          ],
        ),
        child: Center(
          child: Icon(
            switch (state) {
              AvatarState.idle => Icons.face_6,
              AvatarState.listening => Icons.hearing,
              AvatarState.thinking => Icons.psychology,
              AvatarState.speaking => Icons.record_voice_over,
              AvatarState.error => Icons.error_outline,
            },
            size: size * .3,
            color: const Color(0xffb8efff),
          ),
        ),
      );
}

class Live2DAvatarRenderer implements AvatarRenderer {
  const Live2DAvatarRenderer(this.config);

  final AvatarRendererConfig config;

  @override
  Widget build(BuildContext context, AvatarState state, double size) {
    if (defaultTargetPlatform != TargetPlatform.android) {
      return const _Live2DFallback(message: 'Live2D renderer is Android-only.');
    }
    return AndroidView(
      viewType: 'jarvis/live2d',
      creationParams: {
        'modelAsset': config.modelAsset,
        'motion': 'idle',
        'state': state.name,
        'expression': config.expression,
      },
      creationParamsCodec: const StandardMessageCodec(),
    );
  }
}

class AvatarRendererHost extends StatelessWidget {
  const AvatarRendererHost({
    super.key,
    required this.config,
    required this.state,
    required this.size,
  });

  final AvatarRendererConfig config;
  final AvatarState state;
  final double size;

  @override
  Widget build(BuildContext context) {
    final renderer = switch (config.kind) {
      AvatarRendererKind.placeholder => PlaceholderAvatarRenderer(),
      AvatarRendererKind.live2d => Live2DAvatarRenderer(config),
    };
    if (config.kind == AvatarRendererKind.live2d) {
      return renderer.build(context, state, double.infinity);
    }
    return LayoutBuilder(
      builder: (context, constraints) => Center(
        child: renderer.build(
          context,
          state,
          constraints.maxWidth < constraints.maxHeight
              ? constraints.maxWidth * .72
              : constraints.maxHeight * .58,
        ),
      ),
    );
  }
}

class _Live2DFallback extends StatelessWidget {
  const _Live2DFallback({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) => DecoratedBox(
    decoration: BoxDecoration(
      color: const Color(0xff102b43),
      border: Border.all(color: const Color(0xff62d8ff), width: 3),
      shape: BoxShape.circle,
    ),
    child: Center(child: Text(message, textAlign: TextAlign.center)),
  );
}
