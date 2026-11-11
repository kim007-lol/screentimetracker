package com.screentimetrack.app

import org.junit.Assert.*
import org.junit.Test

class NativePolicyTest {
    @Test fun limitIgnoresNormalCooldownAndRechecksSameApp() {
        assertEquals(PauseDecision.LIMIT, PauseDecision.decide(1000, false, 60, 60, 0, 99999))
        assertEquals(PauseDecision.NONE, PauseDecision.decide(1000, false, 60, 60, 1001, 0))
        assertEquals(PauseDecision.LIMIT, PauseDecision.decide(1001, false, 60, 60, 1001, 99999))
        assertEquals(PauseDecision.NONE, PauseDecision.decide(1000, false, 59, 60, 0, 0))
        assertEquals(PauseDecision.NORMAL, PauseDecision.decide(1000, true, 59, 60, 0, 0))
    }

    private fun backup() = mapOf<String, Any>("version" to 1,
        "scrollCounts" to mapOf("20260301|com.example.app|scroll" to 2),
        "monitoredPackages" to listOf("com.example.app"),
        "limits" to mapOf("com.example.app" to 60),
        "bankAllowances" to mapOf("20260301|com.example.app" to 10))

    @Test fun validBackupRoundTripsOnlyAllowedData() {
        assertEquals(backup(), NativeBackup.validate(backup()).toMap())
    }

    @Test fun rejectsRuntimeStateAndUnknownVersionBeforeReplacement() {
        assertThrows(IllegalArgumentException::class.java) {
            NativeBackup.validate(backup() + ("enabled" to true))
        }
        assertThrows(IllegalArgumentException::class.java) {
            NativeBackup.validate(backup() + ("version" to 2))
        }
    }

    @Test fun rejectsMalformedDatesNegativeCountersAndFractionalLimits() {
        for (bad in listOf(
            backup() + ("scrollCounts" to mapOf("20260230|com.example.app|scroll" to 1)),
            backup() + ("scrollCounts" to mapOf("20260301|com.example.app|scroll" to -1)),
            backup() + ("limits" to mapOf("com.example.app" to 2.5)),
            backup() + ("bankAllowances" to mapOf("20260301|com.example.app" to 481))
        )) assertThrows(IllegalArgumentException::class.java) { NativeBackup.validate(bad) }
    }
}
