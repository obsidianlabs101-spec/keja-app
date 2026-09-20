package com.keja.app.ui.theme

import androidx.compose.material3.Typography
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

// The web app uses Inter via Google Fonts. Rather than bundling font
// files (adds build complexity for a design-parity pass), we map to the
// closest system sans-serif — visually very close to Inter's metrics —
// and keep the same weight/size scale used in style.css.
val KejaFontFamily = FontFamily.SansSerif

val KejaTypography = Typography(
    displayLarge = TextStyle(fontFamily = KejaFontFamily, fontWeight = FontWeight.ExtraBold, fontSize = 40.sp, letterSpacing = (-1.4).sp),
    headlineLarge = TextStyle(fontFamily = KejaFontFamily, fontWeight = FontWeight.ExtraBold, fontSize = 27.sp, letterSpacing = (-0.8).sp),
    headlineMedium = TextStyle(fontFamily = KejaFontFamily, fontWeight = FontWeight.Bold, fontSize = 20.sp),
    titleLarge = TextStyle(fontFamily = KejaFontFamily, fontWeight = FontWeight.Bold, fontSize = 18.sp),
    titleMedium = TextStyle(fontFamily = KejaFontFamily, fontWeight = FontWeight.SemiBold, fontSize = 15.sp),
    bodyLarge = TextStyle(fontFamily = KejaFontFamily, fontWeight = FontWeight.Normal, fontSize = 15.sp, lineHeight = 22.sp),
    bodyMedium = TextStyle(fontFamily = KejaFontFamily, fontWeight = FontWeight.Normal, fontSize = 13.sp),
    labelLarge = TextStyle(fontFamily = KejaFontFamily, fontWeight = FontWeight.Bold, fontSize = 14.sp),
    labelSmall = TextStyle(fontFamily = KejaFontFamily, fontWeight = FontWeight.SemiBold, fontSize = 9.sp),
)
