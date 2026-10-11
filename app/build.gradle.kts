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
    defaultConfig {
        applicationId="com.singularity.c4nursery"
        minSdk=26
        targetSdk=35
        versionCode=69
        versionName="0.65.0-native-research"
        ndk { abiFilters += listOf("arm64-v8a") }
    }
}
chaquopy {
    defaultConfig {
        version = "3.13"
        pip { install("numpy") }
    }
}
