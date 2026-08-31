package com.example.avatar_client

import android.Manifest
import android.content.pm.PackageManager
import android.util.Log
import androidx.core.content.ContextCompat
import com.rementia.openwakeword.lib.WakeWordEngine
import com.rementia.openwakeword.lib.model.DetectionMode
import com.rementia.openwakeword.lib.model.WakeWordModel
import io.flutter.embedding.android.FlutterActivity
import io.flutter.plugin.common.BinaryMessenger
import io.flutter.plugin.common.EventChannel
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.MethodChannel
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.launch

class OpenWakeWordBridge(private val activity: FlutterActivity) : MethodChannel.MethodCallHandler, EventChannel.StreamHandler {
    companion object { private const val TAG = "JARVIS_WAKE_WORD" }
    private var engine: WakeWordEngine? = null
    private var detectionJob: Job? = null
    private var sink: EventChannel.EventSink? = null
    private var pendingUnavailable: String? = null
    private val scope = CoroutineScope(Dispatchers.Main.immediate)

    fun attach(messenger: BinaryMessenger) {
        MethodChannel(messenger, "jarvis/wake_word").setMethodCallHandler(this)
        EventChannel(messenger, "jarvis/wake_word/events").setStreamHandler(this)
    }

    override fun onMethodCall(call: MethodCall, result: MethodChannel.Result) {
        try {
            when (call.method) {
                "initialize" -> { initialize(call.argument<String>("modelAsset") ?: "wake_word/development/hey_jarvis.onnx", call.argument<Double>("threshold")?.toFloat() ?: .5f); result.success(null) }
                "start" -> {
                    if (ContextCompat.checkSelfPermission(activity, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) result.error("PERMISSION", "RECORD_AUDIO permission is required", null)
                    else { Log.i(TAG, "mic starting; native AudioRecord owns microphone"); engine?.start() ?: emitUnavailable("wake word model unavailable"); result.success(null) }
                }
                "stop" -> { engine?.stop(); Log.i(TAG, "detector stopped; microphone released"); result.success(null) }
                "dispose" -> { disposeEngine(); result.success(null) }
                else -> result.notImplemented()
            }
        } catch (error: Exception) { emitError(error.message ?: "native wake word error"); result.error("WAKE_WORD", error.message, null) }
    }

    private fun initialize(modelAsset: String, threshold: Float) {
        disposeEngine()
        val modelDirectory = "wake_word/development/"
        val required = listOf(
            "${modelDirectory}melspectrogram.onnx",
            "${modelDirectory}embedding_model.onnx",
            modelAsset,
        )
        val missing = required.filterNot { assetExists(it) }
        if (missing.isNotEmpty()) { Log.i(TAG, "model unavailable: ${missing.joinToString()}"); pendingUnavailable = "Missing wake word assets: ${missing.joinToString()}"; return }
        Log.i(TAG, "wake engine initialized; assets loaded: ${required.joinToString()}")
        engine = WakeWordEngine(activity, listOf(WakeWordModel("Hey Jarvis", modelAsset, threshold)), DetectionMode.SINGLE_BEST, 2000L, scope)
        detectionJob = scope.launch { engine!!.detections.collect { d -> Log.i(TAG, "detection event emitted: ${d.model.name} score=${d.score}"); sink?.success(mapOf("type" to "detected", "name" to d.model.name, "score" to d.score.toDouble())) } }
    }

    private fun assetExists(path: String): Boolean = try { activity.assets.open(path).close(); true } catch (_: Exception) { false }
    private fun emitUnavailable(reason: String) { pendingUnavailable = reason; sink?.success(mapOf("type" to "unavailable", "reason" to reason)) }
    private fun emitError(message: String) { sink?.success(mapOf("type" to "error", "message" to message)) }
    private fun disposeEngine() { detectionJob?.cancel(); detectionJob = null; engine?.release(); engine = null }
    fun onDestroy() { disposeEngine() }
    override fun onListen(arguments: Any?, events: EventChannel.EventSink?) { sink = events; pendingUnavailable?.let { emitUnavailable(it); pendingUnavailable = null } }
    override fun onCancel(arguments: Any?) { sink = null }
}
