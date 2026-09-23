package com.keja.app.ui.screens

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil.compose.AsyncImage
import com.keja.app.data.AppContainer
import com.keja.app.data.model.AdSlotDto
import com.keja.app.ui.components.KejaPrimaryButton
import com.keja.app.ui.components.KejaSecondaryButton
import com.keja.app.ui.components.KejaTextField
import com.keja.app.ui.theme.LocalKejaPalette
import kotlinx.coroutines.launch

private val AD_PLACEMENTS = listOf(
    Triple("home", "Home feed", "Promotional slot under the category buttons"),
    Triple("discover", "Discover", "Slot at the bottom of the Discover feed"),
)

/** Admin-only ad management. Uploading makes the image THE live ad for that
 * placement (the backend deactivates the previous one). */
@Composable
fun AdminAdsSection() {
    val palette = LocalKejaPalette.current
    val context = LocalContext.current
    val repo = remember { AppContainer.repository(context) }
    val scope = rememberCoroutineScope()

    var ads by remember { mutableStateOf<List<AdSlotDto>>(emptyList()) }
    var message by remember { mutableStateOf<String?>(null) }

    fun refresh() {
        scope.launch { ads = runCatching { repo.adminAds() }.getOrDefault(ads) }
    }
    LaunchedEffect(Unit) { refresh() }

    Column(Modifier.fillMaxWidth()) {
        Text("Ad placement", fontSize = 18.sp, fontWeight = FontWeight.Bold, color = palette.text)
        Spacer(Modifier.height(4.dp))
        Text(
            "Upload an image to make it the live ad for a placement. JPG, PNG or WEBP, 5MB max.",
            fontSize = 12.sp, color = palette.muted,
        )
        message?.let {
            Spacer(Modifier.height(8.dp))
            Text(it, fontSize = 12.sp, color = palette.primary)
        }
        Spacer(Modifier.height(12.dp))

        AD_PLACEMENTS.forEach { (key, label, hint) ->
            val live = ads.firstOrNull { it.placement == key && it.is_active }
            AdPlacementEditor(
                label = label,
                hint = hint,
                live = live,
                onUpload = { uri, link ->
                    scope.launch {
                        message = "Uploading…"
                        val temp = copyAdUriToTempFile(context, uri)
                        if (temp == null) { message = "Couldn't read that image"; return@launch }
                        val mime = context.contentResolver.getType(uri) ?: "image/jpeg"
                        message = try {
                            repo.adminUploadAd(key, temp, mime, link)
                            "$label ad is live"
                        } catch (e: Exception) { e.message ?: "Upload failed" }
                        temp.delete()
                        refresh()
                    }
                },
                onSaveLink = { link ->
                    if (live != null) scope.launch {
                        message = try { repo.adminUpdateAd(live.id, linkUrl = link); "Link saved" } catch (e: Exception) { e.message ?: "Couldn't save link" }
                        refresh()
                    }
                },
                onTurnOff = {
                    if (live != null) scope.launch {
                        message = try { repo.adminUpdateAd(live.id, isActive = false); "$label ad turned off" } catch (e: Exception) { e.message ?: "Couldn't turn off" }
                        refresh()
                    }
                },
            )
            Spacer(Modifier.height(12.dp))
        }
    }
}

@Composable
private fun AdPlacementEditor(
    label: String,
    hint: String,
    live: AdSlotDto?,
    onUpload: (android.net.Uri, String?) -> Unit,
    onSaveLink: (String) -> Unit,
    onTurnOff: () -> Unit,
) {
    val palette = LocalKejaPalette.current
    var picked by remember { mutableStateOf<android.net.Uri?>(null) }
    var link by remember(live?.id) { mutableStateOf(live?.link_url ?: "") }

    val picker = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        if (uri != null) picked = uri
    }

    Column(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(14.dp))
            .background(palette.card)
            .padding(14.dp),
    ) {
        Text(label, fontWeight = FontWeight.Bold, color = palette.text)
        Text(hint, fontSize = 11.sp, color = palette.muted)
        Spacer(Modifier.height(8.dp))

        if (live != null) {
            AsyncImage(
                model = live.image_url,
                contentDescription = "Current $label ad",
                contentScale = ContentScale.Crop,
                modifier = Modifier.fillMaxWidth().heightIn(max = 120.dp).clip(RoundedCornerShape(10.dp)),
            )
            Spacer(Modifier.height(4.dp))
            Text("Live now", fontSize = 11.sp, color = palette.muted)
        } else {
            Text("No live ad", fontSize = 12.sp, color = palette.muted)
        }
        Spacer(Modifier.height(8.dp))

        KejaSecondaryButton(
            text = if (picked != null) "Image selected ✓ (tap to change)" else "Choose image",
            onClick = { picker.launch("image/*") },
        )
        Spacer(Modifier.height(8.dp))
        KejaTextField(link, { link = it }, "Click-through link (optional, https://…)")
        Spacer(Modifier.height(10.dp))

        KejaPrimaryButton(
            text = if (live != null) "Replace ad" else "Upload ad",
            enabled = picked != null,
            modifier = Modifier.fillMaxWidth(),
            onClick = {
                picked?.let { onUpload(it, link.trim().ifBlank { null }) }
                picked = null
            },
        )
        if (live != null) {
            Spacer(Modifier.height(8.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                KejaSecondaryButton(text = "Save link", onClick = { onSaveLink(link.trim()) })
                KejaSecondaryButton(text = "Turn off", onClick = onTurnOff)
            }
        }
    }
}

private fun copyAdUriToTempFile(context: android.content.Context, uri: android.net.Uri): java.io.File? {
    return try {
        val ext = when (context.contentResolver.getType(uri)) {
            "image/png" -> ".png"
            "image/webp" -> ".webp"
            else -> ".jpg"
        }
        val temp = java.io.File.createTempFile("keja_ad_", ext, context.cacheDir)
        context.contentResolver.openInputStream(uri)?.use { input ->
            temp.outputStream().use { output -> input.copyTo(output) }
        }
        temp
    } catch (e: Exception) {
        null
    }
}
