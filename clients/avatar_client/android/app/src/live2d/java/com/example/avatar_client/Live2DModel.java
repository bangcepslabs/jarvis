package com.example.avatar_client;

import android.content.res.AssetManager;
import android.util.Log;

import com.live2d.sdk.cubism.framework.CubismFramework;
import com.live2d.sdk.cubism.framework.CubismModelSettingJson;
import com.live2d.sdk.cubism.framework.effect.CubismBreath;
import com.live2d.sdk.cubism.framework.effect.CubismEyeBlink;
import com.live2d.sdk.cubism.framework.model.CubismUserModel;
import com.live2d.sdk.cubism.framework.motion.CubismMotion;
import com.live2d.sdk.cubism.framework.motion.CubismExpressionMotion;
import com.live2d.sdk.cubism.framework.id.CubismId;
import com.live2d.sdk.cubism.framework.math.CubismMatrix44;
import com.live2d.sdk.cubism.framework.rendering.android.CubismRendererAndroid;
import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.io.InputStream;
import java.util.HashMap;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Locale;

/** App-owned adapter around the official Cubism Java Framework. */
final class Live2DModel extends CubismUserModel {
    private final File root;
    private final CubismModelSettingJson setting;
    private final List<CubismMotion> idleMotions = new ArrayList<>();
    private int idleMotionIndex;
    private final CubismEyeBlink eyeBlink;
    private final CubismBreath breath;
    private final Map<String, CubismMotion> motions = new HashMap<>();
    private final Map<String, Integer> motionCandidateCursors = new HashMap<>();
    private final Map<String, CubismExpressionMotion> expressions = new HashMap<>();
    private final CubismMatrix44 projectionMatrix = CubismMatrix44.create();
    private final CubismMatrix44 mvpMatrix = CubismMatrix44.create();
    private final CubismId mouthParameterId;
    private final float mouthMin;
    private final float mouthMax;
    private final float mouthGain;
    private final float mouthMaxOpen;
    private final float mouthNoiseGate;
    private final float mouthAttackSeconds;
    private final float mouthReleaseSeconds;
    private final float modelHeight;
    private final float modelOffsetX;
    private final float modelOffsetY;
    private float mouthTarget;
    private float mouthApplied;
    private int mouthParameterIndex = -1;
    private String lastExpression = "";
    private String lastMotion = "";
    private String lastState = "";

    Live2DModel(File root, File model3Json, String avatarProfile, String mouthParameterName, float mouthMin, float mouthMax, float mouthGain, float mouthMaxOpen, float mouthNoiseGate, float mouthAttackSeconds, float mouthReleaseSeconds, float modelHeight, float modelOffsetX, float modelOffsetY, List<String> ambientMotionNames) throws IOException {
        this.root = root;
        setting = new CubismModelSettingJson(Files.readAllBytes(model3Json.toPath()));
        byte[] mocBytes = read(setting.getModelFileName());
        int mocVersion = getMocVersionFromBuffer(mocBytes);
        loadModel(mocBytes);
        mouthParameterId = CubismFramework.getIdManager().getId(mouthParameterName);
        this.mouthMin = mouthMin;
        this.mouthMax = mouthMax;
        this.mouthGain = mouthGain;
        this.mouthMaxOpen = Math.max(0f, Math.min(1f, mouthMaxOpen));
        this.mouthNoiseGate = Math.max(0f, Math.min(1f, mouthNoiseGate));
        this.mouthAttackSeconds = Math.max(0.001f, mouthAttackSeconds);
        this.mouthReleaseSeconds = Math.max(0.001f, mouthReleaseSeconds);
        this.modelHeight = modelHeight;
        this.modelOffsetX = modelOffsetX;
        this.modelOffsetY = modelOffsetY;
        mouthParameterIndex = getModel().getParameterIndex(mouthParameterId);
        if (mouthParameterIndex >= 0 && mouthParameterIndex < getModel().getParameterCount()) {
            Log.i("JARVIS_LIVE2D", "mouthParameter=" + mouthParameterName +
                    " min=" + getModel().getParameterMinimumValue(mouthParameterIndex) +
                    " default=" + getModel().getParameterDefaultValue(mouthParameterIndex) +
                    " max=" + getModel().getParameterMaximumValue(mouthParameterIndex));
        }
        if (!setting.getPhysicsFileName().isEmpty()) loadPhysics(read(setting.getPhysicsFileName()));
        for (int i = 0; i < setting.getExpressionCount(); i++) {
            CubismExpressionMotion expression = loadExpression(
                    read(setting.getExpressionFileName(i)));
            if (expression != null) expressions.put(setting.getExpressionName(i), expression);
        }
        for (int groupIndex = 0; groupIndex < setting.getMotionGroupCount(); groupIndex++) {
            String group = setting.getMotionGroupName(groupIndex);
            for (int i = 0; i < setting.getMotionCount(group); i++) {
                String fileName = setting.getMotionFileName(group, i);
                CubismMotion loaded = loadMotion(read(fileName));
                if (loaded != null) {
                    loaded.setLoop(false);
                    String name = motionName(fileName);
                    motions.put(name, loaded);
                    motions.put(group.toLowerCase(Locale.ROOT) + ":" + i, loaded);
                    if (ambientMotionNames.contains(name)) idleMotions.add(loaded);
                }
            }
        }
        if (idleMotions.isEmpty() && !motions.isEmpty()) idleMotions.add(motions.values().iterator().next());
        for (CubismMotion motion : idleMotions) motion.setLoop(idleMotions.size() == 1);
        eyeBlink = CubismEyeBlink.create(setting);
        breath = CubismBreath.create();
        configureBreath();
        Log.i("JARVIS_LIVE2D", "avatar profile=" + avatarProfile +
                " model3=" + model3Json.getName() +
                " moc3=" + setting.getModelFileName() +
                " mocVersion=" + mocVersion +
                " textures=" + setting.getTextureCount() +
                " motions=" + motions.size() / 2 +
                " mouthParameter=" + mouthParameterName +
                " eyeBlinkParams=" + eyeBlink.getParameterIds().size() +
                " breathParams=" + breath.getParameters().size() +
                " physics=" + (physics != null) +
                " scale=" + modelHeight +
                " offsetX=" + modelOffsetX +
                " offsetY=" + modelOffsetY);
    }

    void initializeRenderer(int width, int height) {
        CubismRendererAndroid renderer = (CubismRendererAndroid) CubismRendererAndroid.create(width, height);
        setupRenderer(renderer, 1);
        updateViewport(width, height);
        if (!idleMotions.isEmpty()) motionManager.startMotionPriority(idleMotions.get(0), 1);
        Log.i("JARVIS_LIVE2D", "idleLoop=" + !idleMotions.isEmpty() +
                " idleMotions=" + idleMotions.size() +
                " eyeBlinkParams=" + eyeBlink.getParameterIds().size() +
                " breathParams=" + breath.getParameters().size() +
                " physics=" + (physics != null));
    }

    void updateViewport(int width, int height) {
        if (getRenderer() == null || width <= 0 || height <= 0) return;
        setRenderTargetSize(width, height);
        getModelMatrix().loadIdentity();
        // Medium-long portrait framing: leave breathing room above the head
        // and let the lower body fall behind the overlay without stretching
        // either axis.
        getModelMatrix().setHeight(modelHeight);
        getModelMatrix().setX(modelOffsetX);
        getModelMatrix().setY(modelOffsetY);

        // Keep model framing uniform. Correct the physical portrait viewport
        // aspect in a separate projection matrix instead of stretching the
        // model matrix along one axis.
        float viewportAspect = (float) width / (float) height;
        float projectionScaleX = viewportAspect < 1.0f ? 1.0f / viewportAspect : 1.0f;
        float projectionScaleY = viewportAspect > 1.0f ? viewportAspect : 1.0f;
        projectionMatrix.loadIdentity();
        projectionMatrix.scale(projectionScaleX, projectionScaleY);
        mvpMatrix.setMatrix(projectionMatrix);
        mvpMatrix.multiplyByMatrix(getModelMatrix());
        getRenderer().setMvpMatrix(mvpMatrix);

        float canvasWidth = getModel().getCanvasWidth();
        float canvasHeight = getModel().getCanvasHeight();
        float canvasAspect = canvasWidth / canvasHeight;
        float modelScaleX = getModelMatrix().getScaleX();
        float modelScaleY = getModelMatrix().getScaleY();
        Log.i("JARVIS_LIVE2D", "viewport=" + width + "x" + height +
                " viewportAspect=" + viewportAspect +
                " canvas=" + canvasWidth + "x" + canvasHeight +
                " canvasAspect=" + canvasAspect +
                " modelScaleX=" + modelScaleX +
                " modelScaleY=" + modelScaleY +
                " projectionScaleX=" + projectionScaleX +
                " projectionScaleY=" + projectionScaleY +
                " uniformModelScale=" + (Math.abs(modelScaleX - modelScaleY) < 0.0001f));
    }

    int textureCount() { return setting.getTextureCount(); }
    String textureName(int index) { return setting.getTextureFileName(index); }
    File textureFile(int index) { return new File(root, setting.getTextureFileName(index)); }

    void update(float deltaSeconds) {
        if (getModel() == null) return;
        motionManager.updateMotion(getModel(), deltaSeconds);
        if (idleMotions.size() > 1 && motionManager.isFinished()) {
            idleMotionIndex = (idleMotionIndex + 1) % idleMotions.size();
            motionManager.startMotionPriority(idleMotions.get(idleMotionIndex), 1);
            Log.i("JARVIS_LIVE2D", "idle motion loop restart index=" + idleMotionIndex);
        }
        expressionManager.updateMotion(getModel(), deltaSeconds);
        eyeBlink.updateParameters(getModel(), deltaSeconds);
        breath.updateParameters(getModel(), deltaSeconds);
        if (physics != null) physics.evaluate(getModel(), deltaSeconds);
        updateMouth(deltaSeconds);
        getModel().update();
    }

    String debugAnimationSummary() {
        return "idleMotions=" + idleMotions.size() +
                " motionFinished=" + motionManager.isFinished() +
                " eyeBlinkParams=" + eyeBlink.getParameterIds().size() +
                " breathParams=" + breath.getParameters().size() +
                " physics=" + (physics != null);
    }

    private void configureBreath() {
        final List<CubismBreath.BreathParameterData> parameters = new ArrayList<>();
        addBreathParameter(parameters, "ParamAngleX", 0.0f, 0.35f, 6.0f, 0.18f);
        addBreathParameter(parameters, "ParamAngleY", 0.0f, 0.20f, 7.0f, 0.12f);
        addBreathParameter(parameters, "ParamBodyAngleX", 0.0f, 0.25f, 6.5f, 0.15f);
        addBreathParameter(parameters, "ParamBreath", 0.0f, 0.50f, 3.0f, 0.35f);
        breath.setParameters(parameters);
    }

    private void addBreathParameter(
            List<CubismBreath.BreathParameterData> parameters,
            String id,
            float offset,
            float peak,
            float cycle,
            float weight) {
        CubismId parameterId = findParameterId(id);
        if (parameterId != null) {
            parameters.add(new CubismBreath.BreathParameterData(parameterId, offset, peak, cycle, weight));
        }
    }

    private CubismId findParameterId(String id) {
        for (int i = 0; i < getModel().getParameterCount(); i++) {
            CubismId parameterId = getModel().getParameterId(i);
            if (id.equals(parameterId.getString())) return parameterId;
        }
        return null;
    }

    boolean applyExpression(String name) {
        CubismExpressionMotion expression = expressions.get(name);
        if (expression == null) return false;
        return expressionManager.startMotionPriority(expression, 1) >= 0;
    }

    void applyRuntimeUpdate(String state, String expression, String motion, List<String> motionCandidates, String reaction, float intensity) {
        if (state == null) state = "idle";
        String previousState = lastState;
        if (!state.equals(lastState)) {
            Log.i("JARVIS_LIVE2D", "state changed=" + state);
            lastState = state;
        }
        if (!expression.equals(lastExpression)) {
            if (expression.isEmpty()) {
                Log.i("JARVIS_LIVE2D", "expression skipped=empty");
            } else if (applyExpression(expression)) {
                Log.i("JARVIS_LIVE2D", "expression applied=" + expression + " intensity=" + intensity);
            } else {
                Log.i("JARVIS_LIVE2D", "expression skipped=" + expression);
            }
            lastExpression = expression;
        }
        String resolvedMotion = selectMotionName(motion, motionCandidates);
        if (!resolvedMotion.equals(lastMotion) ||
                (!"none".equals(reaction) && "speaking".equals(state) && !"speaking".equals(previousState))) {
            CubismMotion selected = findMotion(resolvedMotion);
            if (selected == null) {
                Log.i("JARVIS_LIVE2D", "motion skipped=" + resolvedMotion);
            } else {
                motionManager.startMotionPriority(selected, 1);
                Log.i("JARVIS_LIVE2D", "motion applied=" + resolvedMotion + " reaction=" + reaction);
            }
            lastMotion = resolvedMotion;
        }
    }

    void setMouthTarget(float value, float configuredMaxOpen, float configuredNoiseGate) {
        float maxOpen = Math.max(0f, Math.min(1f, Math.min(mouthMaxOpen, configuredMaxOpen)));
        float noiseGate = Math.max(0f, Math.min(1f, Math.max(mouthNoiseGate, configuredNoiseGate)));
        float normalized = value <= noiseGate ? 0f : (value - noiseGate) / (1f - noiseGate);
        normalized = Math.max(0f, Math.min(1f, normalized * mouthGain));
        // A shallow curve keeps quiet speech visible while preventing loud
        // syllables from dwelling at the model's maximum mouth opening.
        mouthTarget = (float) Math.sqrt(normalized) * maxOpen;
    }

    private void updateMouth(float deltaSeconds) {
        if (mouthParameterIndex < 0 || mouthParameterIndex >= getModel().getParameterCount()) {
            Log.i("JARVIS_LIVE2D", "mouth skipped=" + mouthParameterId.getString());
            return;
        }
        float seconds = mouthTarget > mouthApplied ? mouthAttackSeconds : mouthReleaseSeconds;
        float alpha = 1f - (float) Math.exp(-Math.max(0f, deltaSeconds) / seconds);
        mouthApplied += (mouthTarget - mouthApplied) * alpha;
        float min = getModel().getParameterMinimumValue(mouthParameterIndex);
        float max = getModel().getParameterMaximumValue(mouthParameterIndex);
        float parameterValue = min + (max - min) * mouthApplied;
        getModel().setParameterValue(mouthParameterId, Math.max(min, Math.min(max, parameterValue)));
    }

    private CubismMotion findMotion(String name) {
        if (name == null || name.isEmpty()) return null;
        String normalized = name.toLowerCase(Locale.ROOT);
        if (normalized.equals("idle")) {
            return idleMotions.isEmpty() ? null : idleMotions.get(0);
        }
        if (normalized.equals("idle2")) {
            return idleMotions.size() < 2 ? null : idleMotions.get(1);
        }
        CubismMotion exact = motions.get(normalized);
        if (exact != null) return exact;
        for (Map.Entry<String, CubismMotion> entry : motions.entrySet()) {
            if (entry.getKey().startsWith(normalized + ":")) return entry.getValue();
        }
        return null;
    }

    private String selectMotionName(String requested, List<String> candidates) {
        if (candidates != null && !candidates.isEmpty()) {
            List<String> available = new ArrayList<>();
            for (String candidate : candidates) {
                if (findMotion(candidate) != null) available.add(candidate);
            }
            if (!available.isEmpty()) {
                String poolKey = String.join("|", available);
                int start = motionCandidateCursors.getOrDefault(poolKey, 0) % available.size();
                for (int offset = 0; offset < available.size(); offset++) {
                    int index = (start + offset) % available.size();
                    String candidate = available.get(index);
                    if (!candidate.equals(lastMotion) || available.size() == 1) {
                        motionCandidateCursors.put(poolKey, (index + 1) % available.size());
                        return candidate;
                    }
                }
                String candidate = available.get(start);
                motionCandidateCursors.put(poolKey, (start + 1) % available.size());
                return candidate;
            }
        }
        return requested == null ? "" : requested;
    }

    private static String motionName(String fileName) {
        String name = new File(fileName).getName().toLowerCase(Locale.ROOT);
        String suffix = ".motion3.json";
        return name.endsWith(suffix) ? name.substring(0, name.length() - suffix.length()) : name;
    }

    void removeExpression(String name) {
        if (expressions.containsKey(name)) expressionManager.stopAllMotions();
    }

    void draw() { if (getRenderer() != null) getRenderer().drawModel(); }
    void closeModel() { delete(); }

    private byte[] read(String relativePath) throws IOException {
        return Files.readAllBytes(new File(root, relativePath).toPath());
    }

    static void initializeFramework(AssetManager assets) {
        if (!CubismFramework.isStarted()) {
            CubismFramework.Option option = new CubismFramework.Option();
            option.loadFileFunction = path -> {
                try (InputStream input = assets.open(path)) {
                    return input.readAllBytes();
                } catch (IOException error) {
                    throw new IllegalStateException("Unable to load Cubism asset: " + path, error);
                }
            };
            CubismFramework.startUp(option);
        }
        if (!CubismFramework.isInitialized()) CubismFramework.initialize();
    }
}
