package com.keja.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
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
import com.keja.app.ui.theme.KejaThemeStyle
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
    val sessionStore = remember { AppContainer.sessionStore(context) }
    val scope = rememberCoroutineScope()
    val user by repo.currentUser.collectAsState()

    val currentStyle by sessionStore.themeStyleFlow.collectAsState(initial = KejaThemeStyle.PROFESSIONAL)
    val darkOverride by sessionStore.darkOverrideFlow.collectAsState(initial = null)
    val systemDark = androidx.compose.foundation.isSystemInDarkTheme()
    val isDarkNow = darkOverride ?: systemDark

    LaunchedEffect(Unit) {
        runCatching { repo.refreshMe() }
    }

    Column(
        Modifier
            .fillMaxSize()
            .background(palette.bg)
            .verticalScroll(rememberScrollState())
            .padding(22.dp),
    ) {
        if (user == null) {
            Box(Modifier.fillMaxWidth().padding(vertical = 40.dp), contentAlignment = Alignment.Center) {
                KejaSecondaryButton(text = "Log in", onClick = onRequireLogin)
            }
        } else {
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
                onClick = { scope.launch { repo.logout(); onLoggedOut() } },
            )
            Spacer(Modifier.height(10.dp))
            SettingRow(
                title = "Switch account",
                subtitle = "Log in as someone else without losing this session first",
                actionLabel = "Switch",
                onClick = onRequireLogin,
            )
            Spacer(Modifier.height(28.dp))
        }

        Text("Appearance", fontSize = 16.sp, fontWeight = FontWeight.Bold, color = palette.text)
        Spacer(Modifier.height(12.dp))

        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            ThemeStyleCard(
                label = "Professional",
                subtitle = "Calm, clean and business-like",
                active = currentStyle == KejaThemeStyle.PROFESSIONAL,
                swatchColors = listOf(Color(0xFF6C4DFF), Color(0xFF22C55E), Color(0xFFF59E0B)),
                onClick = { scope.launch { sessionStore.setThemeStyle(KejaThemeStyle.PROFESSIONAL) } },
                modifier = Modifier.weight(1f),
            )
            ThemeStyleCard(
                label = "Rangi",
                subtitle = "Bold, colourful and playful",
                active = currentStyle == KejaThemeStyle.RANGI,
                swatchColors = listOf(Color(0xFFFFCE4A), Color(0xFF35E1B0), Color(0xFFFF6B9A)),
                onClick = { scope.launch { sessionStore.setThemeStyle(KejaThemeStyle.RANGI) } },
                modifier = Modifier.weight(1f),
            )
        }

        Spacer(Modifier.height(12.dp))

        Row(
            Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(16.dp))
                .background(palette.card)
                .padding(17.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column {
                Text("Dark mode", fontWeight = FontWeight.Bold, color = palette.text)
                Text("Same layout, easier on the eyes at night", fontSize = 12.sp, color = palette.muted)
            }
            Switch(
                checked = isDarkNow,
                onCheckedChange = { checked -> scope.launch { sessionStore.setDarkOverride(checked) } },
                colors = SwitchDefaults.colors(checkedTrackColor = palette.primary),
            )
        }

        Spacer(Modifier.height(20.dp))
    }
}

@Composable
private fun ThemeStyleCard(
    label: String,
    subtitle: String,
    active: Boolean,
    swatchColors: List<Color>,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val palette = LocalKejaPalette.current
    Column(
        modifier
            .clip(RoundedCornerShape(16.dp))
            .background(palette.card)
            .border(if (active) 2.dp else 1.dp, if (active) palette.primary else palette.border, RoundedCornerShape(16.dp))
            .clickable(onClick = onClick)
            .padding(14.dp),
    ) {
        Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
            swatchColors.forEach { c ->
                Box(Modifier.size(14.dp).clip(CircleShape).background(c))
            }
        }
        Spacer(Modifier.height(10.dp))
        Text(label, fontWeight = FontWeight.Bold, fontSize = 13.sp, color = palette.text)
        Text(subtitle, fontSize = 10.sp, color = palette.muted, lineHeight = 13.sp)
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
