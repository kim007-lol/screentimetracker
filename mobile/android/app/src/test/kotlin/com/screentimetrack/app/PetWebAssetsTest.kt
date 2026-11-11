package com.screentimetrack.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class PetWebAssetsTest {
    @Test fun bundledPathsMatchTheFlutterAssetLayout() {
        assertEquals(
            "flutter_assets/packages/model_viewer_plus/assets/model-viewer.min.js",
            PetWebAssets.scriptAsset,
        )
        assertEquals(
            "flutter_assets/assets/3d/momo_bayi.glb",
            PetWebAssets.modelAsset(PetKind.MOMO, PetStage.BAYI),
        )
        assertEquals(
            "flutter_assets/assets/3d/momo_remaja.glb",
            PetWebAssets.modelAsset(PetKind.MOMO, PetStage.REMAJA),
        )
        assertEquals(
            "flutter_assets/assets/3d/momo_dewasa.glb",
            PetWebAssets.modelAsset(PetKind.MOMO, PetStage.DEWASA),
        )
    }

    @Test fun everyCompanionAndStageResolvesToItsOwnModel() {
        for (pet in PetKind.entries) {
            for (stage in PetStage.entries) {
                val file = PetCatalog.modelFile(pet, stage)
                assertTrue("$pet $stage", file.startsWith(pet.storageValue))
                assertEquals(
                    "flutter_assets/assets/3d/$file",
                    PetWebAssets.assetFor("/$file")?.path,
                )
                assertEquals(
                    "model/gltf-binary",
                    PetWebAssets.assetFor("/$file")?.mime,
                )
            }
        }
        assertEquals("drako_bayi.glb", PetCatalog.modelFile(PetKind.DRAKO, PetStage.BAYI))
        assertEquals("drako_dewasa.glb", PetCatalog.modelFile(PetKind.DRAKO, PetStage.DEWASA))
    }

    @Test fun htmlPointsOnlyAtTheInterceptedLocalHost() {
        val html = PetWebAssets.html(PetStage.REMAJA)
        assertTrue(html.contains("https://pet.local/model-viewer.min.js"))
        assertTrue(html.contains("https://pet.local/momo_remaja.glb"))
        assertTrue(html.contains("id=\"pet\""))
        assertTrue(html.contains("animation-name=\"idle_fresh\""))
        assertTrue(html.contains("animation-crossfade-duration=\"250\""))
        assertTrue(html.contains("PetBridge.postMessage('loaded')"))
        assertFalse(html.contains("http://"))
        assertTrue(html.contains("background:transparent"))
        assertTrue(html.contains("camera-orbit=\"0deg 82deg 4.8m\""))
    }

    @Test fun drakoPagesUseTheirVisitedCameraPresets() {
        val babyBody = PetWebAssets.html(PetStage.BAYI, pet = PetKind.DRAKO)
        assertTrue(babyBody.contains("https://pet.local/drako_bayi.glb"))
        assertTrue(babyBody.contains("camera-orbit=\"25deg 82deg 5.15m\""))
        assertTrue(babyBody.contains("camera-target=\"0m 0.55m 0m\""))

        val adultBody = PetWebAssets.html(PetStage.DEWASA, pet = PetKind.DRAKO)
        assertTrue(adultBody.contains("https://pet.local/drako_dewasa.glb"))
        assertTrue(adultBody.contains("camera-orbit=\"25deg 82deg 4.55m\""))
        assertTrue(adultBody.contains("camera-target=\"0m -0.06m 0m\""))

        val adultHead = PetWebAssets.html(PetStage.DEWASA, headFrame = true, pet = PetKind.DRAKO)
        assertTrue(adultHead.contains("camera-orbit=\"0deg 82deg 1.8m\""))
        assertTrue(adultHead.contains("camera-target=\"0m 0.20m 0m\""))

        val teenHead = PetWebAssets.html(PetStage.REMAJA, headFrame = true, pet = PetKind.DRAKO)
        assertTrue(teenHead.contains("camera-orbit=\"0deg 82deg 2.6m\""))
        assertTrue(teenHead.contains("camera-target=\"0m 0.68m 0m\""))
    }

    @Test fun theCompactPillGetsHeadFramingAndARuntimeFrameSwitch() {
        val head = PetWebAssets.html(PetStage.BAYI, headFrame = true)
        assertTrue(head.contains("camera-orbit=\"0deg 82deg 3.4m\""))
        assertTrue(head.contains("camera-target=\"0m 0.5m 0.1m\""))
        assertTrue(head.contains("window.petFrame"))
        assertTrue(head.contains("'0deg 82deg 4.8m'"))
        assertFalse(head.contains("http://"))
    }

    @Test fun onlyKnownAssetPathsAreEverServed() {
        assertEquals(
            PetWebAssets.scriptAsset,
            PetWebAssets.assetFor("/model-viewer.min.js")?.path,
        )
        assertEquals("application/javascript", PetWebAssets.assetFor("/model-viewer.min.js")?.mime)
        assertEquals(
            PetWebAssets.modelAsset(PetKind.MOMO, PetStage.DEWASA),
            PetWebAssets.assetFor("/momo_dewasa.glb")?.path,
        )
        assertEquals("model/gltf-binary", PetWebAssets.assetFor("/momo_dewasa.glb")?.mime)
        assertNull(PetWebAssets.assetFor("/../secret"))
        assertNull(PetWebAssets.assetFor("/model-viewer.min.js/../momo_bayi.glb"))
        assertNull(PetWebAssets.assetFor("/other.glb"))
        assertNull(PetWebAssets.assetFor("/drako_bayi.glb/extra"))
        assertNull(PetWebAssets.assetFor(""))
        assertNull(PetWebAssets.assetFor(null))
    }
}
