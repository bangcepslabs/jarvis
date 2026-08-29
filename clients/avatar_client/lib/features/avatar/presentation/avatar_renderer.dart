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
      // Ellen's verified presentation expression hides the source-model
      // watermark. Keep it as the safe default while allowing an explicit
      // dart-define override for development comparisons.
      defaultValue: 'shuiyin',
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
  final reactionMotion = state == AvatarState.speaking && config.profile.supportsReactionMotions
      ? config.profile.reactionMotions[hint.motionIntent]
      : null;
  final mappedExpression = config.profile.expressionFor(hint.emotion);
  final expression = config.expression == 'shuiyin'
      ? (mappedExpression ?? config.expression)
      : config.expression;
  return {
    'modelAsset': config.modelAsset,
    'motion': reactionMotion ?? (config.profile.ambientMotions.isEmpty ? 'idle' : config.profile.ambientMotions.first),
    'state': state.name,
    // Keep the watermark-hiding default for neutral responses, but allow
    // verified model expressions to override it for emotional responses.
    'expression': expression,
    'mouthOpenParameter': config.profile.mouthOpenParameter,
    'mouthFormParameter': config.profile.mouthFormParameter,
    'mouthMin': config.profile.mouthMin,
    'mouthMax': config.profile.mouthMax,
    'mouthGain': config.profile.mouthGain,
    'mouthMaxOpen': config.profile.mouthMaxOpen,
    'mouthNoiseGate': config.profile.mouthNoiseGate,
    'mouthAttackSeconds': config.profile.mouthAttackSeconds,
    'mouthReleaseSeconds': config.profile.mouthReleaseSeconds,
    'emotion': hint.emotion.name,
    'intensity': hint.intensity,
    'motionIntent': hint.motionIntent.name,
    'reaction': hint.reaction.name,
    'mouthOpen': mouthOpen,
  };
}

Map<String, Object> live2DHostLifecycleParams(AppLifecycleState state) => {
  'resumed': state == AppLifecycleState.resumed,
};

class _Live2DPlatformView extends StatefulWidget {
  const _Live2DPlatformView({required this.config, required this.state, required this.hint, required this.mouthOpen});

  final AvatarRendererConfig config;
  final AvatarState state;
  final AvatarPresentationHint hint;
  final double mouthOpen;

  @override
  State<_Live2DPlatformView> createState() => _Live2DPlatformViewState();
}

class _Live2DPlatformViewState extends State<_Live2DPlatformView>
    with WidgetsBindingObserver {
  static const _channel = MethodChannel('jarvis/live2d/texture');
  int? _textureId;
  bool _released = false;

  Map<String, Object> get _params => live2DUpdateParams(widget.config, widget.state, widget.hint, widget.mouthOpen);

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _createTexture();
  }

  Future<void> _createTexture() async {
    try {
      final textureId = await _channel.invokeMethod<int>('create', _params);
      if (!mounted || _released || textureId == null) return;
      setState(() => _textureId = textureId);
      _sendLifecycle(AppLifecycleState.resumed);
    } catch (_) {
      // Keep the existing UI available if the optional native renderer fails.
    }
  }

  void _sendUpdate() {
    if (_released) return;
    _channel.invokeMethod<void>('update', _params).catchError((_) {});
  }

  Future<void> _sendLifecycle(AppLifecycleState state) async {
    if (_released) return;
    // Detach the old Flutter texture before the native SurfaceTexture entry
    // is released/replaced. Keeping a Texture widget bound to a released
    // entry can leave the compositor white after background/foreground.
    if (state != AppLifecycleState.resumed && mounted && _textureId != null) {
      setState(() => _textureId = null);
    }
    if (state == AppLifecycleState.resumed && mounted && _textureId != null) {
      setState(() => _textureId = null);
    }
    try {
      final textureId = await _channel.invokeMethod<Object?>(
        'lifecycle',
        live2DHostLifecycleParams(state),
      );
      if (state == AppLifecycleState.resumed && textureId is int && mounted && !_released) {
        setState(() => _textureId = textureId);
      }
    } catch (_) {}
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    switch (state) {
      case AppLifecycleState.resumed:
        _sendLifecycle(state);
      case AppLifecycleState.inactive:
        // Android emits inactive during normal foreground transitions. Pausing
        // the GLSurfaceView here can leave its surface blank before resumed.
        break;
      case AppLifecycleState.hidden:
      case AppLifecycleState.paused:
      case AppLifecycleState.detached:
        _sendLifecycle(state);
    }
  }

  @override
  void didUpdateWidget(covariant _Live2DPlatformView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.state != widget.state || oldWidget.hint != widget.hint || oldWidget.config != widget.config || oldWidget.mouthOpen != widget.mouthOpen) {
      _sendUpdate();
    }
  }

  @override
  void dispose() {
    _released = true;
    _channel.invokeMethod<void>('release').catchError((_) {});
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final textureId = _textureId;
    if (textureId == null) {
      return const ColoredBox(color: Color(0xff0a1c2e));
    }
    return Texture(textureId: textureId);
  }
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
