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
import androidx.compose.material.icons.filled.NotificationsActive
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.outlined.AutoAwesome
import androidx.compose.material.icons.outlined.Close
import androidx.compose.material.icons.outlined.Home
import androidx.compose.material.icons.outlined.Storefront
import androidx.compose.material.icons.outlined.Apartment
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items as rowItems
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.keja.app.data.AppContainer
import com.keja.app.data.model.Property
import com.keja.app.ui.components.KejaPrimaryButton
import com.keja.app.ui.components.PropertyCard
import com.keja.app.ui.theme.KejaShapes
import com.keja.app.ui.theme.LocalKejaPalette
import kotlinx.coroutines.launch

/** Property types a landlord can pick as "commercial" (see AddPropertyForm).
 * Shared so Home's Shops filter and Discover both agree on what counts. */
val COMMERCIAL_TYPES = setOf("Shop", "Office", "Warehouse", "Commercial")

fun categoryOfType(type: String): String = when {
    type == "Airbnb" -> "airbnb"
    type == "Hostel" -> "hostels"
    type in COMMERCIAL_TYPES -> "commercial"
    else -> "apartments"
}

fun propertyCategoryOf(p: Property): String = categoryOfType(p.property_type)

@Composable
fun HomeScreen(onOpenProperty: (String) -> Unit, onOpenAlerts: () -> Unit = {}) {
    val palette = LocalKejaPalette.current
    val context = LocalContext.current
    val repo = remember { AppContainer.repository(context) }
    val sessionStore = remember { AppContainer.sessionStore(context) }
    val scope = rememberCoroutineScope()

    // ---- Exit-intent flow (system back button from Home) ----
    var skipExitPrompt by remember { mutableStateOf<Boolean?>(null) } // null = not loaded yet
    var exitDialogShownThisSession by rememberSaveable { mutableStateOf(false) }
    var showExitDialog by remember { mutableStateOf(false) }
    var showAlertPrefsDialog by remember { mutableStateOf(false) }
    LaunchedEffect(Unit) { skipExitPrompt = runCatching { sessionStore.skipExitPrompt() }.getOrDefault(false) }

    fun sayGoodbyeAndExit() {
        val lines = listOf(
            "Bye bye 👋 — your next home will still be here when you're back.",
            "Off you go! We'll keep the lights on for your next visit.",
            "See you soon — Keja will be right here waiting.",
        )
        android.widget.Toast.makeText(context, lines.random(), android.widget.Toast.LENGTH_SHORT).show()
        (context as? android.app.Activity)?.finish()
    }

    androidx.activity.compose.BackHandler(enabled = skipExitPrompt == false) {
        if (!exitDialogShownThisSession) {
            exitDialogShownThisSession = true
            showExitDialog = true
        } else {
            sayGoodbyeAndExit()
        }
    }

    if (showExitDialog) {
        ExitIntentDialog(
            onDismiss = { dontAskAgain ->
                showExitDialog = false
                if (dontAskAgain) {
                    skipExitPrompt = true
                    scope.launch { sessionStore.setSkipExitPrompt(true) }
                }
            },
            onAdjustNotifications = {
                showExitDialog = false
                showAlertPrefsDialog = true
            },
            onExitNow = { sayGoodbyeAndExit() },
        )
    }
    if (showAlertPrefsDialog) {
        AlertPreferencesDialog(onClose = { showAlertPrefsDialog = false })
    }

    var query by remember { mutableStateOf("") }
    var properties by remember { mutableStateOf<List<Property>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }
    var selectedCategory by remember { mutableStateOf<String?>(null) }
    var selectedListingType by remember { mutableStateOf<String?>(null) } // "rent" | "sale" | null (both)

    val displayedProperties = remember(properties, selectedCategory, selectedListingType) {
        properties
            .filter { selectedCategory == null || propertyCategoryOf(it) == selectedCategory }
            .filter { selectedListingType == null || it.listing_type == selectedListingType }
    }

    var counts by remember { mutableStateOf<Map<String, Int>>(emptyMap()) }
    LaunchedEffect(selectedListingType) {
        val byType = runCatching { repo.categoryCounts(selectedListingType) }.getOrDefault(emptyMap())
        val folded = mutableMapOf("apartments" to 0, "hostels" to 0, "airbnb" to 0, "commercial" to 0)
        byType.forEach { (t, n) ->
            val key = categoryOfType(t)
            folded[key] = (folded[key] ?: 0) + n
        }
        counts = folded
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
                Text("Apartments, hostels, Airbnb stays and shops — all in one place.", color = palette.muted, fontSize = 13.sp, lineHeight = 18.sp)
                Spacer(Modifier.height(20.dp))

                HomeSearchBar(
                    query = query,
                    onQueryChange = { query = it },
                    onSearch = { load(query.ifBlank { null }) },
                )

                Spacer(Modifier.height(14.dp))
                ListingTypePills(
                    selected = selectedListingType,
                    onSelect = { selectedListingType = if (it == "all" || selectedListingType == it) null else it },
                )
                Spacer(Modifier.height(18.dp))

                // ---- Fresh listings (sideways row) ----
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                    Text("Fresh listings", fontSize = 19.sp, fontWeight = FontWeight.ExtraBold, color = palette.text)
                }
                Spacer(Modifier.height(10.dp))
                if (loading) {
                    LazyRow(horizontalArrangement = Arrangement.spacedBy(12.dp), contentPadding = PaddingValues(end = 8.dp)) {
                        items(3) { com.keja.app.ui.components.SkeletonCard() }
                    }
                } else if (displayedProperties.isNotEmpty()) {
                    LazyRow(horizontalArrangement = Arrangement.spacedBy(12.dp), contentPadding = PaddingValues(end = 8.dp)) {
                        rowItems(displayedProperties.take(8)) { p ->
                            com.keja.app.ui.components.FreshCard(property = p, onClick = { onOpenProperty(p.id) })
                        }
                    }
                }
                Spacer(Modifier.height(18.dp))
                CategoryRow(
                    selected = selectedCategory,
                    counts = counts,
                    onSelect = { selectedCategory = if (selectedCategory == it) null else it },
                )
                Spacer(Modifier.height(18.dp))

                // ---- Popular areas ----
                Text("Popular areas", fontSize = 19.sp, fontWeight = FontWeight.ExtraBold, color = palette.text)
                Spacer(Modifier.height(10.dp))
                LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    rowItems(listOf("Kilimani", "Westlands", "Roysambu", "Lavington", "Kasarani", "Ruaka", "Juja")) { area ->
                        Box(
                            Modifier
                                .clip(KejaShapes.pill)
                                .background(palette.card)
                                .border(1.dp, palette.border, KejaShapes.pill)
                                .clickable { query = area; load(area) }
                                .padding(horizontal = 14.dp, vertical = 9.dp)
                        ) { Text(area, fontSize = 13.sp, fontWeight = FontWeight.Bold, color = palette.text) }
                    }
                }
                Spacer(Modifier.height(18.dp))
                com.keja.app.ui.components.AdBanner(placement = "home")
                Spacer(Modifier.height(22.dp))
                if (!loading && displayedProperties.size > 8) {
                    Text("Recommended for you", fontSize = 19.sp, fontWeight = FontWeight.ExtraBold, color = palette.text)
                    Spacer(Modifier.height(12.dp))
                }
            }
        }

        if (!loading && displayedProperties.isEmpty()) {
            item(span = { GridItemSpan(maxLineSpan) }) {
                EmptyHomeState(commercial = selectedCategory == "commercial", forSale = selectedListingType == "sale")
            }
        } else if (!loading) {
            items(displayedProperties.drop(8)) { p ->
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
private fun EmptyHomeState(commercial: Boolean, forSale: Boolean = false) {
    val palette = LocalKejaPalette.current
    val title = when {
        commercial && forSale -> "No commercial properties for sale yet"
        commercial -> "No commercial listings yet"
        forSale -> "Nothing for sale yet"
        else -> "No listings yet"
    }
    val subtitle = when {
        commercial -> "Check back as landlords publish shops and offices."
        forSale -> "Landlords haven't listed any properties for sale in this category yet."
        else -> "Be the first to list a property, or check back soon."
    }
    com.keja.app.ui.components.KejaSurface(
        Modifier.fillMaxWidth(),
        contentPadding = PaddingValues(vertical = 36.dp, horizontal = 20.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Box(Modifier.size(56.dp).clip(CircleShape).background(palette.primaryLight), contentAlignment = Alignment.Center) {
            Icon(Icons.Outlined.Home, contentDescription = null, tint = palette.primary, modifier = Modifier.size(26.dp))
        }
        Spacer(Modifier.height(14.dp))
        Text(title, fontWeight = FontWeight.Bold, color = palette.text, textAlign = androidx.compose.ui.text.style.TextAlign.Center)
        Spacer(Modifier.height(4.dp))
        Text(subtitle, fontSize = 12.sp, color = palette.muted, textAlign = androidx.compose.ui.text.style.TextAlign.Center)
    }
}

@Composable
private fun ListingTypePills(selected: String?, onSelect: (String) -> Unit) {
    val palette = LocalKejaPalette.current
    Row(horizontalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.fillMaxWidth()) {
        listOf("all" to "All", "rent" to "For rent", "sale" to "For sale").forEach { (key, label) ->
            // "All" is the selected pill whenever neither rent nor sale is chosen.
            val active = (selected ?: "all") == key
            Row(
                Modifier
                    .weight(1f)
                    .clip(KejaShapes.pill)
                    .background(if (active) palette.primary else palette.card)
                    .border(1.dp, if (active) Color.Transparent else palette.border, KejaShapes.pill)
                    .clickable { onSelect(key) }
                    .padding(vertical = 11.dp),
                horizontalArrangement = Arrangement.Center,
            ) {
                Text(
                    label,
                    fontSize = 13.sp,
                    fontWeight = FontWeight.Bold,
                    color = if (active) Color.White else palette.text,
                )
            }
        }
    }
}

@Composable
private fun CategoryRow(selected: String?, counts: Map<String, Int>, onSelect: (String) -> Unit) {
    val palette = LocalKejaPalette.current
    val rangi = palette.style == com.keja.app.ui.theme.KejaThemeStyle.RANGI
    // (key, icon, label, subtitle, Rangi colour)
    val categories = listOf(
        listOf("apartments", Icons.Outlined.Home, "Apartments", "Long-term homes", palette.sun),
        listOf("hostels", Icons.Outlined.Apartment, "Hostels", "Student rooms", Color(0xFF38B6FF)),
        listOf("airbnb", Icons.Outlined.AutoAwesome, "Airbnb", "Short stays", palette.mint),
        listOf("commercial", Icons.Outlined.Storefront, "Shops", "Business spaces", palette.coral),
    )
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        categories.chunked(2).forEach { pair ->
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.fillMaxWidth()) {
                pair.forEach { c ->
                    val key = c[0] as String
                    val n = counts[key]
                    CategoryCard(
                        icon = c[1] as ImageVector,
                        label = c[2] as String,
                        sub = (if (n != null) "$n ${if (n == 1) "listing" else "listings"} · " else "") + (c[3] as String),
                        active = selected == key,
                        tint = if (rangi) c[4] as Color else null,
                        modifier = Modifier.weight(1f),
                        onClick = { onSelect(key) },
                    )
                }
            }
        }
    }
}

@Composable
private fun CategoryCard(icon: ImageVector, label: String, sub: String, active: Boolean, tint: Color?, modifier: Modifier = Modifier, onClick: () -> Unit) {
    val palette = LocalKejaPalette.current
    val bg = when {
        active -> palette.primary
        tint != null -> tint
        else -> palette.card
    }
    val fg = if (active) Color.White else if (tint != null) Color(0xFF1A1830) else palette.text
    val subFg = if (active) Color.White.copy(alpha = 0.85f) else if (tint != null) Color(0xB81A1830) else palette.muted
    com.keja.app.ui.components.ThemedCard(
        modifier = modifier.padding(end = if (tint != null) 6.dp else 0.dp, bottom = if (tint != null) 7.dp else 0.dp),
        onClick = onClick,
    ) {
        Row(
            Modifier.fillMaxWidth().background(bg).padding(horizontal = 12.dp, vertical = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Box(
                Modifier.size(38.dp).clip(RoundedCornerShape(12.dp)).background(if (active) Color.White.copy(alpha = 0.22f) else if (tint != null) Color.White else palette.primaryLight),
                contentAlignment = Alignment.Center,
            ) {
                Icon(icon, contentDescription = null, tint = if (active) Color.White else if (tint != null) Color(0xFF1A1830) else palette.primary, modifier = Modifier.size(19.dp))
            }
            Spacer(Modifier.width(10.dp))
            Column {
                Text(label, fontSize = 14.sp, fontWeight = FontWeight.ExtraBold, color = fg, maxLines = 1)
                Text(sub, fontSize = 11.sp, color = subFg, maxLines = 2, lineHeight = 14.sp)
            }
        }
    }
}
