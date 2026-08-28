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
    this.mouthGain = 2.1, this.expressionMappings = const {}, this.ambientMotions = const ['idle', 'idle2'],
    this.reactionMotions = const {}, this.excludedAutoExpressions = const {'shuiyin'},
    this.framing = const AvatarFraming(), this.supportsExpressions = true,
    this.supportsReactionMotions = false, this.supportsLipSync = true,
  });
  final String id, displayName, renderer, modelAsset, mouthOpenParameter, mouthFormParameter;
  final List<String> blinkParameterIds, breathParameterIds, ambientMotions;
  final double mouthMin, mouthMax, mouthGain;
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
  static const ellenDev = AvatarProfile(id: 'ellen_dev', displayName: 'Ellen Development', renderer: 'live2d', modelAsset: 'assets/avatars/development/ellen_workshop/무료모델艾莲.4096/무료모델艾莲.model3.json');
  static AvatarProfile byId(String id) => id == 'ellen_dev' ? ellenDev : placeholder;
}
