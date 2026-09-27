package com.keja.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.AdminPanelSettings
import androidx.compose.material.icons.outlined.ContentCopy
import androidx.compose.material.icons.outlined.DarkMode
import androidx.compose.material.icons.outlined.Home
import androidx.compose.material.icons.outlined.LightMode
import androidx.compose.material.icons.outlined.Logout
import androidx.compose.material.icons.outlined.Person
import androidx.compose.material.icons.outlined.Redeem
import androidx.compose.material.icons.outlined.SwapHoriz
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.keja.app.R
import com.keja.app.data.AppContainer
import com.keja.app.ui.components.Avatar
import com.keja.app.ui.components.KejaPrimaryButton
import com.keja.app.ui.components.KejaSecondaryButton
import com.keja.app.ui.theme.KejaShapes
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
    val clipboard = LocalClipboardManager.current
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
            .padding(horizontal = 18.dp, vertical = 16.dp),
    ) {
        if (user == null) {
            LoggedOutHero(isDarkNow = isDarkNow, onRequireLogin = onRequireLogin)
        } else {
            val u = user!!
            val roleLabel = if (u.is_admin) "Admin" else if (u.is_host) "Landlord" else "Renter"

            // ---- Identity hero: a gradient card the rest of the screen sits
            // under, so Profile reads as one designed surface rather than a
            // stack of generic settings rows.
            Box(
                Modifier
                    .fillMaxWidth()
                    .clip(KejaShapes.card)
                    .background(Brush.linearGradient(listOf(palette.primary, palette.coral)))
                    .padding(20.dp),
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        Modifier
                            .size(88.dp)
                            .clip(CircleShape)
                            .border(3.dp, Color.White.copy(alpha = 0.75f), CircleShape)
                            .padding(3.dp),
                    ) {
                        Avatar(url = u.profile_pic_url, name = u.name ?: u.username, size = 82.dp)
                    }
                    Spacer(Modifier.width(16.dp))
                    Column(Modifier.weight(1f)) {
                        Text(
                            u.name ?: u.username ?: "Keja user",
                            fontSize = 19.sp,
                            fontWeight = FontWeight.ExtraBold,
                            color = Color.White,
                        )
                        Spacer(Modifier.height(2.dp))
                        Text(
                            u.email ?: u.username ?: "",
                            fontSize = 12.sp,
                            color = Color.White.copy(alpha = 0.85f),
                        )
                        Spacer(Modifier.height(10.dp))
                        Box(
                            Modifier
                                .clip(KejaShapes.pill)
                                .background(Color.White.copy(alpha = 0.22f))
                                .padding(horizontal = 12.dp, vertical = 5.dp),
                        ) {
                            Text(roleLabel.uppercase(), fontSize = 10.sp, color = Color.White, fontWeight = FontWeight.ExtraBold)
                        }
                    }
                }
            }

            // ---- Quick stats: renter perks that already exist in the
            // account (free unlock credits, referral code) but had nowhere
            // to live before — surfacing them here makes the hero earn its
            // height rather than being purely decorative.
            if (!u.is_admin) {
                Spacer(Modifier.height(12.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    StatChip(
                        icon = Icons.Outlined.Redeem,
                        label = "Free unlocks",
                        value = "${u.free_contact_credits}",
                        modifier = Modifier.weight(1f),
                    )
                    if (!u.referral_code.isNullOrBlank()) {
                        StatChip(
                            icon = Icons.Outlined.ContentCopy,
                            label = "Referral code",
                            value = u.referral_code!!,
                            modifier = Modifier.weight(1f),
                            onClick = {
                                clipboard.setText(AnnotatedString(u.referral_code!!))
                                android.widget.Toast.makeText(context, "Referral code copied", android.widget.Toast.LENGTH_SHORT).show()
                            },
                        )
                    }
                }
            }

            Spacer(Modifier.height(24.dp))

            SectionLabel(if (u.is_admin) "Admin" else "Your workspace")
            Spacer(Modifier.height(10.dp))
            if (u.is_host || u.is_admin) {
                SettingRow(
                    icon = if (u.is_admin) Icons.Outlined.AdminPanelSettings else Icons.Outlined.Home,
                    title = if (u.is_admin) "Admin dashboard" else "Landlord dashboard",
                    subtitle = if (u.is_admin) "Platform management" else "Manage listings and activity",
                    actionLabel = "Open",
                    onClick = { if (u.is_admin) onOpenAdminDashboard() else onOpenLandlordDashboard() },
                )
            } else {
                SettingRow(
                    icon = Icons.Outlined.Home,
                    title = "Become a landlord",
                    subtitle = "List your own properties on Keja",
                    actionLabel = "Get started",
                    onClick = onOpenLandlordDashboard,
                )
            }

            Spacer(Modifier.height(22.dp))
            SectionLabel("Account")
            Spacer(Modifier.height(10.dp))
            SettingRow(
                icon = Icons.Outlined.Person,
                title = "Account",
                subtitle = "Signed in as ${u.email ?: u.username}",
                actionLabel = "Details",
                onClick = {},
            )
            Spacer(Modifier.height(10.dp))
            SettingRow(
                icon = Icons.Outlined.SwapHoriz,
                title = "Switch account",
                subtitle = "Log in as someone else without losing this session first",
                actionLabel = "Switch",
                onClick = onRequireLogin,
            )
            Spacer(Modifier.height(10.dp))
            SettingRow(
                icon = Icons.Outlined.Logout,
                title = "Log out",
                subtitle = "You can always sign back in",
                actionLabel = "Log out",
                danger = true,
                onClick = {
                    com.keja.app.data.notify.AlertsSync.cancel(context)
                    scope.launch { repo.logout(); onLoggedOut() }
                },
            )
            Spacer(Modifier.height(28.dp))
        }

        SectionLabel("Appearance")
        Spacer(Modifier.height(10.dp))

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

        Spacer(Modifier.height(10.dp))

        Row(
            Modifier
                .fillMaxWidth()
                .clip(KejaShapes.card)
                .background(palette.card)
                .padding(17.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                IconChip(if (isDarkNow) Icons.Outlined.DarkMode else Icons.Outlined.LightMode)
                Spacer(Modifier.width(12.dp))
                Column {
                    Text("Dark mode", fontWeight = FontWeight.Bold, color = palette.text)
                    Text("Same layout, easier on the eyes at night", fontSize = 12.sp, color = palette.muted)
                }
            }
            Switch(
                checked = isDarkNow,
                onCheckedChange = { checked -> scope.launch { sessionStore.setDarkOverride(checked) } },
                colors = SwitchDefaults.colors(checkedTrackColor = palette.primary),
            )
        }

        Spacer(Modifier.height(28.dp))

        // Small brand footer — a quiet signature rather than another action.
        Column(Modifier.fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally) {
            androidx.compose.foundation.Image(
                painter = painterResource(if (isDarkNow) R.drawable.keja_logo_white else R.drawable.keja_logo),
                contentDescription = "Keja",
                modifier = Modifier.height(20.dp).alpha(0.55f),
            )
            Spacer(Modifier.height(6.dp))
            Text("Find your next home in Kenya", fontSize = 11.sp, color = palette.muted)
        }

        Spacer(Modifier.height(16.dp))
    }
}

@Composable
private fun LoggedOutHero(isDarkNow: Boolean, onRequireLogin: () -> Unit) {
    val palette = LocalKejaPalette.current
    Column(
        Modifier
            .fillMaxWidth()
            .clip(KejaShapes.card)
            .background(palette.card)
            .padding(vertical = 44.dp, horizontal = 24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Box(
            Modifier
                .size(72.dp)
                .clip(CircleShape)
                .background(Brush.linearGradient(listOf(palette.primary, palette.coral))),
            contentAlignment = Alignment.Center,
        ) {
            androidx.compose.material3.Icon(Icons.Outlined.Person, contentDescription = null, tint = Color.White, modifier = Modifier.size(34.dp))
        }
        Spacer(Modifier.height(16.dp))
        Text("You're not signed in", fontSize = 17.sp, fontWeight = FontWeight.Bold, color = palette.text)
        Spacer(Modifier.height(4.dp))
        Text(
            "Log in to save properties, message landlords and manage your account.",
            fontSize = 13.sp,
            color = palette.muted,
            textAlign = androidx.compose.ui.text.style.TextAlign.Center,
        )
        Spacer(Modifier.height(18.dp))
        KejaPrimaryButton(text = "Log in", onClick = onRequireLogin, modifier = Modifier.fillMaxWidth(0.7f))
    }
}

@Composable
private fun SectionLabel(text: String) {
    val palette = LocalKejaPalette.current
    Text(text.uppercase(), fontSize = 11.sp, fontWeight = FontWeight.ExtraBold, color = palette.muted, letterSpacing = 0.8.sp)
}

@Composable
private fun IconChip(icon: ImageVector) {
    val palette = LocalKejaPalette.current
    Box(
        Modifier.size(40.dp).clip(CircleShape).background(palette.primaryLight),
        contentAlignment = Alignment.Center,
    ) {
        androidx.compose.material3.Icon(icon, contentDescription = null, tint = palette.primary, modifier = Modifier.size(20.dp))
    }
}

@Composable
private fun StatChip(icon: ImageVector, label: String, value: String, modifier: Modifier = Modifier, onClick: (() -> Unit)? = null) {
    val palette = LocalKejaPalette.current
    Column(
        modifier
            .clip(KejaShapes.card)
            .background(palette.card)
            .then(if (onClick != null) Modifier.clickable(onClick = onClick) else Modifier)
            .padding(14.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            androidx.compose.material3.Icon(icon, contentDescription = null, tint = palette.primary, modifier = Modifier.size(15.dp))
            Spacer(Modifier.width(6.dp))
            Text(label, fontSize = 11.sp, color = palette.muted, fontWeight = FontWeight.SemiBold)
        }
        Spacer(Modifier.height(4.dp))
        Text(value, fontSize = 16.sp, fontWeight = FontWeight.ExtraBold, color = palette.text)
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
            .clip(KejaShapes.card)
            .background(palette.card)
            .border(if (active) 2.dp else 1.dp, if (active) palette.primary else palette.border, KejaShapes.card)
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
private fun SettingRow(
    icon: ImageVector,
    title: String,
    subtitle: String,
    actionLabel: String,
    danger: Boolean = false,
    onClick: () -> Unit,
) {
    val palette = LocalKejaPalette.current
    val accent = if (danger) Color(0xFFEF4444) else palette.primary
    val accentBg = if (danger) Color(0xFFFEE2E2) else palette.primaryLight
    Row(
        Modifier
            .fillMaxWidth()
            .clip(KejaShapes.card)
            .background(palette.card)
            .padding(15.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Row(Modifier.weight(1f), verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.size(40.dp).clip(CircleShape).background(accentBg), contentAlignment = Alignment.Center) {
                androidx.compose.material3.Icon(icon, contentDescription = null, tint = accent, modifier = Modifier.size(20.dp))
            }
            Spacer(Modifier.width(12.dp))
            Column {
                Text(title, fontWeight = FontWeight.Bold, color = if (danger) accent else palette.text)
                Text(subtitle, fontSize = 12.sp, color = palette.muted)
            }
        }
        Spacer(Modifier.width(8.dp))
        KejaSecondaryButton(text = actionLabel, onClick = onClick)
    }
}
