package com.screentimetrack.app

import java.text.SimpleDateFormat
import java.util.Locale

/** The entire native backup allowlist. Runtime grants, service state and UI text are excluded. */
data class NativeBackup(val scrollCounts: Map<String, Int>, val monitoredPackages: List<String>,
    val limits: Map<String, Int>, val bankAllowances: Map<String, Int>) {
    fun toMap(): Map<String, Any> = mapOf("version" to 1, "scrollCounts" to scrollCounts,
        "monitoredPackages" to monitoredPackages, "limits" to limits, "bankAllowances" to bankAllowances)

    companion object {
        fun validPackage(value: String): Boolean = value.length <= 255 &&
            Regex("[A-Za-z][A-Za-z0-9_]*(\\.[A-Za-z0-9_]+)+").matches(value)

        fun packages(value: Any?): List<String> {
            require(value is List<*> && value.size <= 1000) { "Invalid package list" }
            require(value.all { it is String && validPackage(it) }) { "Invalid package name" }
            return value.filterIsInstance<String>().distinct()
        }

        fun integer(value: Any?, min: Int, max: Int): Int {
            require(value is Number && value.toDouble().isFinite() &&
                value.toDouble() == value.toLong().toDouble() && value.toLong() in min.toLong()..max.toLong()) {
                "Invalid integer"
            }
            return value.toInt()
        }

        private fun validDay(value: String): Boolean {
            if (!Regex("[0-9]{8}").matches(value)) return false
            val format = SimpleDateFormat("yyyyMMdd", Locale.US).apply { isLenient = false }
            return runCatching { format.format(requireNotNull(format.parse(value))) == value }.getOrDefault(false)
        }

        fun validate(raw: Any?): NativeBackup {
            require(raw is Map<*, *> && raw.keys == setOf("version", "scrollCounts", "monitoredPackages", "limits", "bankAllowances")) {
                "Unknown or missing native backup fields"
            }
            require(integer(raw["version"], 1, 1) == 1)
            fun counters(name: String, max: Int, keyValid: (String) -> Boolean): Map<String, Int> {
                val values = raw[name]
                require(values is Map<*, *> && values.size <= 100000) { "Invalid $name" }
                return values.entries.associate { (key, value) ->
                    require(key is String && keyValid(key)) { "Invalid $name key" }
                    key to integer(value, if (name == "limits") 1 else 0, max)
                }
            }
            val scroll = counters("scrollCounts", Int.MAX_VALUE) {
                val p = it.split('|')
                p.size == 3 && validDay(p[0]) && validPackage(p[1]) && p[2] in setOf("scroll", "replay")
            }
            val targets = packages(raw["monitoredPackages"])
            val limits = counters("limits", 1440, ::validPackage)
            val bank = counters("bankAllowances", 480) {
                val p = it.split('|')
                p.size == 2 && validDay(p[0]) && validPackage(p[1])
            }
            require(bank.keys.all { it.substringAfter('|') in limits }) { "Bank time requires an app limit" }
            return NativeBackup(scroll, targets, limits, bank)
        }
    }
}

/** A daily limit/pass is independent of the normal entry-pause cooldown. */
object PauseDecision {
    const val NONE = 0
    const val NORMAL = 1
    const val LIMIT = 2
    fun decide(now: Long, entered: Boolean, used: Int, limit: Int, passUntil: Long, cooldownUntil: Long): Int = when {
        // An exhausted daily limit is re-checked even when the user stays in
        // the same app, so only an explicit pass defers it. The entry-pause
        // cooldown applies to NORMAL only; otherwise leaving an app near the
        // limit would hand out a free cooldown of unrestricted use.
        limit > 0 && used >= limit ->
            if (now >= passUntil) LIMIT else NONE
        entered && now >= cooldownUntil -> NORMAL
        else -> NONE
    }
}
