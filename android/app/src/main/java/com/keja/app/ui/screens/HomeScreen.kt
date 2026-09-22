package com.keja.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.GridItemSpan
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.keja.app.data.AppContainer
import com.keja.app.data.model.Property
import com.keja.app.ui.components.PropertyCard
import com.keja.app.ui.theme.LocalKejaPalette
import kotlinx.coroutines.launch

@Composable
fun HomeScreen(onOpenProperty: (String) -> Unit) {
    val palette = LocalKejaPalette.current
    val context = LocalContext.current
    val repo = remember { AppContainer.repository(context) }
    val scope = rememberCoroutineScope()

    var query by remember { mutableStateOf("") }
    var properties by remember { mutableStateOf<List<Property>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }
    var selectedCategory by remember { mutableStateOf<String?>(null) }

    val displayedProperties = remember(properties, selectedCategory) {
        when (selectedCategory) {
            "airbnb" -> properties.filter { it.property_type == "Airbnb" }
            "apartments" -> properties.filter { it.property_type != "Airbnb" }
            "commercial" -> emptyList()
            else -> properties
        }
    }

    fun load(searchQuery: String? = null) {
        loading = true
        scope.launch {
            properties = runCatching { repo.listProperties(limit = 24, q = searchQuery) }.getOrDefault(emptyList())
            loading = false
        }
    }

    LaunchedEffect(Unit) { load() }

    LazyVerticalGrid(
        columns = GridCells.Fixed(1),
        contentPadding = PaddingValues(horizontal = 18.dp, vertical = 12.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
        horizontalArrangement = Arrangement.spacedBy(14.dp),
        modifier = Modifier.fillMaxSize().background(palette.bg),
    ) {
        item(span = { GridItemSpan(maxLineSpan) }) {
            Column {
                Text("WELCOME BACK 👋", color = palette.primary, fontWeight = FontWeight.Bold, fontSize = 12.sp)
                Spacer(Modifier.height(6.dp))
                Text("Find a place\nyou'll love.", fontSize = 30.sp, fontWeight = FontWeight.ExtraBold, color = palette.text, lineHeight = 34.sp)
                Spacer(Modifier.height(8.dp))
                Text("Discover apartments, Airbnb stays and shops/commercial spaces in one place.", color = palette.muted, fontSize = 13.sp)
                Spacer(Modifier.height(16.dp))

                Row(
                    Modifier
                        .fillMaxWidth()
                        .background(palette.card, RoundedCornerShape(17.dp))
                        .padding(6.dp),
                    verticalAlignment = androidx.compose.ui.Alignment.CenterVertically,
                ) {
                    Icon(Icons.Filled.Search, contentDescription = null, tint = palette.muted, modifier = Modifier.padding(start = 8.dp))
                    OutlinedTextField(
                        value = query,
                        onValueChange = { query = it },
                        placeholder = { Text("Search location, type or landmark") },
                        singleLine = true,
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedContainerColor = androidx.compose.ui.graphics.Color.Transparent,
                            unfocusedContainerColor = androidx.compose.ui.graphics.Color.Transparent,
                            focusedBorderColor = androidx.compose.ui.graphics.Color.Transparent,
                            unfocusedBorderColor = androidx.compose.ui.graphics.Color.Transparent,
                        ),
                        keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                        keyboardActions = KeyboardActions(onSearch = { load(query.ifBlank { null }) }),
                        modifier = Modifier.weight(1f),
                    )
                }
                Spacer(Modifier.height(22.dp))
                CategoryRow(selected = selectedCategory, onSelect = { selectedCategory = if (selectedCategory == it) null else it })
                Spacer(Modifier.height(22.dp))
                Text("Recommended for you", fontSize = 18.sp, fontWeight = FontWeight.Bold, color = palette.text)
                Spacer(Modifier.height(12.dp))
            }
        }

        if (loading) {
            item(span = { GridItemSpan(maxLineSpan) }) {
                Box(Modifier.fillMaxWidth().padding(30.dp), contentAlignment = androidx.compose.ui.Alignment.Center) {
                    CircularProgressIndicator(color = palette.primary)
                }
            }
        } else if (displayedProperties.isEmpty()) {
            item(span = { GridItemSpan(maxLineSpan) }) {
                Text(
                    if (selectedCategory == "commercial") "No commercial listings yet — check back as landlords publish them." else "No listings yet — be the first to list a property.",
                    color = palette.muted, modifier = Modifier.padding(20.dp),
                )
            }
        } else {
            items(displayedProperties) { p ->
                PropertyCard(property = p, onClick = { onOpenProperty(p.id) })
            }
        }
    }
}

@Composable
private fun CategoryRow(selected: String?, onSelect: (String) -> Unit) {
    val categories = listOf(
        Triple("apartments", "⌂", "Apartments"),
        Triple("airbnb", "✦", "Airbnb"),
        Triple("commercial", "▦", "Shops"),
    )
    Row(horizontalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.fillMaxWidth()) {
        categories.forEach { (key, icon, label) ->
            CategorySquare(
                icon = icon,
                label = label,
                active = selected == key,
                modifier = Modifier.weight(1f),
                onClick = { onSelect(key) },
            )
        }
    }
}

@Composable
private fun CategorySquare(icon: String, label: String, active: Boolean, modifier: Modifier = Modifier, onClick: () -> Unit) {
    val palette = LocalKejaPalette.current
    Column(
        modifier
            .aspectRatio(1f)
            .clip(RoundedCornerShape(16.dp))
            .background(if (active) palette.primaryLight else palette.card)
            .border(1.dp, if (active) palette.primary else palette.border, RoundedCornerShape(16.dp))
            .clickable(onClick = onClick)
            .padding(10.dp),
        horizontalAlignment = androidx.compose.ui.Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Text(icon, fontSize = 22.sp, color = if (active) palette.primary else palette.text)
        Spacer(Modifier.height(6.dp))
        Text(label, fontSize = 11.sp, fontWeight = FontWeight.SemiBold, color = if (active) palette.primary else palette.text, maxLines = 1)
    }
}
