package com.keja.app.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
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
    Button(
        onClick = onClick,
        enabled = enabled,
        shape = KejaShapes.button,
        colors = ButtonDefaults.buttonColors(containerColor = palette.primary, contentColor = Color.White, disabledContainerColor = palette.primary.copy(alpha = 0.5f)),
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
        Text(buildString { append(title) }, fontSize = 24.sp, fontWeight = FontWeight.ExtraBold, color = palette.text)
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

sealed class NavDestination(val route: String, val label: String) {
    object Home : NavDestination("home", "Home")
    object Discover : NavDestination("discover", "Discover")
    object Interested : NavDestination("interested", "Interested")
    object Profile : NavDestination("profile", "Profile")
}

val bottomNavItems = listOf(NavDestination.Home, NavDestination.Discover, NavDestination.Interested, NavDestination.Profile)

@Composable
fun KejaBottomNav(currentRoute: String?, onNavigate: (String) -> Unit) {
    val palette = LocalKejaPalette.current
    Row(
        Modifier
            .fillMaxWidth()
            .background(palette.card)
            .border(width = 1.dp, color = palette.border)
            .padding(vertical = 8.dp),
        horizontalArrangement = Arrangement.SpaceEvenly,
    ) {
        bottomNavItems.forEach { dest ->
            val active = currentRoute == dest.route
            val icon = when (dest) {
                NavDestination.Home -> if (active) Icons.Filled.Home else Icons.Outlined.Home
                NavDestination.Discover -> if (active) Icons.Filled.Search else Icons.Outlined.Search
                NavDestination.Interested -> if (active) Icons.Filled.Favorite else Icons.Outlined.FavoriteBorder
                NavDestination.Profile -> if (active) Icons.Filled.AccountCircle else Icons.Outlined.AccountCircle
            }
            Column(
                horizontalAlignment = Alignment.CenterHorizontally,
                modifier = Modifier.clickable { onNavigate(dest.route) }.padding(6.dp),
            ) {
                Icon(icon, contentDescription = dest.label, tint = if (active) palette.primary else palette.muted, modifier = Modifier.size(20.dp))
                Spacer(Modifier.height(2.dp))
                Text(dest.label, fontSize = 9.sp, color = if (active) palette.primary else palette.muted)
            }
        }
    }
}
