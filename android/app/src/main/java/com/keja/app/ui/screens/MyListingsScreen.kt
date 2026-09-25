package com.keja.app.ui.screens

import android.widget.Toast
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil.compose.AsyncImage
import com.keja.app.data.AppContainer
import com.keja.app.data.model.Property
import com.keja.app.ui.components.*
import com.keja.app.ui.theme.LocalKejaPalette
import kotlinx.coroutines.launch

/** Replaces "Interested" in the bottom nav for landlord accounts: every
 * property they've posted, with a Delete button on each. */
@Composable
fun MyListingsScreen(onOpenProperty: (String) -> Unit, onAddProperty: () -> Unit) {
    val palette = LocalKejaPalette.current
    val context = LocalContext.current
    val repo = remember { AppContainer.repository(context) }
    val scope = rememberCoroutineScope()
    var listings by remember { mutableStateOf<List<Property>?>(null) }
    var deleting by remember { mutableStateOf<Property?>(null) }

    fun load() { scope.launch { listings = runCatching { repo.myListings() }.getOrDefault(emptyList()) } }
    LaunchedEffect(Unit) { load() }

    deleting?.let { p ->
        ConfirmDialog(
            title = "Delete this listing?",
            text = "It will be removed from Keja and renters won't see it any more.",
            confirmLabel = "Delete",
            onDismiss = { deleting = null },
        ) {
            deleting = null
            scope.launch {
                runCatching { repo.deleteProperty(p.id) }
                    .onSuccess { Toast.makeText(context, "Listing deleted", Toast.LENGTH_SHORT).show(); load() }
                    .onFailure { Toast.makeText(context, it.message ?: "Couldn't delete", Toast.LENGTH_SHORT).show() }
            }
        }
    }

    Column(Modifier.fillMaxSize().background(palette.bg)) {
        Row(Modifier.fillMaxWidth().padding(20.dp), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
            Column {
                Text("YOUR PROPERTIES", color = palette.primary, fontWeight = FontWeight.Bold, fontSize = 11.sp)
                Text("My listings", fontSize = 24.sp, fontWeight = FontWeight.ExtraBold, color = palette.text)
            }
            KejaPrimaryButton(text = "＋ Add", onClick = onAddProperty)
        }
        val list = listings
        Column(Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(horizontal = 20.dp)) {
            when {
                list == null -> Box(Modifier.fillMaxWidth().padding(top = 60.dp), contentAlignment = Alignment.Center) { KejaLoader() }
                list.isEmpty() -> Text("You haven't listed anything yet.", color = palette.muted, modifier = Modifier.padding(top = 40.dp))
                else -> list.forEach { p ->
                    CardShell {
                        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                            AsyncImage(
                                model = resolveMediaUrl(p.main_image_url),
                                contentDescription = null,
                                contentScale = ContentScale.Crop,
                                modifier = Modifier.size(84.dp).clip(RoundedCornerShape(12.dp)).clickableOpen { onOpenProperty(p.id) },
                            )
                            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                                Row(horizontalArrangement = Arrangement.SpaceBetween, modifier = Modifier.fillMaxWidth()) {
                                    Text("${p.property_type} · KES ${p.price.toLong()}", fontWeight = FontWeight.Bold, color = palette.text, fontSize = 14.sp, modifier = Modifier.weight(1f))
                                    when {
                                        p.review_status == "rejected" -> Pill("Rejected", Color(0xFFFEE2E2), Color(0xFFB91C1C))
                                        p.is_booked -> Pill("Booked", Color(0xFFFEF3C7), Color(0xFFB45309))
                                        else -> Pill("Live", Color(0xFFDCFCE7), Color(0xFF15803D))
                                    }
                                }
                                Text("${p.area ?: ""} · 👁 ${p.view_count} · ${p.images.size} photos", color = palette.muted, fontSize = 11.sp)
                                if (p.review_status == "rejected" && !p.review_note.isNullOrBlank()) {
                                    Text("Rejected: ${p.review_note}", color = Color(0xFFEF4444), fontSize = 11.sp)
                                }
                            }
                        }
                        Spacer(Modifier.height(6.dp))
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            OutlinedButton(onClick = { onOpenProperty(p.id) }) { Text("View", fontSize = 12.sp) }
                            OutlinedButton(onClick = { deleting = p }) { Text("Delete", fontSize = 12.sp, color = Color(0xFFEF4444)) }
                        }
                    }
                }
            }
        }
    }
}

private fun Modifier.clickableOpen(onClick: () -> Unit): Modifier =
    this.clickable(onClick = onClick)
