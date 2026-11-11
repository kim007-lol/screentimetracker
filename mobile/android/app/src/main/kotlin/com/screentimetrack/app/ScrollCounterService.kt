package com.screentimetrack.app

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.AccessibilityServiceInfo
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.view.accessibility.AccessibilityEvent
import java.lang.ref.WeakReference

/** Counts only scroll metadata. Never requests a node, text, window or content retrieval. */
class ScrollCounterService : AccessibilityService() {
    private val lastCountAt = HashMap<String, Long>()
    private var lastGeneration = -1L
    private val debounceMs = mapOf("com.instagram.android" to 600L,
        "com.zhiliaoapp.musically" to 700L, "com.ss.android.ugc.trill" to 700L,
        "com.google.android.youtube" to 600L, "com.facebook.katana" to 600L)

    override fun onServiceConnected() {
        super.onServiceConnected()
        instance = WeakReference(this)
        updateFilter()
    }

    private fun updateFilter() {
        lastCountAt.clear()
        lastGeneration = NativeStore.generation
        val info = serviceInfo ?: return
        // Scroll hits follow the apps the user chose to monitor (default:
        // Instagram, TikTok, YouTube, Facebook), matching the consent text.
        // Events are metadata only; the package is checked against that set.
        info.eventTypes = if (NativeStore.enabled(this)) {
            AccessibilityEvent.TYPE_VIEW_SCROLLED or AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED
        } else 0
        info.packageNames = null
        info.flags = info.flags and AccessibilityServiceInfo.FLAG_RETRIEVE_INTERACTIVE_WINDOWS.inv()
        serviceInfo = info
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        if (lastGeneration != NativeStore.generation) updateFilter()
        if (!NativeStore.enabled(this)) return
        when (event?.eventType) {
            // The pill names the app that is open now, so it must not wait for
            // the next 30 s tick after a switch.
            AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED -> {
                PillService.notifyStatsChanged(fresh = true)
                PetOverlayService.notifyStatsChanged()
            }
            AccessibilityEvent.TYPE_VIEW_SCROLLED -> {
                val pkg = event.packageName?.toString() ?: return
                if (pkg == packageName || !UsageRepo.isTracked(this, pkg)) return
                val now = SystemClock.elapsedRealtime()
                if (now - (lastCountAt[pkg] ?: Long.MIN_VALUE / 2) < (debounceMs[pkg] ?: 600L)) return
                lastCountAt[pkg] = now
                val backward = Build.VERSION.SDK_INT >= Build.VERSION_CODES.P && event.scrollDeltaY < 0
                NativeStore.recordScroll(this, pkg, backward, lastGeneration)
                PillService.notifyStatsChanged()
                PetOverlayService.notifyStatsChanged()
            }
        }
    }

    override fun onInterrupt() { lastCountAt.clear() }
    override fun onDestroy() {
        if (instance?.get() === this) instance = null
        lastCountAt.clear()
        super.onDestroy()
    }

    companion object {
        const val PREFS = UsageRepo.SCROLL_PREFS
        private var instance: WeakReference<ScrollCounterService>? = null
        fun dayKey(): String = UsageRepo.dayKey()
        fun refreshFilter() {
            Handler(Looper.getMainLooper()).post { instance?.get()?.updateFilter() }
        }
    }
}
