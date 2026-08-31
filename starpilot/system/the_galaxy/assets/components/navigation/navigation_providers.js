import {
  getCoordinatesFromSearch,
  getMapboxSearchContext,
  getRoutes,
} from "./navigation_utilities.js";

function isLikelyKoreanEnvironment(state) {
  return String(state.language || "").trim().toLowerCase().startsWith("main_ko")
    || String(state.language || "").trim().toLowerCase().startsWith("ko")
    || (Number.isFinite(Number(state.lastPosition?.latitude)) && Number.isFinite(Number(state.lastPosition?.longitude))
      && Number(state.lastPosition.latitude) >= 32.5
      && Number(state.lastPosition.latitude) <= 38.9
      && Number(state.lastPosition.longitude) >= 124.5
      && Number(state.lastPosition.longitude) <= 131.0);
}

function createBrowserLanguages() {
  if (typeof navigator === "undefined") return [];
  return navigator.languages || [navigator.language];
}

function buildSearchContext(language, lastPosition, query) {
  const context = getMapboxSearchContext(query, lastPosition, [language, ...createBrowserLanguages()]);
  if (lastPosition) {
    context.proximity = `${lastPosition.longitude},${lastPosition.latitude}`;
  }
  return context;
}

function getMapboxSuggestParams(state, query, sessionToken) {
  return new URLSearchParams({
    access_token: state.mapboxPublic,
    session_token: sessionToken,
    q: query,
    limit: 4,
    ...buildSearchContext(state.language, state.lastPosition, query),
  });
}

function getActiveSearchProvider(state) {
  if (state.searchProvider === "tmap" && state.hasTmapKey) {
    return "tmap";
  }
  if (state.searchProvider === "amap" && state.amap1Key && state.amap2Key) {
    return "amap";
  }
  return state.mapboxPublic ? "mapbox" : "";
}

function normalizeDestinationProvider(provider) {
  const normalized = String(provider || "").trim().toLowerCase();
  if (normalized === "tmap") return "tmap";
  if (normalized === "mapbox") return "mapbox";
  return "";
}

export function getDefaultSearchProvider(state) {
  if (state.hasTmapKey && isLikelyKoreanEnvironment(state)) return "tmap";
  if (state.mapboxPublic) return "mapbox";
  if (state.hasTmapKey) return "tmap";
  if (state.amap1Key && state.amap2Key) return "amap";
  return "";
}

export async function fetchSuggestionsForProvider(state, query, sessionToken) {
  const provider = getActiveSearchProvider(state);

  if (provider === "tmap") {
    try {
      const url = new URL("/api/navigation/search", window.location.origin);
      url.searchParams.set("provider", "tmap");
      url.searchParams.set("q", query);
      const response = await fetch(url);
      const data = await response.json();
      const suggestions = Array.isArray(data?.suggestions) ? data.suggestions : [];
      if (suggestions.length > 0 || !state.mapboxPublic) return suggestions;
    } catch {
      if (!state.mapboxPublic) return [];
    }
  }

  if (provider === "mapbox") {
    const params = getMapboxSuggestParams(state, query, sessionToken);
    const response = await fetch(`https://api.mapbox.com/search/searchbox/v1/suggest?${params}`);
    const data = await response.json();
    return Array.isArray(data?.suggestions) ? data.suggestions : [];
  }

  if (provider === "amap" && typeof AMap !== "undefined") {
    return await new Promise((resolve) => {
      const auto = new AMap.Autocomplete({ city: "auto" });
      auto.search(query, (status, result) => {
        if (status === "complete" && Array.isArray(result?.tips)) {
          resolve(result.tips);
          return;
        }
        resolve([]);
      });
    });
  }

  return [];
}

export async function resolveSuggestionToDestination(state, suggestion, sessionToken) {
  const provider = normalizeDestinationProvider(suggestion?.provider) || getActiveSearchProvider(state);
  const label = suggestion.full_address || suggestion.name || suggestion.address || "Unnamed Location";

  const savedLatitude = Number(suggestion.latitude);
  const savedLongitude = Number(suggestion.longitude);
  if (Number.isFinite(savedLatitude) && Number.isFinite(savedLongitude)) {
    const destination = {
      latitude: savedLatitude,
      longitude: savedLongitude,
      name: suggestion.name || label,
      routeId: suggestion.routeId || null,
    };
    if (provider) destination.provider = provider;
    return destination;
  }

  if (provider === "amap" && suggestion.location) {
    return {
      latitude: suggestion.location.lat,
      longitude: suggestion.location.lng,
      name: label,
      routeId: null,
    };
  }

  let coordinates = null;
  if (suggestion.geometry && Array.isArray(suggestion.geometry.coordinates)) {
    coordinates = suggestion.geometry.coordinates;
  } else if (suggestion.mapbox_id && state.mapboxPublic) {
    const url = new URL(`https://api.mapbox.com/search/searchbox/v1/retrieve/${encodeURIComponent(suggestion.mapbox_id)}`);
    url.searchParams.set("access_token", state.mapboxPublic);
    url.searchParams.set("session_token", sessionToken);
    const response = await fetch(url);
    const data = await response.json();
    coordinates = data?.features?.[0]?.geometry?.coordinates || null;
  } else if (state.mapboxPublic) {
    coordinates = await getCoordinatesFromSearch(
      label,
      state.mapboxPublic,
      buildSearchContext(state.language, state.lastPosition, label)
    );
  }

  if (!Array.isArray(coordinates) || coordinates.length !== 2) {
    throw new Error("Could not determine location.");
  }

  const destination = {
    latitude: coordinates[1],
    longitude: coordinates[0],
    name: label,
    routeId: null,
  };
  if (provider === "tmap" || provider === "mapbox") destination.provider = provider;
  return destination;
}

export async function fetchRoutesForDestination(state, destination) {
  if (!state.lastPosition) {
    throw new Error("Current location unavailable.");
  }

  const provider = normalizeDestinationProvider(destination?.provider) || getActiveSearchProvider(state);

  if (provider === "tmap" && state.hasTmapKey) {
    try {
      const response = await fetch("/api/navigation/route", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider: "tmap",
          start: {
            longitude: state.lastPosition.longitude,
            latitude: state.lastPosition.latitude,
            name: "Current Location",
          },
          destination: {
            longitude: destination.longitude,
            latitude: destination.latitude,
            name: destination.name,
          },
        }),
      });
      const data = await response.json();
      const routes = Array.isArray(data?.routes) ? data.routes : [];
      if (routes.length > 0) return routes;
    } catch {
      if (!state.mapboxPublic) throw new Error("Routing provider unavailable.");
    }
  }

  if (!state.mapboxPublic) {
    throw new Error("Routing provider unavailable.");
  }

  const start = `${state.lastPosition.longitude},${state.lastPosition.latitude}`;
  const end = `${destination.longitude},${destination.latitude}`;
  return getRoutes(start, end, state.mapboxPublic);
}

export async function fetchRouteHazards(route) {
  if (!route?.geometry?.coordinates?.length) return [];

  try {
    const response = await fetch("/api/navigation/hazards", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ route }),
    });
    const data = await response.json();
    return Array.isArray(data?.hazards) ? data.hazards : [];
  } catch {
    return [];
  }
}
