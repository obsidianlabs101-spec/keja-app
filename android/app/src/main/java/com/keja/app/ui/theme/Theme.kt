package com.keja.app.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.compositionLocalOf
import androidx.compose.ui.graphics.Color

val LocalKejaPalette = compositionLocalOf { LightPalette }

/**
 * @param darkOverride null = follow the system setting (like the web app
 * does by default); true/false = the user explicitly picked one in
 * Profile, and that always wins over the system setting.
 */
@Composable
fun KejaTheme(
    themeStyle: KejaThemeStyle = KejaThemeStyle.PROFESSIONAL,
    darkOverride: Boolean? = null,
    content: @Composable () -> Unit,
) {
    val darkTheme = darkOverride ?: isSystemInDarkTheme()
    val palette = paletteFor(themeStyle, darkTheme)

    val colorScheme = if (darkTheme) {
        darkColorScheme(
            primary = palette.primary,
            onPrimary = Color.White,
            background = palette.bg,
            surface = palette.card,
            onBackground = palette.text,
            onSurface = palette.text,
            outline = palette.border,
        )
    } else {
        lightColorScheme(
            primary = palette.primary,
            onPrimary = Color.White,
            background = palette.bg,
            surface = palette.card,
            onBackground = palette.text,
            onSurface = palette.text,
            outline = palette.border,
        )
    }

    CompositionLocalProvider(LocalKejaPalette provides palette) {
        MaterialTheme(
            colorScheme = colorScheme,
            typography = KejaTypography,
            shapes = KejaMaterialShapes,
            content = content,
        )
    }
}
