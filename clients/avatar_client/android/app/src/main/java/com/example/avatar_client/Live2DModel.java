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
import java.util.Map;
import java.util.ArrayList;
import java.util.List;

/** App-owned adapter around the official Cubism Java Framework. */
final class Live2DModel extends CubismUserModel {
    private final File root;
    private final CubismModelSettingJson setting;
    private final List<CubismMotion> idleMotions = new ArrayList<>();
    private int idleMotionIndex;
    private final CubismEyeBlink eyeBlink;
    private final CubismBreath breath;
    private final Map<String, CubismExpressionMotion> expressions = new HashMap<>();
    private final int mouthParameterIndex;
    private final float mouthParameterMax = 2.1f;
    private final float mouthGain;
    private final CubismMatrix44 projectionMatrix = CubismMatrix44.create();
    private final CubismMatrix44 mvpMatrix = CubismMatrix44.create();
    private volatile float mouthOpen;

    Live2DModel(File root, File model3Json, float mouthGain) throws IOException {
        this.root = root;
        this.mouthGain = Math.max(0.0f, Math.min(2.0f, mouthGain));
        setting = new CubismModelSettingJson(Files.readAllBytes(model3Json.toPath()));
        loadModel(read(setting.getModelFileName()));
        if (!setting.getPhysicsFileName().isEmpty()) loadPhysics(read(setting.getPhysicsFileName()));
        for (int i = 0; i < setting.getExpressionCount(); i++) {
            CubismExpressionMotion expression = loadExpression(
                    read(setting.getExpressionFileName(i)));
            if (expression != null) expressions.put(setting.getExpressionName(i), expression);
        }
        if (setting.getMotionGroupCount() > 0) {
            String group = setting.getMotionGroupName(0);
            for (int i = 0; i < setting.getMotionCount(group); i++) {
                CubismMotion motion = loadMotion(read(setting.getMotionFileName(group, i)));
                if (motion != null) idleMotions.add(motion);
            }
        }
        for (CubismMotion motion : idleMotions) motion.setLoop(idleMotions.size() == 1);
        eyeBlink = CubismEyeBlink.create(setting);
        breath = CubismBreath.create();
        configureBreath();
        mouthParameterIndex = findParameterIndex("ParamMouthOpenY");
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
                " canvas=" + getModel().getCanvasWidth() + "x" + getModel().getCanvasHeight());
    }

    void updateViewport(int width, int height) {
        if (getRenderer() == null || width <= 0 || height <= 0) return;
        setRenderTargetSize(width, height);
        getModelMatrix().loadIdentity();
        // Keep presentation framing independent from viewport aspect correction.
        getModelMatrix().setHeight(2.95f);
        getModelMatrix().setY(-0.30f);

        // Keep model framing uniform. The viewport maps clip-space X/Y to
        // different physical pixel scales on a portrait surface, so correct
        // that in a separate projection matrix instead of distorting the
        // model matrix itself.
        float viewportAspect = (float) width / (float) height;
        float projectionScaleX = viewportAspect < 1.0f ? 1.0f / viewportAspect : 1.0f;
        float projectionScaleY = viewportAspect > 1.0f ? viewportAspect : 1.0f;
        projectionMatrix.loadIdentity();
        projectionMatrix.scale(projectionScaleX, projectionScaleY);
        mvpMatrix.setMatrix(projectionMatrix);
        mvpMatrix.multiplyByMatrix(getModelMatrix());
        getRenderer().setMvpMatrix(mvpMatrix);
        Log.i("JARVIS_LIVE2D", "viewport=" + width + "x" + height +
                " viewportAspect=" + viewportAspect +
                " canvas=" + getModel().getCanvasWidth() + "x" + getModel().getCanvasHeight() +
                " canvasAspect=" + ((float) getModel().getCanvasWidth() / getModel().getCanvasHeight()) +
                " modelScaleX=" + getModelMatrix().getScaleX() +
                " modelScaleY=" + getModelMatrix().getScaleY() +
                " projectionScaleX=" + projectionScaleX +
                " projectionScaleY=" + projectionScaleY +
                " uniformModelScale=" +
                (getModelMatrix().getScaleX() == getModelMatrix().getScaleY()));
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
        }
        expressionManager.updateMotion(getModel(), deltaSeconds);
        eyeBlink.updateParameters(getModel(), deltaSeconds);
        breath.updateParameters(getModel(), deltaSeconds);
        if (physics != null) physics.evaluate(getModel(), deltaSeconds);
        if (mouthParameterIndex >= 0) {
            float value = Math.min(mouthParameterMax, mouthOpen * mouthParameterMax * mouthGain);
            getModel().setParameterValue(mouthParameterIndex, value);
        }
        getModel().update();
    }

    void setMouthOpen(float normalizedValue) {
        if (getModel() == null || mouthParameterIndex < 0) return;
        mouthOpen = Math.max(0.0f, Math.min(1.0f, normalizedValue));
    }

    private int findParameterIndex(String id) {
        for (int i = 0; i < getModel().getParameterCount(); i++) {
            CubismId parameterId = getModel().getParameterId(i);
            if (id.equals(parameterId.getString())) return i;
        }
        return -1;
    }

    private CubismId findParameterId(String id) {
        for (int i = 0; i < getModel().getParameterCount(); i++) {
            CubismId parameterId = getModel().getParameterId(i);
            if (id.equals(parameterId.getString())) return parameterId;
        }
        return null;
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

    boolean applyExpression(String name) {
        CubismExpressionMotion expression = expressions.get(name);
        if (expression == null) return false;
        return expressionManager.startMotionPriority(expression, 1) >= 0;
    }

    void removeExpression(String name) {
        if (name.isEmpty() || expressions.containsKey(name)) expressionManager.stopAllMotions();
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
