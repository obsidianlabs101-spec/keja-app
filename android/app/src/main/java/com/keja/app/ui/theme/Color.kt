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

enum class KejaThemeStyle { PROFESSIONAL, RANGI }

data class KejaPalette(
    val bg: Color,
    val card: Color,
    val text: Color,
    val muted: Color,
    val border: Color,
    val primary: Color,
    val primaryDark: Color,
    val primaryLight: Color,
    val sun: Color = Color(0xFFFFCE4A),
    val mint: Color = Color(0xFF35E1B0),
    val coral: Color = Color(0xFFFF6B9A),
    val style: KejaThemeStyle = KejaThemeStyle.PROFESSIONAL,
    // Nav colors are explicit per-palette rather than computed ad-hoc in
    // the component — that's what caused the Rangi dark-mode bug (nav
    // background reused `text`, which is a LIGHT color in dark mode,
    // paired with light inactive icons = invisible against it).
    val navBg: Color = card,
    val navInactive: Color = muted,
    val navActiveBg: Color = Color.Transparent,
    val navActiveFg: Color = primary,
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
    style = KejaThemeStyle.PROFESSIONAL,
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
    style = KejaThemeStyle.PROFESSIONAL,
)

// Rangi — the web's playful theme (body.rangi block in style.css).
val RangiLightPalette = KejaPalette(
    bg = Color(0xFFFFF6E8),
    card = Color(0xFFFFFDF9),
    text = Color(0xFF1A1830),
    muted = Color(0xFF6C6880),
    border = Color(0xFFE4DCCE),
    primary = Color(0xFF7C5CFC),
    primaryDark = Color(0xFF5F3FF0),
    primaryLight = Color(0xFFEDE7FF),
    sun = Color(0xFFFFCE4A),
    mint = Color(0xFF35E1B0),
    coral = Color(0xFFFF6B9A),
    style = KejaThemeStyle.RANGI,
    // Matches body.rangi .bottom-nav / .nav-item / .nav-item.active exactly:
    // dark nav bar, warm off-white inactive icons, coral pill for the
    // active item with dark text on top of it.
    navBg = Color(0xFF1A1830),
    navInactive = Color(0xFFFFF6E8).copy(alpha = 0.6f),
    navActiveBg = Color(0xFFFF6B9A),
    navActiveFg = Color(0xFF1A1830),
)

val RangiDarkPalette = KejaPalette(
    bg = Color(0xFF100E1A),
    card = Color(0xFF1A1727),
    text = Color(0xFFF4EFFF),
    muted = Color(0xFFA49DBA),
    border = Color(0xFF2C2740),
    primary = Color(0xFFA48DFF),
    primaryDark = Color(0xFF7C5CFC),
    primaryLight = Color(0xFF241F3C),
    sun = Color(0xFFFFD873),
    mint = Color(0xFF4FE3BF),
    coral = Color(0xFFFF85B3),
    style = KejaThemeStyle.RANGI,
    // Matches body.rangi.dark .bottom-nav / .nav-item.active exactly.
    // IMPORTANT: this must NOT reuse `text` for the nav background —
    // `text` is a light color in dark mode, and pairing that with the
    // (also light) inactive icon color made the nav unreadable, which
    // is exactly the bug being fixed here.
    navBg = Color(0xE61A1727),
    navInactive = Color(0xFFFFF6E8).copy(alpha = 0.6f),
    navActiveBg = Color(0xFFFF85B3),
    navActiveFg = Color(0xFF14111F),
)

fun paletteFor(style: KejaThemeStyle, dark: Boolean): KejaPalette = when (style) {
    KejaThemeStyle.PROFESSIONAL -> if (dark) DarkPalette else LightPalette
    KejaThemeStyle.RANGI -> if (dark) RangiDarkPalette else RangiLightPalette
}

