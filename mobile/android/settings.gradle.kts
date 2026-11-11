pluginManagement {
    val flutterSdkPath =
        run {
            val propertiesFile = file("local.properties")
            val fromFile = if (propertiesFile.exists()) {
                val properties = java.util.Properties()
                propertiesFile.inputStream().use { properties.load(it) }
                properties.getProperty("flutter.sdk")
            } else null
            val fromEnvironment = System.getenv("FLUTTER_ROOT")
            require(fromFile != null || fromEnvironment != null) {
                "flutter.sdk not set in local.properties and FLUTTER_ROOT is absent"
            }
            fromFile ?: fromEnvironment!!
        }

    includeBuild("$flutterSdkPath/packages/flutter_tools/gradle")

    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

plugins {
    id("dev.flutter.flutter-plugin-loader") version "1.0.0"
    id("com.android.application") version "8.11.1" apply false
    id("org.jetbrains.kotlin.android") version "2.2.20" apply false
}

include(":app")
