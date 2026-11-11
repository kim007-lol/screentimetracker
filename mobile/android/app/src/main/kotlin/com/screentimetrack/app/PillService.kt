package com.screentimetrack.app

import android.animation.Animator
import android.animation.AnimatorListenerAdapter
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
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.PixelFormat
import android.graphics.Rect
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.graphics.drawable.TransitionDrawable
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.PowerManager
import android.os.SystemClock
import android.provider.Settings
import android.text.TextUtils
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.view.ViewConfiguration
import android.view.WindowManager
import android.view.animation.DecelerateInterpolator
import android.view.animation.OvershootInterpolator
import android.webkit.WebView
import android.widget.FrameLayout
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView
import java.lang.ref.WeakReference
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.UUID
import java.util.concurrent.RejectedExecutionException
import java.util.concurrent.atomic.AtomicBoolean

/**
 * A themed, localized view of the shared raw-usage cache; it never force-stops apps.
 *
 * The pill carries the selected companion stage, the foreground app's current
 * session and that app's scroll count. It can be dragged anywhere; the position
 * is kept in [PREFS] and clamped to the screen on every start.
 */
class PillService : Service() {
    companion object {
        const val PREFS = "pill_prefs"
        const val KEY_BACKGROUND = "bg"
        const val KEY_SURFACE = "surface"
        const val KEY_INK = "ink"
        const val KEY_ACCENT = "accent"
        const val KEY_RADIUS = "radius"
        const val KEY_LANGUAGE = "language"
        const val KEY_PET = "pet"
        const val KEY_STAGE = "stage"
        const val KEY_HP_BONUS = "hpBonus"
        const val KEY_HP_DAY = "hpDay"
        const val KEY_HP_HEALTHY = "hpHealthy"
        const val KEY_HP_TIRED = "hpTired"
        const val KEY_HP_CRITICAL = "hpCritical"
        const val KEY_ANIMATION = "animation"
        const val KEY_FORM = "form"
        const val KEY_RESTING = "resting"
        const val KEY_X = "posX"
        const val KEY_Y = "posY"
        const val KEY_REST_TOKEN = "restToken"
        const val EXTRA_REST_TOKEN = "restTokenExtra"
        const val ACTION_REST = "com.screentimetrack.action.REST"
        private const val CHANNEL_ID = "momo_pill"
        private const val NOTIF_ID = 42
        private const val REFRESH_MS = 30_000L
        /** Give the visible window one layout pass before waking WebGL. */
        private const val START_DELAY_MS = 180L
        /** Usage events can land a moment after the window change they describe. */
        private const val FRESH_RETRY_MS = 1_200L
        private const val FRESH_RETRIES = 2
        /** Compact head and the full-body greeting share one window. */
        private const val HOLDER_HEAD_DP = 28f
        private const val HOLDER_BODY_DP = 64f
        private const val HOLDER_ANIM_MS = 220L
        /** Let the body settle for a beat after growing, then show the panel. */
        private const val PANEL_DELAY_MS = HOLDER_ANIM_MS + 340L
        private const val DEFAULT_PET = "momo"
        /** Each companion ships its own [bayi, remaja, dewasa] art per mood: fresh, tired, critical. */
        private val mascotSets = mapOf(
            "momo" to arrayOf(
                intArrayOf(
                    R.drawable.pill_mascot_bayi,
                    R.drawable.pill_mascot_bayi_tired,
                    R.drawable.pill_mascot_bayi_critical,
                ),
                intArrayOf(
                    R.drawable.pill_mascot_remaja,
                    R.drawable.pill_mascot_remaja_tired,
                    R.drawable.pill_mascot_remaja_critical,
                ),
                intArrayOf(
                    R.drawable.pill_mascot_dewasa,
                    R.drawable.pill_mascot_dewasa_tired,
                    R.drawable.pill_mascot_dewasa_critical,
                ),
            ),
            "drako" to arrayOf(
                intArrayOf(
                    R.drawable.pill_mascot_drako_bayi,
                    R.drawable.pill_mascot_drako_bayi_tired,
                    R.drawable.pill_mascot_drako_bayi_critical,
                ),
                intArrayOf(
                    R.drawable.pill_mascot_drako_remaja,
                    R.drawable.pill_mascot_drako_remaja_tired,
                    R.drawable.pill_mascot_drako_remaja_critical,
                ),
                intArrayOf(
                    R.drawable.pill_mascot_drako_dewasa,
                    R.drawable.pill_mascot_drako_dewasa_tired,
                    R.drawable.pill_mascot_drako_dewasa_critical,
                ),
            ),
        )
        /**
         * Full-body art for the unified pill: one sprite per stage, drawn from
         * the same portrait as the head. Mood is still carried by the panel
         * portrait; a 64dp body reads better with one calm pose than with a
         * second expression the pill never has room to show.
         */
        private val bodySets = mapOf(
            "momo" to intArrayOf(
                R.drawable.pill_body_bayi,
                R.drawable.pill_body_remaja,
                R.drawable.pill_body_dewasa,
            ),
            "drako" to intArrayOf(
                R.drawable.pill_body_drako_bayi,
                R.drawable.pill_body_drako_remaja,
                R.drawable.pill_body_drako_dewasa,
            ),
        )
        /** Local day key matching Flutter's HistoryService.dayKey. */        fun todayKey(): String = SimpleDateFormat("yyyyMMdd", Locale.US).format(Date())
        /** Only today's recovery counts; a bonus from before midnight must not leak. */
        fun hpBonusToday(context: Context): Int {
            val p = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            return if (p.getString(KEY_HP_DAY, "") == todayKey()) {
                p.getInt(KEY_HP_BONUS, 0).coerceAtLeast(0)
            } else 0
        }
        /** Resting wins over every spontaneous action in both overlays. */
        fun isResting(context: Context): Boolean =
            context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .getBoolean(KEY_RESTING, false)
        /** Sleep must reach a running pill and roaming pet immediately. */
        fun setResting(context: Context, resting: Boolean) {
            context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
                .putBoolean(KEY_RESTING, resting).apply()
            instance?.get()?.let { service ->
                service.handler.post { service.petLife?.sync() }
            }
            PetOverlayService.notifyStateChanged()
        }
        @Volatile var isRunning = false
            private set
        @Volatile private var hostForeground = false
        private var instance: WeakReference<PillService>? = null
        private var lastPoke = 0L
        @Volatile private var wantFresh = false
        fun start(context: Context) {
            val intent = Intent(context, PillService::class.java)
            if (Build.VERSION.SDK_INT >= 26) context.startForegroundService(intent) else context.startService(intent)
        }
        fun stop(context: Context) {
            instance?.get()?.tearDown()
            context.stopService(Intent(context, PillService::class.java))
        }
        /** The pill must not cover Momo's own screens. */
        fun setHostForeground(foreground: Boolean) {
            hostForeground = foreground
            // Channel calls can arrive on a worker thread; keep view and
            // WebView work on the main looper.
            instance?.get()?.let { service ->
                service.handler.post { service.applyHostVisibility() }
            }
        }
        /** An app switch or scroll happened; re-read stats soon, without a storm. */
        fun notifyStatsChanged(fresh: Boolean = false) {
            val service = instance?.get() ?: return
            if (fresh) wantFresh = true
            val now = SystemClock.elapsedRealtime()
            if (now - lastPoke < 1_200L) return
            lastPoke = now
            service.handler.removeCallbacks(service.refresh)
            service.handler.postDelayed(service.refresh, 400L)
        }
    }

    private lateinit var windowManager: WindowManager
    private var root: LinearLayout? = null
    private var pill: LinearLayout? = null
    private var pillText: LinearLayout? = null
    private var pillApp: TextView? = null
    private var pillValue: TextView? = null
    private var pillHpBar: HpBar? = null
    private var pillHpValue: TextView? = null
    private var panel: LinearLayout? = null
    private var panelTitle: TextView? = null
    private var panelSession: TextView? = null
    private var panelScroll: TextView? = null
    private var panelReminder: TextView? = null
    private var params: WindowManager.LayoutParams? = null
    private val handler = Handler(Looper.getMainLooper())
    private val worker = NativeStore.executor("momo-pill", 1)
    private val busy = AtomicBoolean(false)
    @Volatile private var alive = false
    private var receiverRegistered = false
    private var anchorX = 0
    private var anchorY = 0
    private var downRawX = 0f
    private var downRawY = 0f
    private var startX = 0
    private var startY = 0
    private var dragging = false
    private var lastStats: PillStats? = null
    private var freshRetries = 0
    private var pillIcon: ImageView? = null
    private var iconHolder: FrameLayout? = null
    private var panelMascot: ImageView? = null
    private var currentMascot = 0
    private var currentHp = 100
    /** "head" keeps a compact head until tapped; "body" shows the full body. */
    private var pillForm = "head"
    private var expanded = false
    private var expandAnimator: ValueAnimator? = null
    private var holderParams: LinearLayout.LayoutParams? = null
    private var panelOpenRunnable: Runnable? = null
    private var petRenderer: PetWebRenderer? = null
    private var petWeb: WebView? = null
    private var petLife: PetLife? = null
    private var animationFull = false
    private val refresh = Runnable { refreshStats() }
    /** A hidden window has no surface; only wake the rig once it is on screen. */
    private val startPetRenderer = Runnable {
        if (alive && !hostForeground && screenOn() && animationFull &&
            root?.visibility == View.VISIBLE
        ) {
            petRenderer?.start()
        }
    }
    private val screenReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            handler.removeCallbacks(refresh)
            petLife?.sync()
            if (alive && intent?.action == Intent.ACTION_SCREEN_ON) {
                handler.post(refresh)
                maybeStartPetRenderer()
            }
        }
    }

    private fun prefs() = getSharedPreferences(PREFS, Context.MODE_PRIVATE)
    private fun text(id: String, en: String) = if (prefs().getString(KEY_LANGUAGE, "id") == "en") en else id
    private val surfaceColor get() = prefs().getInt(KEY_SURFACE, 0xFFFFFFFF.toInt())
    private val inkColor get() = prefs().getInt(KEY_INK, 0xFF111111.toInt())
    private val accentColor get() = prefs().getInt(KEY_ACCENT, 0xFFFFD23F.toInt())
    private val hpHealthyColor get() = prefs().getInt(KEY_HP_HEALTHY, 0xFF3DDC84.toInt())
    private val hpTiredColor get() = prefs().getInt(KEY_HP_TIRED, 0xFFFFB020.toInt())
    private val hpCriticalColor get() = prefs().getInt(KEY_HP_CRITICAL, 0xFFFF4D4D.toInt())
    private val radiusDp get() = prefs().getFloat(KEY_RADIUS, 14f)
    private val english get() = prefs().getString(KEY_LANGUAGE, "id") == "en"
    private fun screenOn() = (getSystemService(Context.POWER_SERVICE) as PowerManager).isInteractive
    private fun canShow() = NativeStore.enabled(this) && Settings.canDrawOverlays(this) && UsageRepo.hasUsageAccess(this)
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
        // Rebuild on every explicit start so all existing labels, colors and radii change together.
        removeOverlay()
        addOverlay()
        (getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager).notify(NOTIF_ID, buildNotification())
        handler.removeCallbacks(refresh)
        handler.post(refresh)
        return START_NOT_STICKY
    }

    private fun tearDown() {
        alive = false; isRunning = false
        handler.removeCallbacksAndMessages(null)
        worker.shutdownNow()
        removeOverlay()
        if (receiverRegistered) { unregisterReceiver(screenReceiver); receiverRegistered = false }
    }

    override fun onDestroy() {
        tearDown()
        if (instance?.get() === this) instance = null
        super.onDestroy()
    }

    private fun removeOverlay() {
        handler.removeCallbacks(startPetRenderer)
        cancelPanelOpen()
        expandAnimator?.cancel(); expandAnimator = null
        petLife?.dispose(); petLife = null
        petRenderer?.destroy(); petRenderer = null
        petWeb = null
        pillIcon?.animate()?.cancel()
        panelMascot?.animate()?.cancel()
        root?.let { runCatching { windowManager.removeView(it) } }
        root = null; pill = null; pillText = null; pillApp = null; pillValue = null
        pillHpBar = null; pillHpValue = null; pillIcon = null; iconHolder = null
        panelMascot = null
        panel = null; panelTitle = null; panelSession = null; panelScroll = null
        panelReminder = null; params = null
        holderParams = null
        expanded = false
        pillForm = "head"
        animationFull = false
    }

    private fun dp(value: Float) = (value * resources.displayMetrics.density).toInt()

    /** Text must stay readable even when a theme puts ink close to its surface. */
    private fun readableOn(fill: Int): Int {
        val luminance = (0.299 * Color.red(fill) + 0.587 * Color.green(fill) + 0.114 * Color.blue(fill)) / 255.0
        return if (luminance > 0.55) 0xFF1A1A1A.toInt() else 0xFFFFFFFF.toInt()
    }

    private fun inkOn(fill: Int): Int =
        if (contrast(inkColor, fill) >= 3.0) inkColor else readableOn(fill)

    private fun contrast(a: Int, b: Int): Double {
        fun channel(value: Int): Double {
            val c = value / 255.0
            return if (c <= 0.03928) c / 12.92 else Math.pow((c + 0.055) / 1.055, 2.4)
        }
        val la = 0.2126 * channel(Color.red(a)) + 0.7152 * channel(Color.green(a)) + 0.0722 * channel(Color.blue(a))
        val lb = 0.2126 * channel(Color.red(b)) + 0.7152 * channel(Color.green(b)) + 0.0722 * channel(Color.blue(b))
        return (maxOf(la, lb) + 0.05) / (minOf(la, lb) + 0.05)
    }

    private fun mix(fill: Int, tint: Int, alpha: Float): Int = Color.rgb(
        (Color.red(fill) * (1 - alpha) + Color.red(tint) * alpha).toInt(),
        (Color.green(fill) * (1 - alpha) + Color.green(tint) * alpha).toInt(),
        (Color.blue(fill) * (1 - alpha) + Color.blue(tint) * alpha).toInt(),
    )

    private fun drawable(color: Int, radius: Float, stroke: Int? = null): GradientDrawable =
        GradientDrawable().apply {
            cornerRadius = dp(radius).toFloat(); setColor(color)
            if (radius <= 8f) setStroke(dp(2f).coerceAtLeast(2), inkColor)
            if (stroke != null) setStroke(dp(1f).coerceAtLeast(1), stroke)
        }

    /** A typo or a value from a newer build must fall back to Momo, never crash. */
    private fun currentPet(): PetKind =
        PetKind.parse(prefs().getString(KEY_PET, DEFAULT_PET))

    /** Fresh above 60 HP, tired at 30-60, critical below 30 — the same thresholds Flutter uses. */
    private fun mascotDrawable(hp: Int): Int {
        val set = mascotSets[currentPet().storageValue] ?: mascotSets.getValue(DEFAULT_PET)
        val stage = when (prefs().getString(KEY_STAGE, "bayi")) { "dewasa" -> 2; "remaja" -> 1; else -> 0 }
        val mood = when { hp > 60 -> 0; hp >= 30 -> 1; else -> 2 }
        return set[stage][mood]
    }

    /** The full-body sprite for the current stage; mood lives in the panel. */
    private fun bodyDrawable(): Int {
        val set = bodySets[currentPet().storageValue] ?: bodySets.getValue(DEFAULT_PET)
        val stage = when (prefs().getString(KEY_STAGE, "bayi")) { "dewasa" -> 2; "remaja" -> 1; else -> 0 }
        return set[stage]
    }

    /** The holder shows a body whenever the pill is not the compact head. */
    private fun holderSprite(headRes: Int): Int =
        if (pillForm == "body" || expanded) bodyDrawable() else headRes
    /**
     * Mirrors Flutter's `computeHp`: 0.2 per screen minute, 0.03 per scroll,
     * plus today's recovery. Native owns the math so the pill stays live while
     * the Flutter UI is behind another app.
     */
    private fun hpFrom(stats: PillStats): Int =
        PetBehavior.hp(stats.totalMinutes, stats.totalScroll, hpBonusToday(this))

    private fun hpColor(hp: Int): Int = when {
        hp > 60 -> hpHealthyColor
        hp >= 30 -> hpTiredColor
        else -> hpCriticalColor
    }

    /** Static mode draws one sprite and runs no loops; full mode owns a rig. */
    private fun mascotTap(target: ImageView?) {
        val icon = target ?: return
        if (!alive) return
        icon.animate().cancel()
        icon.rotation = 0f
        icon.scaleX = 1.16f; icon.scaleY = 0.86f
        icon.animate().scaleX(1f).scaleY(1f).setDuration(280)
            .setInterpolator(OvershootInterpolator(3f)).start()
    }

    /** HP crossed a threshold: fade the flat sprite into its new expression. */
    private fun swapMascot(resId: Int) {
        if (animationFull) return
        val icon = pillIcon ?: return
        icon.animate().cancel()
        icon.rotation = 0f
        icon.animate().alpha(0f).scaleX(0.82f).scaleY(0.82f).setDuration(90).withEndAction {
            if (!alive) return@withEndAction
            icon.setImageResource(holderSprite(resId))
            icon.animate().alpha(1f).scaleX(1f).scaleY(1f).setDuration(220)
                .setInterpolator(OvershootInterpolator(2f)).start()
        }.start()
        panelMascot?.setImageResource(resId)
        panelMascot?.apply {
            scaleX = 0.9f; scaleY = 0.9f
            animate().scaleX(1f).scaleY(1f).setDuration(220)
                .setInterpolator(OvershootInterpolator(2.5f)).start()
        }
    }

    /** The renderer failed or timed out: keep a visible static fallback. */
    private fun fallbackToFlatIcon() {
        if (!alive || !animationFull) return
        val holder = iconHolder ?: return
        animationFull = false
        handler.removeCallbacks(startPetRenderer)
        petLife?.dispose(); petLife = null
        petRenderer?.destroy(); petRenderer = null
        petWeb = null
        holder.removeAllViews()
        val hp = lastStats?.let { hpFrom(it) } ?: currentHp
        val res = holderSprite(mascotDrawable(hp))
        currentMascot = mascotDrawable(hp)
        val icon = ImageView(this).apply {
            setImageResource(res)
            scaleType = ImageView.ScaleType.FIT_CENTER
            contentDescription = null
        }
        holder.addView(icon, FrameLayout.LayoutParams(-1, -1))
        pillIcon = icon
        root?.post { updateLayout() }
    }

    private fun buildPetLife(renderer: PetWebRenderer) = PetLife(
        handler, renderer,
        mood = { PetBehavior.mood(currentHp) },
        stage = { PetStage.parse(prefs().getString(KEY_STAGE, "bayi")) },
        resting = { isResting(this) },
        allowed = {
            alive && !hostForeground && screenOn() &&
                panel?.visibility != View.VISIBLE && animationFull
        },
        pet = { currentPet() },
        // The panel hides the loop but not the pill; keep the last frame.
        freeze = { alive && !hostForeground && screenOn() },
    )

    /** The rig is ready: swap the sprite placeholder for the live canvas. */
    private fun onPetRendererLoaded() {
        if (!alive || !animationFull) return
        val web = petWeb ?: return
        pillIcon?.visibility = View.GONE
        // Drag feedback now rotates the holder, not the retired sprite.
        pillIcon = null
        web.visibility = View.VISIBLE
        // The page may have loaded while the pill was already expanded.
        petRenderer?.setHeadFrame(pillForm == "head" && !expanded)
        petLife?.onLoaded()
    }

    private fun maybeStartPetRenderer() {
        if (!alive || hostForeground || !screenOn() || !animationFull) return
        if (root?.visibility != View.VISIBLE) return
        val active = petRenderer ?: return
        if (active.isStarted || active.isLoaded) return
        handler.removeCallbacks(startPetRenderer)
        handler.postDelayed(startPetRenderer, START_DELAY_MS)
    }

    private fun addOverlay() {
        val container = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL; gravity = Gravity.CENTER_HORIZONTAL
        }
        val initialHp = lastStats?.let { hpFrom(it) } ?: 100
        currentHp = initialHp
        val initialMascot = mascotDrawable(initialHp)
        pillForm = if (prefs().getString(KEY_FORM, "head") == "body") "body" else "head"
        expanded = false
        val initialSprite = if (pillForm == "body") bodyDrawable() else initialMascot
        val holder = FrameLayout(this)
        iconHolder = holder
        animationFull = prefs().getString(KEY_ANIMATION, "flat") == "full"
        var flatIcon: ImageView? = null
        if (animationFull) {
            // The sprite holds the spot while the hidden window waits for a
            // visible surface; the rig replaces it once it reports ready.
            flatIcon = ImageView(this).apply {
                setImageResource(initialSprite)
                scaleType = ImageView.ScaleType.FIT_CENTER
                contentDescription = null
            }
            holder.addView(flatIcon, FrameLayout.LayoutParams(-1, -1))
            val renderer = PetWebRenderer(
                this,
                PetStage.parse(prefs().getString(KEY_STAGE, "bayi")),
                headFrame = pillForm == "head",
                pet = currentPet(),
                onLoaded = { onPetRendererLoaded() },
                onUnavailable = { fallbackToFlatIcon() },
            )
            petRenderer = renderer
            val web = renderer.create()
            if (web != null) {
                // Visible but transparent: Chromium gets a real surface and the
                // sprite behind shows through until the rig reports ready.
                holder.addView(web, FrameLayout.LayoutParams(-1, -1))
                petWeb = web
                petLife = buildPetLife(renderer)
            } else {
                fallbackToFlatIcon()
            }
        } else {
            flatIcon = ImageView(this).apply {
                setImageResource(initialSprite)
                scaleType = ImageView.ScaleType.FIT_CENTER
                contentDescription = null
            }
            holder.addView(flatIcon, FrameLayout.LayoutParams(-1, -1))
        }
        val appView = TextView(this).apply {
            textSize = 11f; typeface = Typeface.DEFAULT_BOLD
            setTextColor(inkOn(accentColor))
            maxLines = 1; ellipsize = TextUtils.TruncateAt.END
            maxWidth = dp(128f)
        }
        // Scroll hits and session time share one line: "5m · 12 gulir".
        val valueView = TextView(this).apply {
            textSize = 10f; setTextColor(inkOn(accentColor)); maxLines = 1
        }
        // The pet's live HP replaces the old pet name: a slim bar plus "92/100".
        // It stays visible even with no app open, so the pill never hides health.
        val hpLabel = TextView(this).apply {
            text = "HP"; textSize = 9f; setTextColor(inkOn(accentColor)); alpha = 0.78f
        }
        val hpBar = HpBar(this).apply {
            track = Color.argb(56, Color.red(inkColor), Color.green(inkColor), Color.blue(inkColor))
        }
        val hpValue = TextView(this).apply {
            text = "…"; textSize = 9f; setTextColor(inkOn(accentColor)); maxLines = 1; alpha = 0.9f
        }
        val hpRow = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL
            setPadding(0, dp(2f), 0, 0)
            importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_NO
            addView(hpLabel, LinearLayout.LayoutParams(-2, -2).apply { rightMargin = dp(4f) })
            addView(hpBar, LinearLayout.LayoutParams(dp(36f), dp(4f)))
            addView(hpValue, LinearLayout.LayoutParams(-2, -2).apply { leftMargin = dp(4f) })
        }
        val textColumn = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(7f), 0, 0, 0)
            // Wrap every line: MATCH_PARENT inside a wrap column measures
            // against the window's pinned width and truncates the label.
            addView(appView, LinearLayout.LayoutParams(-2, -2))
            addView(valueView, LinearLayout.LayoutParams(-2, -2))
            addView(hpRow, LinearLayout.LayoutParams(-2, -2))
        }
        val verticalPad = if (pillForm == "body") 2f else 6f
        val holderSize = dp(if (pillForm == "body") HOLDER_BODY_DP else HOLDER_HEAD_DP)
        val holderLayout = LinearLayout.LayoutParams(holderSize, holderSize)
        holderParams = holderLayout
        val pillView = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(8f), dp(verticalPad), dp(12f), dp(verticalPad))
            background = drawable(accentColor, radiusDp)
            isClickable = true
            isFocusable = true
            contentDescription = text("Buka menu pill", "Open pill menu")
            addView(holder, holderLayout)
            addView(textColumn, LinearLayout.LayoutParams(-2, -2))
            setOnClickListener { onPillTap() }
        }
        pillView.setOnTouchListener { view, event -> handleDrag(view, event) }
        // A WebView consumes touches before the pill sees them; forward every
        // mascot layer to the same drag/tap handler so it stays draggable.
        for (index in 0 until holder.childCount) {
            holder.getChildAt(index).setOnTouchListener { _, event -> handleDrag(pillView, event) }
        }

        val panelView = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL; visibility = View.GONE
            setPadding(dp(14f), dp(12f), dp(14f), dp(12f))
            background = drawable(surfaceColor, radiusDp, Color.argb(48, Color.red(inkColor), Color.green(inkColor), Color.blue(inkColor)))
        }
        val header = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL
        }
        val panelPicture = ImageView(this).apply {
            setImageResource(initialMascot)
            scaleType = ImageView.ScaleType.FIT_CENTER
            contentDescription = null
            isClickable = true
            setOnClickListener { mascotTap(panelMascot) }
        }
        val headerText = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(10f), 0, 0, 0)
        }
        val titleView = TextView(this).apply {
            textSize = 14f; typeface = Typeface.DEFAULT_BOLD
            setTextColor(inkOn(surfaceColor)); maxLines = 1
            ellipsize = TextUtils.TruncateAt.END
        }
        val sessionView = TextView(this).apply { textSize = 11f; setTextColor(inkOn(surfaceColor)) }
        val scrollView = TextView(this).apply { textSize = 11f; setTextColor(inkOn(surfaceColor)) }
        headerText.addView(titleView); headerText.addView(sessionView); headerText.addView(scrollView)
        header.addView(panelPicture, LinearLayout.LayoutParams(dp(44f), dp(44f)))
        header.addView(headerText, LinearLayout.LayoutParams(0, -2, 1f))
        panelView.addView(header)

        val reminderView = TextView(this).apply {
            textSize = 12f; setTextColor(inkOn(mix(surfaceColor, accentColor, 0.18f)))
            setPadding(dp(10f), dp(8f), dp(10f), dp(8f))
            background = drawable(mix(surfaceColor, accentColor, 0.18f), 10f)
        }
        panelView.addView(reminderView, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(10f) })

        panelView.addView(TextView(this).apply {
            text = text("Geser pill untuk memindahkan.", "Drag the pill to move it.")
            textSize = 10f; setTextColor(inkOn(surfaceColor))
            alpha = 0.72f
            setPadding(0, dp(8f), 0, 0)
        })

        fun action(label: String, click: () -> Unit) {
            panelView.addView(TextView(this).apply {
                text = label; textSize = 13f; setTextColor(inkOn(surfaceColor))
                setPadding(dp(2f), dp(12f), dp(2f), dp(4f))
                isClickable = true
                setOnClickListener { if (alive && canShow()) click() }
            })
        }
        action(text("Buka aplikasi", "Open app")) { openApp(false) }
        action(text("Istirahat", "Take a rest")) { openApp(true) }
        action(text("Kembali ke Home", "Return to Home")) {
            runCatching { startActivity(Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_HOME).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) }
            closePanel()
        }
        action(text("Sembunyikan pill", "Hide pill")) { tearDown(); stopSelf() }
        panelView.addView(TextView(this).apply {
            text = text("Home tidak menutup paksa aplikasi.", "Home does not force-stop apps.")
            textSize = 10f; setTextColor(inkOn(surfaceColor)); alpha = 0.72f
            setPadding(0, dp(6f), 0, 0)
        })

        container.addView(pillView)
        container.addView(panelView, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(8f) })
        panelView.minimumWidth = dp(244f)

        val type = if (Build.VERSION.SDK_INT >= 26) WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
            else @Suppress("DEPRECATION") WindowManager.LayoutParams.TYPE_PHONE
        val savedX = prefs().getInt(KEY_X, Int.MIN_VALUE)
        val savedY = prefs().getInt(KEY_Y, Int.MIN_VALUE)
        val layoutParams = WindowManager.LayoutParams(-2, -2, type,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
                WindowManager.LayoutParams.FLAG_HARDWARE_ACCELERATED,
            PixelFormat.TRANSLUCENT).apply {
            gravity = Gravity.TOP or Gravity.START
            x = if (savedX == Int.MIN_VALUE) 0 else savedX
            y = if (savedY == Int.MIN_VALUE) dp(48f) else savedY
        }
        try { windowManager.addView(container, layoutParams) } catch (_: RuntimeException) {
            tearDown(); stopSelf(); return
        }
        root = container; pill = pillView; pillText = textColumn; pillApp = appView; pillValue = valueView
        pillHpBar = hpBar; pillHpValue = hpValue
        // A failed renderer already installed its own static icon.
        pillIcon = pillIcon ?: flatIcon
        panelMascot = panelPicture; currentMascot = initialMascot
        panel = panelView; panelTitle = titleView; panelSession = sessionView
        panelScroll = scrollView; panelReminder = reminderView
        params = layoutParams
        anchorX = layoutParams.x; anchorY = layoutParams.y
        container.post {
            val bounds = screenBounds()
            if (savedX == Int.MIN_VALUE) layoutParams.x = maxOf(0, (bounds.width() - container.width) / 2)
            val top = topInset()
            layoutParams.y = layoutParams.y.coerceIn(top, maxOf(top, bounds.height() - container.height))
            anchorX = layoutParams.x; anchorY = layoutParams.y
            updateLayout()
        }
        applyHostVisibility()
    }

    private fun screenBounds(): Rect {
        return if (Build.VERSION.SDK_INT >= 30) windowManager.currentWindowMetrics.bounds
        else Rect(0, 0, resources.displayMetrics.widthPixels, resources.displayMetrics.heightPixels)
    }

    private fun updateLayout() {
        val view = root ?: return
        val layoutParams = params ?: return
        // A wrap-content overlay keeps the width it first measured, so a longer
        // app name stays cut to an ellipsis. Measure the content ourselves and
        // pin the window to that size; updateViewLayout then really resizes it.
        val bounds = screenBounds()
        // A child's setText only flags the child; without a deep force-layout
        // the subtree returns the sizes it cached at the previous window width.
        forceLayoutDeep(view)
        view.measure(
            View.MeasureSpec.makeMeasureSpec(bounds.width(), View.MeasureSpec.AT_MOST),
            View.MeasureSpec.makeMeasureSpec(bounds.height(), View.MeasureSpec.AT_MOST),
        )
        // TextView floors its desired width, so pinning exactly that can leave
        // the label one pixel short and turn "Momo" into "Mo…".
        layoutParams.width = (view.measuredWidth + dp(3f)).coerceAtLeast(1)
        layoutParams.height = (view.measuredHeight + dp(1f)).coerceAtLeast(1)
        val top = topInset()
        layoutParams.x = layoutParams.x.coerceIn(0, maxOf(0, bounds.width() - layoutParams.width))
        layoutParams.y = layoutParams.y.coerceIn(top, maxOf(top, bounds.height() - layoutParams.height))
        runCatching { windowManager.updateViewLayout(view, layoutParams) }
    }

    /** Overlay coordinates start at the display edge, so keep the pill below the status bar. */
    private fun topInset(): Int = if (Build.VERSION.SDK_INT >= 30) {
        windowManager.currentWindowMetrics.windowInsets.getInsets(android.view.WindowInsets.Type.systemBars()).top
    } else 0

    private fun forceLayoutDeep(view: View) {
        view.forceLayout()
        if (view is android.view.ViewGroup) {
            for (index in 0 until view.childCount) forceLayoutDeep(view.getChildAt(index))
        }
    }

    private fun clampToScreen() {
        val view = root ?: return
        val layoutParams = params ?: return
        val bounds = screenBounds()
        val top = topInset()
        layoutParams.x = layoutParams.x.coerceIn(0, maxOf(0, bounds.width() - view.width))
        layoutParams.y = layoutParams.y.coerceIn(top, maxOf(top, bounds.height() - view.height))
        updateLayout()
    }

    /** Drag moves the whole overlay; a tap keeps the old click behaviour. */
    private fun handleDrag(view: View, event: MotionEvent): Boolean {
        val layoutParams = params ?: return false
        when (event.actionMasked) {
            MotionEvent.ACTION_DOWN -> {
                downRawX = event.rawX; downRawY = event.rawY
                startX = layoutParams.x; startY = layoutParams.y
                dragging = false
                return true
            }
            MotionEvent.ACTION_MOVE -> {
                val dx = event.rawX - downRawX
                val dy = event.rawY - downRawY
                if (!dragging && Math.hypot(dx.toDouble(), dy.toDouble()) > ViewConfiguration.get(this).scaledTouchSlop) {
                    dragging = true
                }
                if (dragging) {
                    layoutParams.x = startX + dx.toInt()
                    layoutParams.y = startY + dy.toInt()
                    clampToScreen()
                    // Lean into the drag, then settle upright.
                    (pillIcon ?: iconHolder)?.rotation = (dx * 0.10f).coerceIn(-9f, 9f)
                }
                return true
            }
            MotionEvent.ACTION_UP -> {
                if (dragging) {
                    anchorX = layoutParams.x; anchorY = layoutParams.y
                    prefs().edit().putInt(KEY_X, anchorX).putInt(KEY_Y, anchorY).apply()
                    (pillIcon ?: iconHolder)?.animate()?.rotation(0f)?.setDuration(160)?.start()
                } else {
                    view.performClick()
                }
                dragging = false
                return true
            }
            MotionEvent.ACTION_CANCEL -> {
                dragging = false
                (pillIcon ?: iconHolder)?.animate()?.rotation(0f)?.setDuration(160)?.start()
                return true
            }
        }
        return false
    }

    /**
     * One object, two forms. The compact head grows into the full body on the
     * first tap, holds that pose while the options panel fades in, and folds
     * back to the head when the panel closes.
     */
    private fun onPillTap() {
        if (!alive) return
        val panelView = panel ?: return
        if (panelView.visibility == View.VISIBLE) { closePanel(); return }
        mascotTap(pillIcon)
        if (pillForm == "head" && !expanded) {
            expandToBody()
            // The greeting beat is also the moment Momo reacts in full mode.
            petLife?.onTap()
            openPanelSoon(PANEL_DELAY_MS)
        } else {
            showPanel()
        }
    }

    private fun showPanel() {
        cancelPanelOpen()
        val panelView = panel ?: return
        if (panelView.visibility == View.VISIBLE) return
        lastStats?.let { render(it) }
        refreshStats()
        panelView.alpha = 0f
        panelView.visibility = View.VISIBLE
        panelView.animate().alpha(1f).setDuration(150).start()
        root?.post { keepPanelOnScreen() }
        petLife?.sync()
    }

    /** A greeting beat before the panel; repeated taps must not stack runs. */
    private fun openPanelSoon(delay: Long) {
        cancelPanelOpen()
        val run = Runnable {
            panelOpenRunnable = null
            if (!alive) return@Runnable
            if (panel?.visibility != View.VISIBLE) showPanel()
        }
        panelOpenRunnable = run
        handler.postDelayed(run, delay)
    }

    private fun cancelPanelOpen() {
        panelOpenRunnable?.let(handler::removeCallbacks)
        panelOpenRunnable = null
    }

    private fun closePanel() {
        cancelPanelOpen()
        val panelView = panel ?: return
        panelView.animate().cancel()
        panelView.visibility = View.GONE
        params?.let { it.x = anchorX; it.y = anchorY }
        if (expanded) collapse() else params?.let { updateLayout() }
        petLife?.sync()
    }

    private fun expandToBody() {
        if (expanded) return
        expanded = true
        if (animationFull) {
            petRenderer?.setHeadFrame(false)
            // While the rig warms up the placeholder is still the visible pet.
            if (petRenderer?.isLoaded != true) crossfadeSprite(body = true)
        } else {
            crossfadeSprite(body = true)
        }
        animateHolder(HOLDER_BODY_DP)
    }

    private fun collapse(animate: Boolean = true) {
        if (!expanded) return
        expanded = false
        if (animationFull) {
            petRenderer?.setHeadFrame(true)
            if (petRenderer?.isLoaded != true) crossfadeSprite(body = false, animate = animate)
        } else {
            crossfadeSprite(body = false, animate = animate)
        }
        animateHolder(HOLDER_HEAD_DP, animate)
    }

    /** The flat head and the flat body are different drawings; cross-fade them. */
    private fun crossfadeSprite(body: Boolean, animate: Boolean = true) {
        val icon = pillIcon ?: return
        icon.animate().cancel()
        icon.rotation = 0f
        @Suppress("DEPRECATION")
        val target = resources.getDrawable(if (body) bodyDrawable() else mascotDrawable(currentHp))
        val current = icon.drawable
        if (!animate || current == null) {
            icon.alpha = 1f
            icon.setImageDrawable(target)
            return
        }
        // Overlap both drawings; a fade-out first would blink the holder empty
        // mid-morph.
        val fade = TransitionDrawable(arrayOf(current, target)).apply { isCrossFadeEnabled = true }
        icon.alpha = 1f
        icon.setImageDrawable(fade)
        fade.startTransition(180)
    }

    /** Window width is pinned by [updateLayout]; animate the hole, not the view. */
    private fun animateHolder(targetDp: Float, animate: Boolean = true) {
        val lp = holderParams ?: return
        expandAnimator?.cancel()
        val target = dp(targetDp)
        if (!animate) {
            lp.width = target; lp.height = target
            root?.post { updateLayout() }
            return
        }
        val animator = ValueAnimator.ofInt(lp.width, target).apply {
            duration = HOLDER_ANIM_MS
            interpolator = DecelerateInterpolator()
        }
        expandAnimator = animator
        animator.addUpdateListener { value ->
            val size = value.animatedValue as Int
            lp.width = size; lp.height = size
            root?.post { updateLayout() }
        }
        animator.addListener(object : AnimatorListenerAdapter() {
            override fun onAnimationEnd(animation: Animator) {
                if (expandAnimator === animation) expandAnimator = null
            }
        })
        animator.start()
    }

    /** Slide the whole overlay back when an open panel would fall off an edge. */
    private fun keepPanelOnScreen() {
        val view = root ?: return
        val layoutParams = params ?: return
        val bounds = screenBounds()
        val overflowY = layoutParams.y + view.height - bounds.height() + dp(8f)
        if (overflowY > 0) layoutParams.y = maxOf(0, layoutParams.y - overflowY)
        val overflowX = layoutParams.x + view.width - bounds.width() + dp(8f)
        if (overflowX > 0) layoutParams.x = maxOf(0, layoutParams.x - overflowX)
        updateLayout()
    }

    private fun applyHostVisibility() {
        root?.visibility = if (hostForeground) View.GONE else View.VISIBLE
        if (hostForeground) {
            handler.removeCallbacks(refresh)
            if (petRenderer?.isStarted != true) handler.removeCallbacks(startPetRenderer)
            cancelPanelOpen()
            panel?.visibility = View.GONE
            // A hidden window never animates; restore the compact silhouette.
            if (expanded) collapse(animate = false)
            params?.let { it.x = anchorX; it.y = anchorY; updateLayout() }
        } else if (alive) {
            handler.removeCallbacks(refresh)
            handler.post(refresh)
        }
        // Full mode pauses on every hidden path; static mode has no loop to stop.
        petLife?.sync()
        // A GONE window keeps its old width; remeasure once it is back.
        if (!hostForeground) {
            maybeStartPetRenderer()
            root?.post { updateLayout() }
        }
    }

    private fun openApp(rest: Boolean) {
        val intent = Intent(this, MainActivity::class.java).apply {
            action = if (rest) ACTION_REST else Intent.ACTION_MAIN
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP)
        }
        if (rest) {
            // MainActivity is exported for the launcher; prove the rest action
            // came from this pill, not from another app.
            val token = UUID.randomUUID().toString()
            prefs().edit().putString(KEY_REST_TOKEN, token).apply()
            intent.putExtra(EXTRA_REST_TOKEN, token)
        }
        runCatching { startActivity(intent) }
        closePanel()
    }

    private fun refreshStats() {
        if (!alive) return
        if (!canShow()) { tearDown(); stopSelf(); return }
        if (!screenOn() || hostForeground || !busy.compareAndSet(false, true)) return
        val token = NativeStore.generation
        try {
            worker.execute {
                val fresh = wantFresh
                if (fresh) {
                    wantFresh = false
                    // A window switch is newer than the cached event list; a
                    // short tail makes the new app name appear within ~1 s.
                    runCatching { UsageRepo.refreshRecent(this) }
                }
                val result = runCatching { UsageRepo.pillStats(this) }
                handler.post {
                    busy.set(false)
                    if (!alive) return@post
                    if (!canShow()) { tearDown(); stopSelf(); return@post }
                    if (!screenOn()) return@post
                    var retry = false
                    if (NativeStore.valid(this, token)) {
                        result.onSuccess { stats ->
                            lastStats = stats
                            render(stats)
                            // UsageStats can publish the resume event a beat
                            // after the window change; probe twice before
                            // settling for "no app open".
                            retry = fresh && stats.appPackage == null && freshRetries < FRESH_RETRIES
                        }.onFailure {
                            pillText?.visibility = View.GONE
                            pillApp?.text = ""
                            pillValue?.text = ""
                            panelTitle?.text = text("Belum ada aplikasi", "No app open")
                            panelSession?.text = text("Data pemakaian belum tersedia.", "Usage data is unavailable.")
                            panelScroll?.text = ""
                            panelReminder?.text = text("Aku belum bisa membaca aplikasi yang terbuka.", "I can't read the open app yet.")
                            retry = fresh && freshRetries < FRESH_RETRIES
                        }
                    }
                    freshRetries = if (retry) freshRetries + 1 else 0
                    handler.removeCallbacks(refresh)
                    if (!hostForeground && screenOn()) {
                        if (retry) {
                            wantFresh = true
                            handler.postDelayed(refresh, FRESH_RETRY_MS)
                        } else {
                            handler.postDelayed(refresh, REFRESH_MS)
                        }
                    }
                }
            }
        } catch (_: RejectedExecutionException) { busy.set(false) }
    }

    private fun render(stats: PillStats) {
        val label = stats.appLabel
        val minutes = stats.sessionMinutes
        val duration = if (minutes < 1) text("<1m", "<1m") else "${minutes}m"
        val scrolls = when {
            stats.appScroll <= 0 -> null
            stats.appScroll == 1 -> text("1 gulir hari ini", "1 scroll today")
            else -> text("${stats.appScroll} gulir hari ini", "${stats.appScroll} scrolls today")
        }
        // The mascot identifies the companion; HP is its live health. The app
        // lines only appear while an app is open, so the idle pill stays slim.
        val hp = hpFrom(stats)
        currentHp = hp
        if (animationFull) {
            // The GLB renderer plays its own idle/action set; mood changes only
            // need a scheduler pass. The panel keeps a static portrait.
            val mascot = mascotDrawable(hp)
            if (mascot != currentMascot) {
                currentMascot = mascot
                panelMascot?.setImageResource(mascot)
            }
            petLife?.sync()
        } else {
            val mascot = mascotDrawable(hp)
            if (mascot != currentMascot) {
                currentMascot = mascot
                if (pillForm == "head" && !expanded) {
                    swapMascot(mascot)
                } else {
                    // The flat body keeps one calm pose; mood lives in the panel.
                    panelMascot?.setImageResource(mascot)
                }
            }
        }
        pillText?.visibility = View.VISIBLE
        pillApp?.visibility = if (label == null) View.GONE else View.VISIBLE
        pillValue?.visibility = if (label == null) View.GONE else View.VISIBLE
        pillApp?.text = label?.let { shorten(it) }.orEmpty()
        // "Sesi" makes it explicit that this duration is the current app
        // session, not today's total shown in the panel.
        pillValue?.text = if (label == null) "" else {
            val session = text("Sesi ", "Session ") + duration
            listOfNotNull(session, scrolls).joinToString(" · ")
        }
        pillHpBar?.apply {
            fraction = hp / 100f
            fill = hpColor(hp)
        }
        pillHpValue?.text = "$hp/100"
        pill?.contentDescription = buildString {
            if (label == null) append(text("Belum ada aplikasi terbuka.", "No app is open."))
            else {
                append("$label, ")
                append(if (minutes < 1) text("baru dibuka", "just opened") else text("$minutes menit", "$minutes minutes"))
                if (stats.appScroll > 0) append(text(", ${stats.appScroll} scroll", ", ${stats.appScroll} scrolls"))
            }
            append(text(". HP $hp dari 100.", ". HP $hp of 100."))
            append(text(" Geser untuk memindahkan, ketuk untuk menu.", " Drag to move, tap for menu."))
        }
        panelTitle?.text = label?.let { shorten(it, 28) } ?: text("Belum ada aplikasi", "No app open")
        panelSession?.text = when {
            label == null -> text("Buka aplikasi apa pun, nanti aku catat.", "Open any app and I'll keep track.")
            minutes < 1 -> text("Sesi ini baru dibuka.", "This session just started.")
            else -> text("Sesi ini $minutes menit.", "This session: $minutes min.")
        }
        panelScroll?.text = when {
            label == null -> text(
                "Total layar hari ini: ${stats.totalMinutes} menit · ${stats.totalScroll} gulir.",
                "Today: ${stats.totalMinutes} screen min · ${stats.totalScroll} scrolls.",
            )
            stats.appScroll > 0 -> text(
                "${stats.appScroll} gulir di aplikasi ini · total layar ${stats.totalMinutes} menit.",
                if (stats.appScroll == 1) "1 scroll in this app · ${stats.totalMinutes} min screen time."
                else "${stats.appScroll} scrolls in this app · ${stats.totalMinutes} min screen time.",
            )
            else -> text("Belum ada gulir di aplikasi ini · total layar ${stats.totalMinutes} menit.", "No scrolls in this app yet · ${stats.totalMinutes} min screen time.")
        }
        panelReminder?.text = reminder(stats)
        // A wrap-content overlay caches its width: without this the new label
        // stays cut off ("Chromi…") until something else resizes the window.
        root?.post { updateLayout() }
    }

    private fun shorten(label: String, limit: Int = 14): String =
        if (label.length <= limit) label else label.take(limit - 1) + "…"

    /**
     * Lines are short on purpose: the pill is a nudge, not a lecture. The first
     * rule that fits wins, from the longest session to the quietest day.
     */
    private fun reminder(stats: PillStats): String = when {
        stats.appPackage == null ->
            text("Aku di sini. Kalau buka aplikasi, aku catat durasinya.", "I'm here. Open an app and I'll time it.")
        stats.sessionMinutes >= 60 ->
            text("Satu jam di aplikasi ini. Letakkan HP-nya sebentar, ya.", "An hour in this app. Try putting the phone down for a bit.")
        stats.sessionMinutes >= 30 ->
            text("Setengah jam sudah. Regangkan badan dulu.", "Half an hour already. Stretch a little first.")
        stats.appScroll >= 150 ->
            text("Scroll-nya sudah jauh. Berhenti sebelum capek.", "You've scrolled far. Stop before you tire out.")
        stats.appScroll >= 60 ->
            text("Masih banyak yang bisa dilihat, tapi matamu perlu jeda.", "There's always more to see, but your eyes need a break too.")
        stats.totalMinutes >= 180 ->
            text("Hari ini sudah lama. Coba cek rekap sebentar.", "It's been a long day. Maybe glance at your recap.")
        else ->
            text("Aku temani. Kamu yang pegang kendali.", "I'm with you. You're still in control.")
    }

    private fun buildNotification(): Notification {
        val manager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        if (Build.VERSION.SDK_INT >= 26) manager.createNotificationChannel(NotificationChannel(CHANNEL_ID,
            text("Pill melayang", "Floating pill"), NotificationManager.IMPORTANCE_LOW).apply { setShowBadge(false) })
        val open = PendingIntent.getActivity(this, 0, Intent(this, MainActivity::class.java)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val builder = if (Build.VERSION.SDK_INT >= 26) Notification.Builder(this, CHANNEL_ID)
            else @Suppress("DEPRECATION") Notification.Builder(this)
        return builder.setContentTitle(text("Pendamping layar", "Screen companion"))
            .setContentText(text("Durasi aplikasi dan hit scroll hari ini.", "App time and scroll hits today."))
            .setSmallIcon(R.drawable.ic_pill).setContentIntent(open).setOngoing(true).build()
    }
}

/** A 4dp hand-drawn bar: no theme, no drawable states, no extra padding. */
private class HpBar(context: Context) : View(context) {
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG)

    var fraction: Float = 1f
        set(value) { field = value.coerceIn(0f, 1f); invalidate() }
    var track: Int = 0x33111111
        set(value) { field = value; invalidate() }
    var fill: Int = 0xFF3DDC84.toInt()
        set(value) { field = value; invalidate() }

    override fun onDraw(canvas: Canvas) {
        val radius = height / 2f
        paint.color = track
        canvas.drawRoundRect(0f, 0f, width.toFloat(), height.toFloat(), radius, radius, paint)
        val end = width * fraction
        if (end > 0.5f) {
            paint.color = fill
            // A minimum of one full pill keeps tiny values from looking like a dot.
            canvas.drawRoundRect(0f, 0f, maxOf(end, radius * 2f), height.toFloat(), radius, radius, paint)
        }
    }
}
