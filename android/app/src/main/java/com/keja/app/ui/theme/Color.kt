package com.keja.app.ui.theme

import androidx.compose.ui.graphics.Color

// Exact tokens from the web app's style.css :root and body.dark blocks —
// kept as a direct 1:1 mapping so the Android app doesn't drift from the
// website's look.
object KejaColors {
    val Primary = Color(0xFF6C4DFF)
    val PrimaryDark = Color(0xFF5137D9)
    val PrimaryLight = Color(0xFFEEE9FF)

    val Green = Color(0xFF22C55E)
    val Orange = Color(0xFFF59E0B)
    val Red = Color(0xFFEF4444)

    // Light theme
    val BgLight = Color(0xFFF8F8FC)
    val CardLight = Color(0xFFFFFFFF)
    val TextLight = Color(0xFF17171C)
    val MutedLight = Color(0xFF777784)
    val BorderLight = Color(0xFFE8E8EF)

    // Dark theme
    val BgDark = Color(0xFF0D0D12)
    val CardDark = Color(0xFF17171F)
    val TextDark = Color(0xFFF7F7FA)
    val MutedDark = Color(0xFF9999A7)
    val BorderDark = Color(0xFF292934)
    val PrimaryLightDark = Color(0xFF28223F)

    val AvailableBg = Color(0xFFEAF9EF)
    val AvailableText = Color(0xFF159447)
    val BookedBg = Color(0xFFFFF0F0)
    val BookedText = Color(0xFFC92D2D)
}

data class KejaPalette(
    val bg: Color,
    val card: Color,
    val text: Color,
    val muted: Color,
    val border: Color,
    val primary: Color,
    val primaryDark: Color,
    val primaryLight: Color,
)

val LightPalette = KejaPalette(
    bg = KejaColors.BgLight,
    card = KejaColors.CardLight,
    text = KejaColors.TextLight,
    muted = KejaColors.MutedLight,
    border = KejaColors.BorderLight,
    primary = KejaColors.Primary,
    primaryDark = KejaColors.PrimaryDark,
    primaryLight = KejaColors.PrimaryLight,
)

val DarkPalette = KejaPalette(
    bg = KejaColors.BgDark,
    card = KejaColors.CardDark,
    text = KejaColors.TextDark,
    muted = KejaColors.MutedDark,
    border = KejaColors.BorderDark,
    primary = KejaColors.Primary,
    primaryDark = KejaColors.PrimaryDark,
    primaryLight = KejaColors.PrimaryLightDark,
)
