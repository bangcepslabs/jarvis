package com.example.avatar_client

import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.StandardMessageCodec

class MainActivity : FlutterActivity() {
    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        flutterEngine
            .platformViewsController
            .registry
            .registerViewFactory("jarvis/live2d", Live2DPlatformViewFactory(this, StandardMessageCodec.INSTANCE))
    }
}
