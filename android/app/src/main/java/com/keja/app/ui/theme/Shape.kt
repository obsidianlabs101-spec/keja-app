package com.keja.app.ui.theme

import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Shapes
import androidx.compose.ui.unit.dp

// Mirrors the radii actually used in style.css: 12px buttons, 17-18px
// search/category cards, 20px property cards, 22-24px modals/pills.
object KejaShapes {
    val button = RoundedCornerShape(12.dp)
    val searchBar = RoundedCornerShape(17.dp)
    val card = RoundedCornerShape(20.dp)
    val modal = RoundedCornerShape(24.dp)
    val pill = RoundedCornerShape(999.dp)
    val propertyImage = RoundedCornerShape(topStart = 20.dp, topEnd = 20.dp)
}

val KejaMaterialShapes = Shapes(
    extraSmall = RoundedCornerShape(8.dp),
    small = RoundedCornerShape(12.dp),
    medium = RoundedCornerShape(17.dp),
    large = RoundedCornerShape(20.dp),
    extraLarge = RoundedCornerShape(24.dp),
)
