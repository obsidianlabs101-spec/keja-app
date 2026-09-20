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
import com.keja.app.data.model.LandlordPropertiesResponse
import com.keja.app.ui.components.PropertyCard
import com.keja.app.ui.theme.LocalKejaPalette

@Composable
fun LandlordProfileScreen(landlordId: String, onBack: () -> Unit, onOpenProperty: (String) -> Unit) {
    val palette = LocalKejaPalette.current
    val context = LocalContext.current
    val repo = remember { AppContainer.repository(context) }

    var data by remember { mutableStateOf<LandlordPropertiesResponse?>(null) }
    var loading by remember { mutableStateOf(true) }

    LaunchedEffect(landlordId) {
        loading = true
        data = runCatching { repo.landlordProperties(landlordId) }.getOrNull()
        loading = false
    }

    Column(Modifier.fillMaxSize().background(palette.bg)) {
        Row(
            Modifier.fillMaxWidth().padding(20.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column {
                Text("LANDLORD", color = palette.primary, fontWeight = FontWeight.Bold, fontSize = 11.sp)
                Text(data?.landlord?.full_name ?: "Loading…", fontSize = 20.sp, fontWeight = FontWeight.ExtraBold, color = palette.text)
            }
            TextButton(onClick = onBack) { Text("Back") }
        }

        when {
            loading -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
            data == null || data!!.properties.isEmpty() -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text("No other listings from this landlord yet", color = palette.muted)
            }
            else -> LazyVerticalGrid(
                columns = GridCells.Fixed(2),
                contentPadding = PaddingValues(horizontal = 18.dp),
                verticalArrangement = Arrangement.spacedBy(14.dp),
                horizontalArrangement = Arrangement.spacedBy(14.dp),
            ) {
                items(data!!.properties) { p -> PropertyCard(property = p, onClick = { onOpenProperty(p.id) }) }
            }
        }
    }
}
