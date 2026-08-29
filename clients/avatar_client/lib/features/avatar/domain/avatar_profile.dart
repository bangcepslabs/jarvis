import 'avatar_presentation_hint.dart';

class AvatarFraming {
  const AvatarFraming({this.scale = 2.95, this.offsetX = 0, this.offsetY = -0.30});
  final double scale;
  final double offsetX;
  final double offsetY;
}

class AvatarProfile {
  const AvatarProfile({
    required this.id, required this.displayName, required this.renderer, required this.modelAsset,
    this.mouthOpenParameter = 'ParamMouthOpenY', this.mouthFormParameter = 'ParamMouthForm',
    this.blinkParameterIds = const ['ParamEyeLOpen', 'ParamEyeROpen'],
    this.breathParameterIds = const ['ParamBreath'], this.mouthMin = 0, this.mouthMax = 1,
    this.mouthGain = 1.0, this.mouthMaxOpen = 0.72, this.mouthNoiseGate = 0.04,
    this.mouthAttackSeconds = 0.055, this.mouthReleaseSeconds = 0.14,
    this.expressionMappings = const {
      AvatarEmotion.happy: 'red',
      AvatarEmotion.excited: 'tang',
      AvatarEmotion.surprised: 'shock',
      AvatarEmotion.concerned: 'black',
      AvatarEmotion.thinking: 'shou',
      AvatarEmotion.playful: 'red',
    },
    this.ambientMotions = const ['idle', 'idle2'],
    this.reactionMotions = const {
      AvatarMotionIntent.positive: 'idle2',
      AvatarMotionIntent.reaction: 'idle2',
    },
    this.excludedAutoExpressions = const {'shuiyin'},
    this.framing = const AvatarFraming(), this.supportsExpressions = true,
    this.supportsReactionMotions = true, this.supportsLipSync = true,
  });
  final String id, displayName, renderer, modelAsset, mouthOpenParameter, mouthFormParameter;
  final List<String> blinkParameterIds, breathParameterIds, ambientMotions;
  final double mouthMin, mouthMax, mouthGain, mouthMaxOpen, mouthNoiseGate;
  final double mouthAttackSeconds, mouthReleaseSeconds;
  final Map<AvatarEmotion, String> expressionMappings;
  final Map<AvatarMotionIntent, String> reactionMotions;
  final Set<String> excludedAutoExpressions;
  final AvatarFraming framing;
  final bool supportsExpressions, supportsReactionMotions, supportsLipSync;

  String? expressionFor(AvatarEmotion emotion) {
    if (!supportsExpressions) return null;
    final expression = expressionMappings[emotion];
    return expression == null || excludedAutoExpressions.contains(expression) ? null : expression;
  }
}

class AvatarProfiles {
  static const placeholder = AvatarProfile(id: 'placeholder', displayName: 'JARVIS Placeholder', renderer: 'placeholder', modelAsset: '', supportsExpressions: false, supportsLipSync: false);
  static const ellenDev = AvatarProfile(id: 'ellen_dev', displayName: 'Ellen Development', renderer: 'live2d', modelAsset: 'assets/avatars/development/免费模型艾莲.model3.json');
  static AvatarProfile byId(String id) => id == 'ellen_dev' ? ellenDev : placeholder;
}
