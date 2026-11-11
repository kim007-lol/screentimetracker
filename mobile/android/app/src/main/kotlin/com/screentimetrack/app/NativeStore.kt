package com.screentimetrack.app

import android.content.Context
import android.content.SharedPreferences
import android.provider.Settings
import java.io.IOException
import java.util.concurrent.ArrayBlockingQueue
import java.util.concurrent.ThreadPoolExecutor
import java.util.concurrent.TimeUnit

/** One write barrier shared by accessibility, services, channel jobs and deletion. */
object NativeStore {
    const val PRIVACY = "native_privacy"
    const val DATA = "native_monitoring"
    private val lock = Any()
    @Volatile var generation = 0L
        private set
    @Volatile private var blocked = false

    fun executor(name: String, capacity: Int = 16) = ThreadPoolExecutor(1, 1, 0L,
        TimeUnit.MILLISECONDS, ArrayBlockingQueue<Runnable>(capacity), { r -> Thread(r, name) },
        ThreadPoolExecutor.AbortPolicy())

    fun enabled(context: Context): Boolean = !blocked &&
        context.getSharedPreferences(PRIVACY, Context.MODE_PRIVATE).getBoolean("enabled", false)

    fun valid(context: Context, token: Long): Boolean = token == generation && enabled(context)

    /** Called synchronously before stopping services/queuing deletion: old work cannot write again. */
    fun disable(context: Context) = synchronized(lock) {
        blocked = true
        generation++
        // Same contract as setEnabled(false): a queued apply() can be lost if
        // the process dies, which would leave collection enabled after a
        // deletion/opt-out the UI already reported.
        checkCommit(context.getSharedPreferences(PRIVACY, Context.MODE_PRIVATE).edit().putBoolean("enabled", false))
    }

    fun setEnabled(context: Context, value: Boolean) = synchronized(lock) {
        if (!value) { blocked = true; generation++ }
        checkCommit(context.getSharedPreferences(PRIVACY, Context.MODE_PRIVATE).edit().putBoolean("enabled", value))
        if (value) { generation++; blocked = false }
    }

    fun <T> write(context: Context, token: Long, action: () -> T): T = synchronized(lock) {
        check(valid(context, token)) { "Collection disabled or request expired" }
        action()
    }

    fun checkCommit(editor: SharedPreferences.Editor) {
        if (!editor.commit()) throw IOException("Could not persist native preferences")
    }

    private fun prefs(context: Context) = context.getSharedPreferences(DATA, Context.MODE_PRIVATE)

    fun monitored(context: Context): Set<String> = prefs(context).getStringSet("packages", emptySet())?.toSet().orEmpty()

    fun setMonitored(context: Context, packages: List<String>, token: Long) = synchronized(lock) {
        check(token == generation) { "Request expired" }
        checkCommit(prefs(context).edit().putStringSet("packages", packages.filter { it != context.packageName }.toSet()))
        generation++
    }

    fun limits(context: Context): Map<String, Int> = prefs(context).all.entries.mapNotNull { (key, value) ->
        if (key.startsWith("limit|") && value is Int && value > 0) key.removePrefix("limit|") to value else null
    }.toMap()

    fun setLimits(context: Context, limits: Map<String, Int>, token: Long) = write(context, token) {
        val p = prefs(context)
        val editor = p.edit()
        for (key in p.all.keys) if (key.startsWith("limit|")) editor.remove(key)
        for ((pkg, minutes) in limits) editor.putInt("limit|$pkg", minutes)
        checkCommit(editor)
    }

    fun allowance(context: Context, pkg: String): Int = prefs(context).getInt("bank|${UsageRepo.dayKey()}|$pkg", 0)

    fun grantBankTime(context: Context, pkg: String, minutes: Int, token: Long): Boolean = synchronized(lock) {
        if (!valid(context, token) || minutes !in 1..480 || !NativeBackup.validPackage(pkg) ||
            !UsageRepo.hasUsageAccess(context) || !Settings.canDrawOverlays(context) || !PauseService.isRunning ||
            (limits(context)[pkg] ?: 0) <= 0 || pkg !in monitored(context)) return@synchronized false
        val key = "bank|${UsageRepo.dayKey()}|$pkg"
        val p = prefs(context)
        val total = p.getInt(key, 0).toLong() + minutes
        if (total > 480) return@synchronized false
        checkCommit(p.edit().putInt(key, total.toInt()))
        true
    }

    fun recordScroll(context: Context, pkg: String, backwards: Boolean, token: Long) = synchronized(lock) {
        // Scroll counters follow every launchable app, not only the managed set;
        // the pill reports the app the user is actually scrolling right now.
        if (!valid(context, token) || !NativeBackup.validPackage(pkg) ||
            !UsageRepo.isTracked(context, pkg)) return@synchronized
        val p = context.getSharedPreferences(UsageRepo.SCROLL_PREFS, Context.MODE_PRIVATE)
        val prefix = "${UsageRepo.dayKey()}|$pkg"
        val editor = p.edit().putInt("$prefix|scroll", UsageAggregation.saturatingAdd(p.getInt("$prefix|scroll", 0), 1))
        if (backwards) editor.putInt("$prefix|replay", UsageAggregation.saturatingAdd(p.getInt("$prefix|replay", 0), 1))
        editor.apply()
    }

    fun export(context: Context): Map<String, Any> = synchronized(lock) {
        val scroll = context.getSharedPreferences(UsageRepo.SCROLL_PREFS, Context.MODE_PRIVATE).all
            .mapNotNull { (k, v) -> if (v is Int && v >= 0) k to v else null }.toMap()
        val bank = prefs(context).all.mapNotNull { (k, v) ->
            if (k.startsWith("bank|") && v is Int && k.substringAfterLast('|') in limits(context))
                k.removePrefix("bank|") to v else null
        }.toMap()
        NativeBackup.validate(NativeBackup(scroll, monitored(context).sorted(), limits(context), bank).toMap()).toMap()
    }

    /** Caller has disabled collection and stopped every service first. Tombstone survives process death. */
    fun clear(context: Context) = synchronized(lock) {
        blocked = true
        checkCommit(context.getSharedPreferences(PRIVACY, Context.MODE_PRIVATE).edit().clear().putBoolean("enabled", false))
        var failed = false
        for (name in listOf(UsageRepo.SCROLL_PREFS, DATA, PauseService.PREFS, PillService.PREFS,
            PetOverlayService.PREFS, ReminderScheduler.PREFS)) {
            if (!context.getSharedPreferences(name, Context.MODE_PRIVATE).edit().clear().commit()) failed = true
        }
        if (failed) throw IOException("Some native preferences could not be cleared")
    }

    fun replace(context: Context, data: NativeBackup) = synchronized(lock) {
        clear(context)
        val editor = prefs(context).edit().putStringSet("packages", data.monitoredPackages.filter { it != context.packageName }.toSet())
        for ((pkg, value) in data.limits) editor.putInt("limit|$pkg", value)
        for ((key, value) in data.bankAllowances) editor.putInt("bank|$key", value)
        checkCommit(editor)
        val scroll = context.getSharedPreferences(UsageRepo.SCROLL_PREFS, Context.MODE_PRIVATE).edit()
        for ((key, value) in data.scrollCounts) scroll.putInt(key, value)
        checkCommit(scroll)
        // Deliberately do not set enabled or restart alarms/services.
    }
}
