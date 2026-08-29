package com.example.avatar_client

import android.content.Context
import android.graphics.BitmapFactory
import android.graphics.Color
import android.opengl.GLES20
import android.opengl.GLUtils
import android.opengl.GLSurfaceView
import android.net.Uri
import android.util.Log
import android.view.View
import android.view.ViewGroup
import android.view.SurfaceHolder
import android.widget.FrameLayout
import java.util.Locale
import java.util.concurrent.atomic.AtomicLong
import io.flutter.plugin.common.StandardMessageCodec
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.MethodChannel
import io.flutter.plugin.common.BinaryMessenger
import io.flutter.plugin.platform.PlatformView
import io.flutter.plugin.platform.PlatformViewFactory
import java.io.File
import java.io.FileOutputStream
import javax.microedition.khronos.egl.EGLConfig
import javax.microedition.khronos.opengles.GL10
import com.live2d.sdk.cubism.framework.rendering.android.CubismRendererAndroid

class Live2DPlatformViewFactory(private val messenger: BinaryMessenger, codec: StandardMessageCodec) : PlatformViewFactory(codec) {
    override fun create(context: Context, id: Int, args: Any?): PlatformView =
        Live2DPlatformView(context, id, messenger, args as? Map<*, *>)
}

class Live2DPlatformView(context: Context, id: Int, messenger: BinaryMessenger, params: Map<*, *>?) : PlatformView, MethodChannel.MethodCallHandler {
    private val view: Live2DGlView
    private val container: FrameLayout
    private val channel = MethodChannel(messenger, "jarvis/live2d/$id")

    init {
        view = try {
            val asset = params?.get("modelAsset") as? String ?: error("modelAsset is missing")
            val expression = params?.get("expression") as? String ?: ""
            val model = extractModelTree(context, asset)
            Live2DGlView(context, model.parentFile!!, model, expression)
        } catch (error: Exception) {
            Log.e("JARVIS_LIVE2D", "Asset extraction failed", error)
            Live2DGlView(context, null, null, "").also { it.failure = error.message }
        }
        container = FrameLayout(context).apply {
            setBackgroundColor(Color.rgb(10, 28, 46))
            addView(view, ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT)
        }
        channel.setMethodCallHandler(this)
        if (params != null) view.update(params)
        view.resumeRendering()
    }

    override fun getView(): View = container
    override fun onMethodCall(call: MethodCall, result: MethodChannel.Result) {
        when (call.method) {
            "update" -> {
                if (call.arguments !is Map<*, *>) {
                    result.error("invalid_arguments", "update requires a parameter map", null)
                    return
                }
                view.update(call.arguments as Map<*, *>)
                result.success(null)
            }
            "lifecycle" -> {
                val params = call.arguments as? Map<*, *>
                view.setHostResumed(params?.get("resumed") as? Boolean ?: false)
                result.success(null)
            }
            else -> result.notImplemented()
        }
    }

    override fun dispose() {
        channel.setMethodCallHandler(null)
        view.release()
    }

    private fun extractModelTree(context: Context, modelAsset: String): File {
        // AssetManager addresses Flutter asset paths directly. URL-encoding
        // Unicode model directory names makes the lookup fail on Android.
        val source = "flutter_assets/" + modelAsset.split('/').joinToString("/")
        val sourceDir = source.substringBeforeLast('/')
        val destination = File(context.cacheDir, "jarvis-live2d/$sourceDir")
        Log.i("JARVIS_LIVE2D", "asset source=$sourceDir destination=${destination.absolutePath}")
        copyAssetTree(context, sourceDir, destination)
        val modelName = modelAsset.substringAfterLast('/')
        val extractedModel = destination.walkTopDown().firstOrNull {
            it.isFile && (it.name == modelName || Uri.decode(it.name) == modelName)
        } ?: File(destination, modelName)
        Log.i("JARVIS_LIVE2D", "model path=${extractedModel.absolutePath} exists=${extractedModel.isFile}")
        return extractedModel
    }

    private fun copyAssetTree(context: Context, source: String, destination: File) {
        val children = context.assets.list(source) ?: emptyArray()
        Log.i("JARVIS_LIVE2D", "asset list=$source -> ${children.joinToString()}")
        if (children.isEmpty()) {
            destination.parentFile?.mkdirs()
            context.assets.open(source).use { input ->
                FileOutputStream(destination).use { output -> input.copyTo(output) }
            }
            return
        }
        destination.mkdirs()
        for (child in children) {
            copyAssetTree(context, "$source/$child", File(destination, Uri.decode(child)))
        }
    }

}

private class Live2DGlView(context: Context, private val root: File?, private val modelFile: File?, expression: String) : GLSurfaceView(context) {
    private val liveRenderer = Live2DRenderer(root, modelFile, context.assets, expression)
    var failure: String?
        get() = liveRenderer.failure
        set(value) { liveRenderer.failure = value }

    init {
        setEGLContextClientVersion(2)
        setPreserveEGLContextOnPause(true)
        setRenderer(liveRenderer)
        renderMode = RENDERMODE_CONTINUOUSLY
        holder.addCallback(object : SurfaceHolder.Callback {
            override fun surfaceCreated(holder: SurfaceHolder) {
                Log.i("JARVIS_LIVE2D", "surface_created size=${width}x${height}")
            }

            override fun surfaceChanged(holder: SurfaceHolder, format: Int, width: Int, height: Int) {
                Log.i("JARVIS_LIVE2D", "surface_changed size=${width}x${height}")
            }

            override fun surfaceDestroyed(holder: SurfaceHolder) {
                Log.i("JARVIS_LIVE2D", "surface_destroyed")
                Log.i("JARVIS_LIVE2D", "egl_surface_destroyed")
            }
        })
    }

    fun setHostResumed(resumed: Boolean) {
        if (resumed) resumeRendering() else pauseRendering()
    }

    fun resumeRendering() {
        Log.i("JARVIS_LIVE2D", "host lifecycle=resumed")
        onResume()
        requestRender()
    }

    fun pauseRendering() {
        Log.i("JARVIS_LIVE2D", "host lifecycle=paused")
        onPause()
    }

    fun release() {
        queueEvent { liveRenderer.release() }
        pauseRendering()
    }

    fun update(params: Map<*, *>) {
        liveRenderer.setPendingUpdate(params)
        queueEvent { liveRenderer.applyPendingUpdate() }
    }
}

class Live2DRenderer(
    private val root: File?,
    private val modelFile: File?,
    private val assets: android.content.res.AssetManager,
    private val expression: String,
) : GLSurfaceView.Renderer {
    private var model: Live2DModel? = null
    private var textureIds = IntArray(0)
    private var lastNanos = 0L
    private var frameCounter = 0L
    private var diagnosticsWindowStartNanos = 0L
    private var diagnosticsFrames = 0L
    private var diagnosticsDeltaNanos = 0L
    private var diagnosticsMaxDeltaNanos = 0L
    private var diagnosticsUpdateNanos = 0L
    private var diagnosticsDrawNanos = 0L
    private var diagnosticsMaxUpdateNanos = 0L
    private var diagnosticsMaxDrawNanos = 0L
    private var diagnosticsSlowFrames = 0L
    private val runtimeUpdateCount = AtomicLong(0)
    private val mouthUpdateCount = AtomicLong(0)
    @Volatile private var pendingUpdate: Map<String, Any?>? = null
    var failure: String? = null

    fun setPendingUpdate(params: Map<*, *>) {
        pendingUpdate = params.entries.associate { it.key.toString() to it.value }
        runtimeUpdateCount.incrementAndGet()
        if (params.containsKey("mouthOpen")) mouthUpdateCount.incrementAndGet()
    }

    fun applyPendingUpdate() {
        val target = model ?: return
        val update = pendingUpdate ?: return
        target.applyRuntimeUpdate(
            update.string("state", "idle"),
            update.string("expression", ""),
            update.string("motion", ""),
            update.string("reaction", "none"),
            update.number("intensity", 0.3f),
        )
        target.setMouthTarget(
            update.number("mouthOpen", 0f),
            update.number("mouthMaxOpen", 0.72f),
            update.number("mouthNoiseGate", 0.04f),
        )
        pendingUpdate = null
    }

    override fun onSurfaceCreated(gl: GL10?, config: EGLConfig?) {
        Log.i("JARVIS_LIVE2D", "egl_surface_created")
        GLES20.glClearColor(0.06f, 0.17f, 0.26f, 1f)
        if (root == null || modelFile == null) return
        try {
            Live2DModel.initializeFramework(assets)
            val initial = pendingUpdate
            model = Live2DModel(
                root,
                modelFile,
                initial.string("mouthOpenParameter", "ParamMouthOpenY"),
                initial.number("mouthMin", 0f),
                initial.number("mouthMax", 1f),
                initial.number("mouthGain", 1f),
                initial.number("mouthMaxOpen", 0.72f),
                initial.number("mouthNoiseGate", 0.04f),
                initial.number("mouthAttackSeconds", 0.055f),
                initial.number("mouthReleaseSeconds", 0.14f),
            )
            if (expression.isNotEmpty()) {
                val applied = model!!.applyExpression(expression)
                Log.i("JARVIS_LIVE2D", "expression=$expression applied=$applied")
            }
            model!!.initializeRenderer(1, 1)
            textureIds = IntArray(model!!.textureCount())
            GLES20.glGenTextures(textureIds.size, textureIds, 0)
            val cubism = model!!.getRenderer<CubismRendererAndroid>()
            for (i in textureIds.indices) {
                val bitmap = BitmapFactory.decodeFile(model!!.textureFile(i).absolutePath)
                    ?: error("Unable to decode texture ${model!!.textureName(i)}")
                GLES20.glBindTexture(GLES20.GL_TEXTURE_2D, textureIds[i])
                GLES20.glTexParameteri(GLES20.GL_TEXTURE_2D, GLES20.GL_TEXTURE_MIN_FILTER, GLES20.GL_LINEAR)
                GLES20.glTexParameteri(GLES20.GL_TEXTURE_2D, GLES20.GL_TEXTURE_MAG_FILTER, GLES20.GL_LINEAR)
                GLUtils.texImage2D(GLES20.GL_TEXTURE_2D, 0, bitmap, 0)
                GLES20.glGenerateMipmap(GLES20.GL_TEXTURE_2D)
                bitmap.recycle()
                cubism.bindTexture(i, textureIds[i])
            }
            applyPendingUpdate()
            lastNanos = System.nanoTime()
        } catch (error: Exception) {
            failure = error.message ?: error.javaClass.simpleName
            Log.e("JARVIS_LIVE2D", "Cubism model initialization failed", error)
            model = null
        }
    }

    override fun onSurfaceChanged(gl: GL10?, width: Int, height: Int) {
        Log.i("JARVIS_LIVE2D", "renderer_resumed size=${width}x${height}")
        GLES20.glViewport(0, 0, width, height)
        model?.updateViewport(width, height)
    }

    override fun onDrawFrame(gl: GL10?) {
        GLES20.glClear(GLES20.GL_COLOR_BUFFER_BIT)
        applyPendingUpdate()
        val now = System.nanoTime()
        val rawDeltaNanos = if (lastNanos == 0L) 1_000_000_000L / 60L else now - lastNanos
        val rawDeltaSeconds = rawDeltaNanos / 1_000_000_000f
        val delta = rawDeltaSeconds.coerceAtMost(0.1f)
        lastNanos = now
        frameCounter++
        if (diagnosticsWindowStartNanos == 0L) diagnosticsWindowStartNanos = now
        diagnosticsFrames++
        diagnosticsDeltaNanos += rawDeltaNanos
        diagnosticsMaxDeltaNanos = maxOf(diagnosticsMaxDeltaNanos, rawDeltaNanos)
        if (rawDeltaNanos > 33_333_333L) diagnosticsSlowFrames++
        val currentModel = model
        val updateStartedNanos = System.nanoTime()
        currentModel?.update(delta)
        val updateElapsedNanos = System.nanoTime() - updateStartedNanos
        diagnosticsUpdateNanos += updateElapsedNanos
        diagnosticsMaxUpdateNanos = maxOf(diagnosticsMaxUpdateNanos, updateElapsedNanos)
        val drawStartedNanos = System.nanoTime()
        currentModel?.draw()
        val drawElapsedNanos = System.nanoTime() - drawStartedNanos
        diagnosticsDrawNanos += drawElapsedNanos
        diagnosticsMaxDrawNanos = maxOf(diagnosticsMaxDrawNanos, drawElapsedNanos)
        val diagnosticsElapsedNanos = now - diagnosticsWindowStartNanos
        if (diagnosticsElapsedNanos >= 2_000_000_000L) {
            val elapsedSeconds = diagnosticsElapsedNanos / 1_000_000_000.0
            val fps = diagnosticsFrames / elapsedSeconds
            val averageDeltaMs = diagnosticsDeltaNanos / diagnosticsFrames / 1_000_000.0
            val maxDeltaMs = diagnosticsMaxDeltaNanos / 1_000_000.0
            val averageUpdateMs = diagnosticsUpdateNanos / diagnosticsFrames / 1_000_000.0
            val averageDrawMs = diagnosticsDrawNanos / diagnosticsFrames / 1_000_000.0
            val maxUpdateMs = diagnosticsMaxUpdateNanos / 1_000_000.0
            val maxDrawMs = diagnosticsMaxDrawNanos / 1_000_000.0
            val runtimeUpdates = runtimeUpdateCount.getAndSet(0)
            val mouthUpdates = mouthUpdateCount.getAndSet(0)
            Log.i(
                "JARVIS_LIVE2D",
                String.format(
                    Locale.US,
                    "fps=%.1f avgDeltaMs=%.1f maxDeltaMs=%.1f " +
                        "updateMs=%.1f(max=%.1f) drawMs=%.1f(max=%.1f) slowFrames=%d " +
                        "runtimeUpdates=%d mouthUpdates=%d frame=%d delta=%.3f ",
                    fps,
                    averageDeltaMs,
                    maxDeltaMs,
                    averageUpdateMs,
                    maxUpdateMs,
                    averageDrawMs,
                    maxDrawMs,
                    diagnosticsSlowFrames,
                    runtimeUpdates,
                    mouthUpdates,
                    frameCounter,
                    delta,
                ) +
                    (currentModel?.debugAnimationSummary() ?: "model=null"),
            )
            diagnosticsWindowStartNanos = now
            diagnosticsFrames = 0L
            diagnosticsDeltaNanos = 0L
            diagnosticsMaxDeltaNanos = 0L
            diagnosticsUpdateNanos = 0L
            diagnosticsDrawNanos = 0L
            diagnosticsMaxUpdateNanos = 0L
            diagnosticsMaxDrawNanos = 0L
            diagnosticsSlowFrames = 0L
        }
    }

    fun release() {
        model?.closeModel()
        model = null
        if (textureIds.isNotEmpty()) GLES20.glDeleteTextures(textureIds.size, textureIds, 0)
    }
}

private fun Map<String, Any?>?.string(key: String, fallback: String): String =
    (this?.get(key) as? String) ?: fallback

private fun Map<String, Any?>?.number(key: String, fallback: Float): Float =
    (this?.get(key) as? Number)?.toFloat() ?: fallback
