package com.keja.app.ui.components

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import com.keja.app.data.AppContainer
import com.keja.app.data.model.AdSlotDto

/**
 * Shows the live ad for [placement] ("home" or "discover") from the backend.
 * Renders NOTHING when there is no active ad or the request fails, so an
 * unconfigured slot leaves no empty box. Tapping opens the ad's link (only
 * if it is a real http/https URL).
 */
@Composable
fun AdBanner(placement: String, modifier: Modifier = Modifier) {
    val context = LocalContext.current
    val repo = remember { AppContainer.repository(context) }
    val uriHandler = LocalUriHandler.current
    var ad by remember(placement) { mutableStateOf<AdSlotDto?>(null) }

    LaunchedEffect(placement) {
        ad = runCatching { repo.activeAd(placement) }.getOrNull()
    }

    val current = ad ?: return
    val link = current.link_url?.takeIf { it.startsWith("http://") || it.startsWith("https://") }

    Box(modifier.fillMaxWidth().padding(vertical = 8.dp)) {
        AsyncImage(
            model = current.image_url,
            contentDescription = "Advertisement",
            contentScale = ContentScale.Crop,
            modifier = Modifier
                .fillMaxWidth()
                .aspectRatio(4f)
                .clip(RoundedCornerShape(16.dp))
                .then(if (link != null) Modifier.clickable { runCatching { uriHandler.openUri(link) } } else Modifier),
        )
    }
}
