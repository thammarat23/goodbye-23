plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

android {
    namespace = "app.jotdee.spike"
    compileSdk = 35

    defaultConfig {
        applicationId = "app.jotdee.spike"
        minSdk = 29
        targetSdk = 35
        versionCode = 1
        versionName = "0.1-spike"
    }

    // A fixed debug key, so each new APK from CI installs over the previous one
    // without uninstalling it first. It only signs this test app: the real app
    // gets its own private key that is never committed.
    signingConfigs {
        getByName("debug") {
            storeFile = file("spike-debug.keystore")
            storePassword = "android"
            keyAlias = "androiddebugkey"
            keyPassword = "android"
        }
    }

    buildFeatures {
        compose = true
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }
}

dependencies {
    implementation(project(":core"))

    implementation(platform("androidx.compose:compose-bom:2024.12.01"))
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.9.0")

    // Spike 1: Thai OCR on the device.
    implementation("cz.adaptech.tesseract4android:tesseract4android:4.7.0")
    // Spike 3: a bundled SQLite with FTS5, independent of the phone's SQLite version.
    implementation("androidx.sqlite:sqlite-bundled:2.5.0")
}
