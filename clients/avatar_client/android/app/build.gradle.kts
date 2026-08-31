plugins {
    id("com.android.application")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

android {
    namespace = "com.example.avatar_client"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        // TODO: Specify your own unique Application ID (https://developer.android.com/studio/build/application-id.html).
        applicationId = "com.example.avatar_client"
        // You can update the following values to match your application needs.
        // For more information, see: https://flutter.dev/to/review-gradle-config.
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    flavorDimensions += "avatar"
    productFlavors {
        create("base") {
            dimension = "avatar"
        }
        create("live2d") {
            dimension = "avatar"
        }
    }

    buildTypes {
        release {
            // TODO: Add your own signing config for the release build.
            // Signing with the debug keys for now, so `flutter run --release` works.
            signingConfig = signingConfigs.getByName("debug")
            // CubismCoreJNI resolves framework classes from JNI_OnLoad. Keep
            // release builds unshrunk until the SDK's complete R8 rules are
            // available; otherwise startup aborts with ClassNotFoundException.
            isMinifyEnabled = false
            isShrinkResources = false
        }
    }
}

dependencies {
    implementation("xyz.rementia:openwakeword:0.1.5")
    val live2dCore = file("../live2d_sdk/Core/android/Live2DCubismCore.aar")
    if (live2dCore.exists()) {
        add("live2dImplementation", files(live2dCore))
    }
    if (project.findProject(":live2d_framework") != null) {
        add("live2dImplementation", project(":live2d_framework"))
    }
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

flutter {
    source = "../.."
}
