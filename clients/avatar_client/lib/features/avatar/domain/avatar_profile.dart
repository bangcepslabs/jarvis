import 'avatar_presentation_hint.dart';
import 'avatar_state.dart';

class AvatarFraming {
  const AvatarFraming({this.scale = 2.95, this.offsetX = 0, this.offsetY = -0.30});
  final double scale;
  final double offsetX;
  final double offsetY;
}

class AvatarMotionSelection {
  const AvatarMotionSelection(this.motion, this.candidates);
  final String? motion;
  final List<String> candidates;
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
    this.emotionMotionPools = const {}, this.intenseEmotionMotions = const {},
    this.reactionMotionPools = const {}, this.speakingMotionPool = const [],
    this.excludedAutoExpressions = const {'shuiyin'},
    this.framing = const AvatarFraming(), this.nativeHeight, this.nativeOffsetX,
    this.nativeOffsetY, this.supportsExpressions = true,
    this.supportsReactionMotions = true, this.supportsLipSync = true,
  });
  final String id, displayName, renderer, modelAsset, mouthOpenParameter, mouthFormParameter;
  final List<String> blinkParameterIds, breathParameterIds, ambientMotions;
  final double mouthMin, mouthMax, mouthGain, mouthMaxOpen, mouthNoiseGate;
  final double mouthAttackSeconds, mouthReleaseSeconds;
  final Map<AvatarEmotion, String> expressionMappings;
  final Map<AvatarMotionIntent, String> reactionMotions;
  final Map<AvatarEmotion, List<String>> emotionMotionPools;
  final Map<AvatarEmotion, String> intenseEmotionMotions;
  final Map<AvatarMotionIntent, List<String>> reactionMotionPools;
  final List<String> speakingMotionPool;
  final Set<String> excludedAutoExpressions;
  final AvatarFraming framing;
  final double? nativeHeight, nativeOffsetX, nativeOffsetY;
  final bool supportsExpressions, supportsReactionMotions, supportsLipSync;

  String? expressionFor(AvatarEmotion emotion) {
    if (!supportsExpressions) return null;
    final expression = expressionMappings[emotion];
    return expression == null || excludedAutoExpressions.contains(expression) ? null : expression;
  }

  AvatarMotionSelection motionSelectionFor(
    AvatarState state,
    AvatarPresentationHint hint,
  ) {
    if (state != AvatarState.speaking) {
      return AvatarMotionSelection(
        ambientMotions.isEmpty ? null : ambientMotions.first,
        ambientMotions,
      );
    }
    final intense = hint.intensity > .65 ? intenseEmotionMotions[hint.emotion] : null;
    final candidates = intense == null
        ? (emotionMotionPools[hint.emotion] ?? reactionMotionPools[hint.motionIntent] ?? speakingMotionPool)
        : {intense, ...(emotionMotionPools[hint.emotion] ?? const <String>[])}
            .toList(growable: false);
    final fallback = reactionMotions[hint.motionIntent];
    return AvatarMotionSelection(candidates.isNotEmpty ? candidates.first : fallback, candidates);
  }
}

class AvatarProfiles {
  static const placeholder = AvatarProfile(id: 'placeholder', displayName: 'JARVIS Placeholder', renderer: 'placeholder', modelAsset: '', supportsExpressions: false, supportsLipSync: false);
  static const emiliaMagical = AvatarProfile(
    id: 'emilia_magical', displayName: 'Emilia', renderer: 'live2d',
    modelAsset: 'assets/avatars/development/emilia_magical/Emilia (Magical).model3.json',
    blinkParameterIds: ['ParamEyeLOpen', 'ParamEyeROpen'],
    breathParameterIds: ['ParamBreath'],
    mouthOpenParameter: 'ParamMouthOpenY', mouthFormParameter: 'ParamMouthForm',
    // Emilia's verified ParamMouthOpenY reaches an obvious circular mesh limit
    // before the shared Ellen cap. Keep this model below that visible boundary.
    mouthMin: 0, mouthMax: 1, mouthGain: .9, mouthMaxOpen: .50,
    mouthNoiseGate: .06, mouthAttackSeconds: .055, mouthReleaseSeconds: .18,
    ambientMotions: ['select_idle', 'select_idle02'],
    emotionMotionPools: {
      AvatarEmotion.happy: ['act_egao', 'act_egao02', 'act_egao03'],
      AvatarEmotion.excited: ['act_egao02', 'act_egao03'],
      AvatarEmotion.surprised: ['act_bikkuri', 'act_bikkuri02'],
      AvatarEmotion.concerned: ['act_nayamu', 'act_tameiki'],
      AvatarEmotion.thinking: ['act_kangaeru', 'act_nayamu'],
      AvatarEmotion.playful: ['act_doya', 'act_hohoemu'],
    },
    intenseEmotionMotions: {
      AvatarEmotion.happy: 'act_egao02', AvatarEmotion.excited: 'act_egao03',
      AvatarEmotion.surprised: 'act_bikkuri02', AvatarEmotion.concerned: 'act_tameiki02',
      AvatarEmotion.thinking: 'act_nayamu', AvatarEmotion.playful: 'act_doya',
    },
    reactionMotionPools: {
      AvatarMotionIntent.positive: ['act_egao', 'act_egao02', 'act_unazuku'],
      AvatarMotionIntent.reaction: ['act_unazuku', 'act_doya', 'act_hohoemu'],
      AvatarMotionIntent.subtle: ['act_hohoemu', 'act_unazuku'],
    },
    // These verified act motions animate body, arms, head, hair, and face
    // parameters. They give neutral spoken replies a body-motion choice too.
    speakingMotionPool: [
      'act_normal03', 'act_unazuku', 'act_hohoemu', 'act_doya',
      'act_kangaeru', 'act_shinken02',
    ],
    framing: AvatarFraming(scale: 2.15, offsetX: 0, offsetY: -.28),
    nativeHeight: 2.15, nativeOffsetX: 0, nativeOffsetY: -.28,
    supportsExpressions: false,
  );
  static const ellenDev = AvatarProfile(id: 'ellen_dev', displayName: 'Ellen Development', renderer: 'live2d', modelAsset: 'assets/avatars/development/免费模型艾莲.model3.json');
  static AvatarProfile byId(String id) => switch (id) {
    'ellen' || 'ellen_dev' => ellenDev,
    'emilia' || 'emilia_magical' => emiliaMagical,
    _ => placeholder,
  };
}
