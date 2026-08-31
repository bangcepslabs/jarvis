package com.example.avatar_client

import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine

class MainActivity : FlutterActivity() {
    private lateinit var wakeWordBridge: OpenWakeWordBridge

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        wakeWordBridge = OpenWakeWordBridge(this)
        wakeWordBridge.attach(flutterEngine.dartExecutor.binaryMessenger)
    }

    override fun onDestroy() {
        if (::wakeWordBridge.isInitialized) wakeWordBridge.onDestroy()
        super.onDestroy()
    }
}
