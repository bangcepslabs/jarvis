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
            if (call.method != "setMouthOpen" && call.method != "applyExpression" && call.method != "clearExpression") {
                result.notImplemented()
                return@setMethodCallHandler
            }
            val view = Live2DPlatformViewFactory.current
            when (call.method) {
                "setMouthOpen" -> view?.setMouthOpen((call.arguments as? Number)?.toDouble() ?: 0.0)
                "applyExpression" -> view?.applyExpression(call.arguments as? String ?: "")
                "clearExpression" -> view?.clearExpression(call.arguments as? String ?: "")
            }
            result.success(true)
        }
    }
}
