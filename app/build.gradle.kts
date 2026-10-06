plugins {
    id("com.android.application")
    id("com.chaquo.python")
}
dependencies { implementation("androidx.core:core:1.15.0") }
android {
    namespace="com.singularity.c4nursery"
    compileSdk=35
    defaultConfig {
        applicationId="com.singularity.c4nursery"
        minSdk=26
        targetSdk=35
        versionCode=43
        versionName="0.43-brain-boot"
        ndk { abiFilters += listOf("arm64-v8a") }
    }
}
chaquopy {
    defaultConfig {
        version = "3.13"
        pip { install("numpy") }
    }
}
