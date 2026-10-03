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
        // The shadow box uses matchParentSize() so it exactly fills
        // whatever size the content box below determines — the content
        // box must NOT also use matchParentSize(), or neither box has
        // anything to measure against and the whole thing collapses to
        // zero size (this was the "Rangi shows nothing at all" bug).
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

/**
 * A padded Column inside the theme's card chrome (ThemedCard). Drop-in
 * replacement for `Column(Modifier.clip(..).background(palette.card).padding(..))`
 * so every screen gets Rangi's bold outline + hard offset shadow in
 * Rangi, and the plain bordered card in Professional. The extra end/bottom
 * padding in Rangi leaves room for the offset shadow so it isn't clipped.
 */
@Composable
fun KejaSurface(
    modifier: Modifier = Modifier,
    contentPadding: PaddingValues = PaddingValues(14.dp),
    horizontalAlignment: Alignment.Horizontal = Alignment.Start,
    verticalArrangement: Arrangement.Vertical = Arrangement.Top,
    onClick: (() -> Unit)? = null,
    content: @Composable ColumnScope.() -> Unit,
) {
    val rangi = LocalKejaPalette.current.style == KejaThemeStyle.RANGI
    ThemedCard(modifier = if (rangi) modifier.padding(end = 6.dp, bottom = 7.dp) else modifier, onClick = onClick) {
        Column(
            Modifier.fillMaxWidth().padding(contentPadding),
            horizontalAlignment = horizontalAlignment,
            verticalArrangement = verticalArrangement,
            content = content,
        )
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
                    .height(200.dp)
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
                if (property.landlord_verified) { VerifiedBadge() }
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
        Text(label, fontSize = 11.sp, fontWeight = FontWeight.Bold, color = fg, maxLines = 1, softWrap = false)
    }
}


/** Small green "✓ Verified" pill shown on listings whose landlord passed ID verification. */
@Composable
fun VerifiedBadge(modifier: Modifier = Modifier) {
    androidx.compose.material3.Text(
        "✓ Verified",
        modifier = modifier
            .padding(top = 4.dp)
            .clip(androidx.compose.foundation.shape.RoundedCornerShape(999.dp))
            .background(androidx.compose.ui.graphics.Color(0xFFE6F9F1))
            .padding(horizontal = 8.dp, vertical = 2.dp),
        color = androidx.compose.ui.graphics.Color(0xFF0E8A5B),
        fontSize = 10.5.sp,
        fontWeight = androidx.compose.ui.text.font.FontWeight.ExtraBold,
    )
}


/** Compact card for the Home "Fresh listings" row: photo, price, type · area, verified badge. */
@Composable
fun FreshCard(property: Property, modifier: Modifier = Modifier, onClick: () -> Unit) {
    val palette = LocalKejaPalette.current
    val rangi = palette.style == KejaThemeStyle.RANGI
    ThemedCard(modifier = modifier.width(172.dp).then(if (rangi) Modifier.padding(end = 6.dp, bottom = 7.dp) else Modifier), onClick = onClick) {
        Column(Modifier.width(172.dp)) {
            AsyncImage(
                model = resolveMediaUrl(property.main_image_url),
                contentDescription = property.title,
                contentScale = ContentScale.Crop,
                modifier = Modifier.fillMaxWidth().height(118.dp),
            )
            Column(Modifier.padding(horizontal = 11.dp, vertical = 9.dp)) {
                Text(formatKes(property.price), fontSize = 15.sp, fontWeight = FontWeight.ExtraBold, color = palette.text, maxLines = 1)
                Text(
                    "${property.property_type} · ${property.area ?: property.county}",
                    fontSize = 12.sp, color = palette.muted, maxLines = 1,
                    overflow = androidx.compose.ui.text.style.TextOverflow.Ellipsis,
                )
                if (property.landlord_verified) { VerifiedBadge() }
            }
        }
    }
}

/** Grey shimmer-less placeholder shown while listings load (instead of a blank page / lone spinner). */
@Composable
fun SkeletonCard(modifier: Modifier = Modifier, wide: Boolean = false) {
    val palette = LocalKejaPalette.current
    Column(
        modifier
            .then(if (wide) Modifier.fillMaxWidth() else Modifier.width(172.dp))
            .clip(KejaShapes.card)
            .background(palette.card)
            .border(1.dp, palette.border, KejaShapes.card)
    ) {
        Box(Modifier.fillMaxWidth().height(if (wide) 200.dp else 118.dp).background(palette.primaryLight))
        Spacer(Modifier.height(10.dp))
        Box(Modifier.padding(horizontal = 11.dp).fillMaxWidth().height(12.dp).clip(androidx.compose.foundation.shape.RoundedCornerShape(6.dp)).background(palette.primaryLight))
        Spacer(Modifier.height(8.dp))
        Box(Modifier.padding(horizontal = 11.dp).fillMaxWidth(0.55f).height(12.dp).clip(androidx.compose.foundation.shape.RoundedCornerShape(6.dp)).background(palette.primaryLight))
        Spacer(Modifier.height(12.dp))
    }
}
