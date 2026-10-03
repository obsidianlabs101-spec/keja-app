package com.keja.app.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.keja.app.data.AppContainer
import com.keja.app.data.model.AdminCatalogResponse
import com.keja.app.ui.components.AdminPage
import com.keja.app.ui.components.KejaLoader
import com.keja.app.ui.components.KejaPrimaryButton
import com.keja.app.ui.components.KejaSurface
import com.keja.app.ui.components.KejaTextField
import com.keja.app.ui.theme.LocalKejaPalette
import kotlinx.coroutines.launch

private val GROUP_LABELS = mapOf(
    "apartments" to "Apartments",
    "hostels" to "Hostels",
    "airbnb" to "Airbnb",
    "commercial" to "Shops / Commercial",
)

/** Admin: add house categories (Bungalow, Maisonette…) and keyword locations (Kilimani…). */
@Composable
fun AdminCatalogScreen() {
    val palette = LocalKejaPalette.current
    val context = LocalContext.current
    val repo = remember { AppContainer.repository(context) }
    val scope = rememberCoroutineScope()

    var data by remember { mutableStateOf<AdminCatalogResponse?>(null) }
    var message by remember { mutableStateOf<String?>(null) }
    var newCategory by remember { mutableStateOf("") }
    var newGroup by remember { mutableStateOf("apartments") }
    var newLocation by remember { mutableStateOf("") }
    var renaming by remember { mutableStateOf<Pair<String, String>?>(null) } // id to current text

    fun reload() { scope.launch { data = runCatching { repo.adminCatalog() }.getOrNull() } }
    fun act(okMsg: String? = null, block: suspend () -> Unit) {
        scope.launch {
            runCatching { block() }
                .onSuccess { message = okMsg; reload(); runCatching { repo.refreshCatalog() } }
                .onFailure { message = it.message ?: "Something went wrong" }
        }
    }
    LaunchedEffect(Unit) { reload() }

    AdminPage("KEJA ADMIN", "Categories & locations", "Add house types like Bungalow or Maisonette, and the keyword locations people tap on Home.") {
        message?.let { Text(it, color = palette.primary, fontSize = 12.sp); Spacer(Modifier.height(8.dp)) }
        val d = data
        if (d == null) { KejaLoader(size = 48.dp); return@AdminPage }

        // ---------------- add a category
        KejaSurface(Modifier.fillMaxWidth()) {
            Text("Add a category", fontWeight = FontWeight.Bold, color = palette.text)
            Spacer(Modifier.height(8.dp))
            KejaTextField(newCategory, { newCategory = it }, "e.g. Bungalow")
            Spacer(Modifier.height(8.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp), modifier = Modifier.fillMaxWidth()) {
                d.groups.forEach { g ->
                    FilterChip(selected = newGroup == g, onClick = { newGroup = g }, label = { Text(GROUP_LABELS[g] ?: g, fontSize = 11.sp, maxLines = 1) })
                }
            }
            Spacer(Modifier.height(8.dp))
            KejaPrimaryButton(text = "Add category", modifier = Modifier.fillMaxWidth(), onClick = {
                val n = newCategory.trim()
                if (n.isNotEmpty()) act("Category added") { repo.adminAddCategory(n, newGroup); newCategory = "" }
            })
            Spacer(Modifier.height(6.dp))
            Text("The group decides which Home chip its listings appear under.", fontSize = 11.sp, color = palette.muted)
        }

        // ---------------- categories by group
        d.groups.forEach { g ->
            Spacer(Modifier.height(18.dp))
            Text(GROUP_LABELS[g] ?: g, fontWeight = FontWeight.ExtraBold, fontSize = 17.sp, color = palette.text)
            Spacer(Modifier.height(8.dp))
            val rows = d.categories.filter { it.group == g }
            if (rows.isEmpty()) Text("None yet", fontSize = 12.sp, color = palette.muted)
            rows.forEach { c ->
                KejaSurface(Modifier.fillMaxWidth().padding(bottom = 2.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f)) {
                            Text(c.name + if (c.active) "" else "  (hidden)", fontWeight = FontWeight.Bold, color = palette.text)
                            Text("${c.listings} listing${if (c.listings == 1) "" else "s"}", fontSize = 11.sp, color = palette.muted)
                        }
                    }
                    Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                        TextButton(onClick = { renaming = c.id to c.name }) { Text("Rename") }
                        TextButton(onClick = { act { repo.adminSetCategoryActive(c.id, !c.active) } }) { Text(if (c.active) "Hide" else "Show") }
                        if (c.listings == 0) TextButton(onClick = { act("Deleted") { repo.adminDeleteCategory(c.id) } }) { Text("Delete", color = androidx.compose.ui.graphics.Color(0xFFEF4444)) }
                    }
                }
            }
        }

        // ---------------- keyword locations
        Spacer(Modifier.height(24.dp))
        Text("Keyword locations", fontWeight = FontWeight.ExtraBold, fontSize = 17.sp, color = palette.text)
        Text("Shown as Popular areas on Home, and as suggestions when landlords type a listing's location.", fontSize = 11.sp, color = palette.muted)
        Spacer(Modifier.height(8.dp))
        KejaSurface(Modifier.fillMaxWidth()) {
            KejaTextField(newLocation, { newLocation = it }, "e.g. Kileleshwa")
            Spacer(Modifier.height(8.dp))
            KejaPrimaryButton(text = "Add location", modifier = Modifier.fillMaxWidth(), onClick = {
                val n = newLocation.trim()
                if (n.isNotEmpty()) act("Location added") { repo.adminAddLocation(n); newLocation = "" }
            })
        }
        Spacer(Modifier.height(10.dp))
        d.locations.forEach { l ->
            KejaSurface(Modifier.fillMaxWidth().padding(bottom = 2.dp), contentPadding = PaddingValues(horizontal = 14.dp, vertical = 8.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(l.name + if (l.active) "" else "  (hidden)", Modifier.weight(1f), fontWeight = FontWeight.Bold, color = palette.text)
                    TextButton(onClick = { act { repo.adminSetLocationActive(l.id, !l.active) } }) { Text(if (l.active) "Hide" else "Show") }
                    TextButton(onClick = { act("Deleted") { repo.adminDeleteLocation(l.id) } }) { Text("Delete", color = androidx.compose.ui.graphics.Color(0xFFEF4444)) }
                }
            }
        }
        Spacer(Modifier.height(24.dp))
    }

    renaming?.let { (id, current) ->
        var text by remember(id) { mutableStateOf(current) }
        AlertDialog(
            onDismissRequest = { renaming = null },
            title = { Text("Rename category") },
            text = { KejaTextField(text, { text = it }, "Name") },
            confirmButton = {
                TextButton(onClick = {
                    val n = text.trim()
                    renaming = null
                    if (n.isNotEmpty() && n != current) act("Renamed") { repo.adminRenameCategory(id, n) }
                }) { Text("Save") }
            },
            dismissButton = { TextButton(onClick = { renaming = null }) { Text("Cancel") } },
        )
    }
}
