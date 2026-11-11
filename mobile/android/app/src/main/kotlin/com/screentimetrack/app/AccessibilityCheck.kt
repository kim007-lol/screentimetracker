package com.screentimetrack.app

/**
 * Android stores accessibility services in either long or short ComponentName
 * form depending on the OEM/settings screen. Comparing only the long form made
 * Momo report its own working service as disabled.
 */
internal object AccessibilityCheck {
    fun isEnabled(
        masterEnabled: Boolean,
        rawSetting: String?,
        vararg expectedForms: String,
    ): Boolean {
        if (!masterEnabled || rawSetting.isNullOrBlank()) return false
        val entries = rawSetting.split(':').map { it.trim() }.filter { it.isNotEmpty() }
        return expectedForms.any { form ->
            form.isNotBlank() && entries.any { it.equals(form, ignoreCase = true) }
        }
    }
}
