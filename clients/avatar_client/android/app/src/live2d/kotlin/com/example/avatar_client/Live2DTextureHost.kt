package com.example.avatar_client

import android.content.Context
import android.net.Uri
import android.opengl.EGL14
import android.opengl.EGLConfig as AndroidEglConfig
import android.opengl.EGLContext
import android.opengl.EGLDisplay
import android.opengl.EGLSurface
import android.util.Log
import android.os.Handler
import android.os.Looper
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.MethodChannel
import io.flutter.view.TextureRegistry
import android.view.Surface
import java.io.File
import java.io.FileOutputStream
import java.util.concurrent.atomic.AtomicBoolean

/** Owns a Flutter texture and its EGL surface independently of PlatformView. */
class Live2DTextureHost(
    private val context: Context,
    engine: FlutterEngine,
) : MethodChannel.MethodCallHandler {
    private val textureRegistry = engine.renderer
    private var producer = textureRegistry.createSurfaceProducer(TextureRegistry.SurfaceLifecycle.resetInBackground)
    private var generation = 0
    private val running = AtomicBoolean(false)
    private val mainHandler = Handler(Looper.getMainLooper())
    private var renderer: Live2DRenderer? = null
    private var renderThread: Thread? = null
    private var released = false
    private var paused = false

    init {
        configureTexture()
        producer.setCallback(object : TextureRegistry.SurfaceProducer.Callback {
            override fun onSurfaceAvailable() {
                Log.i("JARVIS_LIVE2D", "surface_texture_available generation=$generation")
                if (!paused && !released) startRendering()
            }

            override fun onSurfaceCleanup() {
                Log.i("JARVIS_LIVE2D", "surface_texture_destroyed generation=$generation")
                stopRendering()
            }
        })
        Log.i("JARVIS_LIVE2D", "surface_producer_created id=${producer.id()} generation=$generation")
    }

    override fun onMethodCall(call: MethodCall, result: MethodChannel.Result) {
        when (call.method) {
            "create" -> try {
                if (renderer == null) {
                    val params = call.arguments as? Map<*, *> ?: error("create requires parameters")
                    renderer = createRenderer(params)
                }
                startRendering()
                    result.success(producer.id())
            } catch (error: Exception) {
                Log.e("JARVIS_LIVE2D", "texture renderer creation failed", error)
                result.error("renderer_creation_failed", error.message, null)
            }
            "update" -> {
                val params = call.arguments as? Map<*, *>
                if (params == null) result.error("invalid_arguments", "update requires a parameter map", null)
                else {
                    renderer?.setPendingUpdate(params)
                    result.success(null)
                }
            }
            "lifecycle" -> {
                val resumed = (call.arguments as? Map<*, *>)?.get("resumed") as? Boolean ?: false
                Log.i("JARVIS_LIVE2D", "texture_lifecycle resumed=$resumed paused=$paused id=${producer.id()} generation=$generation")
                if (resumed) {
                    if (paused) {
                        stopRendering()
                        generation += 1
                        configureTexture()
                        paused = false
                        Log.i("JARVIS_LIVE2D", "surface_texture_reacquired id=${producer.id()} generation=$generation")
                        startRendering()
                    }
                    result.success(producer.id())
                } else {
                    paused = true
                    stopRendering()
                    result.success(null)
                }
            }
            "release" -> {
                Log.i("JARVIS_LIVE2D", "texture_release_requested id=${producer.id()}")
                release()
                result.success(null)
            }
            else -> result.notImplemented()
        }
    }

    private fun configureTexture() {
        val metrics = context.resources.displayMetrics
        producer.setSize(metrics.widthPixels, metrics.heightPixels)
    }

    private fun createRenderer(params: Map<*, *>): Live2DRenderer {
        val asset = params["modelAsset"] as? String ?: error("modelAsset is missing")
        val source = "flutter_assets/" + asset.split('/').joinToString("/")
        val destination = File(context.cacheDir, "jarvis-live2d/${source.substringBeforeLast('/')}")
        copyAssetTree(source.substringBeforeLast('/'), destination)
        val name = asset.substringAfterLast('/')
        val model = destination.walkTopDown().firstOrNull {
            it.isFile && (it.name == name || Uri.decode(it.name) == name)
        } ?: destination.walkTopDown().firstOrNull {
            it.isFile && it.name.endsWith(".model3.json")
        } ?: error("Live2D model not found")
        return Live2DRenderer(model.parentFile!!, model, context.assets, params["expression"] as? String ?: "").also {
            it.setPendingUpdate(params)
        }
    }

    private fun copyAssetTree(source: String, destination: File) {
        val children = context.assets.list(source) ?: emptyArray()
        if (children.isEmpty()) {
            destination.parentFile?.mkdirs()
            context.assets.open(source).use { input -> FileOutputStream(destination).use { output -> input.copyTo(output) } }
            return
        }
        destination.mkdirs()
        children.forEach { child -> copyAssetTree("$source/$child", File(destination, Uri.decode(child))) }
    }

    private fun startRendering() {
        if (released || paused || renderer == null || !running.compareAndSet(false, true)) return
        val target = renderer ?: return
        val thread = Thread({
            var egl: EglTextureSession? = null
            try {
                egl = EglTextureSession(producer.getSurface())
                egl.makeCurrent()
                Log.i("JARVIS_LIVE2D", "texture_surface_available")
                target.onSurfaceCreated(null, null)
                val metrics = context.resources.displayMetrics
                target.onSurfaceChanged(null, metrics.widthPixels, metrics.heightPixels)
                Log.i("JARVIS_LIVE2D", "egl_surface_created")
                while (running.get() && !released && !paused) {
                    target.onDrawFrame(null)
                    if (!egl.swapBuffers()) break
                    // ImageReaderSurfaceProducer schedules the Flutter frame
                    // through FlutterJNI, which must run on the UI thread.
                    mainHandler.post {
                        if (!released) producer.scheduleFrame()
                    }
                }
            } catch (error: Exception) {
                Log.e("JARVIS_LIVE2D", "texture render loop failed", error)
            } finally {
                target.release()
                egl?.close()
                Log.i("JARVIS_LIVE2D", "egl_surface_destroyed")
                running.set(false)
            }
        }, "jarvis-live2d-texture-render")
        renderThread = thread
        thread.start()
    }

    private fun stopRendering() {
        running.set(false)
        val thread = renderThread ?: return
        thread.let {
            it.interrupt()
            if (it !== Thread.currentThread()) {
                try {
                    // Model/resource creation can be in progress when Android
                    // backgrounds the activity. Never start a second renderer
                    // against the shared Live2D instance until this one exits.
                    it.join(15_000)
                } catch (_: InterruptedException) {
                    Thread.currentThread().interrupt()
                }
            }
        }
        if (!thread.isAlive) {
            renderThread = null
        } else {
            Log.e("JARVIS_LIVE2D", "render_thread_stop_timeout")
        }
    }

    fun release() {
        if (released) return
        released = true
        stopRendering()
        producer.release()
        Log.i("JARVIS_LIVE2D", "texture_released id=${producer.id()} generation=$generation")
    }
}

private class EglTextureSession(texture: Surface) {
    private val display: EGLDisplay = EGL14.eglGetDisplay(EGL14.EGL_DEFAULT_DISPLAY)
    private val context: EGLContext
    private val surface: EGLSurface

    init {
        check(display != EGL14.EGL_NO_DISPLAY) { "Unable to acquire EGL display" }
        val version = IntArray(2)
        check(EGL14.eglInitialize(display, version, 0, version, 1)) { "Unable to initialize EGL" }
        val attributes = intArrayOf(EGL14.EGL_RENDERABLE_TYPE, EGL14.EGL_OPENGL_ES2_BIT, EGL14.EGL_SURFACE_TYPE, EGL14.EGL_WINDOW_BIT, EGL14.EGL_RED_SIZE, 8, EGL14.EGL_GREEN_SIZE, 8, EGL14.EGL_BLUE_SIZE, 8, EGL14.EGL_ALPHA_SIZE, 8, EGL14.EGL_NONE)
        val configs = arrayOfNulls<AndroidEglConfig>(1)
        val count = IntArray(1)
        check(EGL14.eglChooseConfig(display, attributes, 0, configs, 0, 1, count, 0) && count[0] > 0) { "Unable to choose EGL config" }
        val config = configs[0] ?: error("Missing EGL config")
        context = EGL14.eglCreateContext(display, config, EGL14.EGL_NO_CONTEXT, intArrayOf(EGL14.EGL_CONTEXT_CLIENT_VERSION, 2, EGL14.EGL_NONE), 0)
        check(context != EGL14.EGL_NO_CONTEXT) { "Unable to create EGL context" }
        surface = EGL14.eglCreateWindowSurface(display, config, texture, intArrayOf(EGL14.EGL_NONE), 0)
        check(surface != EGL14.EGL_NO_SURFACE) { "Unable to create EGL window surface" }
    }

    fun makeCurrent() { check(EGL14.eglMakeCurrent(display, surface, surface, context)) { "Unable to make EGL context current" } }
    fun swapBuffers(): Boolean = EGL14.eglSwapBuffers(display, surface)
    fun close() {
        EGL14.eglMakeCurrent(display, EGL14.EGL_NO_SURFACE, EGL14.EGL_NO_SURFACE, EGL14.EGL_NO_CONTEXT)
        EGL14.eglDestroySurface(display, surface)
        EGL14.eglDestroyContext(display, context)
        EGL14.eglTerminate(display)
    }
}
