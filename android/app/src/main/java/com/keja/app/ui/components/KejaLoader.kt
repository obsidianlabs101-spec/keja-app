package com.keja.app.ui.components

import androidx.compose.animation.core.CubicBezierEasing
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.size
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.graphics.drawscope.scale
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.keja.app.ui.theme.LocalKejaPalette

/**
 * Keja brand loader (from the brand kit): a diamond orbits a house while the
 * door opens and closes. Drawn on a 160x160 grid so it matches keja-loader.svg
 * exactly. Use instead of the default Material spinner.
 */
@Composable
fun KejaLoader(modifier: Modifier = Modifier, size: Dp = 64.dp, label: String? = null) {
    val palette = LocalKejaPalette.current
    val dark = palette.bg.luminance() < 0.5f
    val transition = rememberInfiniteTransition(label = "keja-loader")
    val turn by transition.animateFloat(
        initialValue = 0f,
        targetValue = 360f,
        animationSpec = infiniteRepeatable(tween(1400, easing = CubicBezierEasing(0.65f, 0.05f, 0.35f, 1f))),
        label = "turn",
    )
    val door by transition.animateFloat(
        initialValue = 0.2f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(tween(700, easing = FastOutSlowInEasing), RepeatMode.Reverse),
        label = "door",
    )

    val track = if (dark) Color(0x408B5CF6) else Color(0xFFEDE9FE)
    val home = if (dark) Color(0xFF8B5CF6) else Color(0xFF6D28D9)

    Column(modifier, horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Canvas(Modifier.size(size)) {
            val s = this.size.width / 160f
            fun o(x: Float, y: Float) = Offset(x * s, y * s)

            drawCircle(track, radius = 54f * s, center = o(80f, 80f), style = Stroke(width = 8f * s))

            rotate(turn, pivot = o(80f, 80f)) {
                val diamond = Path().apply {
                    moveTo(80f * s, 17f * s); lineTo(91f * s, 27f * s); lineTo(80f * s, 37f * s); lineTo(69f * s, 27f * s); close()
                }
                drawPath(diamond, Color(0xFF8B5CF6))
            }

            val house = Path().apply {
                moveTo(47f * s, 75f * s); lineTo(80f * s, 47f * s); lineTo(113f * s, 75f * s)
                lineTo(113f * s, 116f * s); lineTo(47f * s, 116f * s); close()
            }
            drawPath(house, home)

            scale(scaleX = door, scaleY = 1f, pivot = o(62f, 91f)) {
                drawRoundRect(
                    Color(0xFFFF6B5B).copy(alpha = 0.45f + 0.55f * ((door - 0.2f) / 0.8f)),
                    topLeft = o(62f, 79f),
                    size = Size(36f * s, 37f * s),
                    cornerRadius = CornerRadius(4f * s),
                )
            }
            drawCircle(Color(0xFFFFF7F5), radius = 3f * s, center = o(91f, 98f))
        }
        if (label != null) {
            Text(label, color = palette.text, fontSize = 14.sp, fontWeight = FontWeight.SemiBold)
        }
    }
}
