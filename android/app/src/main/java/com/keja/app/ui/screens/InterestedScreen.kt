package com.keja.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.outlined.FavoriteBorder
import androidx.compose.material.icons.outlined.Person
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.keja.app.data.AppContainer
import com.keja.app.data.model.Property
import com.keja.app.ui.components.KejaPrimaryButton
import com.keja.app.ui.components.PropertyCard
import com.keja.app.ui.theme.KejaShapes
import com.keja.app.ui.theme.LocalKejaPalette
import kotlinx.coroutines.launch

@Composable
fun InterestedScreen(isLoggedIn: Boolean, onRequireLogin: () -> Unit, onOpenProperty: (String) -> Unit) {
    val palette = LocalKejaPalette.current
    val context = LocalContext.current
    val repo = remember { AppContainer.repository(context) }
    val scope = rememberCoroutineScope()

    var properties by remember { mutableStateOf<List<Property>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }

    LaunchedEffect(isLoggedIn) {
        if (isLoggedIn) {
            loading = true
            properties = runCatching { repo.interested() }.getOrDefault(emptyList())
            loading = false
        }
    }

    if (!isLoggedIn) {
        Box(Modifier.fillMaxSize().background(palette.bg), contentAlignment = Alignment.Center) {
            SavedPlacesEmptyState(
                icon = Icons.Outlined.Person,
                title = "Log in to see your saved places",
                subtitle = "Sign in to keep track of properties you're interested in.",
                actionLabel = "Log in",
                onAction = onRequireLogin,
            )
        }
        return
    }

    Column(Modifier.fillMaxSize().background(palette.bg)) {
        Column(Modifier.padding(horizontal = 22.dp, vertical = 16.dp)) {
            Text("YOUR SAVED PLACES", color = palette.primary, fontWeight = FontWeight.Bold, fontSize = 12.sp, letterSpacing = 0.6.sp)
            Spacer(Modifier.height(4.dp))
            Text("Interested", fontSize = 28.sp, fontWeight = FontWeight.ExtraBold, color = palette.text)
        }
        com.keja.app.ui.components.AdBanner(placement = "interested", modifier = Modifier.padding(horizontal = 18.dp))
        when {
            loading -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { com.keja.app.ui.components.KejaLoader() }
            properties.isEmpty() -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                SavedPlacesEmptyState(
                    icon = Icons.Outlined.FavoriteBorder,
                    title = "Nothing saved yet",
                    subtitle = "Swipe right on something you like in Discover to save it here.",
                )
            }
            else -> LazyVerticalGrid(
                columns = GridCells.Fixed(1),
                contentPadding = PaddingValues(start = 18.dp, end = 18.dp, top = 4.dp, bottom = 24.dp),
                verticalArrangement = Arrangement.spacedBy(14.dp),
                horizontalArrangement = Arrangement.spacedBy(14.dp),
            ) {
                items(properties) { p -> PropertyCard(property = p, onClick = { onOpenProperty(p.id) }) }
            }
        }
    }
}

@Composable
private fun SavedPlacesEmptyState(
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    title: String,
    subtitle: String,
    actionLabel: String? = null,
    onAction: (() -> Unit)? = null,
) {
    val palette = LocalKejaPalette.current
    com.keja.app.ui.components.KejaSurface(
        Modifier.fillMaxWidth(0.86f),
        contentPadding = PaddingValues(vertical = 36.dp, horizontal = 22.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Box(
            Modifier
                .size(60.dp)
                .clip(CircleShape)
                .background(Brush.linearGradient(listOf(palette.primary, palette.coral))),
            contentAlignment = Alignment.Center,
        ) {
            Icon(
                if (icon == Icons.Outlined.FavoriteBorder) Icons.Filled.Favorite else icon,
                contentDescription = null,
                tint = Color.White,
                modifier = Modifier.size(28.dp),
            )
        }
        Spacer(Modifier.height(16.dp))
        Text(title, fontWeight = FontWeight.Bold, fontSize = 16.sp, color = palette.text, textAlign = TextAlign.Center)
        Spacer(Modifier.height(4.dp))
        Text(subtitle, fontSize = 13.sp, color = palette.muted, textAlign = TextAlign.Center)
        if (actionLabel != null && onAction != null) {
            Spacer(Modifier.height(18.dp))
            KejaPrimaryButton(text = actionLabel, onClick = onAction, modifier = Modifier.fillMaxWidth(0.8f))
        }
    }
}
