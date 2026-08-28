import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../domain/avatar_state.dart';
import '../domain/avatar_presentation_hint.dart';
import '../domain/avatar_profile.dart';

enum AvatarRendererKind { placeholder, live2d }

class AvatarRendererConfig {
  const AvatarRendererConfig({
    required this.kind,
    required this.modelAsset,
    required this.expression,
    this.profile = AvatarProfiles.placeholder,
  });

  final AvatarRendererKind kind;
  final String modelAsset;
  final String expression;
  final AvatarProfile profile;

  factory AvatarRendererConfig.fromEnvironment() {
    const renderer = String.fromEnvironment(
      'JARVIS_AVATAR_RENDERER',
      defaultValue: 'placeholder',
    );
    const flavor = String.fromEnvironment(
      'FLUTTER_APP_FLAVOR',
      defaultValue: 'base',
    );
    const model = String.fromEnvironment(
      'JARVIS_LIVE2D_MODEL_ASSET',
      defaultValue:
          '',
    );
    const expression = String.fromEnvironment(
      'JARVIS_LIVE2D_EXPRESSION',
      defaultValue: '',
    );
    final configuredProfile = const String.fromEnvironment('JARVIS_AVATAR_PROFILE', defaultValue: 'placeholder');
    final profile = AvatarProfiles.byId(configuredProfile == 'placeholder' && renderer.toLowerCase() == 'live2d' ? 'ellen_dev' : configuredProfile);
    return AvatarRendererConfig(
      kind: renderer.toLowerCase() == 'live2d' && flavor.toLowerCase() == 'live2d'
          ? AvatarRendererKind.live2d
          : AvatarRendererKind.placeholder,
      modelAsset: model.isEmpty ? profile.modelAsset : model,
      expression: expression,
      profile: profile,
    );
  }
}

abstract interface class AvatarRenderer {
  Widget build(BuildContext context, AvatarState state, double size, AvatarPresentationHint hint);
}

class PlaceholderAvatarRenderer implements AvatarRenderer {
  @override
  Widget build(BuildContext context, AvatarState state, double size, AvatarPresentationHint hint) =>
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
  Widget build(BuildContext context, AvatarState state, double size, AvatarPresentationHint hint) {
    if (defaultTargetPlatform != TargetPlatform.android) {
      return const _Live2DFallback(message: 'Live2D renderer is Android-only.');
    }
    return _Live2DPlatformView(config: config, state: state, hint: hint, mouthOpen: 0);
  }
}

Map<String, Object> live2DUpdateParams(
  AvatarRendererConfig config,
  AvatarState state,
  AvatarPresentationHint hint,
  double mouthOpen,
) {
  final reactionMotion = state == AvatarState.speaking ? config.profile.reactionMotions[hint.motionIntent] : null;
  return {
    'modelAsset': config.modelAsset,
    'motion': reactionMotion ?? (config.profile.ambientMotions.isEmpty ? 'idle' : config.profile.ambientMotions.first),
    'state': state.name,
    'expression': config.expression.isNotEmpty ? config.expression : (config.profile.expressionFor(hint.emotion) ?? ''),
    'mouthOpenParameter': config.profile.mouthOpenParameter,
    'mouthFormParameter': config.profile.mouthFormParameter,
    'mouthMin': config.profile.mouthMin,
    'mouthMax': config.profile.mouthMax,
    'mouthGain': config.profile.mouthGain,
    'emotion': hint.emotion.name,
    'intensity': hint.intensity,
    'motionIntent': hint.motionIntent.name,
    'reaction': hint.reaction.name,
    'mouthOpen': mouthOpen,
  };
}

class _Live2DPlatformView extends StatefulWidget {
  const _Live2DPlatformView({required this.config, required this.state, required this.hint, required this.mouthOpen});

  final AvatarRendererConfig config;
  final AvatarState state;
  final AvatarPresentationHint hint;
  final double mouthOpen;

  @override
  State<_Live2DPlatformView> createState() => _Live2DPlatformViewState();
}

class _Live2DPlatformViewState extends State<_Live2DPlatformView> {
  MethodChannel? _channel;

  Map<String, Object> get _params => live2DUpdateParams(widget.config, widget.state, widget.hint, widget.mouthOpen);

  void _created(int viewId) {
    _channel = MethodChannel('jarvis/live2d/$viewId');
    _sendUpdate();
  }

  void _sendUpdate() {
    final channel = _channel;
    if (channel == null) return;
    channel.invokeMethod<void>('update', _params).catchError((_) {});
  }

  @override
  void didUpdateWidget(covariant _Live2DPlatformView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.state != widget.state || oldWidget.hint != widget.hint || oldWidget.config != widget.config || oldWidget.mouthOpen != widget.mouthOpen) {
      _sendUpdate();
    }
  }

  @override
  Widget build(BuildContext context) => AndroidView(
    viewType: 'jarvis/live2d',
    creationParams: _params,
    creationParamsCodec: const StandardMessageCodec(),
    onPlatformViewCreated: _created,
  );
}

class AvatarRendererHost extends StatelessWidget {
  const AvatarRendererHost({
    super.key,
    required this.config,
    required this.state,
    required this.size,
    required this.presentationHint,
    this.mouthOpen = 0,
  });

  final AvatarRendererConfig config;
  final AvatarState state;
  final double size;
  final AvatarPresentationHint presentationHint;
  final double mouthOpen;

  @override
  Widget build(BuildContext context) {
    final renderer = switch (config.kind) {
      AvatarRendererKind.placeholder => PlaceholderAvatarRenderer(),
      AvatarRendererKind.live2d => Live2DAvatarRenderer(config),
    };
    if (config.kind == AvatarRendererKind.live2d) {
      return _Live2DPlatformView(config: config, state: state, hint: presentationHint, mouthOpen: mouthOpen);
    }
    return LayoutBuilder(
      builder: (context, constraints) => Center(
        child: renderer.build(
          context,
          state,
          constraints.maxWidth < constraints.maxHeight
              ? constraints.maxWidth * .72
              : constraints.maxHeight * .58,
          presentationHint,
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
