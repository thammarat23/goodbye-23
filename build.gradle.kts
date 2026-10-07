// The Android Gradle plugin is declared in settings.gradle.kts and applied only
// by :app, so `-PcoreOnly` builds never need to download it.
plugins {
    id("org.jetbrains.kotlin.android") version "2.0.21" apply false
    id("org.jetbrains.kotlin.jvm") version "2.0.21" apply false
    id("org.jetbrains.kotlin.plugin.compose") version "2.0.21" apply false
}
