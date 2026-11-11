package com.screentimetrack.app

import android.Manifest
import android.app.NotificationManager
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.view.accessibility.AccessibilityManager
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import java.util.concurrent.RejectedExecutionException

/**
 * Modul native tipis: hanya mengumpulkan data mentah lalu mengirimnya ke Flutter.
 * Tidak ada logika game atau visual di sini (docs/06 bagian Aturan Pemisahan).
 */
class MainActivity : FlutterActivity() {
    private val channelName = "com.screentimetrack/usage"
    private var channel: MethodChannel? = null
    private val worker = NativeStore.executor("momo-channel")
    private val main = Handler(Looper.getMainLooper())
    private val pending = mutableSetOf<MethodChannel.Result>()
    @Volatile private var alive = true
    /** Channel work runs off the UI thread; read this instead of assuming. */
    @Volatile private var resumed = false
    private var pendingAction: String? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        pendingAction = savedInstanceState?.getString("pendingPillAction")
        captureAction(intent)
        super.onCreate(savedInstanceState)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        captureAction(intent)
    }

    private fun captureAction(intent: Intent?) {
        if (intent?.action == PillService.ACTION_REST) {
            // The exported launcher activity can be targeted by any app. Only
            // accept the rest action with the unguessable token the pill wrote
            // immediately before starting this activity.
            val provided = intent.getStringExtra(PillService.EXTRA_REST_TOKEN)
            val prefs = getSharedPreferences(PillService.PREFS, Context.MODE_PRIVATE)
            val stored = prefs.getString(PillService.KEY_REST_TOKEN, null)
            val valid = provided != null && stored != null && provided == stored
            if (valid) {
                prefs.edit().remove(PillService.KEY_REST_TOKEN).apply()
                pendingAction = "rest"
            }
            intent.action = Intent.ACTION_MAIN
            intent.removeExtra(PillService.EXTRA_REST_TOKEN)
        }
    }

    override fun onSaveInstanceState(outState: Bundle) {
        outState.putString("pendingPillAction", pendingAction)
        super.onSaveInstanceState(outState)
    }

    override fun onResume() {
        super.onResume()
        resumed = true
        PillService.setHostForeground(true)
        PetOverlayService.setHostForeground(true)
        UsageRepo.invalidate() // Permissions, installed packages, date/timezone may have changed in Settings.
        if (!NativeStore.enabled(this) || !UsageRepo.hasUsageAccess(this) || !Settings.canDrawOverlays(this)) {
            PillService.stop(this); PauseService.stop(this); PetOverlayService.stop(this)
        }
        if (!NativeStore.enabled(this)) {
            // Reconcile an alarm that survived a kill during deletion.
            runCatching { ReminderScheduler.cancel(this) }
        } else {
            // Recover the one-shot daily alarm after an app update or force-stop.
            runCatching { ReminderScheduler.reschedule(this) }
        }
        ScrollCounterService.refreshFilter()
    }

    override fun onPause() {
        resumed = false
        PillService.setHostForeground(false)
        PetOverlayService.setHostForeground(false)
        super.onPause()
    }

    override fun onDestroy() {
        alive = false
        for (result in pending.toList()) result.error("CANCELLED", "Activity was destroyed", null)
        pending.clear()
        worker.shutdownNow()
        main.removeCallbacksAndMessages(null)
        channel?.setMethodCallHandler(null)
        channel = null
        super.onDestroy()
    }

    private fun failure(result: MethodChannel.Result, error: Throwable) {
        val code = when (error) {
            is SecurityException -> "NO_PERMISSION"
            is IllegalArgumentException -> "BAD_ARGUMENTS"
            is InterruptedException, is IllegalStateException -> "CANCELLED"
            else -> "NATIVE_ERROR"
        }
        result.error(code, error.message ?: "Native operation failed", null)
    }

    private fun <T> submit(result: MethodChannel.Result, collection: Boolean = false,
        checkAfter: Boolean = true, work: () -> T, success: (T) -> Unit = { result.success(it) }) {
        val token = NativeStore.generation
        pending.add(result)
        try {
            worker.execute {
                val outcome = runCatching {
                    check(alive && token == NativeStore.generation) { "Request expired" }
                    if (collection) {
                        check(NativeStore.enabled(applicationContext)) { "Collection disabled" }
                        if (!UsageRepo.hasUsageAccess(applicationContext)) throw SecurityException("Usage access not granted")
                    }
                    work()
                }
                main.post {
                    if (!alive || !pending.remove(result)) return@post
                    if (checkAfter && token != NativeStore.generation) {
                        result.error("CANCELLED", "Native data changed", null)
                    } else if (collection && (!NativeStore.enabled(this) || !UsageRepo.hasUsageAccess(this))) {
                        result.error("NO_PERMISSION", "Collection or usage access was revoked", null)
                    } else outcome.fold(success, { failure(result, it) })
                }
            }
        } catch (_: RejectedExecutionException) {
            pending.remove(result)
            result.error("BUSY", "Native worker queue is full or stopped", null)
        }
    }

    private fun disableAndStop() {
        NativeStore.disable(this)
        // Must be synchronous: a queued cancel can be lost if the process dies.
        runCatching { ReminderScheduler.cancel(this) }
        UsageRepo.invalidate()
        PillService.stop(this); PauseService.stop(this); PetOverlayService.stop(this)
        ScrollCounterService.refreshFilter()
        pendingAction = null
    }

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        channel = MethodChannel(flutterEngine.dartExecutor.binaryMessenger, channelName).also { bridge ->
            bridge.setMethodCallHandler { call, result ->
                try {
                    when (call.method) {
                        "hasUsageAccess" -> result.success(UsageRepo.hasUsageAccess(this))
                        "hasAccessibility" -> result.success(hasAccessibility())
                        "hasOverlay" -> result.success(Settings.canDrawOverlays(this))
                        "openUsageSettings" -> { openSettings(Settings.ACTION_USAGE_ACCESS_SETTINGS); result.success(null) }
                        "openAccessibilitySettings" -> { openSettings(Settings.ACTION_ACCESSIBILITY_SETTINGS); result.success(null) }
                        "openOverlaySettings" -> {
                            startActivity(Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, Uri.parse("package:$packageName")))
                            result.success(null)
                        }
                        "getTodayUsage" -> submit(result, collection = true, work = { UsageRepo.todayUsage(applicationContext) })
                        "getUsageRange" -> {
                            val start = requireNotNull(call.argument<Number>("startMs")) { "startMs required" }.toLong()
                            val end = requireNotNull(call.argument<Number>("endMs")) { "endMs required" }.toLong()
                            submit(result, collection = true, work = { UsageRepo.queryRange(applicationContext, start, end) })
                        }
                        "getBaselineMinutes" -> submit(result, collection = true, work = { UsageRepo.baselineMinutes(applicationContext) })
                        "getDailyTotals" -> {
                            val days = NativeBackup.integer(call.argument<Number>("days") ?: 7, 1, 30)
                            submit(result, collection = true, work = { UsageRepo.dailyTotals(applicationContext, days) })
                        }
                        "getNightUsage" -> {
                            val days = NativeBackup.integer(call.argument<Number>("days") ?: 1, 1, 30)
                            require(days in setOf(1, 7, 30)) { "days must be 1, 7 or 30" }
                            submit(result, collection = true, work = { UsageRepo.nightUsage(applicationContext, days) })
                        }
                        "getInstalledApps" -> submit(result, work = { UsageRepo.installedApps(applicationContext) })
                        "setMonitoredApps" -> {
                            val packages = NativeBackup.packages(call.argument<Any>("packages"))
                            val token = NativeStore.generation
                            submit(result, checkAfter = false, work = { NativeStore.setMonitored(applicationContext, packages, token) }) {
                                UsageRepo.invalidate(); ScrollCounterService.refreshFilter(); result.success(null)
                            }
                        }
                        "setCollectionEnabled" -> {
                            val enabled = requireNotNull(call.argument<Boolean>("enabled")) { "enabled required" }
                            if (!enabled) disableAndStop()
                            submit(result, checkAfter = false, work = {
                                if (!enabled) ReminderScheduler.cancel(applicationContext)
                                NativeStore.setEnabled(applicationContext, enabled)
                                UsageRepo.clearCache()
                            }) { ScrollCounterService.refreshFilter(); result.success(null) }
                        }
                        "clearLocalData" -> {
                            disableAndStop()
                            submit(result, work = {
                                val cancel = runCatching { ReminderScheduler.cancel(applicationContext) }
                                try { NativeStore.clear(applicationContext) } finally { UsageRepo.clearCache() }
                                cancel.getOrThrow()
                                null
                            })
                        }
                        "exportNativeData" -> submit(result, work = { NativeStore.export(applicationContext) })
                        "importNativeData" -> {
                            val raw = call.argument<Any>("data")
                            submit(result, work = { NativeBackup.validate(raw) }) { data ->
                                disableAndStop()
                                submit(result, work = {
                                    val cancel = runCatching { ReminderScheduler.cancel(applicationContext) }
                                    try { NativeStore.replace(applicationContext, data) } finally { UsageRepo.clearCache() }
                                    cancel.getOrThrow()
                                    null
                                })
                            }
                        }
                        "grantBankTime" -> {
                            val pkg = call.argument<String>("packageName").orEmpty()
                            val minutes = runCatching { NativeBackup.integer(call.argument<Any>("minutes"), 1, 480) }.getOrNull()
                            if (minutes == null) result.success(false) else {
                                val token = NativeStore.generation
                                submit(result, work = { NativeStore.grantBankTime(applicationContext, pkg, minutes, token) })
                            }
                        }
                        "consumePendingAction" -> { val action = pendingAction; pendingAction = null; result.success(action) }
                        "scheduleReminder" -> {
                            if (!notificationsEnabled()) {
                                // Ask once; scheduling cannot succeed without it.
                                ensureNotificationPermission()
                                result.success(false)
                            } else {
                                val args = call.arguments as? Map<*, *>
                                submit(result, work = { scheduleReminder(args) })
                            }
                        }
                        "cancelReminder" -> submit(result, work = { ReminderScheduler.cancel(applicationContext); null })
                        "isReminderEnabled" -> result.success(ReminderScheduler.isEnabled(this))
                        "showPill" -> {
                            ensureNotificationPermission()
                            val args = call.arguments as? Map<*, *>
                            // Prefs and service start do disk/PackageManager work;
                            // keep them off the UI thread like showPause.
                            submit(result, checkAfter = false, work = { startPill(args) })
                        }
                        "hidePill" -> { PillService.stop(this); result.success(null) }
                        "isPillVisible" -> result.success(PillService.isRunning)
                        "setPillHpBonus" -> {
                            // Only today's recovery counts; the day stamp keeps a
                            // bonus earned before midnight from leaking into a
                            // pill that stays open across the day change.
                            val bonus = ((call.arguments as? Map<*, *>)?.get("bonus") as? Number)
                                ?.toInt() ?: 0
                            getSharedPreferences(PillService.PREFS, Context.MODE_PRIVATE).edit()
                                .putInt(PillService.KEY_HP_BONUS, bonus.coerceIn(0, 100))
                                .putString(PillService.KEY_HP_DAY, PillService.todayKey())
                                .apply()
                            PillService.notifyStatsChanged()
                            PetOverlayService.notifyStatsChanged()
                            result.success(null)
                        }
                        "showPetOverlay" -> {
                            ensureNotificationPermission()
                            val args = call.arguments as? Map<*, *>
                            submit(result, checkAfter = false, work = { startPetOverlay(args) })
                        }
                        "hidePetOverlay" -> { PetOverlayService.stop(this); result.success(null) }
                        "isPetOverlayVisible" -> result.success(PetOverlayService.isRunning)
                        "isPetOverlayFallback" -> result.success(PetOverlayService.isFallback(this))
                        "setPetResting" -> {
                            val resting = requireNotNull(call.argument<Boolean>("resting")) { "resting required" }
                            PillService.setResting(this, resting)
                            result.success(null)
                        }
                        "showPause" -> {
                            ensureNotificationPermission()
                            val args = call.arguments as? Map<*, *>
                            // Persisting limits and starting the service do disk and
                            // PackageManager work; keep both off the UI thread.
                            submit(result, checkAfter = false, work = { startPause(args) })
                        }
                        "hidePause" -> { PauseService.stop(this); result.success(null) }
                        "isPauseRunning" -> result.success(PauseService.isRunning)
                        else -> result.notImplemented()
                    }
                } catch (error: Exception) { failure(result, error) }
            }
        }
    }

    private fun startPill(args: Map<*, *>?): Boolean {
        if (!NativeStore.enabled(this) || !Settings.canDrawOverlays(this) || !UsageRepo.hasUsageAccess(this)) return false
        val language = (args?.get("language") as? String) ?: "id"
        require(language in setOf("id", "en")) { "language must be id or en" }
        val stage = (args?.get("stage") as? String) ?: "bayi"
        require(stage in setOf("bayi", "remaja", "dewasa")) { "stage must be bayi, remaja or dewasa" }
        val animation = (args?.get("animation") as? String) ?: "flat"
        require(animation in setOf("flat", "full")) { "animation must be flat or full" }
        val form = (args?.get("form") as? String) ?: "head"
        require(form in setOf("head", "body")) { "form must be head or body" }
        // The companion is permanent after onboarding; native only validates
        // the value so a bad caller can never point the pill at a missing set.
        val pet = (args?.get("pet") as? String) ?: PetKind.MOMO.storageValue
        require(pet in setOf("momo", "drako")) { "pet must be momo or drako" }
        val prefs = getSharedPreferences(PillService.PREFS, Context.MODE_PRIVATE)
        val background = (args?.get("background") as? Number)?.toInt() ?: 0xFFFFFFFF.toInt()
        val surface = (args?.get("surface") as? Number)?.toInt() ?: background
        val ink = (args?.get("ink") as? Number)?.toInt() ?: 0xFF111111.toInt()
        val accent = (args?.get("accent") as? Number)?.toInt() ?: ink
        val radius = (args?.get("radius") as? Number)?.toFloat() ?: 14f
        val hpBonus = (args?.get("hpBonus") as? Number)?.toInt() ?: 0
        val hpHealthy = (args?.get("hpHealthy") as? Number)?.toInt() ?: 0xFF3DDC84.toInt()
        val hpTired = (args?.get("hpTired") as? Number)?.toInt() ?: 0xFFFFB020.toInt()
        val hpCritical = (args?.get("hpCritical") as? Number)?.toInt() ?: 0xFFFF4D4D.toInt()
        prefs.edit()
            .putInt(PillService.KEY_BACKGROUND, background)
            .putInt(PillService.KEY_SURFACE, surface)
            .putInt(PillService.KEY_INK, ink)
            .putInt(PillService.KEY_ACCENT, accent)
            .putFloat(PillService.KEY_RADIUS, radius.coerceIn(0f, 100f))
            .putString(PillService.KEY_LANGUAGE, language)
            .putString(PillService.KEY_STAGE, stage)
            .putString(PillService.KEY_ANIMATION, animation)
            .putString(PillService.KEY_FORM, form)
            .putString(PillService.KEY_PET, pet)
            .putInt(PillService.KEY_HP_BONUS, hpBonus.coerceIn(0, 100))
            .putString(PillService.KEY_HP_DAY, PillService.todayKey())
            .putInt(PillService.KEY_HP_HEALTHY, hpHealthy)
            .putInt(PillService.KEY_HP_TIRED, hpTired)
            .putInt(PillService.KEY_HP_CRITICAL, hpCritical)
            .apply()
        return runCatching {
            // If the settings UI that enabled the pill is still on screen,
            // flag it first so the new window starts hidden, not flashed.
            PillService.setHostForeground(resumed)
            PillService.start(this)
            true
        }.getOrDefault(false)
    }

    private fun startPetOverlay(args: Map<*, *>?): Boolean {
        // HP and moods read real usage; without the stats permission the pet
        // would roam with a frozen value, so match the pill's gate.
        if (!NativeStore.enabled(this) || !Settings.canDrawOverlays(this) ||
            !UsageRepo.hasUsageAccess(this)
        ) return false
        val language = (args?.get("language") as? String) ?: "id"
        require(language in setOf("id", "en")) { "language must be id or en" }
        val stage = (args?.get("stage") as? String) ?: "bayi"
        require(stage in setOf("bayi", "remaja", "dewasa")) { "stage must be bayi, remaja or dewasa" }
        val animation = (args?.get("animation") as? String) ?: "flat"
        require(animation in setOf("flat", "full")) { "animation must be flat or full" }
        val pet = (args?.get("pet") as? String) ?: PetKind.MOMO.storageValue
        require(pet in setOf("momo", "drako")) { "pet must be momo or drako" }
        val hpBonus = (args?.get("hpBonus") as? Number)?.toInt() ?: 0
        // HP stays native and shared with the pill: write today's recovery,
        // stage and companion once so both overlays agree without a second
        // channel call.
        getSharedPreferences(PillService.PREFS, Context.MODE_PRIVATE).edit()
            .putString(PillService.KEY_STAGE, stage)
            .putString(PillService.KEY_PET, pet)
            .putInt(PillService.KEY_HP_BONUS, hpBonus.coerceIn(0, 100))
            .putString(PillService.KEY_HP_DAY, PillService.todayKey())
            .apply()
        getSharedPreferences(PetOverlayService.PREFS, Context.MODE_PRIVATE).edit()
            .putString(PetOverlayService.KEY_LANGUAGE, language)
            .putString(PetOverlayService.KEY_STAGE, stage)
            .putString(PetOverlayService.KEY_ANIMATION, animation)
            .putString(PetOverlayService.KEY_PET, pet)
            .apply()
        return runCatching {
            // Only hide it while this activity is actually on screen; a sync
            // from the background must not leave the window parked hidden.
            PetOverlayService.setHostForeground(resumed)
            PetOverlayService.start(this)
            true
        }.getOrDefault(false)
    }

    private fun startPause(args: Map<*, *>?): Boolean {
        if (!NativeStore.enabled(this) || !Settings.canDrawOverlays(this) || !UsageRepo.hasUsageAccess(this)) return false
        val selected = NativeBackup.packages(args?.get("packages") ?: emptyList<String>()).filter { it != packageName }
        val packages = selected.joinToString(",")
        if (selected.isEmpty()) { PauseService.stop(this); return false }

        fun intArg(key: String, fallback: Int): Int =
            (args?.get(key) as? Number)?.toInt() ?: fallback

        fun textArg(key: String, fallback: String): String =
            (args?.get(key) as? String) ?: fallback

        val limitMap = (args?.get("limits") as? Map<*, *>).orEmpty().entries.associate { entry ->
            val pkg = entry.key as? String ?: throw IllegalArgumentException("Invalid limit package")
            require(NativeBackup.validPackage(pkg)) { "Invalid limit package" }
            pkg to NativeBackup.integer(entry.value, 1, 1440)
        }
        val previousPackages = NativeStore.monitored(this).toList()
        val previousLimits = NativeStore.limits(this)
        fun rollback() {
            runCatching {
                NativeStore.setMonitored(this, previousPackages, NativeStore.generation)
                NativeStore.setLimits(this, previousLimits, NativeStore.generation)
            }
        }
        val limits = limitMap.entries.joinToString(",") { "${it.key}=${it.value}" }

        val prefs = getSharedPreferences(PauseService.PREFS, Context.MODE_PRIVATE)
        prefs.edit()
            .putString(PauseService.KEY_PACKAGES, packages)
            .putInt(PauseService.KEY_DELAY, intArg("delaySeconds", 5).coerceIn(3, 10))
            .putInt(PauseService.KEY_BACKGROUND, intArg("background", 0xFF0B0D12.toInt()))
            .putInt(PauseService.KEY_SURFACE, intArg("surface", 0xFFFFFFFF.toInt()))
            .putInt(PauseService.KEY_INK, intArg("ink", 0xFF111111.toInt()))
            .putInt(PauseService.KEY_ACCENT, intArg("accent", 0xFFFFD23F.toInt()))
            .putFloat(
                PauseService.KEY_RADIUS,
                (args?.get("radius") as? Number)?.toFloat() ?: 14f
            )
            .putString(
                PauseService.KEY_TITLE,
                textArg("titleTemplate", "Mau ngapain di {app}?")
            )
            .putString(
                PauseService.KEY_AUTO,
                textArg("autoTemplate", "Lanjut otomatis dalam {s} detik")
            )
            .putString(PauseService.KEY_CANCEL, textArg("cancelLabel", "Ke layar utama"))
            .putString(PauseService.KEY_CONTINUE, textArg("continueLabel", "Lanjut"))
            .putString(
                PauseService.KEY_NOTE,
                textArg("note", "Tidak ada blokir paksa. Kamu tetap bisa lanjut.")
            )
            .putString(PauseService.KEY_HP, textArg("hpLine", ""))
            .putString(PauseService.KEY_APP_FALLBACK, textArg("appFallback", "aplikasi ini"))
            .putString(PauseService.KEY_LIMITS, limits)
            .putString(
                PauseService.KEY_LIMIT_TITLE,
                textArg("limitTitle", "Batas harian {app} tercapai")
            )
            .putString(
                PauseService.KEY_LIMIT_NOTE,
                textArg("limitNote", "Hari ini {used}m dari batas {limit}m.")
            )
            .putString(
                PauseService.KEY_LIMIT_PASS,
                textArg("limitPassLabel", "Lanjut 5 menit")
            )
            .putString(
                PauseService.KEY_LIMIT_CLOSE,
                textArg("limitCloseLabel", "Tutup app")
            )
            .apply()

        // Persist policy and only report success once the overlay is actually up.
        // Any failure restores the previous monitored set/limits so the pause
        // configuration never half-applies.
        return try {
            NativeStore.setMonitored(this, selected, NativeStore.generation)
            NativeStore.setLimits(this, limitMap, NativeStore.generation)
            val started = runCatching { PauseService.start(this); true }.getOrDefault(false)
            if (!started) {
                rollback()
                false
            } else {
                ScrollCounterService.refreshFilter()
                true
            }
        } catch (error: Exception) {
            rollback()
            throw error
        }
    }

    private fun scheduleReminder(args: Map<*, *>?): Boolean {
        if (!NativeStore.enabled(this) || !notificationsEnabled()) return false
        val hour = NativeBackup.integer(args?.get("hour") ?: 20, 0, 23)
        val minute = NativeBackup.integer(args?.get("minute") ?: 0, 0, 59)
        // Flutter always sends the localized, companion-aware copy; the
        // fallback must stay neutral for either pet.
        val title = (args?.get("title") as? String) ?: "Pengingat harian"
        val body = (args?.get("body") as? String)
            ?: "Cek HP dan selesaikan satu misi hari ini."
        ReminderScheduler.schedule(this, hour, minute, title, body)
        return true
    }

    private fun notificationsEnabled(): Boolean {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) !=
            PackageManager.PERMISSION_GRANTED
        ) return false
        val manager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        return manager.areNotificationsEnabled()
    }

    private fun ensureNotificationPermission() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) !=
            PackageManager.PERMISSION_GRANTED
        ) {
            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 771)
        }
    }

    private fun openSettings(action: String) {
        startActivity(Intent(action).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
    }

    private fun hasAccessibility(): Boolean {
        val master = Settings.Secure.getInt(
            contentResolver, Settings.Secure.ACCESSIBILITY_ENABLED, 0
        ) == 1
        val raw = Settings.Secure.getString(
            contentResolver, Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES
        )
        val component = ComponentName(this, ScrollCounterService::class.java)
        val listed = AccessibilityCheck.isEnabled(
            master, raw, component.flattenToString(), component.flattenToShortString()
        )
        if (!listed) return false
        // A stale secure setting can survive an OS-level unbind. Only report
        // active when the accessibility manager still has the service enabled.
        val manager = getSystemService(Context.ACCESSIBILITY_SERVICE) as? AccessibilityManager
            ?: return false
        return manager.isEnabled && manager
            .getEnabledAccessibilityServiceList(android.accessibilityservice.AccessibilityServiceInfo.FEEDBACK_ALL_MASK)
            .any { info ->
                val service = info.resolveInfo?.serviceInfo ?: return@any false
                ComponentName(service.packageName, service.name) == component
            }
    }
}
