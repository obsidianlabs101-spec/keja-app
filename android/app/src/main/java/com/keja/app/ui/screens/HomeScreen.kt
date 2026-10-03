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

fun categoryOfType(type: String): String = com.keja.app.data.Catalog.groupOf(type)

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
    var catalogVersion by remember { mutableStateOf(0) }
    LaunchedEffect(Unit) { repo.refreshCatalog(); catalogVersion++ }
    LaunchedEffect(selectedListingType, catalogVersion) {
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

                CategoryRow(
                    selected = selectedCategory,
                    counts = counts,
                    onSelect = { selectedCategory = if (selectedCategory == it) null else it },
                )
                Spacer(Modifier.height(10.dp))

                // ---- Popular areas (one tidy row, no heading — saves a screenful) ----
                LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    rowItems(com.keja.app.data.Catalog.areas()) { area ->
                        Box(
                            Modifier
                                .clip(KejaShapes.pill)
                                .background(palette.card)
                                .border(1.dp, palette.border, KejaShapes.pill)
                                .clickable { query = area; load(area) }
                                .padding(horizontal = 14.dp, vertical = 8.dp)
                        ) { Text("\uD83D\uDCCD $area", fontSize = 12.5.sp, fontWeight = FontWeight.Bold, color = palette.text) }
                    }
                }
                Spacer(Modifier.height(18.dp))

                // ---- Headline that proves the app is full of places ----
                val total = counts.values.sum()
                val headline = when {
                    loading -> "Finding places…"
                    selectedCategory != null -> "${displayedProperties.size} ${when (selectedCategory) { "hostels" -> "hostels"; "airbnb" -> "Airbnb stays"; "commercial" -> "shops & spaces"; else -> "apartments" }}"
                    total > 0 -> "$total places to explore"
                    else -> "Latest listings"
                }
                Text(headline, fontSize = 21.sp, fontWeight = FontWeight.ExtraBold, color = palette.text)
                Text("Newest first · tap a card to see photos, price and contact", fontSize = 12.sp, color = palette.muted)
                Spacer(Modifier.height(4.dp))
            }
        }

        if (loading) {
            items(2) { com.keja.app.ui.components.SkeletonCard(wide = true) }
        } else if (displayedProperties.isEmpty()) {
            item(span = { GridItemSpan(maxLineSpan) }) {
                EmptyHomeState(commercial = selectedCategory == "commercial", forSale = selectedListingType == "sale")
            }
        } else {
            items(displayedProperties.take(3)) { p ->
                PropertyCard(property = p, onClick = { onOpenProperty(p.id) })
            }
            item(span = { GridItemSpan(maxLineSpan) }) {
                com.keja.app.ui.components.AdBanner(placement = "home")
            }
            items(displayedProperties.drop(3)) { p ->
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
    // key, icon, label, Rangi colour
    val categories = listOf(
        listOf("apartments", Icons.Outlined.Home, "Apartments", palette.sun),
        listOf("hostels", Icons.Outlined.Apartment, "Hostels", Color(0xFF38B6FF)),
        listOf("airbnb", Icons.Outlined.AutoAwesome, "Airbnb", palette.mint),
        listOf("commercial", Icons.Outlined.Storefront, "Shops", palette.coral),
    )
    LazyRow(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        rowItems(categories) { c ->
            val key = c[0] as String
            val active = selected == key
            val n = counts[key] ?: 0
            val bg = when { active -> palette.primary; rangi -> c[3] as Color; else -> palette.card }
            val fg = when { active -> Color.White; rangi -> Color(0xFF1A1830); else -> palette.text }
            Row(
                Modifier
                    .clip(KejaShapes.pill)
                    .background(bg)
                    .border(if (rangi) 2.dp else 1.dp, if (active) Color.Transparent else if (rangi) Color(0xFF1A1830) else palette.border, KejaShapes.pill)
                    .clickable { onSelect(key) }
                    .padding(horizontal = 14.dp, vertical = 10.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Icon(c[1] as ImageVector, contentDescription = null, tint = fg, modifier = Modifier.size(18.dp))
                Spacer(Modifier.width(7.dp))
                Text(c[2] as String, fontSize = 13.5.sp, fontWeight = FontWeight.ExtraBold, color = fg, maxLines = 1)
                // Never advertise an empty shelf: counts only appear when there is something to see.
                if (n > 0) {
                    Spacer(Modifier.width(7.dp))
                    Box(
                        Modifier.clip(CircleShape).background(if (active) Color.White.copy(alpha = 0.25f) else fg.copy(alpha = 0.12f)).padding(horizontal = 7.dp, vertical = 1.dp),
                    ) { Text("$n", fontSize = 11.5.sp, fontWeight = FontWeight.ExtraBold, color = fg) }
                }
            }
        }
    }
}

/** Shown on the phone's back button from Home, once per app session (unless
 * "Don't ask again" was set previously). Offers to set up alerts instead of
 * leaving; a second back-press (or tapping Exit here) says goodbye and closes
 * the app for real. See sayGoodbyeAndExit() and the BackHandler above. */
@Composable
private fun ExitIntentDialog(
    onDismiss: (dontAskAgain: Boolean) -> Unit,
    onAdjustNotifications: () -> Unit,
    onExitNow: () -> Unit,
) {
    val palette = LocalKejaPalette.current
    var dontAskAgain by remember { mutableStateOf(false) }

    androidx.compose.ui.window.Dialog(onDismissRequest = { onDismiss(dontAskAgain) }) {
        Column(
            Modifier
                .fillMaxWidth()
                .shadow(16.dp, KejaShapes.card, ambientColor = palette.primary.copy(alpha = 0.25f))
                .clip(KejaShapes.card)
                .background(palette.card)
                .padding(horizontal = 24.dp, vertical = 28.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Box(
                Modifier
                    .size(64.dp)
                    .clip(CircleShape)
                    .background(Brush.linearGradient(listOf(palette.primary, palette.coral))),
                contentAlignment = Alignment.Center,
            ) {
                Icon(Icons.Filled.NotificationsActive, contentDescription = null, tint = Color.White, modifier = Modifier.size(30.dp))
            }
            Spacer(Modifier.height(18.dp))
            Text("Leaving already?", fontSize = 19.sp, fontWeight = FontWeight.ExtraBold, color = palette.text)
            Spacer(Modifier.height(8.dp))
            Text(
                "Not able to find what you're looking for? Turn on alerts and we'll let you know the moment a new property matching your search arrives.",
                fontSize = 13.sp,
                color = palette.muted,
                textAlign = androidx.compose.ui.text.style.TextAlign.Center,
                lineHeight = 18.sp,
            )
            Spacer(Modifier.height(18.dp))
            Row(
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(KejaShapes.pill)
                    .background(palette.bg)
                    .clickable { dontAskAgain = !dontAskAgain }
                    .padding(horizontal = 14.dp, vertical = 10.dp),
            ) {
                Checkbox(checked = dontAskAgain, onCheckedChange = { dontAskAgain = it }, colors = CheckboxDefaults.colors(checkedColor = palette.primary))
                Spacer(Modifier.width(4.dp))
                Text("Don't ask me again", fontSize = 13.sp, color = palette.text)
            }
            Spacer(Modifier.height(20.dp))
            KejaPrimaryButton(text = "Adjust notifications", onClick = onAdjustNotifications, modifier = Modifier.fillMaxWidth())
            Spacer(Modifier.height(10.dp))
            TextButton(onClick = onExitNow, modifier = Modifier.fillMaxWidth()) {
                Text("Exit anyway", color = palette.muted, fontWeight = FontWeight.SemiBold)
            }
        }
    }
}

/** The "adjust notifications" dialog: location, price range, and an optional
 * landlord name. Saved to /properties/alerts/me on the backend; a new
 * property matching these filters notifies the renter (see
 * notify_service.notify_matching_alerts). */
@Composable
private fun AlertPreferencesDialog(onClose: () -> Unit) {
    val context = LocalContext.current
    val repo = remember { AppContainer.repository(context) }
    val scope = rememberCoroutineScope()

    var location by remember { mutableStateOf("") }
    var minPrice by remember { mutableStateOf("") }
    var maxPrice by remember { mutableStateOf("") }
    var landlordName by remember { mutableStateOf("") }
    var loaded by remember { mutableStateOf(false) }
    var saving by remember { mutableStateOf(false) }

    LaunchedEffect(Unit) {
        val existing = runCatching { repo.getMyAlert() }.getOrNull()
        if (existing != null) {
            location = existing.location ?: ""
            minPrice = existing.min_price?.let { if (it == it.toLong().toDouble()) it.toLong().toString() else it.toString() } ?: ""
            maxPrice = existing.max_price?.let { if (it == it.toLong().toDouble()) it.toLong().toString() else it.toString() } ?: ""
            landlordName = existing.landlord_name ?: ""
        }
        loaded = true
    }

    AlertDialog(
        onDismissRequest = onClose,
        title = { Text("Alert me about new properties") },
        text = {
            if (!loaded) {
                Box(Modifier.fillMaxWidth().padding(20.dp), contentAlignment = Alignment.Center) { com.keja.app.ui.components.KejaLoader(size = 32.dp) }
            } else {
                Column {
                    Text("Leave anything blank to match everything.", fontSize = 12.sp, color = Color.Gray)
                    Spacer(Modifier.height(10.dp))
                    OutlinedTextField(location, { location = it }, label = { Text("Location (area or county)") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                    Spacer(Modifier.height(8.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        OutlinedTextField(minPrice, { minPrice = it.filter(Char::isDigit) }, label = { Text("Min price") }, singleLine = true, modifier = Modifier.weight(1f))
                        OutlinedTextField(maxPrice, { maxPrice = it.filter(Char::isDigit) }, label = { Text("Max price") }, singleLine = true, modifier = Modifier.weight(1f))
                    }
                    Spacer(Modifier.height(8.dp))
                    OutlinedTextField(landlordName, { landlordName = it }, label = { Text("A certain landlord (optional)") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                }
            }
        },
        confirmButton = {
            TextButton(
                enabled = loaded && !saving,
                onClick = {
                    saving = true
                    scope.launch {
                        runCatching {
                            repo.setMyAlert(
                                com.keja.app.data.model.PropertyAlertDto(
                                    location = location.trim().ifBlank { null },
                                    min_price = minPrice.toDoubleOrNull(),
                                    max_price = maxPrice.toDoubleOrNull(),
                                    landlord_name = landlordName.trim().ifBlank { null },
                                )
                            )
                        }
                        android.widget.Toast.makeText(context, "We'll alert you when a match comes up", android.widget.Toast.LENGTH_SHORT).show()
                        saving = false
                        onClose()
                    }
                },
            ) { Text(if (saving) "Saving…" else "Save alert") }
        },
        dismissButton = { TextButton(onClick = onClose) { Text("Cancel") } },
    )
}
