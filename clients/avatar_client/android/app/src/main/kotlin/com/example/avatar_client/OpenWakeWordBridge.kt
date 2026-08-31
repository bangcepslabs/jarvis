package com.example.avatar_client

import android.Manifest
import android.content.pm.PackageManager
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
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
    companion object {
        private const val TAG = "JARVIS_WAKE_WORD"
        const val RECORD_AUDIO_REQUEST_CODE = 4107
    }
    private var engine: WakeWordEngine? = null
    private var detectionJob: Job? = null
    private var sink: EventChannel.EventSink? = null
    private var pendingUnavailable: String? = null
    private var pendingStart = false
    private var engineStarted = false
    private var configuredThreshold = .5f
    private var engineStartedAtMs = 0L
    // Wake-word audio processing and ONNX inference must stay off the UI thread.
    private val scope = CoroutineScope(Dispatchers.Default)

    fun attach(messenger: BinaryMessenger) {
        MethodChannel(messenger, "jarvis/wake_word").setMethodCallHandler(this)
        EventChannel(messenger, "jarvis/wake_word/events").setStreamHandler(this)
    }

    override fun onMethodCall(call: MethodCall, result: MethodChannel.Result) {
        try {
            when (call.method) {
                "initialize" -> { initialize(call.argument<String>("modelAsset") ?: "wake_word/development/hey_jarvis.onnx", call.argument<Double>("threshold")?.toFloat() ?: .5f, result) }
                "start" -> {
                    Log.i(TAG, "start request received; engine=${engine != null}")
                    if (ContextCompat.checkSelfPermission(activity, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
                        pendingStart = true
                        Log.i(TAG, "requesting RECORD_AUDIO permission for wake word")
                        activity.requestPermissions(arrayOf(Manifest.permission.RECORD_AUDIO), RECORD_AUDIO_REQUEST_CODE)
                        result.success(null)
                    } else {
                        startEngine()
                        result.success(null)
                    }
                }
                "stop" -> {
                    if (engineStarted) {
                        engine?.stop()
                        engineStarted = false
                        Log.i(TAG, "detector stopped; microphone released")
                    }
                    result.success(null)
                }
                "dispose" -> { disposeEngine(); result.success(null) }
                else -> result.notImplemented()
            }
        } catch (error: Exception) { emitError(error.message ?: "native wake word error"); result.error("WAKE_WORD", error.message, null) }
    }

    private fun initialize(modelAsset: String, threshold: Float, result: MethodChannel.Result) {
        disposeEngine()
        val modelDirectory = "wake_word/development/"
        val required = listOf(
            "${modelDirectory}melspectrogram.onnx",
            "${modelDirectory}embedding_model.onnx",
            modelAsset,
        )
        val missing = required.filterNot { assetExists(it) }
        if (missing.isNotEmpty()) {
            Log.i(TAG, "model unavailable: ${missing.joinToString()}")
            pendingUnavailable = "Missing wake word assets: ${missing.joinToString()}"
            result.success(null)
            return
        }
        Log.i(TAG, "wake engine initialized; assets loaded: ${required.joinToString()}")
        configuredThreshold = threshold.coerceIn(0f, 1f)
        Log.i(TAG, "wake threshold configured=$configuredThreshold warmup_ms=500")
        scope.launch {
            try {
                val initializedEngine = WakeWordEngine(
                    activity,
                    listOf(WakeWordModel("Hey Jarvis", modelAsset, threshold)),
                    DetectionMode.SINGLE_BEST,
                    2000L,
                    scope,
                )
                engine = initializedEngine
                detectionJob = scope.launch {
                    initializedEngine.detections.collect { d ->
                        val score = d.score
                        val warmup = SystemClock.elapsedRealtime() - engineStartedAtMs < 500L
                        if (score < configuredThreshold || warmup) {
                            Log.d(TAG, "detection ignored score=$score threshold=$configuredThreshold warmup=$warmup")
                            return@collect
                        }
                        Log.i(TAG, "detection event emitted: ${d.model.name} score=$score")
                        Handler(Looper.getMainLooper()).post {
                            sink?.success(mapOf("type" to "detected", "name" to d.model.name, "score" to score.toDouble()))
                        }
                    }
                }
                Handler(Looper.getMainLooper()).post {
                    val permissionGranted = ContextCompat.checkSelfPermission(activity, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED
                    Log.i(TAG, "wake engine ready; recordAudioPermission=$permissionGranted")
                    if (permissionGranted) {
                        startEngine()
                    } else {
                        pendingStart = true
                        Log.i(TAG, "requesting RECORD_AUDIO permission for wake word")
                        activity.requestPermissions(arrayOf(Manifest.permission.RECORD_AUDIO), RECORD_AUDIO_REQUEST_CODE)
                    }
                    result.success(null)
                }
            } catch (error: Exception) {
                Log.e(TAG, "wake engine initialization failed", error)
                pendingUnavailable = "Wake word initialization failed"
                Handler(Looper.getMainLooper()).post {
                    emitUnavailable("Wake word initialization failed")
                    result.success(null)
                }
            }
        }
    }

    private fun assetExists(path: String): Boolean = try { activity.assets.open(path).close(); true } catch (_: Exception) { false }
    private fun startEngine() {
        if (engineStarted) return
        Log.i(TAG, "mic starting; native AudioRecord owns microphone")
        if (engine == null) {
            emitUnavailable("wake word model unavailable")
            return
        }
        engineStarted = true
        engineStartedAtMs = SystemClock.elapsedRealtime()
        try {
            engine!!.start()
            Log.i(TAG, "audio capture running")
        } catch (error: Exception) {
            engineStarted = false
            Log.e(TAG, "audio capture failed", error)
            throw error
        }
    }

    fun onRequestPermissionsResult(requestCode: Int, grantResults: IntArray) {
        if (requestCode != RECORD_AUDIO_REQUEST_CODE || !pendingStart) return
        pendingStart = false
        if (grantResults.firstOrNull() == PackageManager.PERMISSION_GRANTED) {
            startEngine()
        } else {
            emitUnavailable("RECORD_AUDIO permission denied")
        }
    }
    private fun emitUnavailable(reason: String) { pendingUnavailable = reason; sink?.success(mapOf("type" to "unavailable", "reason" to reason)) }
    private fun emitError(message: String) { sink?.success(mapOf("type" to "error", "message" to message)) }
    private fun disposeEngine() { detectionJob?.cancel(); detectionJob = null; engine?.release(); engine = null; engineStarted = false }
    fun onDestroy() { disposeEngine() }
    override fun onListen(arguments: Any?, events: EventChannel.EventSink?) { sink = events; pendingUnavailable?.let { emitUnavailable(it); pendingUnavailable = null } }
    override fun onCancel(arguments: Any?) { sink = null }
}
