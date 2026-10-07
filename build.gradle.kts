// Plugin versions live in settings.gradle.kts. Each module applies its own plugins,
// so the Kotlin Android plugin loads alongside the Android Gradle plugin in :app,
// and `-PcoreOnly` builds never need to download the Android plugin.
