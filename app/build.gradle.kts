plugins {
    id("com.android.application")
    id("com.chaquo.python")
}
dependencies {
    implementation("androidx.core:core:1.15.0")
    implementation("androidx.webkit:webkit:1.17.1")
}
android {
    namespace="com.singularity.c4nursery"
    compileSdk=35
    signingConfigs.getByName("debug") {
        storeFile=rootProject.file("ci-signing/debug.keystore")
        storePassword="android"
        keyAlias="androiddebugkey"
        keyPassword="android"
    }
    defaultConfig {
        applicationId="com.singularity.c4nursery.world"
        minSdk=26
        targetSdk=35
        versionCode=71
        versionName="0.66.1-player-world"
        ndk { abiFilters += listOf("arm64-v8a") }
    }
}
chaquopy {
    defaultConfig {
        version = "3.13"
        pip { install("numpy") }
    }
}
