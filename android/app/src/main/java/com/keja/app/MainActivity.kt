package com.keja.app

import android.os.Bundle
import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import com.keja.app.data.AppContainer
import com.keja.app.ui.nav.KejaNavGraph
import com.keja.app.ui.theme.KejaThemeStyle
import com.keja.app.ui.theme.KejaTheme
import kotlinx.coroutines.flow.first

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        // Resize the content (not just pan) when the keyboard opens, so text
        // fields and buttons stay reachable instead of being covered.
        window.setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE)
        setContent {
            val context = this
            val repo = remember { AppContainer.repository(context) }
            val sessionStore = remember { AppContainer.sessionStore(context) }

            // If a token was saved from a previous launch, restore the
            // user silently so the app opens already signed in — same
            // idea as the website's refreshCurrentUser() on boot.
            LaunchedEffect(Unit) {
                val token = sessionStore.tokenFlow.first()
                if (!token.isNullOrBlank()) {
                    runCatching { repo.refreshMe() }
                }
            }

            val themeStyle by sessionStore.themeStyleFlow.collectAsState(initial = KejaThemeStyle.PROFESSIONAL)
            val darkOverride by sessionStore.darkOverrideFlow.collectAsState(initial = null)

            KejaTheme(themeStyle = themeStyle, darkOverride = darkOverride) {
                KejaNavGraph()
            }
        }
    }
}
