package com.screentimetrack.app

import android.annotation.SuppressLint
import android.content.Context
import android.graphics.Color
import android.net.Uri
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.view.View
import android.view.ViewGroup
import android.webkit.ConsoleMessage
import android.webkit.JavascriptInterface
import android.webkit.RenderProcessGoneDetail
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import java.io.ByteArrayInputStream

/**
 * Transparent WebView that plays the bundled rig without Flutter.
 *
 * Everything is served from the APK's Flutter asset bundle through an exact
 * allowlist on [PetWebAssets.HOST]; the page never reaches the network. The
 * JavaScript bridge only accepts a fixed "loaded" event. A missing renderer or
 * a model that never loads is reported so the caller can fall back to the
 * static poster instead of pretending full animation is running.
 */
class PetWebRenderer(
    private val context: Context,
    private val stage: PetStage,
    /** Compact head framing for the pill; body framing for the roaming pet. */
    headFrame: Boolean = false,
    private val pet: PetKind = PetKind.MOMO,
    private val onLoaded: () -> Unit,
    private val onUnavailable: () -> Unit,
) {
    companion object {
        private const val TAG = "PetWebRenderer"
        private const val LOAD_TIMEOUT_MS = 10_000L
        private const val BRIDGE = "PetBridge"
    }

    private val main = Handler(Looper.getMainLooper())
    private var web: WebView? = null
    private var destroyed = false
    private var timeout: Runnable? = null

    var isLoaded = false
        private set

    /** Head-only framing for a compact pill, full body otherwise. */
    var headFrame = headFrame
        private set

    /** True once [start] has asked the page to load; a load never runs twice. */
    var isStarted = false
        private set

    @SuppressLint("SetJavaScriptEnabled")
    fun create(): WebView? {
        if (destroyed) return null
        web?.let { return it }
        val view = try {
            WebView(context)
        } catch (error: Throwable) {
            Log.w(TAG, "WebView is unavailable", error)
            notifyUnavailable()
            return null
        }
        view.setBackgroundColor(Color.TRANSPARENT)
        view.setLayerType(View.LAYER_TYPE_HARDWARE, null)
        view.isVerticalScrollBarEnabled = false
        view.isHorizontalScrollBarEnabled = false
        view.overScrollMode = View.OVER_SCROLL_NEVER
        view.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = false
            allowFileAccess = false
            allowContentAccess = false
            mediaPlaybackRequiresUserGesture = false
            cacheMode = WebSettings.LOAD_NO_CACHE
            setSupportZoom(false)
            builtInZoomControls = false
            displayZoomControls = false
            mixedContentMode = WebSettings.MIXED_CONTENT_NEVER_ALLOW
            if (Build.VERSION.SDK_INT >= 33) isAlgorithmicDarkeningAllowed = false
        }
        view.webViewClient = object : WebViewClient() {
            override fun shouldInterceptRequest(
                webView: WebView,
                request: WebResourceRequest,
            ): WebResourceResponse = serve(request.url)

            override fun shouldOverrideUrlLoading(
                webView: WebView,
                request: WebResourceRequest,
            ): Boolean = request.url.scheme != "about"

            override fun onPageFinished(webView: WebView, url: String?) {
                Log.i(TAG, "Pet page finished, starting the model")
            }

            override fun onReceivedError(
                webView: WebView,
                request: WebResourceRequest,
                error: WebResourceError,
            ) {
                if (request.isForMainFrame) {
                    Log.w(TAG, "Pet page error ${error.errorCode}: ${error.description}")
                }
            }

            override fun onRenderProcessGone(
                webView: WebView,
                detail: RenderProcessGoneDetail,
            ): Boolean {
                isLoaded = false
                main.post {
                    Log.w(TAG, "The WebView renderer stopped")
                    notifyUnavailable()
                }
                return true
            }
        }
        view.webChromeClient = object : WebChromeClient() {
            override fun onConsoleMessage(message: ConsoleMessage): Boolean {
                if (message.messageLevel() == ConsoleMessage.MessageLevel.ERROR) {
                    Log.w(TAG, "Pet page console: ${message.message()}")
                }
                return true
            }
        }
        view.addJavascriptInterface(Bridge(), BRIDGE)
        web = view
        return view
    }

    /**
     * Loads the page. Call only once the view is attached to a window the user
     * can actually see: a hidden overlay has no surface, and a WebGL page that
     * starts in that state never reports ready. The caller keeps a static
     * poster on screen until [onLoaded] arrives.
     */
    fun start() {
        if (destroyed || isStarted) return
        val view = web ?: return
        isStarted = true
        Log.i(TAG, "Starting the pet page")
        timeout = Runnable {
            if (!destroyed && !isLoaded) {
                Log.w(TAG, "The pet model did not load in time")
                notifyUnavailable()
            }
        }.also { main.postDelayed(it, LOAD_TIMEOUT_MS) }
        // A real https origin (served by [serve]) keeps the module script and
        // the GLB fetch same-origin; a data: document can be treated as opaque.
        view.loadUrl(PetWebAssets.BASE_URL)
    }

    /** Plays a looping base clip or a one-shot action. */
    fun play(clip: String, looping: Boolean) {
        val view = web ?: return
        if (destroyed || !isLoaded) return
        // Clip names come from PetCatalog; reject anything else before it
        // reaches the page's JavaScript.
        if (!clip.matches(Regex("[a-z_]{1,32}"))) return
        view.onResume()
        view.evaluateJavascript(
            "window.petPlay&&window.petPlay('$clip',$looping);",
            null,
        )
    }

    /**
     * Freezes the rig but keeps its last frame. Pausing the WebView itself
     * drops the transparent surface, so this is the only safe stop while the
     * pill is still on screen (for example behind an open panel).
     */
    fun hold() {
        if (destroyed || !isLoaded) return
        val view = web ?: return
        // The surface may have been paused earlier (screen off); resuming is
        // what brings the last frame back without restarting the clip.
        view.onResume()
        view.evaluateJavascript("window.petPause&&window.petPause();", null)
    }

    /** Stops both WebView timers and the rig; no frame is drawn while hidden. */
    fun pause() {
        if (destroyed || !isLoaded) return
        val view = web ?: return
        view.evaluateJavascript("window.petPause&&window.petPause();", null)
        view.onPause()
    }

    /**
     * Switches between the head portrait and the full body without reloading
     * the rig. Safe before load: the next served page uses [headFrame].
     */
    fun setHeadFrame(head: Boolean) {
        if (headFrame == head) return
        headFrame = head
        pushFrame()
    }

    private fun pushFrame() {
        val view = web ?: return
        if (destroyed || !isLoaded) return
        val mode = if (headFrame) "head" else "body"
        view.evaluateJavascript("window.petFrame&&window.petFrame('$mode');", null)
    }

    fun destroy() {
        destroyed = true
        timeout?.let(main::removeCallbacks)
        timeout = null
        web?.let { view ->
            (view.parent as? ViewGroup)?.removeView(view)
            runCatching { view.stopLoading() }
            runCatching { view.loadUrl("about:blank") }
            runCatching { view.removeJavascriptInterface(BRIDGE) }
            runCatching { view.destroy() }
        }
        web = null
    }

    private fun notifyUnavailable() {
        if (destroyed) return
        main.post { if (!destroyed) onUnavailable() }
    }

    private fun serve(uri: Uri): WebResourceResponse {
        if (uri.host != PetWebAssets.HOST) return empty(403, "Forbidden")
        if (uri.path == "/" || uri.path == "/index.html") {
            val page = PetWebAssets.html(stage, headFrame = headFrame, pet = pet)
                .toByteArray(Charsets.UTF_8)
            return WebResourceResponse(
                "text/html", "utf-8", 200, "OK", headers(),
                ByteArrayInputStream(page),
            )
        }
        val asset = PetWebAssets.assetFor(uri.path) ?: return empty(404, "Not found")
        return try {
            WebResourceResponse(
                asset.mime,
                null,
                200,
                "OK",
                headers(),
                context.assets.open(asset.path),
            )
        } catch (error: Throwable) {
            Log.w(TAG, "Bundled asset is missing: ${asset.path}")
            empty(404, "Not found")
        }
    }

    /** The whole page is local; CORS headers only unblock module/GLB fetches. */
    private fun headers(): Map<String, String> = mapOf(
        "Cache-Control" to "no-store",
        "Access-Control-Allow-Origin" to "*",
    )

    private fun empty(status: Int, reason: String): WebResourceResponse =
        WebResourceResponse(
            "text/plain",
            "utf-8",
            status,
            reason,
            headers(),
            ByteArrayInputStream(ByteArray(0)),
        )

    private inner class Bridge {
        @JavascriptInterface
        fun postMessage(message: String?) {
            if (message != "loaded") return
            main.post {
                if (destroyed || isLoaded) return@post
                isLoaded = true
                timeout?.let(main::removeCallbacks)
                timeout = null
                // The pill may have expanded while the page was loading.
                pushFrame()
                onLoaded()
            }
        }
    }
}
