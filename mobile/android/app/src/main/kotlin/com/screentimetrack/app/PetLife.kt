package com.screentimetrack.app

import android.os.Handler
import kotlin.random.Random

/**
 * State-aware scheduling shared by the full-mode pill and the roaming overlay.
 *
 * It owns only timers and clip choices; visibility, permission and HP checks
 * arrive through [allowed]/[mood]/[resting]. Sleep always wins. No callback can
 * start a clip after [dispose]. Walking asks the host to move its window for
 * the same two clip cycles, so the gait and the travel stay in sync.
 *
 * Momo loops one idle clip per mood. Drako has several idle variants per mood;
 * this scheduler mirrors the Flutter widget: play one variant, breathe for
 * 0.5-2.0 s, then choose a different one. Taps cycle the family's tap clips, so
 * every second Drako tap is its wing display.
 */
class PetLife(
    private val handler: Handler,
    private val renderer: PetWebRenderer,
    private val mood: () -> PetMood,
    private val stage: () -> PetStage,
    private val resting: () -> Boolean,
    private val allowed: () -> Boolean,
    private val pet: () -> PetKind = { PetKind.MOMO },
    private val freeze: () -> Boolean = { false },
    private val onWalk: ((Long) -> Unit)? = null,
    private val random: Random = Random.Default,
) {
    private companion object {
        const val GREET_DELAY_MS = 1_600L
        const val WALK_CYCLES = 2L
    }

    private var loaded = false
    private var destroyed = false
    private var oneShot = false
    private var currentBase: String? = null
    private var idleClip: String? = null
    private var idleMood: PetMood? = null
    private var idleIndex = -1
    private var tapCount = 0
    private var spontaneousQueued = false
    private var lastSpontaneous: String? = null
    private var greetingPending = true
    private var greetingQueued = false

    private val returnTask = Runnable { finishOneShot() }
    private val spontaneousTask = Runnable { runSpontaneous() }
    private val greetTask = Runnable { runGreeting() }
    private val idleTask = Runnable { runIdleStep() }

    fun onLoaded() {
        if (destroyed) return
        loaded = true
        sync()
    }

    /** Re-evaluate visibility, mood, and sleep after any state change. */
    fun sync() {
        if (destroyed) return
        if (!allowed()) {
            cancelTransient()
            currentBase = null
            // Hidden windows can drop their surface; a visible pill must keep
            // its last frame (the panel opens on top of a still pet).
            if (freeze()) renderer.hold() else renderer.pause()
            return
        }
        if (!loaded) return
        if (resting()) {
            cancelTransient()
            idleClip = null
            idleMood = null
            if (currentBase != PetClips.SLEEP) playLoop(PetClips.SLEEP)
            return
        }
        if (oneShot) return
        val family = pet()
        val clips = PetCatalog.idleClips(mood(), family)
        if (clips.size > 1) {
            // A phase flip or wake needs a fresh variant, not the old frame.
            if (idleClip == null || idleMood != mood()) startIdleCycle()
        } else {
            stopIdle()
            idleClip = null
            idleMood = mood()
            val base = clips.first()
            if (currentBase != base) playLoop(base)
        }
        ensureSpontaneous()
        maybeGreet()
    }

    fun onTap() {
        if (resting()) return
        val clip = PetBehavior.tapClip(
            resting = false, tapCount = tapCount, pet = pet(),
        ) ?: return
        tapCount++
        act(clip)
    }

    fun onPet() {
        val clip = PetBehavior.pettingClip(resting(), pet()) ?: return
        act(clip)
    }

    fun dispose() {
        destroyed = true
        cancelTransient()
        renderer.pause()
        loaded = false
    }

    /** A tap or pet may interrupt another one-shot; idle never blocks input. */
    private fun act(clip: String) {
        if (destroyed || !allowed() || !loaded) return
        playAction(clip)
    }

    private fun playLoop(clip: String) {
        currentBase = clip
        renderer.play(clip, looping = true)
    }

    private fun playAction(clip: String) {
        oneShot = true
        stopIdle()
        cancelSpontaneous()
        handler.removeCallbacks(returnTask)
        currentBase = clip
        val family = pet()
        val walking = clip == PetClips.WALK
        renderer.play(clip, looping = walking)
        val duration = if (walking) {
            val length = PetCatalog.durationMs(family, stage(), clip) * WALK_CYCLES
            onWalk?.invoke(length)
            length
        } else {
            PetCatalog.durationMs(family, stage(), clip)
        }
        handler.postDelayed(returnTask, duration)
    }

    private fun finishOneShot() {
        oneShot = false
        currentBase = null
        stopIdle()
        idleClip = null
        idleMood = null
        if (destroyed) return
        sync()
    }

    /** Play one idle variant on a loop, then crossfade to another after a hold. */
    private fun startIdleCycle() {
        stopIdle()
        idleMood = mood()
        runIdleStep()
    }

    private fun runIdleStep() {
        if (destroyed || !allowed() || resting() || oneShot) return
        val family = pet()
        val clips = PetCatalog.idleClips(mood(), family)
        if (clips.isEmpty()) return
        var index = random.nextInt(clips.size)
        if (clips.size > 1 && index == idleIndex) {
            index = (index + 1) % clips.size
        }
        idleIndex = index
        val clip = clips[index]
        idleClip = clip
        currentBase = clip
        // Loop the variant for the whole hold; never sit on a frozen frame.
        renderer.play(clip, looping = true)
        handler.removeCallbacks(idleTask)
        handler.postDelayed(idleTask, PetBehavior.idleHoldMs(family, random))
    }

    private fun ensureSpontaneous() {
        if (spontaneousQueued || destroyed || !allowed() || resting() || !loaded || oneShot) return
        spontaneousQueued = true
        handler.postDelayed(
            spontaneousTask,
            PetBehavior.nextDelayMs(
                mood(), stage(), resting = false, random = random, pet = pet(),
            ),
        )
    }

    private fun runSpontaneous() {
        spontaneousQueued = false
        if (destroyed || !allowed() || resting() || !loaded || oneShot) {
            ensureSpontaneous()
            return
        }
        val clip = PetBehavior.choose(
            mood(), stage(), resting = false, previous = lastSpontaneous,
            random = random, pet = pet(),
        ) ?: run {
            ensureSpontaneous()
            return
        }
        lastSpontaneous = clip
        playAction(clip)
    }

    private fun maybeGreet() {
        if (!greetingPending || greetingQueued || destroyed) return
        if (!allowed() || resting() || !loaded || oneShot) return
        greetingQueued = true
        handler.postDelayed(greetTask, GREET_DELAY_MS)
    }

    private fun runGreeting() {
        greetingQueued = false
        // A spontaneous action may be mid-flight; keep the greeting pending so
        // it still happens after that clip finishes.
        if (destroyed || !allowed() || resting() || !loaded || oneShot) return
        greetingPending = false
        playAction(PetClips.GREET)
    }

    private fun stopIdle() {
        handler.removeCallbacks(idleTask)
    }

    private fun cancelSpontaneous() {
        handler.removeCallbacks(spontaneousTask)
        spontaneousQueued = false
    }

    private fun cancelTransient() {
        handler.removeCallbacks(returnTask)
        handler.removeCallbacks(greetTask)
        stopIdle()
        cancelSpontaneous()
        greetingQueued = false
        oneShot = false
        // Drop the idle cursor too: a hidden window or a sleep beat must not
        // resume as if its variant timer were still armed.
        idleClip = null
        idleMood = null
    }
}
