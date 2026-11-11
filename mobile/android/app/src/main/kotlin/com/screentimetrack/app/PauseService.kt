package com.screentimetrack.app

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.PowerManager
import android.provider.Settings
import java.lang.ref.WeakReference
import java.util.concurrent.RejectedExecutionException
import android.graphics.Color
import android.graphics.PixelFormat
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.view.Gravity
import android.view.View
import android.view.WindowManager
import android.widget.LinearLayout
import android.widget.TextView

/**
 * Jeda Sadar (prd Bab 10.2): overlay layar penuh selama beberapa detik sebelum
 * app target terbuka. User tetap bisa membatalkan atau lanjut; tidak ada blokir
 * paksa, dan setiap app punya jeda cooldown agar tidak mengganggu terus-menerus.
 *
 * Deteksi app terdepan memakai UsageStats (izin yang sama dengan rekap), bukan
 * membaca isi layar. Overlay digambar sebagai window sistem, bukan activity,
 * sehingga tidak memerlukan izin tambahan selain "tampil di atas aplikasi lain".
 */
class PauseService : Service() {

    companion object {
        const val PREFS = "pause_prefs"
        const val KEY_PACKAGES = "packages"
        const val KEY_DELAY = "delay"
        const val KEY_BACKGROUND = "bg"
        const val KEY_SURFACE = "surface"
        const val KEY_INK = "ink"
        const val KEY_ACCENT = "accent"
        const val KEY_RADIUS = "radius"
        const val KEY_TITLE = "title"
        const val KEY_AUTO = "auto"
        const val KEY_CANCEL = "cancel"
        const val KEY_CONTINUE = "continueLabel"
        const val KEY_NOTE = "note"
        const val KEY_HP = "hpLine"
        const val KEY_APP_FALLBACK = "appFallback"
        const val KEY_LIMITS = "limits"
        const val KEY_LIMIT_TITLE = "limitTitle"
        const val KEY_LIMIT_NOTE = "limitNote"
        const val KEY_LIMIT_PASS = "limitPass"
        const val KEY_LIMIT_CLOSE = "limitClose"

        private const val CHANNEL_ID = "momo_pause"
        private const val NOTIF_ID = 43
        // Three seconds keeps a just-crossed limit visible quickly while halving
        // the UsageStats wakeups compared with the previous 1.5s cadence.
        private const val POLL_MS = 3000L

        /**
         * UsageStats can deliver events slightly late. Re-read a short tail
         * instead of advancing the cursor to "now" and losing a late RESUME.
         */
        private const val CURSOR_MARGIN_MS = 5000L

        /** Setelah lanjut, app yang sama tidak dijeda lagi selama 15 menit. */
        private const val COOLDOWN_MS = 15 * 60 * 1000L

        /** Setelah batal, beri jeda pendek agar tidak memicu loop instan. */
        private const val CANCEL_COOLDOWN_MS = 30 * 1000L

        /** Lolos sementara dari batas harian setelah user memilih lanjut. */
        private const val PASS_MS = 5 * 60 * 1000L

        /** One free 5-minute pass per app per day; further time must come from Bank Waktu. */
        private const val PASS_CAP = 1

        @Volatile
        var isRunning: Boolean = false
            private set

        fun start(context: Context) {
            val intent = Intent(context, PauseService::class.java)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(intent)
            } else {
                context.startService(intent)
            }
        }

        private var instance: WeakReference<PauseService>? = null
        fun stop(context: Context) {
            instance?.get()?.tearDown()
            context.stopService(Intent(context, PauseService::class.java))
        }
    }

    private val worker = NativeStore.executor("momo-pause", 1)
    @Volatile private var alive = false
    @Volatile private var resetForeground = true
    private var receiverRegistered = false
    private var eventCursor = 0L
    private var foreground: String? = null
    private var runtimeDay = ""
    private val screenReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            handler.removeCallbacks(poll)
            resetForeground = true
            lastForeground = null
            dismissOverlay()
            if (intent?.action == Intent.ACTION_SCREEN_ON && alive) handler.post(poll)
        }
    }
    private val poll = Runnable { pollOnce() }
    private lateinit var windowManager: WindowManager
    private val handler = Handler(Looper.getMainLooper())

    private var overlay: View? = null
    private var countdownText: TextView? = null
    private var activePackage: String? = null
    private var countdown = 0
    private var lastForeground: String? = null

    private val tick = object : Runnable {
        override fun run() {
            if (overlay == null) return
            countdown -= 1
            if (countdown <= 0) {
                continueToApp()
                return
            }
            renderCountdown()
            handler.postDelayed(this, 1000L)
        }
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        windowManager = getSystemService(Context.WINDOW_SERVICE) as WindowManager
        // A foreground-service start must be acknowledged even when consent was just revoked.
        startForeground(NOTIF_ID, buildNotification())
        instance = WeakReference(this)
        if (!canMonitor()) { stopSelf(); return }
        alive = true
        isRunning = true
        val filter = IntentFilter().apply { addAction(Intent.ACTION_SCREEN_ON); addAction(Intent.ACTION_SCREEN_OFF) }
        if (Build.VERSION.SDK_INT >= 33) registerReceiver(screenReceiver, filter, Context.RECEIVER_NOT_EXPORTED)
        else registerReceiver(screenReceiver, filter)
        receiverRegistered = true
        handler.post(poll)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (!canMonitor()) { tearDown(); stopSelf() }
        return START_NOT_STICKY
    }

    private fun tearDown() {
        alive = false
        isRunning = false
        handler.removeCallbacksAndMessages(null)
        worker.shutdownNow()
        dismissOverlay()
        if (receiverRegistered) { unregisterReceiver(screenReceiver); receiverRegistered = false }
    }

    override fun onDestroy() {
        tearDown()
        if (instance?.get() === this) instance = null
        super.onDestroy()
    }

    private fun prefs() = getSharedPreferences(PREFS, Context.MODE_PRIVATE)
    private fun dp(value: Float): Int = (value * resources.displayMetrics.density).toInt()
    private fun screenOn() = (getSystemService(Context.POWER_SERVICE) as PowerManager).isInteractive
    private fun canMonitor() = NativeStore.enabled(this) && UsageRepo.hasUsageAccess(this) && Settings.canDrawOverlays(this)

    private fun pollOnce() {
        if (!alive) return
        if (!canMonitor()) { tearDown(); stopSelf(); return }
        if (!screenOn()) { dismissOverlay(); resetForeground = true; return }
        val token = NativeStore.generation
        try {
            worker.execute {
                val outcome = runCatching {
                    val pkg = currentPackage()
                    val configured = pkg?.let { NativeStore.limits(this)[it] } ?: 0
                    val limit = if (configured > 0 && pkg != null) configured + NativeStore.allowance(this, pkg) else 0
                    val used = if (limit > 0 && pkg != null) UsageRepo.todayMinutesFor(this, pkg) else 0
                    Triple(pkg, limit, used)
                }
                handler.post {
                    if (!alive) return@post
                    if (!canMonitor()) { tearDown(); stopSelf(); return@post }
                    if (!screenOn()) { resetForeground = true; dismissOverlay(); return@post }
                    if (NativeStore.valid(this, token)) outcome.onSuccess { (pkg, limit, used) ->
                        val entered = pkg != lastForeground
                        lastForeground = pkg
                        if (activePackage != null && activePackage != pkg) dismissOverlay()
                        if (pkg != null && pkg != packageName && pkg in NativeStore.monitored(this)) {
                            val now = System.currentTimeMillis()
                            val decision = PauseDecision.decide(now, entered, used, limit,
                                prefs().getLong("pass|${UsageRepo.dayKey()}|$pkg", 0L),
                                prefs().getLong("cooldown|$pkg", 0L))
                            if (decision == PauseDecision.LIMIT) showOverlay(pkg, limit, used)
                            else if (decision == PauseDecision.NORMAL) showOverlay(pkg)
                        }
                    }
                    handler.removeCallbacks(poll)
                    handler.postDelayed(poll, POLL_MS)
                }
            }
        } catch (_: RejectedExecutionException) {
            // A transient full queue must not silently remove the foreground
            // notification while pause checks stop forever.
            handler.removeCallbacks(poll)
            handler.postDelayed(poll, POLL_MS)
        }
    }

    /** Worker-owned foreground state, retained across polls even when no new event arrives. */
    private fun currentPackage(): String? {
        val end = System.currentTimeMillis()
        val today = UsageRepo.dayKey()
        val dayChanged = runtimeDay != today
        if (dayChanged) runtimeDay = today
        val reset = resetForeground || eventCursor == 0L || end < eventCursor || dayChanged
        if (reset) {
            // Keep the known foreground across midnight. An app that has been
            // open since yesterday emits no new RESUME today, so clearing it
            // would let limits/pauses escape until the next app switch. Only a
            // screen-off reset or a dead cursor invalidates the value.
            if (resetForeground || eventCursor == 0L || end < eventCursor) foreground = null
            resetForeground = false
        }
        val start = if (reset) UsageRepo.startOfToday() else eventCursor
        // A foreground scan only needs today's events; the old seven-day
        // bootstrap scanned a week of UsageStats on every unlock.
        for (event in UsageRepo.readEvents(this, start, end)) {
            when (event.kind) {
                UsageAggregation.Kind.RESUME -> foreground = event.pkg
                UsageAggregation.Kind.PAUSE -> if (foreground == event.pkg) foreground = null
                UsageAggregation.Kind.SCREEN_OFF, UsageAggregation.Kind.SHUTDOWN -> foreground = null
                UsageAggregation.Kind.SCREEN_ON -> Unit
            }
        }
        eventCursor = (end - CURSOR_MARGIN_MS).coerceAtLeast(start)
        return foreground
    }

    private fun showOverlay(pkg: String, limitMinutes: Int = 0, usedMinutes: Int = 0) {
        if (overlay != null || !alive || !canMonitor() || !screenOn()) return

        val p = prefs()
        val limitMode = limitMinutes > 0
        val bg = p.getInt(KEY_BACKGROUND, 0xFF0B0D12.toInt())
        val surface = p.getInt(KEY_SURFACE, 0xFFFFFFFF.toInt())
        val ink = p.getInt(KEY_INK, 0xFF111111.toInt())
        val accent = p.getInt(KEY_ACCENT, 0xFFFFD23F.toInt())
        val radius = p.getFloat(KEY_RADIUS, 14f)
        val onAccent = if (Color.luminance(accent) > 0.5) Color.BLACK else Color.WHITE
        val mutedInk = (ink and 0x00FFFFFF) or 0x99000000.toInt()

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            setBackgroundColor(bg)
            setPadding(dp(24f), dp(24f), dp(24f), dp(24f))
            isClickable = true
        }

        val card = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(22f), dp(22f), dp(22f), dp(22f))
            background = cardDrawable(surface, radius, ink)
        }

        val title = TextView(this).apply {
            val template = if (limitMode) {
                p.getString(KEY_LIMIT_TITLE, "Batas harian {app} tercapai")
            } else {
                p.getString(KEY_TITLE, "Mau ngapain di {app}?")
            }
            text = (template ?: "").replace("{app}", appLabel(pkg))
            textSize = 20f
            typeface = Typeface.DEFAULT_BOLD
            setTextColor(ink)
        }

        val hpLine = TextView(this).apply {
            text = if (limitMode) {
                (p.getString(KEY_LIMIT_NOTE, "Hari ini {used}m dari batas {limit}m.") ?: "")
                    .replace("{used}", usedMinutes.toString())
                    .replace("{limit}", limitMinutes.toString())
            } else {
                p.getString(KEY_HP, "") ?: ""
            }
            textSize = 13f
            setTextColor(mutedInk)
            setPadding(0, dp(8f), 0, 0)
        }

        val auto = TextView(this).apply {
            textSize = 13f
            typeface = Typeface.DEFAULT_BOLD
            setTextColor(ink)
            gravity = Gravity.CENTER
            setPadding(0, dp(18f), 0, dp(6f))
            visibility = if (limitMode) View.GONE else View.VISIBLE
        }

        val cancel = TextView(this).apply {
            text = if (limitMode) {
                p.getString(KEY_LIMIT_CLOSE, "Tutup app") ?: "Tutup app"
            } else {
                p.getString(KEY_CANCEL, "Ke layar utama") ?: "Ke layar utama"
            }
            textSize = 15f
            typeface = Typeface.DEFAULT_BOLD
            gravity = Gravity.CENTER
            setTextColor(onAccent)
            setPadding(dp(12f), dp(15f), dp(12f), dp(15f))
            background = cardDrawable(accent, 10f, accent)
            setOnClickListener { cancelToHome() }
        }

        val cont = TextView(this).apply {
            text = if (limitMode) {
                p.getString(KEY_LIMIT_PASS, "Lanjut 5 menit") ?: "Lanjut 5 menit"
            } else {
                p.getString(KEY_CONTINUE, "Lanjut") ?: "Lanjut"
            }
            textSize = 14f
            gravity = Gravity.CENTER
            setTextColor(ink)
            setPadding(dp(12f), dp(14f), dp(12f), dp(14f))
            setOnClickListener {
                if (limitMode) passFiveMinutes() else continueToApp()
            }
        }
        if (limitMode &&
            p.getInt("passCount|${UsageRepo.dayKey()}|$pkg", 0) >= PASS_CAP
        ) {
            // The free pass is spent; extra time is only available by redeeming
            // Bank Waktu, so do not offer an endlessly reusable bypass button.
            cont.visibility = View.GONE
        }

        val note = TextView(this).apply {
            text = if (limitMode) "" else (p.getString(KEY_NOTE, "") ?: "")
            textSize = 11f
            setTextColor(mutedInk)
            gravity = Gravity.CENTER
            setPadding(0, dp(10f), 0, 0)
        }

        card.addView(title)
        card.addView(hpLine)
        card.addView(auto)
        card.addView(
            cancel,
            LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            ).apply { bottomMargin = dp(6f) }
        )
        card.addView(cont)
        card.addView(note)
        root.addView(
            card,
            LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            )
        )

        val type = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
        } else {
            @Suppress("DEPRECATION")
            WindowManager.LayoutParams.TYPE_PHONE
        }
        val params = WindowManager.LayoutParams(
            WindowManager.LayoutParams.MATCH_PARENT,
            WindowManager.LayoutParams.MATCH_PARENT,
            type,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE,
            PixelFormat.TRANSLUCENT
        ).apply {
            gravity = Gravity.TOP or Gravity.START
        }

        val added = runCatching { windowManager.addView(root, params) }.isSuccess
        if (!added) {
            stopSelf()
            return
        }

        overlay = root
        countdownText = auto
        activePackage = pkg
        if (!limitMode) {
            countdown = p.getInt(KEY_DELAY, 5).coerceIn(3, 10)
            renderCountdown()
            handler.postDelayed(tick, 1000L)
        }
    }

    /** Lolos 5 menit dari batas harian, tanpa pindah ke home. */
    private fun passFiveMinutes() {
        val pkg = activePackage
        if (pkg == null || !alive) return
        val day = UsageRepo.dayKey()
        val countKey = "passCount|$day|$pkg"
        val used = prefs().getInt(countKey, 0)
        if (used >= PASS_CAP) return
        // Persist before dismissing: a failed write must leave the limit
        // overlay up instead of silently pretending the pass was granted.
        val saved = runCatching {
            NativeStore.write(this, NativeStore.generation) {
                NativeStore.checkCommit(
                    prefs().edit()
                        .putLong("pass|$day|$pkg", System.currentTimeMillis() + PASS_MS)
                        .putInt(countKey, used + 1)
                )
            }
        }.isSuccess
        if (!saved) return
        dismissOverlay()
    }

    private fun saveRuntime(key: String, value: Long) {
        if (!alive || !canMonitor()) return
        runCatching {
            NativeStore.write(this, NativeStore.generation) { prefs().edit().putLong(key, value).apply() }
        }
    }

    private fun cardDrawable(color: Int, radius: Float, ink: Int): GradientDrawable {
        val drawable = GradientDrawable()
        drawable.cornerRadius = dp(radius).toFloat()
        drawable.setColor(color)
        if (radius <= 8f) {
            drawable.setStroke(dp(2f).coerceAtLeast(2), ink)
        }
        return drawable
    }

    private fun renderCountdown() {
        val template = prefs().getString(KEY_AUTO, "Lanjut otomatis dalam {s} detik")
            ?: "Lanjut otomatis dalam {s} detik"
        countdownText?.text = template.replace("{s}", countdown.toString())
    }

    private fun appLabel(pkg: String): String {
        val fallback = prefs().getString(KEY_APP_FALLBACK, pkg) ?: pkg
        return try {
            packageManager.getApplicationLabel(
                packageManager.getApplicationInfo(pkg, 0)
            ).toString()
        } catch (e: Exception) {
            fallback
        }
    }

    private fun continueToApp() {
        val pkg = activePackage
        dismissOverlay()
        if (pkg != null) saveRuntime("cooldown|$pkg", System.currentTimeMillis() + COOLDOWN_MS)
    }

    private fun cancelToHome() {
        if (!alive || !canMonitor()) return
        val pkg = activePackage
        dismissOverlay()
        if (pkg != null) saveRuntime("cooldown|$pkg", System.currentTimeMillis() + CANCEL_COOLDOWN_MS)
        lastForeground = null
        val home = Intent(Intent.ACTION_MAIN)
            .addCategory(Intent.CATEGORY_HOME)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        runCatching { startActivity(home) }
    }

    private fun dismissOverlay() {
        handler.removeCallbacks(tick)
        overlay?.let { view ->
            runCatching { windowManager.removeView(view) }
        }
        overlay = null
        countdownText = null
        activePackage = null
    }

    private fun buildNotification(): Notification {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val manager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            val channel = NotificationChannel(
                CHANNEL_ID,
                "Jeda Sadar",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Menampilkan jeda singkat sebelum app yang dipantau terbuka."
                setShowBadge(false)
            }
            manager.createNotificationChannel(channel)
        }

        val openIntent = Intent(this, MainActivity::class.java).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
        }
        val pending = PendingIntent.getActivity(
            this,
            1,
            openIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val builder = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            Notification.Builder(this, CHANNEL_ID)
        } else {
            @Suppress("DEPRECATION")
            Notification.Builder(this)
        }

        return builder
            .setContentTitle("Jeda Sadar aktif")
            .setContentText("Jeda singkat muncul sebelum app yang dipantau terbuka.")
            .setSmallIcon(R.drawable.ic_pill)
            .setContentIntent(pending)
            .setOngoing(true)
            .build()
    }
}
