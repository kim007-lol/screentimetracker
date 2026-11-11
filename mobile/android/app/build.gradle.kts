import java.util.Properties

plugins {
    id("com.android.application")
    id("kotlin-android")
    // The Flutter Gradle Plugin must follow Android and Kotlin.
    id("dev.flutter.flutter-gradle-plugin")
}

// Optional private android/key.properties. Environment values take precedence.
// Relative storeFile/ANDROID_KEYSTORE_PATH paths are resolved from android/.
val releaseKeys = Properties().apply {
    val propertiesFile = rootProject.file("key.properties")
    if (propertiesFile.isFile) propertiesFile.inputStream().use { load(it) }
}
fun signingValue(property: String, environment: String): String? =
    providers.environmentVariable(environment).orNull?.takeIf { it.isNotBlank() }
        ?: releaseKeys.getProperty(property)?.takeIf { it.isNotBlank() }

val releaseStorePath = signingValue("storeFile", "ANDROID_KEYSTORE_PATH")
val releaseStorePassword = signingValue("storePassword", "ANDROID_KEYSTORE_PASSWORD")
val releaseKeyAlias = signingValue("keyAlias", "ANDROID_KEY_ALIAS")
val releaseKeyPassword = signingValue("keyPassword", "ANDROID_KEY_PASSWORD")
val releaseSigningComplete = listOf(
    releaseStorePath, releaseStorePassword, releaseKeyAlias, releaseKeyPassword,
).all { it != null }

android {
    namespace = "com.screentimetrack.app"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = JavaVersion.VERSION_17.toString()
    }
    defaultConfig {
        applicationId = "com.screentimetrack.app"
        minSdk = 24
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }
    signingConfigs {
        if (releaseSigningComplete) {
            create("release") {
                storeFile = rootProject.file(releaseStorePath!!)
                storePassword = releaseStorePassword
                keyAlias = releaseKeyAlias
                keyPassword = releaseKeyPassword
            }
        }
    }
    buildTypes {
        release {
            // Never fall back to the debug key, even on a developer machine.
            signingConfig = signingConfigs.findByName("release")
        }
    }
}

val verifyReleaseSigning = tasks.register("verifyReleaseSigning") {
    doLast {
        check(releaseSigningComplete) {
            "Release signing is not configured. Provide private android/key.properties " +
                "(storeFile, storePassword, keyAlias, keyPassword), or set " +
                "ANDROID_KEYSTORE_PATH, ANDROID_KEYSTORE_PASSWORD, ANDROID_KEY_ALIAS, " +
                "ANDROID_KEY_PASSWORD. Debug builds do not require release credentials."
        }
        val keyFile = rootProject.file(releaseStorePath!!)
        check(keyFile.isFile) {
            "Release keystore not found. Check storeFile/ANDROID_KEYSTORE_PATH " +
                "(relative paths resolve from android/)."
        }
        check(keyFile.name != "debug.keystore" && releaseKeyAlias != "androiddebugkey") {
            "A debug keystore or androiddebugkey alias cannot sign a release. " +
                "Provide your private release signing key."
        }
    }
}
// Guard packaging/validation tasks, not configuration: debug and JVM tests work
// without secrets. This also catches bundleRelease and aggregate assemble tasks.
tasks.configureEach {
    if (name.contains("Release") && listOf("assemble", "bundle", "package", "validateSigning")
            .any { name.startsWith(it) }) {
        dependsOn(verifyReleaseSigning)
    }
}

dependencies {
    testImplementation("junit:junit:4.13.2")
}

flutter {
    source = "../.."
}
