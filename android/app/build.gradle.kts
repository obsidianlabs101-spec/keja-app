plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.keja.app"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.keja.app"
        minSdk = 24
        targetSdk = 34
        // CI sets GITHUB_RUN_NUMBER, so every build has a higher versionCode
        // than the last — that's what the in-app updater compares against.
        versionCode = (System.getenv("GITHUB_RUN_NUMBER")?.toIntOrNull() ?: 1)
        versionName = "1.0"
    }

    // One permanent signing key (kept in GitHub secrets, decoded by CI).
    // Without this, every CI build got a brand-new random debug key, and
    // Android refuses to install an update signed with a different key —
    // which is why every fix used to need an uninstall first.
    val kejaKeystore = System.getenv("KEJA_KEYSTORE_PATH")
    if (kejaKeystore != null) {
        signingConfigs {
            create("keja") {
                storeFile = file(kejaKeystore)
                storePassword = System.getenv("KEJA_KEYSTORE_PASSWORD")
                keyAlias = "keja"
                keyPassword = System.getenv("KEJA_KEYSTORE_PASSWORD")
            }
        }
    }

    buildTypes {
        debug {
            // The APK we publish is the "debug" variant; make sure it is NOT
            // debuggable, otherwise anyone with a cable can `adb run-as` into
            // the app's private storage (saved login token) or attach a debugger.
            isDebuggable = false
            if (kejaKeystore != null) signingConfig = signingConfigs.getByName("keja")
        }
        release {
            isMinifyEnabled = false
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
    buildFeatures {
        compose = true
    }
    composeOptions {
        kotlinCompilerExtensionVersion = "1.5.14"
    }
    packaging {
        resources {
            excludes += "/META-INF/{AL2.0,LGPL2.1}"
        }
    }
}

dependencies {
    implementation(platform("androidx.compose:compose-bom:2024.06.00"))
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    implementation("androidx.activity:activity-compose:1.9.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.2")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.2")
    implementation("androidx.navigation:navigation-compose:2.7.7")
    implementation("androidx.datastore:datastore-preferences:1.1.1")
    implementation("androidx.work:work-runtime-ktx:2.9.1")
    implementation("androidx.core:core-ktx:1.13.1")

    implementation("com.squareup.retrofit2:retrofit:2.11.0")
    implementation("com.squareup.retrofit2:converter-gson:2.11.0")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("com.squareup.okhttp3:logging-interceptor:4.12.0")

    implementation("io.coil-kt:coil-compose:2.6.0")

    debugImplementation("androidx.compose.ui:ui-tooling")
}
