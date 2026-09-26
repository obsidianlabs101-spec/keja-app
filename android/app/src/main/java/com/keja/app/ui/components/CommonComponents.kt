package com.keja.app.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.collectAsState
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.keja.app.ui.theme.KejaShapes
import com.keja.app.ui.theme.LocalKejaPalette

@Composable
fun KejaPrimaryButton(
    text: String,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    onClick: () -> Unit,
) {
    val palette = LocalKejaPalette.current
    val isRangi = palette.style == com.keja.app.ui.theme.KejaThemeStyle.RANGI
    Button(
        onClick = onClick,
        enabled = enabled,
        shape = KejaShapes.button,
        colors = if (isRangi) {
            ButtonDefaults.buttonColors(containerColor = palette.text, contentColor = palette.bg, disabledContainerColor = palette.text.copy(alpha = 0.5f))
        } else {
            ButtonDefaults.buttonColors(containerColor = palette.primary, contentColor = Color.White, disabledContainerColor = palette.primary.copy(alpha = 0.5f))
        },
        border = if (isRangi) androidx.compose.foundation.BorderStroke(2.dp, palette.mint) else null,
        modifier = modifier.height(50.dp),
    ) {
        Text(text, fontWeight = FontWeight.Bold, fontSize = 15.sp)
    }
}

@Composable
fun KejaSecondaryButton(text: String, modifier: Modifier = Modifier, onClick: () -> Unit) {
    val palette = LocalKejaPalette.current
    OutlinedButton(
        onClick = onClick,
        shape = KejaShapes.pill,
        colors = ButtonDefaults.outlinedButtonColors(contentColor = palette.text),
        border = androidx.compose.foundation.BorderStroke(1.dp, palette.border),
        modifier = modifier,
    ) {
        Text(text, fontWeight = FontWeight.SemiBold, fontSize = 13.sp)
    }
}

@Composable
fun KejaTextField(
    value: String,
    onValueChange: (String) -> Unit,
    label: String,
    modifier: Modifier = Modifier,
    isPassword: Boolean = false,
    keyboardType: KeyboardType = KeyboardType.Text,
) {
    val palette = LocalKejaPalette.current
    Column(modifier) {
        Text(label, fontSize = 13.sp, fontWeight = FontWeight.SemiBold, color = palette.muted)
        Spacer(Modifier.height(6.dp))
        OutlinedTextField(
            value = value,
            onValueChange = onValueChange,
            singleLine = true,
            shape = KejaShapes.button,
            visualTransformation = if (isPassword) PasswordVisualTransformation() else VisualTransformation.None,
            keyboardOptions = KeyboardOptions(keyboardType = keyboardType),
            colors = OutlinedTextFieldDefaults.colors(
                focusedContainerColor = palette.card,
                unfocusedContainerColor = palette.card,
                focusedBorderColor = palette.primary,
                unfocusedBorderColor = palette.border,
            ),
            modifier = Modifier.fillMaxWidth(),
        )
    }
}

@Composable
fun KejaTopBar(
    title: String = "keja",
    avatarInitials: String,
    onAvatarClick: () -> Unit,
    showBell: Boolean = false,
    unreadCount: Int = 0,
    onBellClick: () -> Unit = {},
) {
    val palette = LocalKejaPalette.current
    Row(
        Modifier
            .fillMaxWidth()
            .background(palette.bg)
            .padding(horizontal = 22.dp, vertical = 16.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        androidx.compose.foundation.Image(
            painter = androidx.compose.ui.res.painterResource(
                if (palette.bg.luminance() < 0.5f) com.keja.app.R.drawable.keja_logo_white else com.keja.app.R.drawable.keja_logo,
            ),
            contentDescription = "Keja",
            modifier = Modifier.height(32.dp),
        )
        Row(verticalAlignment = Alignment.CenterVertically) {
            if (showBell) {
                Box(
                    Modifier
                        .padding(end = 10.dp)
                        .size(40.dp)
                        .clip(CircleShape)
                        .background(palette.card)
                        .clickable(onClick = onBellClick),
                    contentAlignment = Alignment.Center,
                ) {
                    Icon(Icons.Outlined.Notifications, contentDescription = "Alerts", tint = palette.text, modifier = Modifier.size(20.dp))
                    if (unreadCount > 0) {
                        Box(
                            Modifier
                                .align(Alignment.TopEnd)
                                .clip(CircleShape)
                                .background(Color(0xFFFF4D4F))
                                .padding(horizontal = 5.dp, vertical = 1.dp),
                        ) {
                            Text(if (unreadCount > 9) "9+" else "$unreadCount", color = Color.White, fontSize = 9.sp, fontWeight = FontWeight.Bold)
                        }
                    }
                }
            }
            Box(
                Modifier
                    .size(42.dp)
                    .clip(CircleShape)
                    .background(palette.primary)
                    .clickable(onClick = onAvatarClick),
                contentAlignment = Alignment.Center,
            ) {
                Text(avatarInitials, color = Color.White, fontWeight = FontWeight.Bold, fontSize = 14.sp)
            }
        }
    }
}

sealed class NavDestination(val route: String, val label: String) {
    object Home : NavDestination("home", "Home")
    object Discover : NavDestination("discover", "Discover")
    object Interested : NavDestination("interested", "Interested")
    object MyListings : NavDestination("my-listings", "My listings")
    object Profile : NavDestination("profile", "Profile")
    object AdminHome : NavDestination("admin-home", "Overview")
    object AdminNew : NavDestination("admin-new", "New")
    object AdminLandlords : NavDestination("admin-landlords", "Landlords")
    object AdminPayments : NavDestination("admin-payments", "Payments")
    object AdminListings : NavDestination("admin-listings", "Listings")
}

val renterNavItems = listOf(NavDestination.Home, NavDestination.Discover, NavDestination.Interested, NavDestination.Profile)
val landlordNavItems = listOf(NavDestination.Home, NavDestination.Discover, NavDestination.MyListings, NavDestination.Profile)
val adminNavItems = listOf(NavDestination.AdminHome, NavDestination.AdminNew, NavDestination.AdminLandlords, NavDestination.AdminPayments, NavDestination.AdminListings, NavDestination.Profile)

private fun iconFor(dest: NavDestination, active: Boolean) = when (dest) {
    NavDestination.Home -> if (active) Icons.Filled.Home else Icons.Outlined.Home
    NavDestination.Discover -> if (active) Icons.Filled.Search else Icons.Outlined.Search
    NavDestination.Interested -> if (active) Icons.Filled.Favorite else Icons.Outlined.FavoriteBorder
    NavDestination.MyListings -> if (active) Icons.Filled.List else Icons.Outlined.List
    NavDestination.Profile -> if (active) Icons.Filled.AccountCircle else Icons.Outlined.AccountCircle
    NavDestination.AdminHome -> if (active) Icons.Filled.Home else Icons.Outlined.Home
    NavDestination.AdminNew -> if (active) Icons.Filled.Star else Icons.Outlined.Star
    NavDestination.AdminLandlords -> if (active) Icons.Filled.Person else Icons.Outlined.Person
    NavDestination.AdminPayments -> if (active) Icons.Filled.CheckCircle else Icons.Outlined.CheckCircle
    NavDestination.AdminListings -> if (active) Icons.Filled.List else Icons.Outlined.List
}

@Composable
fun KejaBottomNav(currentRoute: String?, items: List<NavDestination>, badges: Map<String, Int> = emptyMap(), onNavigate: (String) -> Unit) {
    val palette = LocalKejaPalette.current
    Row(
        Modifier
            .fillMaxWidth()
            .background(palette.navBg)
            .border(width = if (palette.style == com.keja.app.ui.theme.KejaThemeStyle.RANGI) 0.dp else 1.dp, color = palette.border)
            .padding(vertical = 8.dp)
            .horizontalScroll(androidx.compose.foundation.rememberScrollState()),
        horizontalArrangement = if (items.size > 5) Arrangement.spacedBy(4.dp) else Arrangement.SpaceEvenly,
    ) {
        items.forEach { dest ->
            val active = currentRoute == dest.route
            val fg = if (active) palette.navActiveFg else palette.navInactive
            val count = badges[dest.route] ?: 0
            Box(
                modifier = Modifier
                    .clip(RoundedCornerShape(10.dp))
                    .background(if (active) palette.navActiveBg else Color.Transparent)
                    .clickable { onNavigate(dest.route) }
                    .padding(horizontal = 10.dp, vertical = 6.dp)
                    .widthIn(min = if (items.size > 5) 64.dp else 0.dp),
            ) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Icon(iconFor(dest, active), contentDescription = dest.label, tint = fg, modifier = Modifier.size(20.dp))
                    Spacer(Modifier.height(2.dp))
                    Text(dest.label, fontSize = 9.sp, color = fg, maxLines = 1)
                }
                if (count > 0) {
                    Box(
                        Modifier
                            .align(Alignment.TopEnd)
                            .clip(CircleShape)
                            .background(Color(0xFFFF4D4F))
                            .padding(horizontal = 5.dp, vertical = 1.dp),
                    ) {
                        Text(if (count > 9) "9+" else "$count", color = Color.White, fontSize = 9.sp, fontWeight = FontWeight.Bold)
                    }
                }
            }
        }
    }
}

/** The bell on Home: shows the count of unread Alerts (renters/landlords only —
 * hidden for admins, who have their own overview badges). */
@Composable
fun AlertBell(onClick: () -> Unit) {
    val palette = LocalKejaPalette.current
    val context = androidx.compose.ui.platform.LocalContext.current
    val repo = remember { com.keja.app.data.AppContainer.repository(context) }
    val user by repo.currentUser.collectAsState()
    var unread by remember { mutableStateOf(0) }

    LaunchedEffect(user?.id) {
        if (user == null || user?.is_admin == true) { unread = 0; return@LaunchedEffect }
        while (true) {
            unread = runCatching { repo.notifications() }.getOrNull()?.count { !it.read } ?: 0
            kotlinx.coroutines.delay(60000)
        }
    }
    if (user == null || user?.is_admin == true) return

    Box(
        Modifier
            .size(40.dp)
            .clip(CircleShape)
            .background(palette.card)
            .clickable(onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        Icon(Icons.Outlined.Notifications, contentDescription = "Alerts", tint = palette.text, modifier = Modifier.size(20.dp))
        if (unread > 0) {
            Box(
                Modifier
                    .align(Alignment.TopEnd)
                    .clip(CircleShape)
                    .background(Color(0xFFFF4D4F))
                    .padding(horizontal = 5.dp, vertical = 1.dp),
            ) {
                Text(if (unread > 9) "9+" else "$unread", color = Color.White, fontSize = 9.sp, fontWeight = FontWeight.Bold)
            }
        }
    }
}
