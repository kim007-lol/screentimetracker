package com.screentimetrack.app

import android.animation.ValueAnimator
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.res.Configuration
import android.graphics.PixelFormat
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.PowerManager
import android.os.SystemClock
import android.provider.Settings
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.view.ViewConfiguration
import android.view.WindowManager
import android.view.animation.LinearInterpolator
import android.webkit.WebView
import android.widget.FrameLayout
import android.widget.ImageView
import java.lang.ref.WeakReference
import java.util.concurrent.RejectedExecutionException
import java.util.concurrent.atomic.AtomicBoolean

/**
 * A full-body companion that roams over other apps in a small, draggable
 * window. It is a separate opt-in from the pill: the service starts only when
 * the user turns it on, pauses on screen-off or while the app is foreground,
 * and keeps a single static poster in flat mode.
 *
 * Full mode reuses [PetLife] and [PetWebRenderer], so spontaneous behavior,
 * sleep priority, and mood follow exactly the same rules as the pill.
 */
class PetOverlayService : Service() {
    companion object {
        const val PREFS = "pet_overlay_prefs"
        const val KEY_LANGUAGE = "language"
        const val KEY_PET = "pet"
        const val KEY_STAGE = "stage"
        const val KEY_ANIMATION = "animation"
        const val KEY_X = "posX"
        const val KEY_Y = "posY"
        const val KEY_FALLBACK = "fallback"
        private const val CHANNEL_ID = "momo_roam"
        private const val NOTIF_ID = 43
        private const val REFRESH_MS = 60_000L
        private const val POKE_DELAY_MS = 400L
        private const val POKE_GAP_MS = 1_200L
        private const val LONG_PRESS_MS = 480L
        private const val START_DELAY_MS = 180L
        private const val SIZE_DP = 160f
        private const val WALK_DISTANCE_DP = 72f

        @Volatile var isRunning = false
            private set
        @Volatile private var hostForeground = false
        private var instance: WeakReference<PetOverlayService>? = null
        private var lastPoke = 0L

        fun start(context: Context) {
            val intent = Intent(context, PetOverlayService::class.java)
            if (Build.VERSION.SDK_INT >= 26) context.startForegroundService(intent)
            else context.startService(intent)
        }

        /** Stops the window synchronously before the async service stop. */
        fun stop(context: Context) {
            instance?.get()?.tearDown()
            context.stopService(Intent(context, PetOverlayService::class.java))
        }

        /** The app's own screens must never have the roaming pet on top. */
        fun setHostForeground(foreground: Boolean) {
            hostForeground = foreground
            // Channel calls can arrive on a worker thread, but window and
            // WebView changes must run on main.
            instance?.get()?.let { service ->
                service.handler.post { service.applyHostVisibility() }
            }
        }

        /** HP or rest state changed; re-read soon without a storm. */
        fun notifyStatsChanged() {
            val service = instance?.get() ?: return
            val now = SystemClock.elapsedRealtime()
            if (now - lastPoke < POKE_GAP_MS) return
            lastPoke = now
            service.handler.removeCallbacks(service.refresh)
            service.handler.postDelayed(service.refresh, POKE_DELAY_MS)
        }

        /** Rest state changed: sleep or wake the rig without waiting for a tick. */
        fun notifyStateChanged() {
            instance?.get()?.let { service ->
                service.handler.post { service.life?.sync() }
            }
        }

        /** True when full animation failed and the static poster took over. */
        fun isFallback(context: Context): Boolean =
            context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .getBoolean(KEY_FALLBACK, false)
    }

    private lateinit var windowManager: WindowManager
    private var root: FrameLayout? = null
    private var petView: View? = null
    private var params: WindowManager.LayoutParams? = null
    private val handler = Handler(Looper.getMainLooper())
    private val worker = NativeStore.executor("pet-overlay", 1)
    private val busy = AtomicBoolean(false)
    @Volatile private var alive = false
    private var receiverRegistered = false
    private var renderer: PetWebRenderer? = null
    private var life: PetLife? = null
    private var liveView: WebView? = null
    private var posterView: ImageView? = null
    private var animationFull = false
    private var currentHp = 100
    private var direction = 1
    private var walking: ValueAnimator? = null
    private var downRawX = 0f
    private var downRawY = 0f
    private var startX = 0
    private var startY = 0
    private var dragging = false
    private var longPressed = false
    private val refresh = Runnable { refreshStats() }
    /** Starts the rig only after a visible window can give it a surface. */
    private val startRenderer = Runnable {
        if (alive && !hostForeground && screenOn() && animationFull &&
            root?.visibility == View.VISIBLE
        ) {
            renderer?.start()
        }
    }
    private val longPress = Runnable {
        if (!dragging && alive) {
            longPressed = true
            if (rigReady()) life?.onPet() else popPet()
        }
    }
    private val screenReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            if (intent?.action == Intent.ACTION_SCREEN_OFF) {
                cancelWalk()
                handler.removeCallbacks(refresh)
                if (renderer?.isStarted != true) handler.removeCallbacks(startRenderer)
            }
            life?.sync()
            if (alive && intent?.action == Intent.ACTION_SCREEN_ON) {
                handler.removeCallbacks(refresh)
                handler.post(refresh)
                maybeStartRenderer()
            }
        }
    }

    private fun prefs() = getSharedPreferences(PREFS, Context.MODE_PRIVATE)
    private fun currentPet(): PetKind =
        PetKind.parse(prefs().getString(KEY_PET, PetKind.MOMO.storageValue))
    private fun screenOn() = (getSystemService(Context.POWER_SERVICE) as PowerManager).isInteractive
    private fun canShow() = NativeStore.enabled(this) && Settings.canDrawOverlays(this) &&
        UsageRepo.hasUsageAccess(this)
    private fun dp(value: Float) = (value * resources.displayMetrics.density).toInt()
    private fun english() = prefs().getString(KEY_LANGUAGE, "id") == "en"

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        windowManager = getSystemService(Context.WINDOW_SERVICE) as WindowManager
        startForeground(NOTIF_ID, buildNotification())
        instance = WeakReference(this)
        if (!canShow()) { stopSelf(); return }
        alive = true; isRunning = true
        val filter = IntentFilter().apply { addAction(Intent.ACTION_SCREEN_ON); addAction(Intent.ACTION_SCREEN_OFF) }
        if (Build.VERSION.SDK_INT >= 33) registerReceiver(screenReceiver, filter, Context.RECEIVER_NOT_EXPORTED)
        else registerReceiver(screenReceiver, filter)
        receiverRegistered = true
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == "stop" || !canShow() || !alive) { tearDown(); stopSelf(); return START_NOT_STICKY }
        // Rebuild on every explicit start so stage, mode, and language change together.
        removeOverlay()
        addOverlay()
        (getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager).notify(NOTIF_ID, buildNotification())
        return START_NOT_STICKY
    }

    override fun onConfigurationChanged(newConfig: Configuration) {
        super.onConfigurationChanged(newConfig)
        root?.post { keepOnScreen() }
    }

    private fun tearDown() {
        alive = false; isRunning = false
        handler.removeCallbacksAndMessages(null)
        worker.shutdownNow()
        cancelWalk()
        removeOverlay()
        if (receiverRegistered) { unregisterReceiver(screenReceiver); receiverRegistered = false }
    }

    override fun onDestroy() {
        tearDown()
        if (instance?.get() === this) instance = null
        super.onDestroy()
    }

    private fun removeOverlay() {
        cancelWalk()
        handler.removeCallbacks(startRenderer)
        life?.dispose(); life = null
        renderer?.destroy(); renderer = null
        liveView = null; posterView = null
        petView?.animate()?.cancel()
        root?.let { runCatching { windowManager.removeView(it) } }
        root = null; petView = null; params = null
        animationFull = false
    }

    private fun addOverlay() {
        val stage = PetStage.parse(prefs().getString(KEY_STAGE, "bayi"))
        animationFull = prefs().getString(KEY_ANIMATION, "flat") == "full"
        prefs().edit().putBoolean(KEY_FALLBACK, false).apply()

        val container = FrameLayout(this).apply {
            isClickable = true
            isFocusable = true
            contentDescription = if (english()) {
                "${currentPet().label}, the roaming pet"
            } else {
                "${currentPet().label}, pet keliling"
            }
            setOnTouchListener { view, event -> handleTouch(view, event) }
            setOnClickListener { tapPet() }
        }
        if (animationFull) {
            // Poster first: the window must never be a transparent hole while
            // the rig warms up or after a failure.
            installPoster(container)
            val webRenderer = PetWebRenderer(
                this, stage,
                pet = currentPet(),
                onLoaded = { onRendererLoaded() },
                onUnavailable = { fallbackToPoster() },
            )
            renderer = webRenderer
            val web = webRenderer.create()
            if (web != null) {
                // Keep it visible but transparent so Chromium owns a real
                // surface; the poster behind shows through until the rig is
                // ready and is then switched off.
                container.addView(web, FrameLayout.LayoutParams(-1, -1))
                // The WebView would otherwise swallow every gesture.
                web.setOnTouchListener { _, event -> handleTouch(container, event) }
                liveView = web
                life = PetLife(
                    handler, webRenderer,
                    mood = { PetBehavior.mood(currentHp) },
                    stage = { PetStage.parse(prefs().getString(KEY_STAGE, "bayi")) },
                    resting = { PillService.isResting(this) },
                    allowed = {
                        alive && !hostForeground && screenOn() && animationFull &&
                            root?.visibility == View.VISIBLE
                    },
                    pet = { currentPet() },
                    onWalk = { duration -> startWalk(duration) },
                )
            } else {
                animationFull = false
                renderer = null
                prefs().edit().putBoolean(KEY_FALLBACK, true).apply()
            }
        } else {
            installPoster(container)
        }

        val type = if (Build.VERSION.SDK_INT >= 26) WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
            else @Suppress("DEPRECATION") WindowManager.LayoutParams.TYPE_PHONE
        val savedX = prefs().getInt(KEY_X, Int.MIN_VALUE)
        val savedY = prefs().getInt(KEY_Y, Int.MIN_VALUE)
        val size = dp(SIZE_DP)
        val layoutParams = WindowManager.LayoutParams(size, size, type,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
                WindowManager.LayoutParams.FLAG_HARDWARE_ACCELERATED,
            PixelFormat.TRANSLUCENT).apply {
            gravity = Gravity.TOP or Gravity.START
            x = if (savedX == Int.MIN_VALUE) 0 else savedX
            y = if (savedY == Int.MIN_VALUE) 0 else savedY
        }
        try { windowManager.addView(container, layoutParams) } catch (_: RuntimeException) {
            tearDown(); stopSelf(); return
        }
        root = container; params = layoutParams
        container.post {
            val bounds = screenBounds()
            val insets = screenInsets()
            if (savedX == Int.MIN_VALUE) layoutParams.x = bounds.width() - size - dp(12f)
            if (savedY == Int.MIN_VALUE) layoutParams.y = bounds.height() - size - dp(120f)
            val (x, y) = PetOverlayGeometry.clamp(
                layoutParams.x, layoutParams.y, size, size,
                bounds.width(), bounds.height(), insets.first, insets.second,
            )
            layoutParams.x = x; layoutParams.y = y
            runCatching { windowManager.updateViewLayout(container, layoutParams) }
        }
        applyHostVisibility()
        refreshStats()
    }

    private fun installPoster(container: FrameLayout? = null) {
        val target = container ?: root ?: return
        val icon = ImageView(this).apply {
            setImageResource(poster(parseStage()))
            scaleType = ImageView.ScaleType.FIT_CENTER
            contentDescription = null
            alpha = 0.96f
        }
        target.removeAllViews()
        target.addView(icon, FrameLayout.LayoutParams(-1, -1))
        icon.setOnTouchListener { _, event -> handleTouch(target, event) }
        posterView = icon
        petView = icon
        target.post { keepOnScreen() }
    }

    /** The rig reported ready: reveal it and retire the placeholder poster. */
    private fun onRendererLoaded() {
        if (!alive || !animationFull) return
        val web = liveView ?: return
        posterView?.visibility = View.GONE
        web.visibility = View.VISIBLE
        petView = web
        life?.onLoaded()
    }

    private fun rigReady(): Boolean = animationFull && renderer?.isLoaded == true

    private fun maybeStartRenderer() {
        if (!alive || hostForeground || !screenOn() || !animationFull) return
        if (root?.visibility != View.VISIBLE) return
        val active = renderer ?: return
        if (active.isStarted || active.isLoaded) return
        handler.removeCallbacks(startRenderer)
        handler.postDelayed(startRenderer, START_DELAY_MS)
    }

    private fun fallbackToPoster() {
        if (!alive || !animationFull) return
        animationFull = false
        handler.removeCallbacks(startRenderer)
        life?.dispose(); life = null
        renderer?.destroy(); renderer = null
        liveView = null
        prefs().edit().putBoolean(KEY_FALLBACK, true).apply()
        val container = root ?: return
        installPoster(container)
    }

    private fun parseStage(): PetStage = PetStage.parse(prefs().getString(KEY_STAGE, "bayi"))

    private fun poster(stage: PetStage): Int = when (currentPet()) {
        PetKind.MOMO -> when (stage) {
            PetStage.BAYI -> R.drawable.pet_roam_bayi
            PetStage.REMAJA -> R.drawable.pet_roam_remaja
            PetStage.DEWASA -> R.drawable.pet_roam_dewasa
        }
        PetKind.DRAKO -> when (stage) {
            PetStage.BAYI -> R.drawable.pet_roam_drako_bayi
            PetStage.REMAJA -> R.drawable.pet_roam_drako_remaja
            PetStage.DEWASA -> R.drawable.pet_roam_drako_dewasa
        }
    }

    private fun screenBounds() = if (Build.VERSION.SDK_INT >= 30) {
        windowManager.currentWindowMetrics.bounds
    } else {
        android.graphics.Rect(0, 0, resources.displayMetrics.widthPixels, resources.displayMetrics.heightPixels)
    }

    private fun screenInsets(): Pair<Int, Int> = if (Build.VERSION.SDK_INT >= 30) {
        val bars = windowManager.currentWindowMetrics.windowInsets
            .getInsets(android.view.WindowInsets.Type.systemBars())
        bars.top to bars.bottom
    } else 0 to 0

    /** Clamp the whole window inside the usable screen with a small margin. */
    private fun keepOnScreen() {
        val view = root ?: return
        val layoutParams = params ?: return
        val bounds = screenBounds()
        val (top, bottom) = screenInsets()
        val (x, y) = PetOverlayGeometry.clamp(
            layoutParams.x, layoutParams.y, view.width, view.height,
            bounds.width(), bounds.height(), top + dp(4f), bottom + dp(4f),
        )
        layoutParams.x = x; layoutParams.y = y
        runCatching { windowManager.updateViewLayout(view, layoutParams) }
    }

    private fun handleTouch(view: View, event: MotionEvent): Boolean {
        val layoutParams = params ?: return false
        when (event.actionMasked) {
            MotionEvent.ACTION_DOWN -> {
                cancelWalk()
                downRawX = event.rawX; downRawY = event.rawY
                startX = layoutParams.x; startY = layoutParams.y
                dragging = false; longPressed = false
                handler.postDelayed(longPress, LONG_PRESS_MS)
                return true
            }
            MotionEvent.ACTION_MOVE -> {
                val dx = event.rawX - downRawX
                val dy = event.rawY - downRawY
                if (!dragging && Math.hypot(dx.toDouble(), dy.toDouble()) >
                    ViewConfiguration.get(this).scaledTouchSlop
                ) {
                    dragging = true
                    handler.removeCallbacks(longPress)
                }
                if (dragging) {
                    layoutParams.x = startX + dx.toInt()
                    layoutParams.y = startY + dy.toInt()
                    keepOnScreen()
                    view.rotation = (dx * 0.08f).coerceIn(-8f, 8f)
                }
                return true
            }
            MotionEvent.ACTION_UP -> {
                handler.removeCallbacks(longPress)
                if (dragging) {
                    prefs().edit().putInt(KEY_X, layoutParams.x).putInt(KEY_Y, layoutParams.y).apply()
                    view.animate().rotation(0f).setDuration(160).start()
                } else if (!longPressed) {
                    tapPet()
                }
                dragging = false
                return true
            }
            MotionEvent.ACTION_CANCEL -> {
                handler.removeCallbacks(longPress)
                dragging = false
                view.animate().rotation(0f).setDuration(160).start()
                return true
            }
        }
        return false
    }

    private fun tapPet() {
        if (!alive) return
        if (rigReady()) life?.onTap() else popPet()
    }

    /** A tiny bob is the whole reaction in static mode; no loop runs. */
    private fun popPet() {
        val view = petView ?: return
        view.animate().cancel()
        view.scaleX = 1.1f; view.scaleY = 0.9f
        view.animate().scaleX(1f).scaleY(1f).setDuration(240).start()
    }

    /**
     * The walk clip asks for two cycles; the window travels for exactly the
     * same duration and bounces at the screen edge.
     */
    private fun startWalk(durationMs: Long) {
        if (!animationFull) return
        val layoutParams = params ?: return
        val view = root ?: return
        val width = view.width
        if (width <= 0) return
        val bounds = screenBounds()
        val (target, nextDirection) = PetOverlayGeometry.step(
            layoutParams.x, width, bounds.width(), direction, dp(WALK_DISTANCE_DP),
        )
        direction = nextDirection
        if (target == layoutParams.x) return
        val from = layoutParams.x
        cancelWalk()
        walking = ValueAnimator.ofFloat(0f, 1f).apply {
            duration = durationMs.coerceAtLeast(600L)
            interpolator = LinearInterpolator()
            addUpdateListener { animator ->
                if (!alive || hostForeground || !screenOn()) return@addUpdateListener
                val t = animator.animatedValue as Float
                layoutParams.x = from + ((target - from) * t).toInt()
                runCatching { windowManager.updateViewLayout(view, layoutParams) }
            }
            start()
        }
    }

    private fun cancelWalk() {
        walking?.cancel()
        walking = null
    }

    private fun applyHostVisibility() {
        val visible = !hostForeground
        root?.visibility = if (visible) View.VISIBLE else View.GONE
        if (!visible) {
            cancelWalk()
            handler.removeCallbacks(refresh)
            handler.removeCallbacks(longPress)
            if (renderer?.isStarted != true) handler.removeCallbacks(startRenderer)
        } else if (alive) {
            handler.removeCallbacks(refresh)
            handler.post(refresh)
        }
        life?.sync()
        if (visible) {
            maybeStartRenderer()
            root?.post { keepOnScreen() }
        }
    }

    private fun refreshStats() {
        if (!alive) return
        if (!canShow()) { tearDown(); stopSelf(); return }
        if (!screenOn() || hostForeground || !busy.compareAndSet(false, true)) return
        val token = NativeStore.generation
        try {
            worker.execute {
                val totals = runCatching { UsageRepo.totalsToday(this) }
                handler.post {
                    busy.set(false)
                    if (!alive) return@post
                    if (!canShow() || token != NativeStore.generation) { tearDown(); stopSelf(); return@post }
                    totals.onSuccess { (minutes, scrolls) ->
                        currentHp = PetBehavior.hp(minutes, scrolls, PillService.hpBonusToday(this))
                        life?.sync()
                    }
                    handler.removeCallbacks(refresh)
                    if (!hostForeground && screenOn()) handler.postDelayed(refresh, REFRESH_MS)
                }
            }
        } catch (_: RejectedExecutionException) { busy.set(false) }
    }

    private fun buildNotification(): Notification {
        val manager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        if (Build.VERSION.SDK_INT >= 26) {
            manager.createNotificationChannel(
                NotificationChannel(
                    CHANNEL_ID,
                    if (english()) "Roaming pet" else "Pet keliling",
                    NotificationManager.IMPORTANCE_LOW,
                ).apply { setShowBadge(false) },
            )
        }
        val open = PendingIntent.getActivity(this, 0, Intent(this, MainActivity::class.java)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val builder = if (Build.VERSION.SDK_INT >= 26) Notification.Builder(this, CHANNEL_ID)
            else @Suppress("DEPRECATION") Notification.Builder(this)
        return builder
            .setContentTitle(if (english()) "Roaming pet" else "Pet keliling")
            .setContentText(
                if (english()) {
                    "${currentPet().label} walks over other apps. Tap to open the app."
                } else {
                    "${currentPet().label} menemani di atas aplikasi lain. Ketuk untuk membuka aplikasi."
                },
            )
            .setSmallIcon(R.drawable.ic_pill).setContentIntent(open).setOngoing(true).build()
    }
}
