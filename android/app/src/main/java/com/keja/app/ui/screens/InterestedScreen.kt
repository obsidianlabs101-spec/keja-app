package com.keja.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.keja.app.data.AppContainer
import com.keja.app.data.model.Property
import com.keja.app.ui.components.PropertyCard
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
        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text("♡", fontSize = 36.sp)
                Spacer(Modifier.height(10.dp))
                Text("Log in to see your saved places", fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(14.dp))
                Button(onClick = onRequireLogin) { Text("Log in") }
            }
        }
        return
    }

    Column(Modifier.fillMaxSize().background(palette.bg)) {
        Text(
            "Interested", fontSize = 24.sp, fontWeight = FontWeight.ExtraBold, color = palette.text,
            modifier = Modifier.padding(horizontal = 22.dp, vertical = 16.dp),
        )
        com.keja.app.ui.components.AdBanner(placement = "interested", modifier = Modifier.padding(horizontal = 18.dp))
        when {
            loading -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { com.keja.app.ui.components.KejaLoader() }
            properties.isEmpty() -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text("Nothing saved yet — swipe right on something you like in Discover.", color = palette.muted, modifier = Modifier.padding(30.dp))
            }
            else -> LazyVerticalGrid(
                columns = GridCells.Fixed(1),
                contentPadding = PaddingValues(horizontal = 18.dp),
                verticalArrangement = Arrangement.spacedBy(14.dp),
                horizontalArrangement = Arrangement.spacedBy(14.dp),
            ) {
                items(properties) { p -> PropertyCard(property = p, onClick = { onOpenProperty(p.id) }) }
            }
        }
    }
}
