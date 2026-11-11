package com.screentimetrack.app

import kotlin.random.Random

/**
 * Native mirror of Dart's `PetBehavior`. The pill and roaming service live
 * outside Flutter, so the same state-aware rules must exist on both sides.
 * Nothing here touches HP, XP, or usage: it only picks a clip.
 */
enum class PetKind(val storageValue: String, val label: String) {
    MOMO("momo", "Momo"),
    DRAKO("drako", "Drako");

    companion object {
        /** An unknown or legacy value must never leave the overlay petless. */
        fun parse(value: String?): PetKind =
            entries.firstOrNull { it.storageValue == value } ?: MOMO
    }
}

enum class PetMood { FRESH, TIRED, CRITICAL }

enum class PetStage {
    BAYI, REMAJA, DEWASA;

    companion object {
        fun parse(value: String?): PetStage = when (value) {
            "remaja" -> REMAJA
            "dewasa" -> DEWASA
            else -> BAYI
        }
    }
}

/** Clip names exactly as the delivered GLBs spell them. */
object PetClips {
    const val IDLE_FRESH = "idle_fresh"
    const val IDLE_TIRED = "idle_tired"
    const val IDLE_CRITICAL = "idle_critical"
    const val SLEEP = "sleep"
    const val TAP_REACTION = "tap_reaction"
    const val CELEBRATE = "celebrate"
    const val GREET = "greet"
    const val LOOK_AROUND = "look_around"
    const val GROOM = "groom"
    const val STRETCH = "stretch"
    const val WALK = "walk"
    const val PETTING = "petting"
    const val WING_FLAP = "wing_flap"
    const val TAIL_WAG = "tail_wag"
    const val HEAD_LOOK = "head_look"
    const val FIRE_PUFF = "fire_puff"
    const val HAPPY_BOUNCE = "happy_bounce"
    const val WING_SHOW = "wing_show"
}

/** Everything the native overlay needs to know about one companion family. */
object PetCatalog {
    /** Momo ships one idle loop per mood; Drako ships four to five variants. */
    private val MOMO_IDLE = mapOf(
        PetMood.FRESH to listOf(PetClips.IDLE_FRESH),
        PetMood.TIRED to listOf(PetClips.IDLE_TIRED),
        PetMood.CRITICAL to listOf(PetClips.IDLE_CRITICAL),
    )
    private val DRAKO_IDLE = mapOf(
        PetMood.FRESH to listOf(
            PetClips.IDLE_FRESH,
            "idle_fresh_a",
            "idle_fresh_b",
            "idle_fresh_c",
            "idle_fresh_d",
        ),
        PetMood.TIRED to listOf(
            PetClips.IDLE_TIRED,
            "idle_tired_a",
            "idle_tired_b",
            "idle_tired_c",
        ),
        PetMood.CRITICAL to listOf(
            PetClips.IDLE_CRITICAL,
            "idle_critical_a",
            "idle_critical_b",
            "idle_critical_c",
        ),
    )

    private val MOMO_DURATIONS = mapOf(
        PetClips.IDLE_FRESH to 8_000L,
        PetClips.IDLE_TIRED to 8_000L,
        PetClips.IDLE_CRITICAL to 3_000L,
        PetClips.SLEEP to 8_000L,
        PetClips.TAP_REACTION to 1_000L,
        PetClips.CELEBRATE to 2_000L,
        PetClips.GREET to 2_000L,
        PetClips.LOOK_AROUND to 3_000L,
        PetClips.GROOM to 3_200L,
        PetClips.STRETCH to 2_600L,
        PetClips.WALK to 1_200L,
        PetClips.PETTING to 2_000L,
    )

    private val DRAKO_BAYI_DURATIONS = mapOf(
        PetClips.IDLE_FRESH to 2_667L,
        "idle_fresh_a" to 2_900L,
        "idle_fresh_b" to 2_900L,
        "idle_fresh_c" to 2_400L,
        "idle_fresh_d" to 2_900L,
        PetClips.IDLE_TIRED to 3_600L,
        "idle_tired_a" to 3_600L,
        "idle_tired_b" to 3_600L,
        "idle_tired_c" to 3_600L,
        PetClips.IDLE_CRITICAL to 1_467L,
        "idle_critical_a" to 1_467L,
        "idle_critical_b" to 1_467L,
        "idle_critical_c" to 1_467L,
        PetClips.SLEEP to 4_333L,
        PetClips.TAP_REACTION to 800L,
        PetClips.CELEBRATE to 1_800L,
        PetClips.WING_FLAP to 1_467L,
        PetClips.TAIL_WAG to 1_467L,
        PetClips.HEAD_LOOK to 1_933L,
        PetClips.FIRE_PUFF to 1_000L,
        PetClips.HAPPY_BOUNCE to 1_000L,
        PetClips.GREET to 2_400L,
        PetClips.PETTING to 2_200L,
        PetClips.WALK to 1_400L,
        PetClips.WING_SHOW to 2_200L,
    )

    private val DRAKO_REMAJA_DURATIONS = mapOf(
        PetClips.IDLE_FRESH to 2_200L,
        "idle_fresh_a" to 2_400L,
        "idle_fresh_b" to 2_400L,
        "idle_fresh_c" to 2_000L,
        "idle_fresh_d" to 2_400L,
        PetClips.IDLE_TIRED to 3_000L,
        "idle_tired_a" to 3_000L,
        "idle_tired_b" to 3_000L,
        "idle_tired_c" to 3_000L,
        PetClips.IDLE_CRITICAL to 1_200L,
        "idle_critical_a" to 1_200L,
        "idle_critical_b" to 1_200L,
        "idle_critical_c" to 1_200L,
        PetClips.SLEEP to 3_600L,
        PetClips.TAP_REACTION to 800L,
        PetClips.CELEBRATE to 1_800L,
        PetClips.WING_FLAP to 1_200L,
        PetClips.TAIL_WAG to 1_200L,
        PetClips.HEAD_LOOK to 1_600L,
        PetClips.FIRE_PUFF to 1_000L,
        PetClips.HAPPY_BOUNCE to 1_000L,
        PetClips.GREET to 2_000L,
        PetClips.PETTING to 2_000L,
        PetClips.WALK to 1_000L,
        PetClips.WING_SHOW to 1_800L,
    )

    private val DRAKO_DEWASA_DURATIONS = mapOf(
        PetClips.IDLE_FRESH to 3_200L,
        "idle_fresh_a" to 3_600L,
        "idle_fresh_b" to 3_400L,
        "idle_fresh_c" to 2_800L,
        "idle_fresh_d" to 3_000L,
        PetClips.IDLE_TIRED to 3_800L,
        "idle_tired_a" to 4_000L,
        "idle_tired_b" to 3_600L,
        "idle_tired_c" to 3_800L,
        PetClips.IDLE_CRITICAL to 1_600L,
        "idle_critical_a" to 1_400L,
        "idle_critical_b" to 2_600L,
        "idle_critical_c" to 1_500L,
        PetClips.SLEEP to 4_200L,
        PetClips.TAP_REACTION to 900L,
        PetClips.CELEBRATE to 2_000L,
        PetClips.WING_FLAP to 1_600L,
        PetClips.TAIL_WAG to 1_600L,
        PetClips.HEAD_LOOK to 2_200L,
        PetClips.FIRE_PUFF to 1_100L,
        PetClips.HAPPY_BOUNCE to 1_100L,
        PetClips.GREET to 2_200L,
        PetClips.PETTING to 2_400L,
        PetClips.WALK to 1_600L,
        PetClips.WING_SHOW to 2_400L,
    )

    private val MOMO_TAP = listOf(PetClips.TAP_REACTION)
    private val DRAKO_TAP = listOf(PetClips.TAP_REACTION, PetClips.WING_SHOW)

    data class Camera(val orbit: String, val target: String)

    /** Bundled file name for one pet and stage, shared with the WebView server. */
    fun modelFile(pet: PetKind, stage: PetStage): String =
        "${pet.storageValue}_${when (stage) {
            PetStage.BAYI -> "bayi"
            PetStage.REMAJA -> "remaja"
            PetStage.DEWASA -> "dewasa"
        }}.glb"

    fun idleClips(mood: PetMood, pet: PetKind = PetKind.MOMO): List<String> =
        (if (pet == PetKind.DRAKO) DRAKO_IDLE else MOMO_IDLE).getValue(mood)

    fun durationMs(pet: PetKind, stage: PetStage, clip: String): Long = when (pet) {
        PetKind.MOMO -> MOMO_DURATIONS[clip]
        PetKind.DRAKO -> when (stage) {
            PetStage.BAYI -> DRAKO_BAYI_DURATIONS[clip]
            PetStage.REMAJA -> DRAKO_REMAJA_DURATIONS[clip]
            PetStage.DEWASA -> DRAKO_DEWASA_DURATIONS[clip]
        }
    } ?: 2_000L

    fun tapClips(pet: PetKind = PetKind.MOMO): List<String> =
        if (pet == PetKind.DRAKO) DRAKO_TAP else MOMO_TAP

    fun hasIdleVariants(pet: PetKind): Boolean = pet == PetKind.DRAKO

    /**
     * Framing verified against offline model-viewer renders. The pill shows a
     * head, the roaming window a full body; Drako's 25deg azimuth keeps the
     * wings and tail visible, and the radii come from pixel-measured renders
     * of the square window (its tighter horizontal aspect).
     */
    fun bodyCamera(pet: PetKind, stage: PetStage): Camera = when (pet) {
        PetKind.MOMO -> Camera("0deg 82deg 4.8m", "0m 0.02m 0m")
        PetKind.DRAKO -> when (stage) {
            PetStage.BAYI -> Camera("25deg 82deg 5.15m", "0m 0.55m 0m")
            PetStage.REMAJA -> Camera("25deg 82deg 5.2m", "0m 0.43m 0m")
            PetStage.DEWASA -> Camera("25deg 82deg 4.55m", "0m -0.06m 0m")
        }
    }

    fun headCamera(pet: PetKind, stage: PetStage): Camera = when (pet) {
        PetKind.MOMO -> Camera("0deg 82deg 3.4m", "0m 0.5m 0.1m")
        PetKind.DRAKO -> when (stage) {
            PetStage.BAYI -> Camera("0deg 82deg 3.2m", "0m 0.62m 0m")
            PetStage.REMAJA -> Camera("0deg 82deg 2.6m", "0m 0.68m 0m")
            PetStage.DEWASA -> Camera("0deg 82deg 1.8m", "0m 0.20m 0m")
        }
    }
}

object PetBehavior {
    const val MIN_DELAY_MS = 6_000L
    const val MAX_DELAY_MS = 60_000L
    const val SLEEP_DELAY_MS = 3_600_000L

    fun mood(hp: Int): PetMood = when {
        hp > 60 -> PetMood.FRESH
        hp >= 30 -> PetMood.TIRED
        else -> PetMood.CRITICAL
    }

    /** Mirrors Flutter's `computeHp`: 0.2/min + 0.03/scroll, plus today's bonus. */
    fun hp(totalMinutes: Int, totalScroll: Int, bonus: Int): Int {
        val penalty = Math.round(totalMinutes * 0.2 + totalScroll * 0.03).toInt()
        return (100 - penalty + bonus.coerceAtLeast(0)).coerceIn(0, 100)
    }

    fun baseClip(
        mood: PetMood,
        resting: Boolean = false,
        pet: PetKind = PetKind.MOMO,
    ): String = if (resting) PetClips.SLEEP else PetCatalog.idleClips(mood, pet).first()

    fun isRestingClip(clip: String?): Boolean = clip == PetClips.SLEEP

    fun weightsFor(
        mood: PetMood,
        stage: PetStage,
        pet: PetKind = PetKind.MOMO,
    ): Map<String, Double> = when (pet) {
        PetKind.MOMO -> momoWeights(mood, stage)
        PetKind.DRAKO -> drakoWeights(mood, stage)
    }

    private fun momoWeights(mood: PetMood, stage: PetStage): Map<String, Double> {
        val weights = when (mood) {
            PetMood.FRESH -> when (stage) {
                PetStage.BAYI -> linkedMapOf(
                    PetClips.GREET to 2.0, PetClips.LOOK_AROUND to 2.0,
                    PetClips.GROOM to 2.6, PetClips.STRETCH to 1.0,
                    PetClips.WALK to 1.2,
                )
                PetStage.REMAJA -> linkedMapOf(
                    PetClips.GREET to 2.0, PetClips.LOOK_AROUND to 2.0,
                    PetClips.GROOM to 1.2, PetClips.STRETCH to 1.5,
                    PetClips.WALK to 3.0,
                )
                PetStage.DEWASA -> linkedMapOf(
                    PetClips.GREET to 2.4, PetClips.LOOK_AROUND to 2.0,
                    PetClips.GROOM to 1.2, PetClips.STRETCH to 1.2,
                    PetClips.WALK to 1.0,
                )
            }
            PetMood.TIRED -> when (stage) {
                PetStage.BAYI -> linkedMapOf(
                    PetClips.GREET to 1.0, PetClips.LOOK_AROUND to 2.0,
                    PetClips.GROOM to 2.6, PetClips.STRETCH to 1.0,
                )
                PetStage.REMAJA -> linkedMapOf(
                    PetClips.GREET to 1.0, PetClips.LOOK_AROUND to 2.0,
                    PetClips.GROOM to 1.5, PetClips.STRETCH to 1.2,
                )
                PetStage.DEWASA -> linkedMapOf(
                    PetClips.GREET to 1.0, PetClips.LOOK_AROUND to 2.4,
                    PetClips.GROOM to 1.2, PetClips.STRETCH to 1.0,
                )
            }
            PetMood.CRITICAL -> linkedMapOf(
                PetClips.LOOK_AROUND to 2.0, PetClips.GROOM to 1.0,
            )
        }
        return weights
    }

    private fun drakoWeights(mood: PetMood, stage: PetStage): Map<String, Double> =
        when (mood) {
            PetMood.FRESH -> when (stage) {
                PetStage.BAYI -> linkedMapOf(
                    PetClips.GREET to 1.6, PetClips.HEAD_LOOK to 2.2,
                    PetClips.TAIL_WAG to 2.4, PetClips.HAPPY_BOUNCE to 2.2,
                    PetClips.FIRE_PUFF to 0.8, PetClips.WALK to 1.2,
                    PetClips.WING_FLAP to 1.0, PetClips.WING_SHOW to 0.25,
                )
                PetStage.REMAJA -> linkedMapOf(
                    PetClips.GREET to 1.8, PetClips.HEAD_LOOK to 2.0,
                    PetClips.TAIL_WAG to 1.8, PetClips.HAPPY_BOUNCE to 1.8,
                    PetClips.FIRE_PUFF to 1.4, PetClips.WALK to 3.0,
                    PetClips.WING_FLAP to 1.6, PetClips.WING_SHOW to 0.4,
                )
                PetStage.DEWASA -> linkedMapOf(
                    PetClips.GREET to 2.2, PetClips.HEAD_LOOK to 2.0,
                    PetClips.TAIL_WAG to 1.6, PetClips.HAPPY_BOUNCE to 0.8,
                    PetClips.FIRE_PUFF to 1.8, PetClips.WALK to 1.0,
                    PetClips.WING_FLAP to 1.0, PetClips.WING_SHOW to 0.8,
                )
            }
            PetMood.TIRED -> when (stage) {
                PetStage.BAYI -> linkedMapOf(
                    PetClips.GREET to 1.2, PetClips.HEAD_LOOK to 2.0,
                    PetClips.TAIL_WAG to 2.0, PetClips.HAPPY_BOUNCE to 1.2,
                    PetClips.FIRE_PUFF to 0.6, PetClips.WING_FLAP to 0.4,
                )
                PetStage.REMAJA -> linkedMapOf(
                    PetClips.GREET to 1.4, PetClips.HEAD_LOOK to 2.2,
                    PetClips.TAIL_WAG to 1.8, PetClips.HAPPY_BOUNCE to 1.0,
                    PetClips.FIRE_PUFF to 1.0, PetClips.WING_FLAP to 0.5,
                )
                PetStage.DEWASA -> linkedMapOf(
                    PetClips.GREET to 1.6, PetClips.HEAD_LOOK to 2.4,
                    PetClips.TAIL_WAG to 1.6, PetClips.HAPPY_BOUNCE to 0.6,
                    PetClips.FIRE_PUFF to 1.2, PetClips.WING_FLAP to 0.4,
                )
            }
            PetMood.CRITICAL -> linkedMapOf(
                PetClips.HEAD_LOOK to 2.0, PetClips.TAIL_WAG to 1.0,
            )
        }

    fun choose(
        mood: PetMood,
        stage: PetStage,
        resting: Boolean = false,
        previous: String? = null,
        random: Random = Random.Default,
        pet: PetKind = PetKind.MOMO,
    ): String? {
        if (resting) return null
        val weights = weightsFor(mood, stage, pet)
        if (weights.isEmpty()) return null
        val pool = if (previous != null && weights.size > 1 && weights.containsKey(previous)) {
            weights.filterKeys { it != previous }
        } else weights
        val total = pool.values.sum()
        if (total <= 0.0) return null
        var target = random.nextDouble() * total
        for ((clip, weight) in pool) {
            target -= weight
            if (target <= 0.0) return clip
        }
        return pool.keys.last()
    }

    /** Taps alternate through the family's clips; Drako shows its wings next. */
    fun tapClip(
        resting: Boolean,
        tapCount: Int = 0,
        pet: PetKind = PetKind.MOMO,
    ): String? {
        if (resting) return null
        val clips = PetCatalog.tapClips(pet)
        return clips[tapCount % clips.size]
    }

    fun pettingClip(resting: Boolean, pet: PetKind = PetKind.MOMO): String? =
        if (resting) null else PetClips.PETTING

    fun nextDelayMs(
        mood: PetMood,
        stage: PetStage,
        resting: Boolean = false,
        random: Random = Random.Default,
        pet: PetKind = PetKind.MOMO,
    ): Long {
        if (resting) return SLEEP_DELAY_MS
        val base = when (mood) {
            PetMood.FRESH -> 12.0
            PetMood.TIRED -> 20.0
            PetMood.CRITICAL -> 30.0
        }
        val stageFactor = when (stage) {
            PetStage.BAYI -> 1.0
            PetStage.REMAJA -> 0.8
            PetStage.DEWASA -> 1.15
        }
        // Drako's authored idles are shorter; it earns a livelier schedule.
        val familyFactor = if (pet == PetKind.DRAKO) 0.8 else 1.0
        val jitter = 0.6 + random.nextDouble() * 0.8
        return (base * stageFactor * familyFactor * jitter * 1000).toLong()
            .coerceIn(MIN_DELAY_MS, MAX_DELAY_MS)
    }

    /**
     * How long one idle variant stays before crossfading to the next. Momo
     * never switches (single clip). Drako keeps looping the current variant for
     * the whole hold, so the overlay never freezes between clips.
     */
    fun idleHoldMs(pet: PetKind, random: Random = Random.Default): Long =
        if (PetCatalog.hasIdleVariants(pet)) 6_000L + random.nextInt(6_001) else 0L
}

/** One place that decides whether any overlay loop may run. */
object PetAnimationPolicy {
    fun shouldAnimate(
        alive: Boolean,
        screenOn: Boolean,
        hostForeground: Boolean,
        panelOpen: Boolean,
        fullMode: Boolean,
    ): Boolean = alive && screenOn && !hostForeground && !panelOpen && fullMode
}

/** Pure screen math so window placement and walking are testable off-device. */
object PetOverlayGeometry {
    fun clamp(
        x: Int,
        y: Int,
        width: Int,
        height: Int,
        screenWidth: Int,
        screenHeight: Int,
        topInset: Int = 0,
        bottomInset: Int = 0,
    ): Pair<Int, Int> {
        val maxX = (screenWidth - width).coerceAtLeast(0)
        val minY = topInset.coerceAtLeast(0)
        val maxY = (screenHeight - bottomInset - height).coerceAtLeast(minY)
        return x.coerceIn(0, maxX) to y.coerceIn(minY, maxY)
    }

    /** Returns the next x and the direction after bouncing at a screen edge. */
    fun step(
        x: Int,
        width: Int,
        screenWidth: Int,
        direction: Int,
        distance: Int,
    ): Pair<Int, Int> {
        val dir = if (direction < 0) -1 else 1
        val maxX = (screenWidth - width).coerceAtLeast(0)
        val target = x + dir * distance
        return when {
            target >= maxX -> maxX to -1
            target <= 0 -> 0 to 1
            else -> target to dir
        }
    }
}
