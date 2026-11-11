allprojects {
    repositories {
        google()
        mavenCentral()
    }
}

val newBuildDir: Directory =
    rootProject.layout.buildDirectory
        .dir("../../build")
        .get()
rootProject.layout.buildDirectory.value(newBuildDir)

subprojects {
    val newSubprojectBuildDir: Directory = newBuildDir.dir(project.name)
    project.layout.buildDirectory.value(newSubprojectBuildDir)
}
subprojects {
    project.evaluationDependsOn(":app")
}

// Third-party Flutter plugin projects ship their own JVM unit tests (e.g.
// android_intent_plus' MethodCallHandlerImplTest) written against outdated test
// libraries that no longer compile. Those tests are not part of this app's test
// contract, so let the aggregate `testDebugUnitTest` task run only :app's tests.
subprojects {
    if (name != "app") {
        tasks.configureEach {
            if (this is Test || name.contains("UnitTest")) {
                enabled = false
            }
        }
    }
}

tasks.register<Delete>("clean") {
    delete(rootProject.layout.buildDirectory)
}
