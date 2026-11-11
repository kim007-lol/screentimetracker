package com.screentimetrack.app

import android.app.AppOpsManager
import android.app.usage.UsageEvents
import android.app.usage.UsageStatsManager
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.Process
import android.os.SystemClock
import java.util.Date
import java.util.TimeZone

/** Snapshot for the floating pill: today's totals plus the app in front right now. */
data class PillStats(
    val totalMinutes: Int,
    val totalScroll: Int,
    val appPackage: String?,
    val appLabel: String?,
    val sessionMinutes: Int,
    val appScroll: Int,
)

/** Raw measured usage only. All entry points doing queries must be called from a worker. */
object UsageRepo {
    const val SCROLL_PREFS = "scroll_counts"
    private const val TODAY_TTL = 10_000L
    private val cacheLock = Any()
    @Volatile private var revision = 0L
    private var cacheIdentity = ""
    private var todayAt = 0L
    private var todayEnd = 0L
    private var todayEvents: List<UsageAggregation.Event>? = null
    private var todayRows: Map<String, UsageAggregation.Totals> = emptyMap()
    private val dayCache = object : LinkedHashMap<Long, Map<String, UsageAggregation.Totals>>(48, .75f, true) {
        override fun removeEldestEntry(eldest: MutableMap.MutableEntry<Long, Map<String, UsageAggregation.Totals>>?) = size > 45
    }
    private var baselineKey = ""
    private var baseline = 0
    private val allowedLock = Any()
    private var allowedKey = ""
    private var allowedPackages: Set<String> = emptySet()
    private var homePackages: Set<String> = emptySet()

    fun invalidate() { revision++ }
    fun dayKey(): String = UsageAggregation.dayKey(System.currentTimeMillis())
    fun dayKey(date: Date): String = UsageAggregation.dayKey(date.time)
    fun startOfToday(): Long = UsageAggregation.midnight(System.currentTimeMillis())
    fun hasUsageAccess(context: Context): Boolean = runCatching {
        val ops = context.getSystemService(Context.APP_OPS_SERVICE) as AppOpsManager
        val mode = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q)
            ops.unsafeCheckOpNoThrow(AppOpsManager.OPSTR_GET_USAGE_STATS, Process.myUid(), context.packageName)
        else {
            @Suppress("DEPRECATION")
            ops.checkOpNoThrow(AppOpsManager.OPSTR_GET_USAGE_STATS, Process.myUid(), context.packageName)
        }
        mode == AppOpsManager.MODE_ALLOWED
    }.getOrDefault(false)

    private fun checkAccess(context: Context, token: Long) {
        check(NativeStore.valid(context, token)) { "Collection disabled or request expired" }
        if (!hasUsageAccess(context)) { invalidate(); throw SecurityException("Usage access not granted") }
    }

    fun installedApps(context: Context): List<Map<String, String>> {
        val intent = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
        return context.packageManager.queryIntentActivities(intent, 0)
            .filter { it.activityInfo.packageName != context.packageName }
            .distinctBy { it.activityInfo.packageName }
            .map { mapOf("packageName" to it.activityInfo.packageName, "label" to it.loadLabel(context.packageManager).toString()) }
            .sortedBy { it.getValue("label").lowercase() }
    }

    private fun allowed(context: Context): Set<String> = synchronized(allowedLock) {
        // PackageManager enumeration is not free and was repeated every poll.
        // Installs/removals arrive via onResume invalidation, so cache per revision.
        val key = "${NativeStore.generation}|$revision"
        if (allowedKey != key) {
            // The home app is where the phone idles, not something the user
            // "uses"; counting it made the launcher the top app most days.
            homePackages = runCatching {
                context.packageManager.queryIntentActivities(
                    Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_HOME), 0,
                ).map { it.activityInfo.packageName }.toSet()
            }.getOrDefault(emptySet())
            allowedPackages = installedApps(context).map { it.getValue("packageName") }.toSet() - homePackages
            allowedKey = key
        }
        allowedPackages
    }

    /** The current home app, resolved once per revision. */
    private fun homeApps(context: Context): Set<String> {
        allowed(context)
        return synchronized(allowedLock) { homePackages }
    }

    /** Launchable apps the tracker reports on; home launchers are excluded. */
    fun trackedPackages(context: Context): Set<String> = allowed(context)

    /**
     * Scroll counting follows the monitored set, matching the Android consent
     * text and the in-app Accessibility disclosure. Screen time still covers
     * every launchable app.
     */
    fun isTracked(context: Context, pkg: String): Boolean = pkg in NativeStore.monitored(context)

    /** Includes a seven-calendar-day lookback only when bootstrapping state. */
    fun readEvents(context: Context, start: Long, end: Long, lookback: Boolean = false): List<UsageAggregation.Event> {
        val token = NativeStore.generation
        checkAccess(context, token)
        if (end <= start) return emptyList()
        val from = if (lookback) UsageAggregation.addDays(start, -7) else start
        val source = (context.getSystemService(Context.USAGE_STATS_SERVICE) as UsageStatsManager).queryEvents(from, end)
            ?: return emptyList()
        val event = UsageEvents.Event()
        val out = ArrayList<UsageAggregation.Event>()
        while (source.hasNextEvent()) {
            if (Thread.currentThread().isInterrupted || !NativeStore.valid(context, token)) throw InterruptedException("Usage query cancelled")
            source.getNextEvent(event)
            val kind = when (event.eventType) {
                UsageEvents.Event.ACTIVITY_RESUMED -> UsageAggregation.Kind.RESUME
                UsageEvents.Event.ACTIVITY_PAUSED, UsageEvents.Event.ACTIVITY_STOPPED -> UsageAggregation.Kind.PAUSE
                UsageEvents.Event.SCREEN_NON_INTERACTIVE -> UsageAggregation.Kind.SCREEN_OFF
                UsageEvents.Event.SCREEN_INTERACTIVE, UsageEvents.Event.DEVICE_STARTUP -> UsageAggregation.Kind.SCREEN_ON
                UsageEvents.Event.DEVICE_SHUTDOWN -> UsageAggregation.Kind.SHUTDOWN
                else -> null
            } ?: continue
            if (event.timeStamp < end) out.add(UsageAggregation.Event(event.timeStamp, kind, event.packageName))
        }
        checkAccess(context, token)
        return out
    }

    private fun identity(context: Context): String = "${NativeStore.generation}|$revision|${TimeZone.getDefault().id}|${startOfToday()}"
    private fun prepareCache(context: Context) {
        val key = identity(context)
        if (cacheIdentity != key) {
            dayCache.clear(); todayEvents = null; todayRows = emptyMap(); todayAt = 0; todayEnd = 0
            baselineKey = ""; cacheIdentity = key
        }
    }

    private fun today(context: Context): Map<String, UsageAggregation.Totals> = synchronized(cacheLock) {
        val token = NativeStore.generation
        checkAccess(context, token)
        prepareCache(context)
        val key = cacheIdentity
        val now = System.currentTimeMillis()
        if (todayAt == 0L || SystemClock.elapsedRealtime() - todayAt >= TODAY_TTL || now < todayEnd) {
            val start = startOfToday()
            val previous = todayEvents
            val events = if (previous != null && now >= todayEnd) {
                // Re-read a short tail for UsageStats delivery latency, replacing rather than double counting it.
                val from = maxOf(start, todayEnd - 5_000L)
                previous.filter { it.time < from } + readEvents(context, from, now)
            } else readEvents(context, start, now, lookback = true)
            val packages = allowed(context)
            val rows = UsageAggregation.aggregate(events, start, now).filterKeys { it in packages }
            checkAccess(context, token)
            if (identity(context) != key) throw InterruptedException("Usage cache invalidated")
            todayRows = rows
            todayEvents = events.takeIf { it.size <= 100_000 }
            todayEnd = now
            todayAt = SystemClock.elapsedRealtime()
        }
        // Scroll counters are cheap and merged live; scrolling must not trigger another full event query.
        val counters = UsageAggregation.aggregate(emptyList(), startOfToday(), now,
            context.getSharedPreferences(SCROLL_PREFS, Context.MODE_PRIVATE).all)
        val packages = allowed(context)
        val rows = todayRows.mapValues { (_, v) -> v.copy() }.toMutableMap()
        for ((pkg, count) in counters) if (pkg in packages) {
            val row = rows.getOrPut(pkg) { UsageAggregation.Totals() }
            row.scrollHits = count.scrollHits; row.replays = count.replays
        }
        checkAccess(context, token)
        rows
    }

    private fun aggregate(context: Context, start: Long, end: Long): Map<String, UsageAggregation.Totals> {
        val token = NativeStore.generation
        checkAccess(context, token)
        val packages = allowed(context)
        val rows = UsageAggregation.aggregate(readEvents(context, start, end, true), start, end,
            context.getSharedPreferences(SCROLL_PREFS, Context.MODE_PRIVATE).all).filterKeys { it in packages }
        checkAccess(context, token)
        return rows
    }

    private fun rows(context: Context, values: Map<String, UsageAggregation.Totals>): List<Map<String, Any>> =
        values.map { (pkg, agg) -> mapOf("packageName" to pkg, "label" to appLabel(context, pkg),
            "minutes" to (agg.foregroundMs / 60000).toInt(), "seconds" to (agg.foregroundMs / 1000).toInt(),
            "opens" to agg.opens,
            "longestSessionMinutes" to (agg.longestMs / 60000).toInt(),
            "scrollHits" to agg.scrollHits, "replays" to agg.replays) }.sortedByDescending { it["minutes"] as Int }

    fun todayUsage(context: Context): List<Map<String, Any>> = rows(context, today(context))
    fun queryRange(context: Context, start: Long, end: Long): List<Map<String, Any>> {
        require(start >= 0 && end > start && end <= UsageAggregation.addDays(start, 367)) { "Invalid usage range (maximum 367 days)" }
        return rows(context, aggregate(context, start, minOf(end, System.currentTimeMillis())))
    }

    private fun day(context: Context, start: Long): Map<String, UsageAggregation.Totals> = synchronized(cacheLock) {
        checkAccess(context, NativeStore.generation)
        prepareCache(context)
        if (start == startOfToday()) return@synchronized today(context)
        dayCache[start]?.let { return@synchronized it }
        val key = cacheIdentity
        val result = aggregate(context, start, UsageAggregation.addDays(start, 1))
        if (identity(context) != key) throw InterruptedException("Usage cache invalidated")
        dayCache[start] = result
        result
    }

    fun baselineMinutes(context: Context): Int = synchronized(cacheLock) {
        checkAccess(context, NativeStore.generation)
        prepareCache(context)
        if (baselineKey != cacheIdentity) {
            val start = startOfToday()
            baseline = ((1..7).sumOf { offset -> day(context, UsageAggregation.addDays(start, -offset)).values.sumOf { it.foregroundMs } } / 7 / 60000).toInt()
            baselineKey = cacheIdentity
        }
        baseline
    }

    fun totalsToday(context: Context): Pair<Int, Int> {
        val values = today(context).values
        return (values.sumOf { it.foregroundMs } / 60000).toInt() to values.fold(0) { n, row -> UsageAggregation.saturatingAdd(n, row.scrollHits) }
    }

    /**
     * The pill must name a newly opened app right away, but re-reading the whole
     * day on every switch would be wasteful. Extend the cached event list with a
     * short tail instead; totals still refresh on the normal TTL.
     */
    fun refreshRecent(context: Context) = synchronized(cacheLock) {
        val token = NativeStore.generation
        checkAccess(context, token)
        prepareCache(context)
        val events = todayEvents ?: return@synchronized
        val now = System.currentTimeMillis()
        if (now <= todayEnd) return@synchronized
        val from = maxOf(startOfToday(), todayEnd - 5_000L)
        val tail = readEvents(context, from, now)
        if (tail.isEmpty()) return@synchronized
        todayEvents = (events.filter { it.time < from } + tail).takeIf { it.size <= 100_000 }
        todayEnd = now
    }

    /**
     * Totals plus the foreground app for the floating pill. One cached usage read
     * serves both numbers; the session only needs the events already in hand.
     */
    fun pillStats(context: Context): PillStats = synchronized(cacheLock) {
        val rows = today(context)
        val now = System.currentTimeMillis()
        val totalMinutes = (rows.values.sumOf { it.foregroundMs } / 60000).toInt()
        val totalScroll = rows.values.fold(0) { n, row -> UsageAggregation.saturatingAdd(n, row.scrollHits) }
        val events = todayEvents ?: readEvents(context, UsageAggregation.addDays(now, -1), now)
        val current = UsageAggregation.currentSession(events, now)
            ?.takeIf { it.first != context.packageName && it.first !in homeApps(context) }
        if (current == null) return@synchronized PillStats(totalMinutes, totalScroll, null, null, 0, 0)
        val (pkg, since) = current
        PillStats(
            totalMinutes = totalMinutes,
            totalScroll = totalScroll,
            appPackage = pkg,
            appLabel = appLabel(context, pkg),
            sessionMinutes = ((now - since) / 60000).toInt().coerceIn(0, 24 * 60),
            appScroll = rows[pkg]?.scrollHits ?: 0,
        )
    }
    fun todayMinutesFor(context: Context, pkg: String): Int = ((today(context)[pkg]?.foregroundMs ?: 0L) / 60000).toInt()
    fun appLabel(context: Context, pkg: String): String = runCatching {
        context.packageManager.getApplicationLabel(context.packageManager.getApplicationInfo(pkg, 0)).toString()
    }.getOrDefault(pkg)

    fun dailyTotals(context: Context, days: Int): List<Map<String, Any>> {
        val span = days.coerceIn(1, 30)
        val start = startOfToday()
        val daily = (0 until span + 7).map { day(context, UsageAggregation.addDays(start, -it)) }
        return (0 until span).map { index ->
            val values = daily[index]
            val top = values.maxByOrNull { it.value.foregroundMs }
            mapOf("day" to UsageAggregation.dayKey(UsageAggregation.addDays(start, -index)),
                "minutes" to (values.values.sumOf { it.foregroundMs } / 60000).toInt(),
                "scrollHits" to values.values.fold(0) { n, row -> UsageAggregation.saturatingAdd(n, row.scrollHits) },
                "replays" to values.values.fold(0) { n, row -> UsageAggregation.saturatingAdd(n, row.replays) },
                "baselineMinutes" to (((index + 1)..(index + 7)).sumOf { daily[it].values.sumOf { v -> v.foregroundMs } } / 7 / 60000).toInt(),
                "topAppLabel" to (top?.let { appLabel(context, it.key) } ?: ""),
                "topAppMinutes" to ((top?.value?.foregroundMs ?: 0) / 60000).toInt())
        }
    }

    fun nightUsage(context: Context, days: Int): Map<String, Int> {
        require(days in setOf(1, 7, 30)) { "days must be 1, 7 or 30" }
        val start = UsageAggregation.addDays(startOfToday(), -(days - 1))
        val end = System.currentTimeMillis()
        val packages = allowed(context)
        val minutes = UsageAggregation.nightMillis(readEvents(context, start, end, true), start, end, allowed = { it in packages }) / 60000
        return mapOf("minutes" to minutes.toInt(), "startHour" to 22, "endHour" to 6, "days" to days)
    }

    /** Clear synchronously on a worker after the generation barrier, never on the UI thread. */
    fun clearCache() = synchronized(cacheLock) {
        todayEvents = null; todayRows = emptyMap(); dayCache.clear(); baselineKey = ""; cacheIdentity = ""
        synchronized(allowedLock) { allowedKey = ""; allowedPackages = emptySet(); homePackages = emptySet() }
    }
}
