package com.example.avatar_client

import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.StandardMessageCodec
import io.flutter.plugin.common.MethodChannel
import io.flutter.plugin.platform.PlatformViewRegistry

class MainActivity : FlutterActivity() {
    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        flutterEngine
            .platformViewsController
            .registry
            .registerViewFactory("jarvis/live2d", Live2DPlatformViewFactory(this, StandardMessageCodec.INSTANCE))
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "jarvis/live2d")
            .setMethodCallHandler { call, result ->
                if (call.method != "setMouthOpen") {
                    result.notImplemented()
                    return@setMethodCallHandler
                }
                val value = (call.arguments as? Number)?.toDouble() ?: 0.0
                Live2DPlatformViewFactory.current?.setMouthOpen(value)
                result.success(null)
            }
    }
}
