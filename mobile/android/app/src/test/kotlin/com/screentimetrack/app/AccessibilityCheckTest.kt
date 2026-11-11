package com.screentimetrack.app

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class AccessibilityCheckTest {
    private val longForm =
        "com.screentimetrack.app/" +
            "com.screentimetrack.app.ScrollCounterService"
    private val shortForm =
        "com.screentimetrack.app/.ScrollCounterService"

    @Test
    fun `service stored in short form counts as enabled`() {
        assertTrue(
            AccessibilityCheck.isEnabled(
                true,
                "com.other/.Svc:$shortForm",
                longForm,
                shortForm,
            ),
        )
    }

    @Test
    fun `service stored in long form still counts`() {
        assertTrue(
            AccessibilityCheck.isEnabled(true, longForm, longForm, shortForm),
        )
    }

    @Test
    fun `master accessibility toggle off always wins`() {
        assertFalse(
            AccessibilityCheck.isEnabled(false, longForm, longForm, shortForm),
        )
    }

    @Test
    fun `other services and missing values do not count`() {
        assertFalse(
            AccessibilityCheck.isEnabled(
                true,
                "com.other/.Svc",
                longForm,
                shortForm,
            ),
        )
        assertFalse(AccessibilityCheck.isEnabled(true, null, longForm, shortForm))
        assertFalse(AccessibilityCheck.isEnabled(true, "", longForm, shortForm))
    }

    @Test
    fun `component match is case insensitive`() {
        assertTrue(
            AccessibilityCheck.isEnabled(
                true,
                longForm.uppercase(),
                longForm,
                shortForm,
            ),
        )
    }
}
