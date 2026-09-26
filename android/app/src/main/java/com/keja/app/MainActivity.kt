package com.keja.app

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.content.Intent
import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.core.content.ContextCompat
import com.keja.app.data.AppContainer
import com.keja.app.data.notify.AlertNotifier
import com.keja.app.data.notify.AlertsSync
import com.keja.app.ui.nav.KejaNavGraph
import com.keja.app.ui.theme.KejaThemeStyle
import com.keja.app.ui.theme.KejaTheme
import kotlinx.coroutines.flow.first

class MainActivity : ComponentActivity() {

    companion object {
        const val EXTRA_OPEN_ROUTE = "open_route"
        const val ROUTE_ALERTS = "alerts"
    }

    // Set from a notification tap (see AlertNotifier) so the nav graph can
    // jump straight to Alerts, whether the app was closed or already open.
    private var pendingRoute by mutableStateOf<String?>(null)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        // Resize the content (not just pan) when the keyboard opens, so text
        // fields and buttons stay reachable instead of being covered.
        window.setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE)
        AlertNotifier.ensureChannel(this)
        pendingRoute = intent?.getStringExtra(EXTRA_OPEN_ROUTE)

        setContent {
            val context = this
            val repo = remember { AppContainer.repository(context) }
            val sessionStore = remember { AppContainer.sessionStore(context) }

            val notificationPermission = rememberLauncherForActivityResult(
                ActivityResultContracts.RequestPermission(),
            ) { /* If declined, alerts still work inside the app — just not in the tray. */ }

            // If a token was saved from a previous launch, restore the
            // user silently so the app opens already signed in — same
            // idea as the website's refreshCurrentUser() on boot.
            LaunchedEffect(Unit) {
                val token = sessionStore.tokenFlow.first()
                if (!token.isNullOrBlank()) {
                    runCatching { repo.refreshMe() }
                    AlertsSync.schedulePeriodic(context)
                    AlertsSync.checkNow(context)
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
                        ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
                    ) {
                        notificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
                    }
                }
            }

            val themeStyle by sessionStore.themeStyleFlow.collectAsState(initial = KejaThemeStyle.PROFESSIONAL)
            val darkOverride by sessionStore.darkOverrideFlow.collectAsState(initial = null)

            KejaTheme(themeStyle = themeStyle, darkOverride = darkOverride) {
                KejaNavGraph(
                    pendingRoute = pendingRoute,
                    onPendingRouteConsumed = { pendingRoute = null },
                    onRequestNotificationPermission = {
                        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
                            ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
                        ) {
                            notificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
                        }
                        AlertsSync.schedulePeriodic(context)
                        AlertsSync.checkNow(context)
                    },
                )
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        pendingRoute = intent.getStringExtra(EXTRA_OPEN_ROUTE)
    }
}
