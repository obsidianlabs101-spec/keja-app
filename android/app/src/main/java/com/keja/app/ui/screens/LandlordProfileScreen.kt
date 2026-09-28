package com.keja.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.ChatBubbleOutline
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.keja.app.data.AppContainer
import com.keja.app.data.model.LandlordPropertiesResponse
import com.keja.app.ui.components.Avatar
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
            Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 12.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text("LANDLORD", color = palette.primary, fontWeight = FontWeight.Bold, fontSize = 11.sp)
            TextButton(onClick = onBack) { Text("Back") }
        }

        val d = data
        when {
            loading -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { com.keja.app.ui.components.KejaLoader() }
            d == null -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text("Couldn't load this profile", color = palette.muted)
            }
            else -> LazyColumn(
                contentPadding = PaddingValues(start = 18.dp, end = 18.dp, bottom = 24.dp),
                verticalArrangement = Arrangement.spacedBy(14.dp),
            ) {
                item {
                    Column(Modifier.fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally) {
                        Avatar(url = d.landlord.profile_picture, name = d.landlord.full_name, size = 96.dp)
                        Spacer(Modifier.height(10.dp))
                        Text(d.landlord.full_name, fontSize = 22.sp, fontWeight = FontWeight.ExtraBold, color = palette.text)
                        d.landlord.username?.let { Text("@$it", fontSize = 13.sp, color = palette.muted) }
                        d.landlord.bio?.takeIf { it.isNotBlank() }?.let {
                            Spacer(Modifier.height(8.dp))
                            Text(it, fontSize = 13.sp, color = palette.muted, lineHeight = 18.sp)
                        }
                        Spacer(Modifier.height(14.dp))
                        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                            ProfileStat("Properties uploaded", d.property_count.toString(), Modifier.weight(1f))
                            ProfileStat("Available now", d.properties.size.toString(), Modifier.weight(1f))
                        }
                        Spacer(Modifier.height(14.dp))
                        HostCommentsPlaceholder()
                        Spacer(Modifier.height(14.dp))
                        Text(
                            if (d.properties.isEmpty()) "No available listings right now" else "Available listings",
                            modifier = Modifier.fillMaxWidth(),
                            fontWeight = FontWeight.ExtraBold, fontSize = 16.sp, color = palette.text,
                        )
                    }
                }
                items(d.properties) { p -> PropertyCard(property = p, onClick = { onOpenProperty(p.id) }) }
            }
        }
    }
}

@Composable
private fun ProfileStat(label: String, value: String, modifier: Modifier = Modifier) {
    val palette = LocalKejaPalette.current
    Column(
        modifier.clip(RoundedCornerShape(16.dp)).background(palette.card).padding(14.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(value, fontSize = 26.sp, fontWeight = FontWeight.ExtraBold, color = palette.text)
        Text(label, fontSize = 11.sp, color = palette.muted)
    }
}

/** Placeholder only — comments about a host aren't built yet. Keeps the
 * spot (and the layout) ready so the real feature can drop in later. */
@Composable
private fun HostCommentsPlaceholder() {
    val palette = LocalKejaPalette.current
    Column(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(20.dp)).background(palette.card).padding(16.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.size(36.dp).clip(CircleShape).background(palette.primaryLight), contentAlignment = Alignment.Center) {
                Icon(Icons.Outlined.ChatBubbleOutline, contentDescription = null, tint = palette.primary, modifier = Modifier.size(18.dp))
            }
            Spacer(Modifier.width(10.dp))
            Column {
                Text("What renters say", fontWeight = FontWeight.Bold, color = palette.text)
                Text("Comments about this host", fontSize = 11.sp, color = palette.muted)
            }
        }
        Spacer(Modifier.height(12.dp))
        Text("No comments yet. Renter comments about this host are coming soon.", fontSize = 13.sp, color = palette.muted)
        Spacer(Modifier.height(12.dp))
        OutlinedButton(onClick = {}, enabled = false, modifier = Modifier.fillMaxWidth()) { Text("Write a comment (coming soon)") }
    }
}
