package com.keja.app.ui.nav

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.layout.imePadding
import androidx.compose.material3.Scaffold
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import androidx.navigation.NavType
import com.keja.app.data.AppContainer
import com.keja.app.ui.components.*
import com.keja.app.ui.screens.*

private const val ROUTE_AUTH = "auth"
private const val ROUTE_HOME = "home"
private const val ROUTE_DISCOVER = "discover"
private const val ROUTE_INTERESTED = "interested"
private const val ROUTE_MY_LISTINGS = "my-listings"
private const val ROUTE_ALERTS = "alerts"
private const val ROUTE_PROFILE = "profile"
private const val ROUTE_PROPERTY = "property/{id}"
private const val ROUTE_LANDLORD_PROFILE = "landlord-profile/{id}"
private const val ROUTE_LANDLORD_DASHBOARD = "landlord-dashboard"
private const val ROUTE_ADMIN_HOME = "admin-home"
private const val ROUTE_ADMIN_NEW = "admin-new"
private const val ROUTE_ADMIN_LANDLORDS = "admin-landlords"
private const val ROUTE_ADMIN_PAYMENTS = "admin-payments"
private const val ROUTE_ADMIN_LISTINGS = "admin-listings"
private const val ROUTE_ADMIN_ADS = "admin-ads"

@Composable
fun KejaNavGraph() {
    val navController = rememberNavController()
    val context = LocalContext.current
    val repo = remember { AppContainer.repository(context) }
    val user by repo.currentUser.collectAsState()
    val backStackEntry by navController.currentBackStackEntryAsState()
    val currentRoute = backStackEntry?.destination?.route

    val bottomRoutes = listOf(
        ROUTE_HOME, ROUTE_DISCOVER, ROUTE_INTERESTED, ROUTE_MY_LISTINGS, ROUTE_PROFILE,
        ROUTE_ADMIN_HOME, ROUTE_ADMIN_NEW, ROUTE_ADMIN_LANDLORDS, ROUTE_ADMIN_PAYMENTS, ROUTE_ADMIN_LISTINGS,
    )
    val showBottomBar = currentRoute in bottomRoutes

    val navItems = when {
        user?.is_admin == true -> adminNavItems
        user?.is_host == true -> landlordNavItems
        else -> renterNavItems
    }
    var badges by remember { mutableStateOf<Map<String, Int>>(emptyMap()) }
    LaunchedEffect(user?.id, user?.is_admin) {
        if (user?.is_admin == true) {
            while (true) {
                val o = runCatching { repo.adminOverview() }.getOrNull()
                if (o != null) {
                    badges = mapOf(
                        ROUTE_ADMIN_NEW to o.unreviewed_properties,
                        ROUTE_ADMIN_LANDLORDS to o.pending_landlords,
                        ROUTE_ADMIN_PAYMENTS to o.pending_payments,
                    )
                }
                kotlinx.coroutines.delay(60000)
            }
        } else {
            badges = emptyMap()
        }
    }

    // An admin account has no need for the renter/landlord pages — redirect
    // straight to the admin overview if one of those routes is somehow hit.
    LaunchedEffect(currentRoute, user?.is_admin) {
        if (user?.is_admin == true && currentRoute in listOf(ROUTE_HOME, ROUTE_DISCOVER, ROUTE_INTERESTED, ROUTE_MY_LISTINGS)) {
            navController.navigate(ROUTE_ADMIN_HOME) { popUpTo(0) }
        }
    }

    Scaffold(
        bottomBar = {
            if (showBottomBar) {
                KejaBottomNav(currentRoute = currentRoute, items = navItems, badges = badges) { route ->
                    navController.navigate(route) {
                        popUpTo(navItems.first().route) { saveState = true }
                        launchSingleTop = true
                        restoreState = true
                    }
                }
            }
        },
    ) { padding ->
        NavHost(
            navController = navController,
            startDestination = ROUTE_HOME,
            modifier = Modifier.padding(padding).imePadding(),
        ) {
            composable(ROUTE_AUTH) {
                AuthScreen(onAuthenticated = { navController.popBackStack() })
            }
            composable(ROUTE_HOME) {
                HomeScreen(
                    onOpenProperty = { id -> navController.navigate("property/$id") },
                    onOpenAlerts = { navController.navigate(ROUTE_ALERTS) },
                )
            }
            composable(ROUTE_DISCOVER) {
                DiscoverScreen(
                    isLoggedIn = user != null,
                    onRequireLogin = { navController.navigate(ROUTE_AUTH) },
                    onOpenProperty = { id -> navController.navigate("property/$id") },
                    onOpenLandlord = { id -> navController.navigate("landlord-profile/$id") },
                )
            }
            composable(ROUTE_INTERESTED) {
                InterestedScreen(
                    isLoggedIn = user != null,
                    onRequireLogin = { navController.navigate(ROUTE_AUTH) },
                    onOpenProperty = { id -> navController.navigate("property/$id") },
                )
            }
            composable(ROUTE_MY_LISTINGS) {
                MyListingsScreen(
                    onOpenProperty = { id -> navController.navigate("property/$id") },
                    onAddProperty = { navController.navigate(ROUTE_LANDLORD_DASHBOARD) },
                )
            }
            composable(ROUTE_ALERTS) {
                AlertsScreen(
                    isLoggedIn = user != null,
                    onRequireLogin = { navController.navigate(ROUTE_AUTH) },
                    onOpenProperty = { id -> navController.navigate("property/$id") },
                )
            }
            composable(ROUTE_PROFILE) {
                ProfileScreen(
                    onRequireLogin = { navController.navigate(ROUTE_AUTH) },
                    onOpenLandlordDashboard = { navController.navigate(ROUTE_LANDLORD_DASHBOARD) },
                    onOpenAdminDashboard = { navController.navigate(ROUTE_ADMIN_HOME) },
                    onLoggedOut = { navController.navigate(ROUTE_HOME) { popUpTo(0) } },
                )
            }
            composable(
                ROUTE_PROPERTY,
                arguments = listOf(navArgument("id") { type = NavType.StringType }),
            ) { entry ->
                val id = entry.arguments?.getString("id") ?: return@composable
                PropertyDetailScreen(
                    propertyId = id,
                    onBack = { navController.popBackStack() },
                    onRequireLogin = { navController.navigate(ROUTE_AUTH) },
                    onOpenLandlord = { lid -> navController.navigate("landlord-profile/$lid") },
                )
            }
            composable(
                ROUTE_LANDLORD_PROFILE,
                arguments = listOf(navArgument("id") { type = NavType.StringType }),
            ) { entry ->
                val id = entry.arguments?.getString("id") ?: return@composable
                LandlordProfileScreen(
                    landlordId = id,
                    onBack = { navController.popBackStack() },
                    onOpenProperty = { pid -> navController.navigate("property/$pid") },
                )
            }
            composable(ROUTE_LANDLORD_DASHBOARD) {
                if (user == null) {
                    LaunchedEffect(Unit) { navController.navigate(ROUTE_AUTH) }
                } else {
                    LandlordDashboardScreen(
                        onBack = { navController.popBackStack() },
                        onOpenPublicProfile = { lid -> navController.navigate("landlord-profile/$lid") },
                    )
                }
            }
            composable(ROUTE_ADMIN_HOME) {
                if (user?.is_admin != true) { LaunchedEffect(Unit) { navController.popBackStack() } }
                else AdminOverviewScreen(onOpen = { navController.navigate(it) })
            }
            composable(ROUTE_ADMIN_NEW) {
                if (user?.is_admin != true) { LaunchedEffect(Unit) { navController.popBackStack() } }
                else AdminNewListingsScreen()
            }
            composable(ROUTE_ADMIN_LANDLORDS) {
                if (user?.is_admin != true) { LaunchedEffect(Unit) { navController.popBackStack() } }
                else AdminLandlordsScreen()
            }
            composable(ROUTE_ADMIN_PAYMENTS) {
                if (user?.is_admin != true) { LaunchedEffect(Unit) { navController.popBackStack() } }
                else AdminPaymentsScreen()
            }
            composable(ROUTE_ADMIN_LISTINGS) {
                if (user?.is_admin != true) { LaunchedEffect(Unit) { navController.popBackStack() } }
                else AdminListingsScreen()
            }
            composable(ROUTE_ADMIN_ADS) {
                if (user?.is_admin != true) { LaunchedEffect(Unit) { navController.popBackStack() } }
                else AdminAdsScreen()
            }
        }
    }
}
