package com.keja.app.data

import com.keja.app.data.model.CatalogCategory

/**
 * In-memory copy of the admin-managed categories and keyword locations.
 * Filled by KejaRepository.refreshCatalog() (Home, the add-listing form).
 * Until it loads — or if the phone is offline — the original built-in lists
 * are used so nothing ever looks empty.
 */
object Catalog {
    @Volatile var categories: List<CatalogCategory> = emptyList()
    @Volatile var locations: List<String> = emptyList()

    private val commercialDefaults = listOf("Shop", "Office", "Warehouse", "Commercial")

    val defaultAreas = listOf("Kilimani", "Westlands", "Roysambu", "Lavington", "Kasarani", "Ruaka", "Juja")
    fun areas(): List<String> = locations.ifEmpty { defaultAreas }

    /** Which Home group a property type belongs to (apartments | hostels | airbnb | commercial). */
    fun groupOf(type: String): String {
        categories.firstOrNull { it.name == type }?.let { return it.group }
        return when {
            type == "Airbnb" -> "airbnb"
            type == "Hostel" -> "hostels"
            type in commercialDefaults -> "commercial"
            else -> "apartments"
        }
    }

    /** Active type names a landlord can pick for a group. */
    fun typesFor(group: String): List<String> {
        val live = categories.filter { it.group == group && it.active }.map { it.name }
        if (live.isNotEmpty() || categories.isNotEmpty()) return live
        return when (group) {
            "apartments" -> listOf("Bedsitter", "Studio", "1 Bedroom", "2 Bedroom", "3+ Bedroom", "House")
            "hostels" -> listOf("Hostel")
            "airbnb" -> listOf("Airbnb")
            else -> commercialDefaults
        }
    }
}
