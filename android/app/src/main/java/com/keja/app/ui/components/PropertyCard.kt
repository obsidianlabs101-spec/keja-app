package com.keja.app.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil.compose.AsyncImage
import com.keja.app.data.model.Property
import com.keja.app.ui.theme.KejaColors
import com.keja.app.ui.theme.KejaShapes
import com.keja.app.ui.theme.KejaThemeStyle
import com.keja.app.ui.theme.LocalKejaPalette
import java.text.NumberFormat
import java.util.Locale

fun formatKes(amount: Double): String {
    val nf = NumberFormat.getNumberInstance(Locale.US)
    return "KES " + nf.format(amount.toInt())
}

fun resolveMediaUrl(url: String?): String {
    if (url.isNullOrBlank()) return "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?auto=format&fit=crop&w=1000&q=80"
    if (url.startsWith("http")) return url
    return "https://keja-backend-uqzk.onrender.com/" + url.trimStart('/')
}

/**
 * Wraps content in the card "chrome" for the current theme style: a
 * plain soft-bordered surface for Professional, or Rangi's bold 2dp
 * outline + hard offset shadow (the web's `box-shadow: 5px 6px 0
 * var(--text)` neo-brutalist look — approximated here with a solid
 * color block offset behind the card, since Compose has no direct
 * equivalent of a hard, non-blurred CSS box-shadow).
 */
@Composable
fun ThemedCard(modifier: Modifier = Modifier, onClick: (() -> Unit)? = null, content: @Composable () -> Unit) {
    val palette = LocalKejaPalette.current
    val clickMod = if (onClick != null) Modifier.clickable(onClick = onClick) else Modifier

    if (palette.style == KejaThemeStyle.RANGI) {
        Box(modifier) {
            Box(
                Modifier
                    .matchParentSize()
                    .offset(x = 5.dp, y = 6.dp)
                    .clip(KejaShapes.card)
                    .background(palette.text)
            )
            Box(
                Modifier
                    .matchParentSize()
                    .clip(KejaShapes.card)
                    .background(palette.card)
                    .border(2.dp, palette.text, KejaShapes.card)
                    .then(clickMod)
            ) { content() }
        }
    } else {
        Box(
            modifier
                .clip(KejaShapes.card)
                .background(palette.card)
                .border(1.dp, palette.border, KejaShapes.card)
                .then(clickMod)
        ) { content() }
    }
}

@Composable
fun PropertyCard(property: Property, modifier: Modifier = Modifier, onClick: () -> Unit) {
    val palette = LocalKejaPalette.current
    ThemedCard(modifier = modifier, onClick = onClick) {
        Column {
            AsyncImage(
                model = resolveMediaUrl(property.main_image_url),
                contentDescription = property.title,
                contentScale = ContentScale.Crop,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(140.dp)
                    .clip(KejaShapes.propertyImage)
            )
            Column(Modifier.padding(14.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(formatKes(property.price), fontSize = 20.sp, fontWeight = FontWeight.ExtraBold, color = palette.text)
                    if (property.is_booked) {
                        Spacer(Modifier.width(8.dp))
                        StatusPill(label = "Booked", bg = KejaColors.BookedBg, fg = KejaColors.BookedText)
                    }
                }
                Spacer(Modifier.height(4.dp))
                Text(
                    "${property.property_type} · ${property.area ?: property.county}",
                    fontSize = 13.sp, color = palette.muted,
                )
                property.proximity_note?.let {
                    Spacer(Modifier.height(8.dp))
                    TagPill(it)
                }
            }
        }
    }
}

@Composable
fun TagPill(text: String) {
    val palette = LocalKejaPalette.current
    Box(
        Modifier
            .clip(KejaShapes.pill)
            .background(palette.primaryLight)
            .padding(horizontal = 9.dp, vertical = 6.dp)
    ) {
        Text(text, fontSize = 11.sp, fontWeight = FontWeight.Bold, color = palette.primary)
    }
}

@Composable
fun StatusPill(label: String, bg: androidx.compose.ui.graphics.Color, fg: androidx.compose.ui.graphics.Color) {
    Box(Modifier.clip(KejaShapes.pill).background(bg).padding(horizontal = 9.dp, vertical = 4.dp)) {
        Text(label, fontSize = 11.sp, fontWeight = FontWeight.Bold, color = fg)
    }
}
