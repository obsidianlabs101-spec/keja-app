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

@Composable
fun KejaTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    val palette = if (darkTheme) DarkPalette else LightPalette

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
