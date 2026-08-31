package com.example.avatar_client

import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.android.RenderMode
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import io.flutter.plugin.common.StandardMessageCodec

class MainActivity : FlutterActivity() {
    private lateinit var wakeWordBridge: OpenWakeWordBridge
    private var textureHost: Live2DTextureHost? = null
    // Hybrid-composed Live2D owns a GLSurfaceView. Keep Flutter itself on a
    // TextureView so the two SurfaceView layers do not compete after an
    // activity pause/resume.
    override fun getRenderMode(): RenderMode = RenderMode.texture

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        wakeWordBridge = OpenWakeWordBridge(this)
        wakeWordBridge.attach(flutterEngine.dartExecutor.binaryMessenger)
        flutterEngine
            .platformViewsController
            .registry
            .registerViewFactory("jarvis/live2d", Live2DPlatformViewFactory(flutterEngine.dartExecutor.binaryMessenger, StandardMessageCodec.INSTANCE))
        textureHost = Live2DTextureHost(this, flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "jarvis/live2d/texture")
            .setMethodCallHandler(textureHost)
    }

    override fun onDestroy() {
        if (::wakeWordBridge.isInitialized) wakeWordBridge.onDestroy()
        textureHost?.release()
        textureHost = null
        super.onDestroy()
    }
}
