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
    private final Map<String, CubismExpressionMotion> expressions = new HashMap<>();
    private final CubismMatrix44 projectionMatrix = CubismMatrix44.create();
    private final CubismMatrix44 mvpMatrix = CubismMatrix44.create();
    private final CubismId mouthParameterId;
    private final float mouthMin;
    private final float mouthMax;
    private final float mouthGain;
    private String lastExpression = "";
    private String lastMotion = "";
    private String lastState = "";

    Live2DModel(File root, File model3Json, String mouthParameterName, float mouthMin, float mouthMax, float mouthGain) throws IOException {
        this.root = root;
        setting = new CubismModelSettingJson(Files.readAllBytes(model3Json.toPath()));
        loadModel(read(setting.getModelFileName()));
        mouthParameterId = CubismFramework.getIdManager().getId(mouthParameterName);
        this.mouthMin = mouthMin;
        this.mouthMax = mouthMax;
        this.mouthGain = mouthGain;
        if (!setting.getPhysicsFileName().isEmpty()) loadPhysics(read(setting.getPhysicsFileName()));
        for (int i = 0; i < setting.getExpressionCount(); i++) {
            CubismExpressionMotion expression = loadExpression(
                    read(setting.getExpressionFileName(i)));
            if (expression != null) expressions.put(setting.getExpressionName(i), expression);
        }
        if (setting.getMotionGroupCount() > 0) {
            String group = setting.getMotionGroupName(0);
            for (int i = 0; i < setting.getMotionCount(group); i++) {
                CubismMotion loaded = loadMotion(read(setting.getMotionFileName(group, i)));
                if (loaded != null) {
                    motions.put(group.toLowerCase(Locale.ROOT) + ":" + i, loaded);
                    idleMotions.add(loaded);
                }
            }
        }
        for (CubismMotion motion : idleMotions) motion.setLoop(idleMotions.size() == 1);
        eyeBlink = CubismEyeBlink.create(setting);
        breath = CubismBreath.create();
        configureBreath();
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
        getModelMatrix().setHeight(2.15f);
        getModelMatrix().setY(-0.28f);

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

    void applyRuntimeUpdate(String state, String expression, String motion, float intensity) {
        if (state == null) state = "idle";
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
        if (!motion.equals(lastMotion)) {
            CubismMotion selected = findMotion(motion);
            if (selected == null) {
                Log.i("JARVIS_LIVE2D", "motion skipped=" + motion);
            } else {
                motionManager.startMotionPriority(selected, 1);
                Log.i("JARVIS_LIVE2D", "motion applied=" + motion);
            }
            lastMotion = motion;
        }
    }

    void setMouthOpen(float value) {
        float clamped = Math.max(mouthMin, Math.min(mouthMax, value * mouthGain));
        int parameterIndex = getModel().getParameterIndex(mouthParameterId);
        if (parameterIndex >= getModel().getParameterCount()) {
            Log.i("JARVIS_LIVE2D", "mouth skipped=" + mouthParameterId.getString());
            return;
        }
        getModel().setParameterValue(mouthParameterId, clamped);
    }

    private CubismMotion findMotion(String name) {
        if (name == null || name.isEmpty()) return null;
        String normalized = name.toLowerCase(Locale.ROOT);
        for (Map.Entry<String, CubismMotion> entry : motions.entrySet()) {
            if (entry.getKey().startsWith(normalized + ":")) return entry.getValue();
        }
        return null;
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
