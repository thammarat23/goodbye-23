pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
    plugins {
        id("com.android.application") version "8.7.3"
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
        maven("https://jitpack.io")
    }
}

rootProject.name = "jotdee"

include(":core")

// The Android app needs the Android SDK. Pass -PcoreOnly to build and test
// the pure-Kotlin core on a machine without it.
if (!providers.gradleProperty("coreOnly").isPresent) {
    include(":app")
}
