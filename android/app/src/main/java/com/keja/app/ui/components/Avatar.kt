package com.keja.app.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.sp
import coil.compose.AsyncImage
import com.keja.app.ui.theme.LocalKejaPalette

/** Round profile picture; falls back to the person's initial on a coloured circle. */
@Composable
fun Avatar(url: String?, name: String?, size: Dp, modifier: Modifier = Modifier) {
    val palette = LocalKejaPalette.current
    Box(
        modifier.size(size).clip(CircleShape).background(palette.primary),
        contentAlignment = Alignment.Center,
    ) {
        if (!url.isNullOrBlank()) {
            AsyncImage(
                model = resolveMediaUrl(url),
                contentDescription = name,
                contentScale = ContentScale.Crop,
                modifier = Modifier.fillMaxSize(),
            )
        } else {
            Text(
                (name?.trim()?.firstOrNull()?.uppercase() ?: "K"),
                color = Color.White, fontWeight = FontWeight.Bold, fontSize = (size.value * 0.42f).sp,
            )
        }
    }
}
