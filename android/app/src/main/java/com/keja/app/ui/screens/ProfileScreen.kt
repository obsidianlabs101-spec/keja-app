package com.keja.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.keja.app.data.AppContainer
import com.keja.app.ui.components.KejaSecondaryButton
import com.keja.app.ui.theme.LocalKejaPalette
import kotlinx.coroutines.launch

@Composable
fun ProfileScreen(
    onRequireLogin: () -> Unit,
    onOpenLandlordDashboard: () -> Unit,
    onOpenAdminDashboard: () -> Unit,
    onLoggedOut: () -> Unit,
) {
    val palette = LocalKejaPalette.current
    val context = LocalContext.current
    val repo = remember { AppContainer.repository(context) }
    val scope = rememberCoroutineScope()
    val user by repo.currentUser.collectAsState()

    LaunchedEffect(Unit) {
        runCatching { repo.refreshMe() }
    }

    Column(
        Modifier
            .fillMaxSize()
            .background(palette.bg)
            .padding(22.dp),
    ) {
        if (user == null) {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                KejaSecondaryButton(text = "Log in", onClick = onRequireLogin)
            }
            return@Column
        }
        val u = user!!
        val initials = (u.name ?: u.username ?: "K").trim().take(2).uppercase()
        val roleLabel = if (u.is_admin) "Admin" else if (u.is_host) "Landlord" else "Renter"

        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(
                Modifier.size(64.dp).clip(CircleShape).background(palette.primary),
                contentAlignment = Alignment.Center,
            ) { Text(initials, color = Color.White, fontSize = 22.sp, fontWeight = FontWeight.ExtraBold) }
            Spacer(Modifier.width(14.dp))
            Column {
                Text(u.name ?: u.username ?: "Keja user", fontSize = 18.sp, fontWeight = FontWeight.Bold, color = palette.text)
                Spacer(Modifier.height(4.dp))
                Box(Modifier.clip(RoundedCornerShape(999.dp)).background(palette.primaryLight).padding(horizontal = 10.dp, vertical = 4.dp)) {
                    Text(roleLabel, fontSize = 11.sp, color = palette.primary, fontWeight = FontWeight.Bold)
                }
            }
        }

        Spacer(Modifier.height(24.dp))

        if (u.is_host || u.is_admin) {
            SettingRow(
                title = if (u.is_admin) "Admin dashboard" else "Landlord dashboard",
                subtitle = if (u.is_admin) "Platform management" else "Manage listings and activity",
                actionLabel = "Open",
                onClick = { if (u.is_admin) onOpenAdminDashboard() else onOpenLandlordDashboard() },
            )
        } else {
            SettingRow(
                title = "Become a landlord",
                subtitle = "List your own properties on Keja",
                actionLabel = "Get started",
                onClick = onOpenLandlordDashboard,
            )
        }

        Spacer(Modifier.height(10.dp))
        SettingRow(
            title = "Account",
            subtitle = "Signed in as ${u.email ?: u.username}",
            actionLabel = "Log out",
            onClick = {
                scope.launch { repo.logout(); onLoggedOut() }
            },
        )
    }
}

@Composable
private fun SettingRow(title: String, subtitle: String, actionLabel: String, onClick: () -> Unit) {
    val palette = LocalKejaPalette.current
    Row(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(16.dp))
            .background(palette.card)
            .padding(17.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            Text(title, fontWeight = FontWeight.Bold, color = palette.text)
            Text(subtitle, fontSize = 12.sp, color = palette.muted)
        }
        KejaSecondaryButton(text = actionLabel, onClick = onClick)
    }
}
