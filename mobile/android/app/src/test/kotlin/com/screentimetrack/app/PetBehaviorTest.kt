package com.screentimetrack.app

import kotlin.random.Random
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class PetBehaviorTest {
    @Test fun moodThresholdsMatchFlutter() {
        assertEquals(PetMood.FRESH, PetBehavior.mood(61))
        assertEquals(PetMood.TIRED, PetBehavior.mood(60))
        assertEquals(PetMood.TIRED, PetBehavior.mood(30))
        assertEquals(PetMood.CRITICAL, PetBehavior.mood(29))
        assertEquals(PetMood.CRITICAL, PetBehavior.mood(0))
    }

    @Test fun sleepWinsOverEveryMoodAndBlocksActions() {
        for (pet in PetKind.entries) {
            for (mood in PetMood.entries) {
                assertEquals(PetClips.SLEEP, PetBehavior.baseClip(mood, resting = true, pet = pet))
                assertTrue(PetBehavior.weightsFor(mood, PetStage.REMAJA, pet).isNotEmpty())
                assertNull(PetBehavior.choose(mood, PetStage.REMAJA, resting = true, random = Random(1), pet = pet))
                assertNull(PetBehavior.tapClip(resting = true, pet = pet))
                assertNull(PetBehavior.pettingClip(resting = true, pet = pet))
                assertEquals(
                    PetBehavior.SLEEP_DELAY_MS,
                    PetBehavior.nextDelayMs(mood, PetStage.REMAJA, resting = true, random = Random(1), pet = pet),
                )
            }
        }
        assertTrue(PetBehavior.isRestingClip(PetClips.SLEEP))
        assertFalse(PetBehavior.isRestingClip(PetClips.IDLE_FRESH))
    }

    @Test fun momoClipCatalogKeepsItsDeliveredDurations() {
        assertEquals(8_000L, PetCatalog.durationMs(PetKind.MOMO, PetStage.BAYI, PetClips.IDLE_FRESH))
        assertEquals(8_000L, PetCatalog.durationMs(PetKind.MOMO, PetStage.DEWASA, PetClips.SLEEP))
        assertEquals(1_000L, PetCatalog.durationMs(PetKind.MOMO, PetStage.REMAJA, PetClips.TAP_REACTION))
        assertEquals(2_000L, PetCatalog.durationMs(PetKind.MOMO, PetStage.BAYI, PetClips.CELEBRATE))
        assertEquals(2_000L, PetCatalog.durationMs(PetKind.MOMO, PetStage.BAYI, PetClips.GREET))
        assertEquals(3_000L, PetCatalog.durationMs(PetKind.MOMO, PetStage.BAYI, PetClips.LOOK_AROUND))
        assertEquals(3_200L, PetCatalog.durationMs(PetKind.MOMO, PetStage.BAYI, PetClips.GROOM))
        assertEquals(2_600L, PetCatalog.durationMs(PetKind.MOMO, PetStage.BAYI, PetClips.STRETCH))
        assertEquals(1_200L, PetCatalog.durationMs(PetKind.MOMO, PetStage.BAYI, PetClips.WALK))
        assertEquals(2_000L, PetCatalog.durationMs(PetKind.MOMO, PetStage.BAYI, PetClips.PETTING))
    }

    @Test fun drakoDurationsMatchTheDartRegistryForEveryStage() {
        val expected = listOf(
            Triple(PetStage.BAYI, PetClips.IDLE_FRESH, 2_667L),
            Triple(PetStage.BAYI, "idle_fresh_a", 2_900L),
            Triple(PetStage.BAYI, PetClips.IDLE_CRITICAL, 1_467L),
            Triple(PetStage.BAYI, PetClips.WING_FLAP, 1_467L),
            Triple(PetStage.BAYI, PetClips.TAIL_WAG, 1_467L),
            Triple(PetStage.BAYI, PetClips.SLEEP, 4_333L),
            Triple(PetStage.BAYI, PetClips.GREET, 2_400L),
            Triple(PetStage.BAYI, PetClips.PETTING, 2_200L),
            Triple(PetStage.BAYI, PetClips.WALK, 1_400L),
            Triple(PetStage.BAYI, PetClips.WING_SHOW, 2_200L),
            Triple(PetStage.REMAJA, PetClips.IDLE_FRESH, 2_200L),
            Triple(PetStage.REMAJA, PetClips.SLEEP, 3_600L),
            Triple(PetStage.REMAJA, PetClips.WING_FLAP, 1_200L),
            Triple(PetStage.REMAJA, PetClips.WING_SHOW, 1_800L),
            Triple(PetStage.DEWASA, PetClips.IDLE_FRESH, 3_200L),
            Triple(PetStage.DEWASA, "idle_fresh_b", 3_400L),
            Triple(PetStage.DEWASA, PetClips.SLEEP, 4_200L),
            Triple(PetStage.DEWASA, PetClips.TAP_REACTION, 900L),
            Triple(PetStage.DEWASA, PetClips.WING_FLAP, 1_600L),
            Triple(PetStage.DEWASA, PetClips.WING_SHOW, 2_400L),
        )
        for ((stage, clip, ms) in expected) {
            assertEquals("$stage $clip", ms, PetCatalog.durationMs(PetKind.DRAKO, stage, clip))
        }
        // An unknown clip must not divide by zero or block the loop forever.
        assertEquals(2_000L, PetCatalog.durationMs(PetKind.DRAKO, PetStage.BAYI, "missing"))
    }

    @Test fun drakoShipsFourToFiveIdleVariantsPerMood() {
        assertEquals(5, PetCatalog.idleClips(PetMood.FRESH, PetKind.DRAKO).size)
        assertEquals(4, PetCatalog.idleClips(PetMood.TIRED, PetKind.DRAKO).size)
        assertEquals(4, PetCatalog.idleClips(PetMood.CRITICAL, PetKind.DRAKO).size)
        assertTrue(PetCatalog.hasIdleVariants(PetKind.DRAKO))
        assertFalse(PetCatalog.hasIdleVariants(PetKind.MOMO))
        // Momo keeps one loop per mood, exactly as before.
        for (mood in PetMood.entries) {
            assertEquals(1, PetCatalog.idleClips(mood, PetKind.MOMO).size)
        }
        assertTrue(PetBehavior.idleHoldMs(PetKind.MOMO) >= 0L)
        assertEquals(0L, PetBehavior.idleHoldMs(PetKind.MOMO, Random(3)))
        val hold = PetBehavior.idleHoldMs(PetKind.DRAKO, Random(3))
        assertTrue("hold $hold", hold in 6_000L..12_000L)
    }

    @Test fun tappedDrakoAlternatesReactionAndWingShow() {
        assertEquals(PetClips.TAP_REACTION, PetBehavior.tapClip(resting = false, tapCount = 0, pet = PetKind.DRAKO))
        assertEquals(PetClips.WING_SHOW, PetBehavior.tapClip(resting = false, tapCount = 1, pet = PetKind.DRAKO))
        assertEquals(PetClips.TAP_REACTION, PetBehavior.tapClip(resting = false, tapCount = 2, pet = PetKind.DRAKO))
        assertEquals(PetClips.TAP_REACTION, PetBehavior.tapClip(resting = false, tapCount = 9, pet = PetKind.MOMO))
    }

    @Test fun criticalOnlyUsesCalmActionsAndTiredNeverWalks() {
        assertEquals(setOf(PetClips.LOOK_AROUND, PetClips.GROOM),
            PetBehavior.weightsFor(PetMood.CRITICAL, PetStage.DEWASA, PetKind.MOMO).keys)
        assertEquals(setOf(PetClips.HEAD_LOOK, PetClips.TAIL_WAG),
            PetBehavior.weightsFor(PetMood.CRITICAL, PetStage.DEWASA, PetKind.DRAKO).keys)
        repeat(100) { seed ->
            assertNotEquals(PetClips.WALK,
                PetBehavior.choose(PetMood.TIRED, PetStage.entries[seed % 3], random = Random(seed)))
            assertNotEquals(PetClips.WALK,
                PetBehavior.choose(PetMood.TIRED, PetStage.entries[seed % 3], random = Random(seed), pet = PetKind.DRAKO))
        }
    }

    @Test fun freshAdolescentWalksMoreThanAdultAndBabyGroomsMore() {
        val remaja = PetBehavior.weightsFor(PetMood.FRESH, PetStage.REMAJA)
        val dewasa = PetBehavior.weightsFor(PetMood.FRESH, PetStage.DEWASA)
        val bayi = PetBehavior.weightsFor(PetMood.FRESH, PetStage.BAYI)
        assertTrue(remaja.getValue(PetClips.WALK) > dewasa.getValue(PetClips.WALK))
        assertTrue(bayi.getValue(PetClips.GROOM) >= remaja.getValue(PetClips.GROOM))
    }

    @Test fun drakoAdultShowsWingsMoreOftenThanBaby() {
        val bayi = PetBehavior.weightsFor(PetMood.FRESH, PetStage.BAYI, PetKind.DRAKO)
        val dewasa = PetBehavior.weightsFor(PetMood.FRESH, PetStage.DEWASA, PetKind.DRAKO)
        assertTrue(dewasa.getValue(PetClips.WING_SHOW) > bayi.getValue(PetClips.WING_SHOW))
        assertTrue(dewasa.getValue(PetClips.FIRE_PUFF) > bayi.getValue(PetClips.FIRE_PUFF))
        // Adolescence remains the wandering stage for Drako too.
        assertTrue(
            PetBehavior.weightsFor(PetMood.FRESH, PetStage.REMAJA, PetKind.DRAKO)
                .getValue(PetClips.WALK) >
                PetBehavior.weightsFor(PetMood.FRESH, PetStage.DEWASA, PetKind.DRAKO)
                    .getValue(PetClips.WALK),
        )
    }

    @Test fun antiRepeatSkipsPreviousWhenAlternativesExist() {
        for (pet in PetKind.entries) {
            for (mood in PetMood.entries) {
                repeat(40) { seed ->
                    assertNotEquals(PetClips.LOOK_AROUND,
                        PetBehavior.choose(mood, PetStage.REMAJA,
                            previous = PetClips.LOOK_AROUND, random = Random(seed), pet = pet))
                }
            }
        }
    }

    @Test fun delaysStayBoundedAndFollowMoodAndStage() {
        val random = Random(11)
        var fresh = 0L
        var critical = 0L
        var remaja = 0L
        var dewasa = 0L
        repeat(400) {
            val f = PetBehavior.nextDelayMs(PetMood.FRESH, PetStage.DEWASA, random = random)
            val c = PetBehavior.nextDelayMs(PetMood.CRITICAL, PetStage.DEWASA, random = random)
            val r = PetBehavior.nextDelayMs(PetMood.FRESH, PetStage.REMAJA, random = random)
            val d = PetBehavior.nextDelayMs(PetMood.FRESH, PetStage.DEWASA, random = random)
            for (delay in listOf(f, c, r, d)) {
                assertTrue("delay $delay", delay >= PetBehavior.MIN_DELAY_MS)
                assertTrue("delay $delay", delay <= PetBehavior.MAX_DELAY_MS)
            }
            fresh += f; critical += c; remaja += r; dewasa += d
        }
        assertTrue(critical > fresh)
        assertTrue(remaja < dewasa)
    }

    @Test fun drakoSchedulesFasterThanMomoOnTheSameSeed() {
        repeat(50) { seed ->
            val momo = PetBehavior.nextDelayMs(PetMood.FRESH, PetStage.BAYI, random = Random(seed), pet = PetKind.MOMO)
            val drako = PetBehavior.nextDelayMs(PetMood.FRESH, PetStage.BAYI, random = Random(seed), pet = PetKind.DRAKO)
            assertTrue("seed $seed", drako < momo)
        }
    }

    @Test fun unknownPetValuesFallBackToMomo() {
        assertEquals(PetKind.MOMO, PetKind.parse(null))
        assertEquals(PetKind.MOMO, PetKind.parse(""))
        assertEquals(PetKind.MOMO, PetKind.parse("momo"))
        assertEquals(PetKind.DRAKO, PetKind.parse("drako"))
        assertEquals(PetKind.MOMO, PetKind.parse("kucing"))
    }

    @Test fun animationPolicyStopsLoopsWhenHiddenOrStatic() {
        assertTrue(PetAnimationPolicy.shouldAnimate(
            alive = true, screenOn = true, hostForeground = false,
            panelOpen = false, fullMode = true))
        assertFalse(PetAnimationPolicy.shouldAnimate(
            alive = true, screenOn = true, hostForeground = false,
            panelOpen = false, fullMode = false))
        assertFalse(PetAnimationPolicy.shouldAnimate(
            alive = true, screenOn = true, hostForeground = true,
            panelOpen = false, fullMode = true))
        assertFalse(PetAnimationPolicy.shouldAnimate(
            alive = true, screenOn = false, hostForeground = false,
            panelOpen = false, fullMode = true))
        assertFalse(PetAnimationPolicy.shouldAnimate(
            alive = true, screenOn = true, hostForeground = false,
            panelOpen = true, fullMode = true))
        assertFalse(PetAnimationPolicy.shouldAnimate(
            alive = false, screenOn = true, hostForeground = false,
            panelOpen = false, fullMode = true))
    }

    @Test fun overlayClampKeepsWholeBodyInsideInsets() {
        val (x, y) = PetOverlayGeometry.clamp(
            x = -40, y = 2000, width = 160, height = 160,
            screenWidth = 450, screenHeight = 800, topInset = 24, bottomInset = 48)
        assertEquals(0, x)
        assertEquals(592, y)
        val (x2, y2) = PetOverlayGeometry.clamp(
            x = 999, y = -99, width = 160, height = 160,
            screenWidth = 450, screenHeight = 800, topInset = 24, bottomInset = 48)
        assertEquals(290, x2)
        assertEquals(24, y2)
    }

    @Test fun hpMirrorsFlutterPenaltyAndIgnoresNegativeBonus() {
        assertEquals(100, PetBehavior.hp(0, 0, 0))
        assertEquals(93, PetBehavior.hp(20, 100, 0))
        assertEquals(100, PetBehavior.hp(20, 100, 10))
        assertEquals(0, PetBehavior.hp(1_000, 10_000, 0))
        assertEquals(98, PetBehavior.hp(10, 0, -5))
        assertEquals(99, PetBehavior.hp(3, 1, 0))
    }

    @Test fun walkTravelIsHorizontalBoundedAndReversible() {
        val step = PetOverlayGeometry.step(
            x = 100, width = 160, screenWidth = 450, direction = 1, distance = 60)
        assertEquals(160, step.first)
        assertEquals(1, step.second)
        val edge = PetOverlayGeometry.step(
            x = 280, width = 160, screenWidth = 450, direction = 1, distance = 60)
        assertEquals(290, edge.first)
        assertEquals(-1, edge.second)
    }
}
