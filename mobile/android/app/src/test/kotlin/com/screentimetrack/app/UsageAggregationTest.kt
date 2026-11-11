package com.screentimetrack.app

import org.junit.Assert.*
import org.junit.Test
import java.util.Calendar
import java.util.TimeZone

class UsageAggregationTest {
    private val utc = TimeZone.getTimeZone("UTC")
    private fun at(day: Int, hour: Int = 0, zone: TimeZone = utc, month: Int = Calendar.MARCH): Long =
        Calendar.getInstance(zone).apply { clear(); set(2026, month, day, hour, 0) }.timeInMillis
    private fun event(time: Long, kind: UsageAggregation.Kind, pkg: String? = null) =
        UsageAggregation.Event(time, kind, pkg)

    @Test fun carriesForegroundFromLookbackWithoutCountingAnOpen() {
        val rows = UsageAggregation.aggregate(listOf(
            event(50, UsageAggregation.Kind.RESUME, "a"),
            event(150, UsageAggregation.Kind.PAUSE, "a")
        ), 100, 200)
        assertEquals(50L, rows.getValue("a").foregroundMs)
        assertEquals(0, rows.getValue("a").opens)
    }

    @Test fun endIsExclusiveAndDuplicateResumeDoesNotDoubleCount() {
        val rows = UsageAggregation.aggregate(listOf(
            event(100, UsageAggregation.Kind.RESUME, "a"),
            event(120, UsageAggregation.Kind.RESUME, "a"),
            event(200, UsageAggregation.Kind.RESUME, "b")
        ), 100, 200)
        assertEquals(100L, rows.getValue("a").foregroundMs)
        assertEquals(1, rows.getValue("a").opens)
        assertFalse(rows.containsKey("b"))
    }

    @Test fun screenOffAndShutdownCloseSessionsAndDoNotInventScreenOnUsage() {
        val rows = UsageAggregation.aggregate(listOf(
            event(50, UsageAggregation.Kind.RESUME, "a"),
            event(120, UsageAggregation.Kind.SCREEN_OFF),
            event(140, UsageAggregation.Kind.SCREEN_ON),
            event(160, UsageAggregation.Kind.RESUME, "a"),
            event(180, UsageAggregation.Kind.SHUTDOWN)
        ), 100, 200)
        assertEquals(40L, rows.getValue("a").foregroundMs)
        assertEquals(20L, rows.getValue("a").longestMs)
    }

    @Test fun switchingAppsClosesPreviousAndLatePauseCannotCloseNewApp() {
        val rows = UsageAggregation.aggregate(listOf(
            event(100, UsageAggregation.Kind.RESUME, "a"),
            event(140, UsageAggregation.Kind.RESUME, "b"),
            event(160, UsageAggregation.Kind.PAUSE, "a")
        ), 100, 200)
        assertEquals(40L, rows.getValue("a").foregroundMs)
        assertEquals(60L, rows.getValue("b").foregroundMs)
    }

    @Test fun scrollSumsOnlyIntersectingLocalDaysAndRetainsScrollOnlyPackage() {
        val counts = mapOf("20260301|a|scroll" to 3, "20260302|a|scroll" to 4,
            "20260303|a|scroll" to 90, "20260302|b|replay" to 2)
        val rows = UsageAggregation.aggregate(emptyList(), at(1), at(3), counts, utc)
        assertEquals(7, rows.getValue("a").scrollHits)
        assertEquals(2, rows.getValue("b").replays)
        assertEquals(0L, rows.getValue("a").foregroundMs)
    }

    @Test fun daysUseCalendarAcrossBothDstTransitions() {
        val ny = TimeZone.getTimeZone("America/New_York")
        val spring = UsageAggregation.days(at(8, zone = ny), at(10, zone = ny), ny)
        assertEquals(2, spring.size)
        assertEquals(23 * 3600000L, spring[0].end - spring[0].start)
        val fall = UsageAggregation.days(at(1, zone = ny, month = Calendar.NOVEMBER),
            at(3, zone = ny, month = Calendar.NOVEMBER), ny)
        assertEquals(25 * 3600000L, fall[0].end - fall[0].start)
    }

    @Test fun nightIsMeasuredOverlapWithinRequestedRange() {
        val events = listOf(event(at(1, 21), UsageAggregation.Kind.RESUME, "a"),
            event(at(2, 7), UsageAggregation.Kind.PAUSE, "a"))
        assertEquals(8 * 3600000L, UsageAggregation.nightMillis(events, at(1), at(3), utc))
        assertEquals(6 * 3600000L, UsageAggregation.nightMillis(events, at(2), at(3), utc))
    }

    @Test fun invalidRangesAreEmpty() {
        assertTrue(UsageAggregation.aggregate(emptyList(), 200, 100).isEmpty())
        assertTrue(UsageAggregation.days(100, 100).isEmpty())
    }

    @Test fun currentSessionKeepsLatestOpenAppAndItsStart() {
        val events = listOf(
            event(100, UsageAggregation.Kind.RESUME, "a"),
            event(140, UsageAggregation.Kind.RESUME, "b"),
            event(160, UsageAggregation.Kind.PAUSE, "a"),
        )
        assertEquals("b" to 140L, UsageAggregation.currentSession(events, 200))
    }

    @Test fun currentSessionEndsOnPauseOrScreenOff() {
        val paused = listOf(
            event(100, UsageAggregation.Kind.RESUME, "a"),
            event(180, UsageAggregation.Kind.PAUSE, "a"),
        )
        assertNull(UsageAggregation.currentSession(paused, 200))
        val asleep = listOf(
            event(100, UsageAggregation.Kind.RESUME, "a"),
            event(180, UsageAggregation.Kind.SCREEN_OFF),
        )
        assertNull(UsageAggregation.currentSession(asleep, 200))
    }

    @Test fun currentSessionIgnoresEventsAfterEnd() {
        val events = listOf(
            event(100, UsageAggregation.Kind.RESUME, "a"),
            event(260, UsageAggregation.Kind.PAUSE, "a"),
        )
        assertEquals("a" to 100L, UsageAggregation.currentSession(events, 200))
    }
}
