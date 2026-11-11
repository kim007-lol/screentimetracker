package com.screentimetrack.app

/**
 * The only data the native WebView renderer may load. Everything is read from
 * the APK's Flutter asset bundle; no server, file path, or URL comes from the
 * bridge, backup, or user input.
 */
object PetWebAssets {
    const val HOST = "pet.local"
    const val BASE_URL = "https://pet.local/"

    const val scriptAsset =
        "flutter_assets/packages/model_viewer_plus/assets/model-viewer.min.js"

    fun modelAsset(pet: PetKind, stage: PetStage): String =
        "flutter_assets/assets/3d/${PetCatalog.modelFile(pet, stage)}"

    data class Asset(val path: String, val mime: String)

    /** Exact-match allowlist; path traversal and unknown names are rejected. */
    fun assetFor(path: String?): Asset? {
        if (path == "/model-viewer.min.js") {
            return Asset(scriptAsset, "application/javascript")
        }
        val name = path?.removePrefix("/") ?: return null
        if (name.isEmpty() || name.contains('/') || name.contains("..")) return null
        for (pet in PetKind.entries) {
            for (stage in PetStage.entries) {
                if (name == PetCatalog.modelFile(pet, stage)) {
                    return Asset(modelAsset(pet, stage), "model/gltf-binary")
                }
            }
        }
        return null
    }

    /**
     * Mirrors the framing used by `Companion3D`: frontal full body, slight
     * exposure lift, 250 ms crossfade. [headFrame] narrows the camera to the
     * head for the compact pill; the page can switch at runtime through
     * `petFrame`. Drako's head and body presets differ per stage because its
     * adult silhouette and spread wings use a different volume. The page stays
     * transparent so the overlay window shows only the pet.
     */
    fun html(
        stage: PetStage,
        headFrame: Boolean = false,
        pet: PetKind = PetKind.MOMO,
    ): String {
        val model = "https://$HOST/${PetCatalog.modelFile(pet, stage)}"
        val head = PetCatalog.headCamera(pet, stage)
        val body = PetCatalog.bodyCamera(pet, stage)
        val start = if (headFrame) head else body
        return """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<style>
html,body{margin:0;padding:0;width:100%;height:100%;overflow:hidden;background:transparent}
#pet{width:100%;height:100%;background:transparent;--poster-color:transparent;outline:none}
</style>
<script type="module" src="https://$HOST/model-viewer.min.js"></script>
</head>
<body>
<model-viewer id="pet" src="$model"
  camera-orbit="${start.orbit}" camera-target="${start.target}" field-of-view="26deg"
  exposure="1.05" shadow-intensity="0.7" shadow-softness="0.8"
  animation-crossfade-duration="250" autoplay="false" animation-name="idle_fresh"
  camera-controls="false" disable-zoom disable-pan disable-tap
  interaction-prompt="none" touch-action="none"
  style="background:transparent;--poster-color:transparent">
</model-viewer>
<script>
(function(){
  var v=document.getElementById('pet');
  if(!v)return;
  var sent=false;
  function ready(){
    if(sent)return;
    sent=true;
    document.title='READY';
    try{PetBridge.postMessage('loaded')}catch(e){}
  }
  v.addEventListener('load',ready);
  setInterval(function(){if(v.loaded)ready()},120);
  window.petPlay=function(name,loop){
    if(!v||!name||!/^[a-z_]+$/.test(name))return;
    v.animationName=name;
    if(loop){v.play()}else{v.play({repetitions:1})}
  };
  window.petPause=function(){if(v){v.pause()}};
  // Compact head vs full body share one rig; only the camera moves.
  var frames={
    head:{orbit:'${head.orbit}',target:'${head.target}'},
    body:{orbit:'${body.orbit}',target:'${body.target}'}
  };
  window.petFrame=function(mode){
    if(!v)return;
    var f=frames[mode]||frames.body;
    v.setAttribute('camera-orbit',f.orbit);
    v.setAttribute('camera-target',f.target);
  };
})();
</script>
</body>
</html>
""".trimIndent()
    }
}
