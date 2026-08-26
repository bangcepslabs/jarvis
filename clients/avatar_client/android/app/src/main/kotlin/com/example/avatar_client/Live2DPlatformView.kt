package com.example.avatar_client

import android.content.Context
import android.graphics.BitmapFactory
import android.opengl.GLES20
import android.opengl.GLUtils
import android.opengl.GLSurfaceView
import android.view.View
import io.flutter.plugin.common.StandardMessageCodec
import io.flutter.plugin.platform.PlatformView
import io.flutter.plugin.platform.PlatformViewFactory
import java.io.File
import java.io.FileOutputStream
import javax.microedition.khronos.egl.EGLConfig
import javax.microedition.khronos.opengles.GL10
import com.live2d.sdk.cubism.framework.rendering.android.CubismRendererAndroid

class Live2DPlatformViewFactory(private val context: Context, codec: StandardMessageCodec) : PlatformViewFactory(codec) {
    override fun create(context: Context, id: Int, args: Any?): PlatformView =
        Live2DPlatformView(context, args as? Map<*, *>)
}

class Live2DPlatformView(context: Context, params: Map<*, *>?) : PlatformView {
    private val view: Live2DGlView

    init {
        view = try {
            val asset = params?.get("modelAsset") as? String ?: error("modelAsset is missing")
            val model = extractModelTree(context, asset)
            Live2DGlView(context, model.parentFile!!, model)
        } catch (error: Exception) {
            Live2DGlView(context, null, null).also { it.failure = error.message }
        }
    }

    override fun getView(): View = view
    override fun dispose() { view.release() }

    private fun extractModelTree(context: Context, modelAsset: String): File {
        val source = "flutter_assets/$modelAsset"
        val sourceDir = source.substringBeforeLast('/')
        val destination = File(context.cacheDir, "jarvis-live2d/$sourceDir")
        copyAssetTree(context, sourceDir, destination)
        return File(destination, modelAsset.substringAfterLast('/'))
    }

    private fun copyAssetTree(context: Context, source: String, destination: File) {
        destination.mkdirs()
        val children = context.assets.list(source) ?: emptyArray()
        if (children.isEmpty()) {
            context.assets.open(source).use { input ->
                FileOutputStream(destination).use { output -> input.copyTo(output) }
            }
            return
        }
        for (child in children) copyAssetTree(context, "$source/$child", File(destination, child))
    }
}

private class Live2DGlView(context: Context, private val root: File?, private val modelFile: File?) : GLSurfaceView(context) {
    private val liveRenderer = Live2DRenderer(root, modelFile)
    var failure: String?
        get() = liveRenderer.failure
        set(value) { liveRenderer.failure = value }

    init {
        setEGLContextClientVersion(2)
        setRenderer(liveRenderer)
        renderMode = RENDERMODE_CONTINUOUSLY
    }

    fun release() {
        queueEvent { liveRenderer.release() }
        onPause()
    }
}

private class Live2DRenderer(private val root: File?, private val modelFile: File?) : GLSurfaceView.Renderer {
    private var model: Live2DModel? = null
    private var textureIds = IntArray(0)
    private var lastNanos = 0L
    var failure: String? = null

    override fun onSurfaceCreated(gl: GL10?, config: EGLConfig?) {
        GLES20.glClearColor(0.06f, 0.17f, 0.26f, 1f)
        if (root == null || modelFile == null) return
        try {
            Live2DModel.initializeFramework()
            model = Live2DModel(root, modelFile)
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
                bitmap.recycle()
                cubism.bindTexture(i, textureIds[i])
            }
            lastNanos = System.nanoTime()
        } catch (error: Exception) {
            failure = error.message ?: error.javaClass.simpleName
            model = null
        }
    }

    override fun onSurfaceChanged(gl: GL10?, width: Int, height: Int) {
        GLES20.glViewport(0, 0, width, height)
        model?.setRenderTargetSize(width, height)
    }

    override fun onDrawFrame(gl: GL10?) {
        GLES20.glClear(GLES20.GL_COLOR_BUFFER_BIT)
        val now = System.nanoTime()
        val delta = if (lastNanos == 0L) 1f / 60f else ((now - lastNanos) / 1_000_000_000f).coerceAtMost(0.1f)
        lastNanos = now
        model?.update(delta)
        model?.draw()
    }

    fun release() {
        model?.closeModel()
        model = null
        if (textureIds.isNotEmpty()) GLES20.glDeleteTextures(textureIds.size, textureIds, 0)
    }
}
