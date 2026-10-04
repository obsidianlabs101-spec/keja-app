package com.keja.app.ui.screens

import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.PagerState
import androidx.compose.foundation.pager.VerticalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material.icons.outlined.FavoriteBorder
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil.compose.AsyncImage
import com.keja.app.data.AppContainer
import com.keja.app.data.model.Property
import com.keja.app.ui.components.formatKes
import com.keja.app.ui.components.resolveMediaUrl
import kotlinx.coroutines.launch

@OptIn(ExperimentalFoundationApi::class)
@Composable
fun DiscoverScreen(
    isLoggedIn: Boolean,
    onRequireLogin: () -> Unit,
    onOpenProperty: (String) -> Unit,
    onOpenLandlord: (String) -> Unit,
) {
    val context = LocalContext.current
    val repo = remember { AppContainer.repository(context) }
    val scope = rememberCoroutineScope()

    var properties by remember { mutableStateOf<List<Property>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }
    var interestedIds by remember { mutableStateOf(setOf<String>()) }
    var uiHidden by remember { mutableStateOf(false) }
    var listingFilter by remember { mutableStateOf<String?>(null) } // "rent" | "sale" | null (both)

    var loadError by remember { mutableStateOf(false) }
    var reloadKey by remember { mutableStateOf(0) }
    var loadingMore by remember { mutableStateOf(false) }
    var endReached by remember { mutableStateOf(false) }
    val pageSize = 30

    // First page. Re-runs when the rent/sale filter changes (the SERVER filters, so the
    // whole catalogue is reachable, not just the first batch) or on Retry.
    LaunchedEffect(listingFilter, reloadKey) {
        properties = emptyList()   // never show the previous tab's cards under the new tab
        loading = true
        loadError = false
        endReached = false
        val seed = com.keja.app.data.DiscoverSeed.current()
        // Don't swallow failures into an empty list — that made a slow/failed request
        // look like "You've seen everything". Retry once (Render can be cold-starting).
        var result = runCatching { repo.discover(limit = pageSize, offset = 0, seed = seed, listingType = listingFilter) }
        if (result.isFailure) {
            kotlinx.coroutines.delay(1500)
            result = runCatching { repo.discover(limit = pageSize, offset = 0, seed = seed, listingType = listingFilter) }
        }
        result.onSuccess { properties = it; endReached = it.size < pageSize }.onFailure { loadError = true }
        loading = false
    }
    // Saved hearts (logged-in only; guests browse freely).
    LaunchedEffect(isLoggedIn) {
        if (isLoggedIn) runCatching { repo.interested() }.onSuccess { list -> interestedIds = list.map { it.id }.toSet() }
    }

    // Next page, used by the pager when you get near the end.
    fun loadMore() {
        if (loadingMore || endReached || loading) return
        loadingMore = true
        scope.launch {
            val seed = com.keja.app.data.DiscoverSeed.current()
            runCatching { repo.discover(limit = pageSize, offset = properties.size, seed = seed, listingType = listingFilter) }
                .onSuccess { more ->
                    val known = properties.map { it.id }.toSet()
                    properties = properties + more.filter { it.id !in known }
                    if (more.size < pageSize) endReached = true
                }
                .onFailure { /* try again on the next swipe */ }
            loadingMore = false
        }
    }

    if (loadError && properties.isEmpty()) {
        Box(Modifier.fillMaxSize().background(Color.Black), contentAlignment = Alignment.Center) {
            DiscoverStateCard(
                icon = Icons.Filled.Search,
                title = "Couldn't load Discover",
                subtitle = "Check your connection and try again.",
                actionLabel = "Retry",
                onAction = { reloadKey++ },
            )
        }
        return
    }

    // The server already applied the rent/sale filter.
    val shown = properties

    Column(Modifier.fillMaxSize().background(Color.Black)) {
    Box(Modifier.weight(1f).fillMaxWidth()) {
        if (shown.isEmpty() && loading) {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { com.keja.app.ui.components.KejaLoader() }
        } else if (shown.isEmpty()) {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                DiscoverStateCard(
                    icon = Icons.Filled.Search,
                    title = when (listingFilter) { "sale" -> "Nothing for sale yet"; "rent" -> "Nothing for rent yet"; else -> "No listings yet" },
                    subtitle = if (listingFilter == null) "Check back soon — new listings are added often." else "Tap the other tab, or check back soon.",
                )
            }
        } else {
            androidx.compose.runtime.key(listingFilter) {
                // Exactly one property per screen; swipe up/down to move on.
                val pagerState = rememberPagerState(pageCount = { shown.size })
                LaunchedEffect(pagerState.currentPage, shown.size) {
                    if (pagerState.currentPage >= shown.size - 5) loadMore()
                }
                VerticalPager(state = pagerState, modifier = Modifier.fillMaxSize()) { page ->
                    val property = shown[page]
                    val isSaved = interestedIds.contains(property.id)
                    DiscoverCard(
                        property = property,
                        isSaved = isSaved,
                        uiHidden = uiHidden,
                        onTap = { onOpenProperty(property.id) },
                        onLandlordClick = { onOpenLandlord(property.landlord_id) },
                        onInterestedClick = {
                            if (!isLoggedIn) { onRequireLogin(); return@DiscoverCard }
                            scope.launch {
                                runCatching { repo.swipe(property.id, "right") }
                                interestedIds = interestedIds + property.id
                            }
                        },
                        onHideToggle = { uiHidden = !uiHidden },
                    )
                }
            }
        }

        if (!uiHidden) {
            Column(Modifier.align(Alignment.TopCenter).padding(top = 12.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                Row(
                    Modifier
                        .background(Color.Black.copy(alpha = 0.45f), androidx.compose.foundation.shape.RoundedCornerShape(999.dp))
                        .border(if (com.keja.app.ui.theme.LocalKejaPalette.current.style == com.keja.app.ui.theme.KejaThemeStyle.RANGI) 2.dp else 0.dp, Color.White, androidx.compose.foundation.shape.RoundedCornerShape(999.dp))
                        .padding(4.dp),
                    horizontalArrangement = Arrangement.spacedBy(4.dp),
                ) {
                    listOf("rent" to "For rent", "sale" to "For sale").forEach { (key, label) ->
                        val active = listingFilter == key
                        Text(
                            label,
                            color = if (active) com.keja.app.ui.theme.LocalKejaPalette.current.text else Color.White,
                            fontSize = 12.sp,
                            fontWeight = FontWeight.Bold,
                            modifier = Modifier
                                .clip(androidx.compose.foundation.shape.RoundedCornerShape(999.dp))
                                .background(if (active) com.keja.app.ui.theme.LocalKejaPalette.current.sun else Color.Transparent)
                                .clickableSimple { listingFilter = if (active) null else key }
                                .padding(horizontal = 18.dp, vertical = 8.dp),
                        )
                    }
                }
            }
        }
    }
    }
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun DiscoverCard(
    property: Property,
    isSaved: Boolean,
    uiHidden: Boolean,
    onTap: () -> Unit,
    onLandlordClick: () -> Unit,
    onInterestedClick: () -> Unit,
    onHideToggle: () -> Unit,
) {
    val images = if (property.images.isNotEmpty()) {
        property.images.sortedBy { it.sort_order }.map { it.url }
    } else {
        listOf(property.main_image_url)
    }
    val galleryState = rememberPagerState(pageCount = { images.size })

    Box(Modifier.fillMaxSize()) {
        HorizontalPager(state = galleryState, modifier = Modifier.fillMaxSize()) { page ->
            AsyncImage(
                model = resolveMediaUrl(images[page]),
                contentDescription = property.title,
                contentScale = ContentScale.Crop,
                modifier = Modifier
                    .fillMaxSize()
                    .clickableSimple(onTap),
            )
        }

        // Gradient overlay so text stays legible over any photo.
        Box(
            Modifier
                .fillMaxSize()
                .background(Brush.verticalGradient(colorStops = arrayOf(0f to Color.Transparent, 0.6f to Color.Transparent, 1f to Color.Black.copy(alpha = 0.7f))))
        )

        if (images.size > 1 && !uiHidden) {
            Row(
                Modifier
                    .align(Alignment.TopCenter)
                    .padding(top = 14.dp, start = 14.dp, end = 14.dp)
                    .fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                images.indices.forEach { i ->
                    Box(
                        Modifier
                            .weight(1f)
                            .height(3.dp)
                            .clip(androidx.compose.foundation.shape.RoundedCornerShape(2.dp))
                            .background(if (i == galleryState.currentPage) Color.White else Color.White.copy(alpha = 0.4f))
                    )
                }
            }
        }

        if (!uiHidden) {
            Column(
                Modifier
                    .align(Alignment.BottomStart)
                    .padding(start = 20.dp, end = 90.dp, bottom = 28.dp),
            ) {
                Text(formatKes(property.price), color = Color.White, fontSize = 26.sp, fontWeight = FontWeight.ExtraBold)
                Text("${property.property_type} · ${property.area ?: property.county}", color = Color.White.copy(alpha = 0.9f), fontSize = 14.sp)
                property.proximity_note?.let {
                    Spacer(Modifier.height(8.dp))
                    Text(it, color = Color.White.copy(alpha = 0.85f), fontSize = 12.sp)
                }
            }
        }

        // The three requested action buttons, bottom-right.
        Column(
            Modifier
                .align(Alignment.BottomEnd)
                .padding(end = 16.dp, bottom = 26.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            if (!uiHidden) {
                DiscoverFab(icon = Icons.Filled.Home, onClick = onLandlordClick)
                DiscoverFab(
                    icon = if (isSaved) Icons.Filled.Favorite else Icons.Outlined.FavoriteBorder,
                    active = isSaved,
                    onClick = onInterestedClick,
                )
            }
            DiscoverFab(icon = if (uiHidden) Icons.Filled.VisibilityOff else Icons.Filled.Visibility, onClick = onHideToggle)
        }
    }
}

@Composable
private fun DiscoverFab(icon: androidx.compose.ui.graphics.vector.ImageVector, active: Boolean = false, onClick: () -> Unit) {
    val palette = com.keja.app.ui.theme.LocalKejaPalette.current
    Box(
        Modifier
            .size(48.dp)
            .clip(CircleShape)
            .background(if (active) palette.coral else Color.Black.copy(alpha = 0.55f))
            .border(2.dp, if (palette.style == com.keja.app.ui.theme.KejaThemeStyle.RANGI) Color.White else Color.White.copy(alpha = if (active) 0f else 0.15f), CircleShape)
            .clickableSimple(onClick),
        contentAlignment = Alignment.Center,
    ) {
        Icon(icon, contentDescription = null, tint = Color.White, modifier = Modifier.size(22.dp))
    }
}

@Composable
private fun DiscoverStateCard(
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    title: String,
    subtitle: String,
    actionLabel: String? = null,
    onAction: (() -> Unit)? = null,
) {
    Column(
        Modifier
            .fillMaxWidth(0.82f)
            .clip(androidx.compose.foundation.shape.RoundedCornerShape(20.dp))
            .background(Color.White.copy(alpha = 0.08f))
            .border(1.dp, Color.White.copy(alpha = 0.12f), androidx.compose.foundation.shape.RoundedCornerShape(20.dp))
            .padding(vertical = 32.dp, horizontal = 22.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Box(
            Modifier.size(56.dp).clip(CircleShape).background(Color.White.copy(alpha = 0.14f)),
            contentAlignment = Alignment.Center,
        ) {
            Icon(icon, contentDescription = null, tint = Color.White, modifier = Modifier.size(26.dp))
        }
        Spacer(Modifier.height(16.dp))
        Text(title, fontWeight = FontWeight.Bold, fontSize = 16.sp, color = Color.White, textAlign = androidx.compose.ui.text.style.TextAlign.Center)
        Spacer(Modifier.height(4.dp))
        Text(subtitle, fontSize = 13.sp, color = Color.White.copy(alpha = 0.7f), textAlign = androidx.compose.ui.text.style.TextAlign.Center)
        if (actionLabel != null && onAction != null) {
            Spacer(Modifier.height(18.dp))
            Button(
                onClick = onAction,
                colors = ButtonDefaults.buttonColors(containerColor = Color.White, contentColor = Color.Black),
                modifier = Modifier.fillMaxWidth(0.75f),
            ) { Text(actionLabel, fontWeight = FontWeight.Bold) }
        }
    }
}

@Composable
private fun Modifier.clickableSimple(onClick: () -> Unit): Modifier {
    val interactionSource = remember { MutableInteractionSource() }
    return this.clickable(
        indication = null,
        interactionSource = interactionSource,
        onClick = onClick,
    )
}
