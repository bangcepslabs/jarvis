package com.example.avatar_client;

import android.content.res.AssetManager;
import android.util.Log;

import com.live2d.sdk.cubism.framework.CubismFramework;
import com.live2d.sdk.cubism.framework.CubismModelSettingJson;
import com.live2d.sdk.cubism.framework.model.CubismUserModel;
import com.live2d.sdk.cubism.framework.motion.CubismMotion;
import com.live2d.sdk.cubism.framework.motion.CubismExpressionMotion;
import com.live2d.sdk.cubism.framework.math.CubismMatrix44;
import com.live2d.sdk.cubism.framework.rendering.android.CubismRendererAndroid;
import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.io.InputStream;
import java.util.HashMap;
import java.util.Map;

/** App-owned adapter around the official Cubism Java Framework. */
final class Live2DModel extends CubismUserModel {
    private final File root;
    private final CubismModelSettingJson setting;
    private final CubismMotion idleMotion;
    private final Map<String, CubismExpressionMotion> expressions = new HashMap<>();
    private final CubismMatrix44 projectionMatrix = CubismMatrix44.create();
    private final CubismMatrix44 mvpMatrix = CubismMatrix44.create();

    Live2DModel(File root, File model3Json) throws IOException {
        this.root = root;
        setting = new CubismModelSettingJson(Files.readAllBytes(model3Json.toPath()));
        loadModel(read(setting.getModelFileName()));
        if (!setting.getPhysicsFileName().isEmpty()) loadPhysics(read(setting.getPhysicsFileName()));
        for (int i = 0; i < setting.getExpressionCount(); i++) {
            CubismExpressionMotion expression = loadExpression(
                    read(setting.getExpressionFileName(i)));
            if (expression != null) expressions.put(setting.getExpressionName(i), expression);
        }
        CubismMotion motion = null;
        if (setting.getMotionGroupCount() > 0) {
            String group = setting.getMotionGroupName(0);
            if (setting.getMotionCount(group) > 0) motion = loadMotion(read(setting.getMotionFileName(group, 0)));
        }
        idleMotion = motion;
    }

    void initializeRenderer(int width, int height) {
        CubismRendererAndroid renderer = (CubismRendererAndroid) CubismRendererAndroid.create(width, height);
        setupRenderer(renderer, 1);
        updateViewport(width, height);
        if (idleMotion != null) motionManager.startMotionPriority(idleMotion, 1);
    }

    void updateViewport(int width, int height) {
        if (getRenderer() == null || width <= 0 || height <= 0) return;
        setRenderTargetSize(width, height);
        getModelMatrix().loadIdentity();
        getModelMatrix().setHeight(2.25f);
        getModelMatrix().setY(-0.20f);

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
        expressionManager.updateMotion(getModel(), deltaSeconds);
        if (physics != null) physics.evaluate(getModel(), deltaSeconds);
        getModel().update();
    }

    boolean applyExpression(String name) {
        CubismExpressionMotion expression = expressions.get(name);
        if (expression == null) return false;
        return expressionManager.startMotionPriority(expression, 1) >= 0;
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
