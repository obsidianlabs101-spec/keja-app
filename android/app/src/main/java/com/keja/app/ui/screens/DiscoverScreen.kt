package com.keja.app.ui.screens

import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
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

    LaunchedEffect(isLoggedIn) {
        if (isLoggedIn) {
            loading = true
            properties = runCatching { repo.discover(limit = 30) }.getOrDefault(emptyList())
            loading = false
        }
    }

    if (!isLoggedIn) {
        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text("🔍", fontSize = 40.sp)
                Spacer(Modifier.height(10.dp))
                Text("Log in to discover places", fontWeight = FontWeight.Bold, fontSize = 17.sp)
                Spacer(Modifier.height(16.dp))
                Button(onClick = onRequireLogin) { Text("Log in") }
            }
        }
        return
    }

    if (loading) {
        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { com.keja.app.ui.components.KejaLoader() }
        return
    }

    if (properties.isEmpty()) {
        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            Text("You've seen everything for now 🎉", fontWeight = FontWeight.Bold)
        }
        return
    }

    val pagerState = rememberPagerState(pageCount = { properties.size })

    Column(Modifier.fillMaxSize().background(Color.Black)) {
    Box(Modifier.weight(1f).fillMaxWidth()) {
        VerticalPager(state = pagerState, modifier = Modifier.fillMaxSize()) { page ->
            val property = properties[page]
            val isSaved = interestedIds.contains(property.id)

            DiscoverCard(
                property = property,
                isSaved = isSaved,
                uiHidden = uiHidden,
                onTap = { onOpenProperty(property.id) },
                onLandlordClick = { onOpenLandlord(property.landlord_id) },
                onInterestedClick = {
                    scope.launch {
                        runCatching { repo.swipe(property.id, "right") }
                        interestedIds = interestedIds + property.id
                    }
                },
                onHideToggle = { uiHidden = !uiHidden },
            )
        }

        if (!uiHidden) {
            Text(
                "Scroll up or down to browse the next property",
                color = Color.White.copy(alpha = 0.85f),
                fontSize = 11.sp,
                modifier = Modifier
                    .align(Alignment.TopCenter)
                    .padding(top = 16.dp)
                    .background(Color.Black.copy(alpha = 0.35f), androidx.compose.foundation.shape.RoundedCornerShape(999.dp))
                    .padding(horizontal = 12.dp, vertical = 6.dp),
            )
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
                .background(Brush.verticalGradient(colors = listOf(Color.Transparent, Color.Black.copy(alpha = 0.75f)), startY = 300f))
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
    Box(
        Modifier
            .size(48.dp)
            .clip(CircleShape)
            .background(if (active) Color(0xFF6C4DFF) else Color.Black.copy(alpha = 0.55f))
            .clickableSimple(onClick),
        contentAlignment = Alignment.Center,
    ) {
        Icon(icon, contentDescription = null, tint = Color.White, modifier = Modifier.size(22.dp))
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
