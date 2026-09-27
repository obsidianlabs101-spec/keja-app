package com.keja.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.GridItemSpan
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.outlined.AutoAwesome
import androidx.compose.material.icons.outlined.Close
import androidx.compose.material.icons.outlined.Home
import androidx.compose.material.icons.outlined.Storefront
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.keja.app.data.AppContainer
import com.keja.app.data.model.Property
import com.keja.app.ui.components.PropertyCard
import com.keja.app.ui.theme.KejaShapes
import com.keja.app.ui.theme.LocalKejaPalette
import kotlinx.coroutines.launch

@Composable
fun HomeScreen(onOpenProperty: (String) -> Unit, onOpenAlerts: () -> Unit = {}) {
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
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                    Text("WELCOME BACK 👋", color = palette.primary, fontWeight = FontWeight.Bold, fontSize = 12.sp, letterSpacing = 0.6.sp)
                    com.keja.app.ui.components.AlertBell(onClick = onOpenAlerts)
                }
                Spacer(Modifier.height(8.dp))
                Text("Find a place\nyou'll love.", fontSize = 32.sp, fontWeight = FontWeight.ExtraBold, color = palette.text, lineHeight = 36.sp)
                Spacer(Modifier.height(8.dp))
                Text("Discover apartments, Airbnb stays and shops/commercial spaces in one place.", color = palette.muted, fontSize = 13.sp, lineHeight = 18.sp)
                Spacer(Modifier.height(20.dp))

                HomeSearchBar(
                    query = query,
                    onQueryChange = { query = it },
                    onSearch = { load(query.ifBlank { null }) },
                )

                Spacer(Modifier.height(22.dp))
                CategoryRow(selected = selectedCategory, onSelect = { selectedCategory = if (selectedCategory == it) null else it })
                Spacer(Modifier.height(18.dp))
                com.keja.app.ui.components.AdBanner(placement = "home")
                Spacer(Modifier.height(22.dp))
                Text("Recommended for you", fontSize = 19.sp, fontWeight = FontWeight.ExtraBold, color = palette.text)
                Spacer(Modifier.height(12.dp))
            }
        }

        if (loading) {
            item(span = { GridItemSpan(maxLineSpan) }) {
                Box(Modifier.fillMaxWidth().padding(30.dp), contentAlignment = Alignment.Center) {
                    com.keja.app.ui.components.KejaLoader()
                }
            }
        } else if (displayedProperties.isEmpty()) {
            item(span = { GridItemSpan(maxLineSpan) }) {
                EmptyHomeState(commercial = selectedCategory == "commercial")
            }
        } else {
            items(displayedProperties) { p ->
                PropertyCard(property = p, onClick = { onOpenProperty(p.id) })
            }
        }
    }
}

@Composable
private fun HomeSearchBar(query: String, onQueryChange: (String) -> Unit, onSearch: () -> Unit) {
    val palette = LocalKejaPalette.current
    Row(
        Modifier
            .fillMaxWidth()
            .shadow(elevation = 10.dp, shape = KejaShapes.pill, ambientColor = palette.primary.copy(alpha = 0.15f), spotColor = palette.primary.copy(alpha = 0.15f))
            .clip(KejaShapes.pill)
            .background(palette.card)
            .padding(6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            Modifier.size(40.dp).clip(CircleShape).background(palette.primaryLight),
            contentAlignment = Alignment.Center,
        ) {
            Icon(Icons.Filled.Search, contentDescription = null, tint = palette.primary, modifier = Modifier.size(19.dp))
        }
        Spacer(Modifier.width(4.dp))
        BasicTextFieldSearch(
            query = query,
            onQueryChange = onQueryChange,
            onSearch = onSearch,
            modifier = Modifier.weight(1f),
        )
        if (query.isNotEmpty()) {
            IconButton(onClick = { onQueryChange("") }, modifier = Modifier.size(36.dp)) {
                Icon(Icons.Outlined.Close, contentDescription = "Clear search", tint = palette.muted, modifier = Modifier.size(16.dp))
            }
            Spacer(Modifier.width(4.dp))
        }
    }
}

@Composable
private fun BasicTextFieldSearch(query: String, onQueryChange: (String) -> Unit, onSearch: () -> Unit, modifier: Modifier = Modifier) {
    val palette = LocalKejaPalette.current
    TextField(
        value = query,
        onValueChange = onQueryChange,
        placeholder = { Text("Search location, type or landmark", color = palette.muted, fontSize = 14.sp) },
        singleLine = true,
        textStyle = androidx.compose.ui.text.TextStyle(fontSize = 14.sp, color = palette.text),
        colors = TextFieldDefaults.colors(
            focusedContainerColor = Color.Transparent,
            unfocusedContainerColor = Color.Transparent,
            focusedIndicatorColor = Color.Transparent,
            unfocusedIndicatorColor = Color.Transparent,
            cursorColor = palette.primary,
        ),
        keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
        keyboardActions = KeyboardActions(onSearch = { onSearch() }),
        modifier = modifier,
    )
}

@Composable
private fun EmptyHomeState(commercial: Boolean) {
    val palette = LocalKejaPalette.current
    Column(
        Modifier
            .fillMaxWidth()
            .clip(KejaShapes.card)
            .background(palette.card)
            .padding(vertical = 36.dp, horizontal = 20.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Box(Modifier.size(56.dp).clip(CircleShape).background(palette.primaryLight), contentAlignment = Alignment.Center) {
            Icon(Icons.Outlined.Home, contentDescription = null, tint = palette.primary, modifier = Modifier.size(26.dp))
        }
        Spacer(Modifier.height(14.dp))
        Text(
            if (commercial) "No commercial listings yet" else "No listings yet",
            fontWeight = FontWeight.Bold,
            color = palette.text,
        )
        Spacer(Modifier.height(4.dp))
        Text(
            if (commercial) "Check back as landlords publish shops and offices." else "Be the first to list a property, or check back soon.",
            fontSize = 12.sp,
            color = palette.muted,
            textAlign = androidx.compose.ui.text.style.TextAlign.Center,
        )
    }
}

@Composable
private fun CategoryRow(selected: String?, onSelect: (String) -> Unit) {
    val categories = listOf(
        Triple("apartments", Icons.Outlined.Home, "Apartments"),
        Triple("airbnb", Icons.Outlined.AutoAwesome, "Airbnb"),
        Triple("commercial", Icons.Outlined.Storefront, "Shops"),
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
private fun CategorySquare(icon: ImageVector, label: String, active: Boolean, modifier: Modifier = Modifier, onClick: () -> Unit) {
    val palette = LocalKejaPalette.current
    Column(
        modifier
            .aspectRatio(1.05f)
            .shadow(if (active) 6.dp else 0.dp, KejaShapes.card, ambientColor = palette.primary.copy(alpha = 0.2f))
            .clip(KejaShapes.card)
            .background(if (active) palette.primary else palette.card)
            .border(1.dp, if (active) Color.Transparent else palette.border, KejaShapes.card)
            .clickable(onClick = onClick)
            .padding(10.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Box(
            Modifier.size(38.dp).clip(CircleShape).background(if (active) Color.White.copy(alpha = 0.22f) else palette.primaryLight),
            contentAlignment = Alignment.Center,
        ) {
            Icon(icon, contentDescription = null, tint = if (active) Color.White else palette.primary, modifier = Modifier.size(19.dp))
        }
        Spacer(Modifier.height(8.dp))
        Text(label, fontSize = 12.sp, fontWeight = FontWeight.Bold, color = if (active) Color.White else palette.text, maxLines = 1)
    }
}
