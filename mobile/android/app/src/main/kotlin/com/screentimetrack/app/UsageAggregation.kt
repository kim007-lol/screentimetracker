package com.screentimetrack.app

import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Date
import java.util.Locale
import java.util.TimeZone

/** Pure calendar/interval logic. Ranges are [start, end); no Android or game rules. */
object UsageAggregation {
    enum class Kind { RESUME, PAUSE, SCREEN_OFF, SCREEN_ON, SHUTDOWN }
    data class Event(val time: Long, val kind: Kind, val pkg: String? = null)
    data class Interval(val pkg: String, val start: Long, val end: Long, val opened: Boolean)
    data class Day(val key: String, val start: Long, val end: Long)
    data class Totals(var foregroundMs: Long = 0, var opens: Int = 0,
        var longestMs: Long = 0, var scrollHits: Int = 0, var replays: Int = 0)

    fun dayKey(time: Long, zone: TimeZone = TimeZone.getDefault()): String =
        SimpleDateFormat("yyyyMMdd", Locale.US).apply { timeZone = zone }.format(Date(time))

    fun midnight(time: Long, zone: TimeZone = TimeZone.getDefault()): Long =
        Calendar.getInstance(zone).apply {
            timeInMillis = time
            set(Calendar.HOUR_OF_DAY, 0); set(Calendar.MINUTE, 0)
            set(Calendar.SECOND, 0); set(Calendar.MILLISECOND, 0)
        }.timeInMillis

    fun addDays(time: Long, count: Int, zone: TimeZone = TimeZone.getDefault()): Long =
        Calendar.getInstance(zone).apply { timeInMillis = time; add(Calendar.DAY_OF_YEAR, count) }.timeInMillis

    fun days(start: Long, end: Long, zone: TimeZone = TimeZone.getDefault()): List<Day> {
        if (end <= start) return emptyList()
        val result = ArrayList<Day>()
        var cursor = midnight(start, zone)
        while (cursor < end) {
            val next = addDays(cursor, 1, zone)
            result.add(Day(dayKey(cursor, zone), cursor, next))
            cursor = next
        }
        return result
    }

    /**
     * App still on screen at [end], together with the moment its current session
     * began. Uses the same open/close rules as [intervals]; a session that
     * started before the first event is reported with that first resume time.
     */
    /** The foreground app at [end]; [events] must be in chronological order. */
    fun currentSession(events: List<Event>, end: Long): Pair<String, Long>? {
        // Newest first: the last unresolved resume wins; a pause on the way back
        // means that app is already closed. No re-sort on every pill refresh.
        val closed = HashSet<String>()
        for (index in events.indices.reversed()) {
            val event = events[index]
            if (event.time > end) continue
            when (event.kind) {
                Kind.RESUME -> {
                    val pkg = event.pkg ?: continue
                    if (pkg in closed) { closed.remove(pkg); continue }
                    return pkg to event.time.coerceAtMost(end)
                }
                Kind.PAUSE -> event.pkg?.let { closed.add(it) }
                Kind.SCREEN_OFF, Kind.SHUTDOWN -> return null
                Kind.SCREEN_ON -> Unit
            }
        }
        return null
    }

    /** Events before start establish state but never count as an open inside the range. */
    fun intervals(events: List<Event>, start: Long, end: Long): List<Interval> {
        if (end <= start) return emptyList()
        val result = ArrayList<Interval>()
        var pkg: String? = null
        var since = 0L
        var interactive = true
        fun close(time: Long) {
            val current = pkg ?: return
            val from = maxOf(start, since)
            val to = minOf(end, time)
            if (to > from) result.add(Interval(current, from, to, since >= start))
            pkg = null
        }
        for (event in events.sortedBy { it.time }) {
            if (event.time >= end) break
            when (event.kind) {
                Kind.RESUME -> if (event.pkg != null && interactive && event.pkg != pkg) {
                    close(event.time); pkg = event.pkg; since = event.time
                }
                Kind.PAUSE -> if (event.pkg == pkg) close(event.time)
                Kind.SCREEN_OFF, Kind.SHUTDOWN -> { close(event.time); interactive = false }
                Kind.SCREEN_ON -> interactive = true
            }
        }
        close(end)
        return result
    }

    // Local scroll data has day precision, so partial-day ranges include that day's counters.
    fun aggregate(events: List<Event>, start: Long, end: Long,
        scroll: Map<String, *> = emptyMap<String, Int>(),
        zone: TimeZone = TimeZone.getDefault()): Map<String, Totals> {
        if (end <= start) return emptyMap()
        val out = linkedMapOf<String, Totals>()
        for (interval in intervals(events, start, end)) {
            val row = out.getOrPut(interval.pkg) { Totals() }
            val duration = interval.end - interval.start
            row.foregroundMs += duration
            row.longestMs = maxOf(row.longestMs, duration)
            if (interval.opened) row.opens++
        }
        val keys = days(start, end, zone).map { it.key }.toSet()
        for ((key, value) in scroll) {
            if (value !is Int || value <= 0) continue
            val parts = key.split('|')
            if (parts.size != 3 || parts[0] !in keys || parts[2] !in setOf("scroll", "replay")) continue
            val row = out.getOrPut(parts[1]) { Totals() }
            if (parts[2] == "scroll") row.scrollHits = saturatingAdd(row.scrollHits, value)
            else row.replays = saturatingAdd(row.replays, value)
        }
        return out
    }

    fun nightMillis(events: List<Event>, start: Long, end: Long,
        zone: TimeZone = TimeZone.getDefault(), allowed: (String) -> Boolean = { true }): Long {
        val windows = days(start, end, zone).flatMap { day ->
            fun hour(value: Int) = Calendar.getInstance(zone).apply {
                timeInMillis = day.start; set(Calendar.HOUR_OF_DAY, value)
            }.timeInMillis
            listOf(day.start to hour(6), hour(22) to day.end)
        }
        return intervals(events, start, end).filter { allowed(it.pkg) }.sumOf { interval ->
            windows.sumOf { (from, to) -> (minOf(interval.end, to) - maxOf(interval.start, from)).coerceAtLeast(0) }
        }
    }

    fun saturatingAdd(a: Int, b: Int): Int = (a.toLong() + b).coerceAtMost(Int.MAX_VALUE.toLong()).toInt()
}
