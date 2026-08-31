import json
import sys

from openpilot.common.params import ParamKeyType

from test_dashboard_stats import MODULE_DIR, _install_server_import_stubs


def _load_server_module():
  import importlib.util

  favorite_slots_name = "openpilot.starpilot.common.favorite_slots"
  previous_favorite_slots = sys.modules.get(favorite_slots_name)
  _install_server_import_stubs()
  try:
    spec = importlib.util.spec_from_file_location("navigation_params_server", MODULE_DIR / "the_galaxy.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
  finally:
    if previous_favorite_slots is None:
      sys.modules.pop(favorite_slots_name, None)
    else:
      sys.modules[favorite_slots_name] = previous_favorite_slots


the_galaxy = _load_server_module()


class FakeParamsBackend:
  def __init__(self, key_types=None, default_values=None, values=None):
    self.key_types = key_types or {}
    self.default_values = default_values or {}
    self.values = values or {}
    self.writes = []

  def get_key_type(self, key):
    return self.key_types[key]

  def get_default_value(self, key):
    return self.default_values.get(key)

  def put(self, key, value):
    self.writes.append((key, value))
    self.values[key] = value

  def put_bool(self, key, value):
    self.writes.append((key, bool(value)))
    self.values[key] = bool(value)

  def get(self, key, block=False):
    return self.values.get(key)


class WritableFakeParams:
  def __init__(self, values=None):
    self.values = dict(values or {})
    self.writes = []
    self.removals = []

  def get(self, key, encoding=None, default=None, block=False):
    del encoding, block
    return self.values.get(key, default)

  def get_bool(self, key):
    value = self.values.get(key, False)
    if isinstance(value, bool):
      return value
    return str(value).strip().lower() in ("1", "true", "yes", "on")

  def put(self, key, value):
    self.writes.append((key, value))
    self.values[key] = value

  def put_bool(self, key, value):
    self.writes.append((key, bool(value)))
    self.values[key] = bool(value)

  def get_int(self, key, default=0):
    return int(self.values.get(key, default))

  def put_int(self, key, value):
    self.writes.append((key, int(value)))
    self.values[key] = int(value)

  def remove(self, key):
    self.removals.append(key)
    self.values.pop(key, None)


def _params_client(monkeypatch, values, device_type):
  fake_params = WritableFakeParams(values)
  monkeypatch.setattr(the_galaxy, "params", fake_params)
  monkeypatch.setattr(
    the_galaxy,
    "_get_param_type_info",
    lambda: (
      {"AlphaLongitudinalEnabled", "ForceOffroad"},
      {
        "AlphaLongitudinalEnabled": bool,
        "ForceOffroad": bool,
      },
    ),
  )
  monkeypatch.setattr(the_galaxy.HARDWARE, "get_device_type", lambda: device_type)
  monkeypatch.setattr(the_galaxy.Paths, "comma_home", lambda: "/tmp/dashboard-test-home", raising=False)

  assert the_galaxy._import_galaxy_web_symbols()
  app = the_galaxy.Flask(f"params_test_{device_type}")
  the_galaxy.setup(app)
  return app.test_client(), fake_params


def test_params_compat_accepts_json_strings_for_json_keys():
  backend = FakeParamsBackend(
    key_types={"FavoriteDestinations": ParamKeyType.JSON},
    default_values={"FavoriteDestinations": []},
  )
  compat = the_galaxy.ParamsCompat(backend)

  compat.put("FavoriteDestinations", json.dumps([{"name": "Home"}]))

  assert backend.writes == [("FavoriteDestinations", [{"name": "Home"}])]


def test_params_compat_syncs_lead_indicator_inverse_key():
  backend = FakeParamsBackend()
  compat = the_galaxy.ParamsCompat(backend)

  compat.put_bool("LeadIndicator", True)

  assert backend.writes == [("LeadIndicator", True), ("HideLeadMarker", False)]


def test_params_compat_syncs_hide_lead_marker_inverse_key():
  backend = FakeParamsBackend()
  compat = the_galaxy.ParamsCompat(backend)

  compat.put_bool("HideLeadMarker", True)

  assert backend.writes == [("HideLeadMarker", True), ("LeadIndicator", False)]


def test_navigation_last_position_uses_recent_persisted_fix(monkeypatch):
  recent_payload = json.dumps({
    "latitude": 41.0,
    "longitude": -87.0,
    "hasFix": True,
    "updatedAtSec": 10_000.0,
  })
  memory_backend = FakeParamsBackend(values={"LastGPSPosition": ""})
  persisted_backend = FakeParamsBackend(values={"LastGPSPosition": recent_payload})

  monkeypatch.setattr(the_galaxy, "params_memory", the_galaxy.ParamsCompat(memory_backend))
  monkeypatch.setattr(the_galaxy, "params", the_galaxy.ParamsCompat(persisted_backend))
  monkeypatch.setattr(the_galaxy.time, "time", lambda: 10_300.0)
  monkeypatch.setattr(the_galaxy, "system_time_valid", lambda: True)

  position = the_galaxy._get_navigation_last_position()

  assert position["latitude"] == 41.0
  assert position["longitude"] == -87.0


def test_navigation_last_position_rejects_stale_persisted_fix(monkeypatch):
  stale_payload = json.dumps({
    "latitude": 41.0,
    "longitude": -87.0,
    "hasFix": True,
    "updatedAtSec": 10_000.0,
  })
  memory_backend = FakeParamsBackend(values={"LastGPSPosition": ""})
  persisted_backend = FakeParamsBackend(values={"LastGPSPosition": stale_payload})

  monkeypatch.setattr(the_galaxy, "params_memory", the_galaxy.ParamsCompat(memory_backend))
  monkeypatch.setattr(the_galaxy, "params", the_galaxy.ParamsCompat(persisted_backend))
  monkeypatch.setattr(the_galaxy.time, "time", lambda: 10_000.0 + the_galaxy.NAVIGATION_PERSISTED_LOCATION_MAX_AGE_SECONDS + 1.0)
  monkeypatch.setattr(the_galaxy, "system_time_valid", lambda: True)

  assert the_galaxy._get_navigation_last_position() is None


def test_navigation_endpoint_includes_tmap_key(monkeypatch):
  client, _ = _params_client(monkeypatch, {
    "AMapKey1": "",
    "AMapKey2": "",
    "MapboxPublicKey": "pk.test",
    "MapboxSecretKey": "sk.test",
    "TMapApiKey": "tmap-test-key",
    "ApiCache_NavDestinations": "[]",
    "LanguageSetting": "main_ko",
    "IsMetric": True,
  }, "tici")
  monkeypatch.setattr(the_galaxy, "_get_navigation_last_position", lambda: {"latitude": 37.5665, "longitude": 126.9780})

  response = client.get("/api/navigation")

  assert response.status_code == 200
  assert response.get_json()["tmapKey"] == "tmap-test-key"


def test_normalize_tmap_poi_results_extracts_coordinates_and_address():
  payload = {
    "searchPoiInfo": {
      "pois": {
        "poi": [{
          "name": "서울역",
          "frontLat": "37.554722",
          "frontLon": "126.970833",
          "upperAddrName": "서울",
          "middleAddrName": "중구",
          "roadName": "한강대로",
          "firstNo": "405",
          "id": "poi-1",
        }]
      }
    }
  }

  results = the_galaxy._normalize_tmap_poi_results(payload)

  assert results == [{
    "name": "서울역",
    "full_address": "서울 중구 405",
    "address": "서울 중구 405",
    "latitude": 37.554722,
    "longitude": 126.970833,
    "provider": "tmap",
    "poiId": "poi-1",
    "roadName": "한강대로",
    "bizCategory": "",
  }]


def test_normalize_tmap_route_response_matches_navigation_shape():
  payload = {
    "features": [
      {
        "geometry": {"type": "Point", "coordinates": [126.9780, 37.5665]},
        "properties": {"totalDistance": 1200, "totalTime": 360, "description": "출발"},
      },
      {
        "geometry": {"type": "LineString", "coordinates": [[126.9780, 37.5665], [126.9790, 37.5670]]},
        "properties": {},
      },
      {
        "geometry": {"type": "Point", "coordinates": [126.9790, 37.5670]},
        "properties": {"description": "도착"},
      },
    ]
  }

  routes = the_galaxy._normalize_tmap_route_response(payload)

  assert len(routes) == 1
  assert routes[0]["distance"] == 1200
  assert routes[0]["duration"] == 360
  assert routes[0]["geometry"]["coordinates"] == [[126.978, 37.5665], [126.979, 37.567]]
  assert routes[0]["legs"][0]["steps"][0]["maneuver"]["instruction"] == "출발"


def test_route_geometry_bounds_adds_padding_for_hazard_lookup():
  bounds = the_galaxy._route_geometry_bounds([
    [126.9780, 37.5665],
    [126.9900, 37.5700],
  ])

  assert bounds == (
    37.5565,
    126.968,
    37.58,
    127.0,
  )


def test_navigation_endpoint_includes_tmap_key(monkeypatch):
  client, _ = _params_client(monkeypatch, {
    "AMapKey1": "",
    "AMapKey2": "",
    "MapboxPublicKey": "pk.test",
    "MapboxSecretKey": "sk.test",
    "TMapApiKey": "tmap-test-key",
    "ApiCache_NavDestinations": "[]",
    "LanguageSetting": "main_ko",
    "IsMetric": True,
  }, "tici")
  monkeypatch.setattr(the_galaxy, "_get_navigation_last_position", lambda: {"latitude": 37.5665, "longitude": 126.9780})

  response = client.get("/api/navigation")
  payload = response.get_json()

  assert response.status_code == 200
  assert payload["hasTmapKey"] is True
  assert "tmapKey" not in payload


def test_normalize_tmap_poi_results_extracts_coordinates_and_address():
  payload = {
    "searchPoiInfo": {
      "pois": {
        "poi": [{
          "name": "서울역",
          "frontLat": "37.554722",
          "frontLon": "126.970833",
          "upperAddrName": "서울",
          "middleAddrName": "중구",
          "roadName": "한강대로",
          "firstNo": "405",
          "id": "poi-1",
          "bizCatName": "교통시설",
        }]
      }
    }
  }

  results = the_galaxy._normalize_tmap_poi_results(payload)

  assert results == [{
    "name": "서울역",
    "full_address": "한강대로 405",
    "address": "서울 중구 405",
    "roadAddress": "한강대로 405",
    "secondary": "교통시설 | 한강대로 405 | 서울 중구 405",
    "latitude": 37.554722,
    "longitude": 126.970833,
    "provider": "tmap",
    "poiId": "poi-1",
    "roadName": "한강대로",
    "bizCategory": "교통시설",
  }]


def test_normalize_tmap_route_response_matches_navigation_shape():
  payload = {
    "features": [
      {
        "geometry": {"type": "Point", "coordinates": [126.9780, 37.5665]},
        "properties": {"totalDistance": 1200, "totalTime": 360, "description": "출발"},
      },
      {
        "geometry": {"type": "LineString", "coordinates": [[126.9780, 37.5665], [126.9790, 37.5670]]},
        "properties": {},
      },
      {
        "geometry": {"type": "Point", "coordinates": [126.9790, 37.5670]},
        "properties": {"description": "도착"},
      },
    ]
  }

  routes = the_galaxy._normalize_tmap_route_response(payload)

  assert len(routes) == 1
  assert routes[0]["distance"] == 1200
  assert routes[0]["duration"] == 360
  assert routes[0]["geometry"]["coordinates"] == [[126.978, 37.5665], [126.979, 37.567]]
  assert routes[0]["legs"][0]["steps"][0]["maneuver"]["instruction"] == "출발"
  assert routes[0]["legs"][0]["steps"][1]["maneuver"]["instruction"] == "도착"


def test_route_geometry_bounds_adds_padding_for_hazard_lookup():
  bounds = the_galaxy._route_geometry_bounds([
    [126.9780, 37.5665],
    [126.9900, 37.5700],
  ])

  assert bounds == (
    37.5565,
    126.968,
    37.58,
    127.0,
  )


def test_is_likely_korean_position_accepts_korea_and_rejects_invalid():
  assert the_galaxy._is_likely_korean_position({"latitude": 37.5665, "longitude": 126.9780}) is True
  assert the_galaxy._is_likely_korean_position({"latitude": 91.0, "longitude": 126.9780}) is False
  assert the_galaxy._is_likely_korean_position({"latitude": 35.6762, "longitude": 139.6503}) is False


def test_normalize_tmap_poi_results_rejects_invalid_coordinates():
  payload = {
    "searchPoiInfo": {
      "pois": {
        "poi": [{
          "name": "잘못된 POI",
          "frontLat": "137.0",
          "frontLon": "126.970833",
        }]
      }
    }
  }

  assert the_galaxy._normalize_tmap_poi_results(payload) == []


def test_normalize_route_geometry_rejects_excessive_points():
  route_points = [[126.0 + (index * 0.00001), 37.0] for index in range(the_galaxy._NAVIGATION_HAZARD_MAX_ROUTE_POINTS + 1)]

  try:
    the_galaxy._normalize_route_geometry(route_points)
  except ValueError as exc:
    assert "exceeds limit" in str(exc)
  else:
    raise AssertionError("Expected ValueError for excessive route geometry")


def test_perform_tmap_poi_search_returns_empty_without_key(monkeypatch):
  monkeypatch.setattr(the_galaxy, "params", WritableFakeParams({"TMapApiKey": ""}))

  assert the_galaxy._perform_tmap_poi_search("서울역") == []


def test_navigation_route_endpoint_rejects_invalid_coordinates(monkeypatch):
  client, _ = _params_client(monkeypatch, {
    "MapboxPublicKey": "pk.test",
    "MapboxSecretKey": "sk.test",
    "TMapApiKey": "tmap-test-key",
  }, "tici")

  response = client.post("/api/navigation/route", json={
    "provider": "tmap",
    "start": {"longitude": 126.9780, "latitude": 95.0, "name": "Start"},
    "destination": {"longitude": 127.0, "latitude": 37.5, "name": "End"},
  })

  assert response.status_code == 400
  assert response.get_json()["routes"] == []


def test_navigation_search_and_route_endpoints_return_empty_without_tmap_key(monkeypatch):
  client, _ = _params_client(monkeypatch, {
    "MapboxPublicKey": "pk.test",
    "MapboxSecretKey": "sk.test",
    "TMapApiKey": "",
  }, "tici")

  search_response = client.get("/api/navigation/search?provider=tmap&q=서울역")
  route_response = client.post("/api/navigation/route", json={
    "provider": "tmap",
    "start": {"longitude": 126.9780, "latitude": 37.5665, "name": "Start"},
    "destination": {"longitude": 127.0, "latitude": 37.5, "name": "End"},
  })

  assert search_response.status_code == 200
  assert search_response.get_json()["suggestions"] == []
  assert route_response.status_code == 200
  assert route_response.get_json()["routes"] == []


def test_build_tmap_poi_request_params_uses_documented_fields():
  params = the_galaxy._build_tmap_poi_request_params("서울역", count=5)

  assert params == {
    "version": "1",
    "searchKeyword": "서울역",
    "searchType": "all",
    "reqCoordType": "WGS84GEO",
    "resCoordType": "WGS84GEO",
    "count": 5,
  }


def test_build_tmap_route_payload_uses_vehicle_route_fields():
  payload = the_galaxy._build_tmap_route_payload(
    {"longitude": 126.9780, "latitude": 37.5665, "name": "출발"},
    {"longitude": 127.0276, "latitude": 37.4979, "name": "도착"},
  )

  assert payload["startX"] == 126.9780
  assert payload["startY"] == 37.5665
  assert payload["endX"] == 127.0276
  assert payload["endY"] == 37.4979
  assert payload["reqCoordType"] == "WGS84GEO"
  assert payload["resCoordType"] == "WGS84GEO"
  assert payload["searchOption"] == "0"
  assert payload["trafficInfo"] == "Y"


def test_overpass_hazard_filtering_keeps_only_hazards_near_route():
  route = [
    [126.9780, 37.5665],
    [126.9790, 37.5665],
  ]
  hazards = [
    {"id": "near-camera", "longitude": 126.9785, "latitude": 37.56655, "type": "speed_camera"},
    {"id": "far-signal", "longitude": 126.9900, "latitude": 37.5800, "type": "traffic_signal"},
  ]

  filtered = the_galaxy._filter_hazards_near_route(hazards, route)

  assert [hazard["id"] for hazard in filtered] == ["near-camera"]
  assert filtered[0]["distanceToRouteMeters"] >= 0.0


def test_fetch_navigation_hazards_returns_cached_result(monkeypatch):
  route = [[126.9780, 37.5665], [126.9790, 37.5665]]
  expected = [{"id": "camera-1", "longitude": 126.9785, "latitude": 37.5665, "type": "speed_camera"}]
  monkeypatch.setattr(the_galaxy, "_navigation_hazard_cache", {})
  monkeypatch.setattr(the_galaxy, "_load_overpass_request_state", lambda: {"day": "2026-08-31", "total_requests": 0, "total_bytes": 0, "max_requests": 10, "max_bytes": 1000})
  monkeypatch.setattr(the_galaxy, "_parse_overpass_hazards", lambda payload: expected)
  monkeypatch.setattr(the_galaxy, "_filter_hazards_near_route", lambda hazards, route_points: hazards)

  class FakeResponse:
    content = b"{}"

    def raise_for_status(self):
      return None

    def json(self):
      return {"elements": []}

  calls = []
  monkeypatch.setattr(the_galaxy.requests, "get", lambda *args, **kwargs: calls.append((args, kwargs)) or FakeResponse())
  monkeypatch.setattr(the_galaxy, "_update_overpass_request_tracking", lambda content_length=0: None)

  first = the_galaxy._fetch_navigation_hazards_from_overpass(route)
  second = the_galaxy._fetch_navigation_hazards_from_overpass(route)

  assert first == expected
  assert second == expected
  assert len(calls) == 1


def test_fetch_navigation_hazards_respects_overpass_budget(monkeypatch):
  route = [[126.9780, 37.5665], [126.9790, 37.5665]]
  monkeypatch.setattr(the_galaxy, "_navigation_hazard_cache", {})
  monkeypatch.setattr(the_galaxy, "_load_overpass_request_state", lambda: {"day": "2026-08-31", "total_requests": 10, "total_bytes": 0, "max_requests": 10, "max_bytes": 1000})

  called = {"value": False}

  def _unexpected_request(*args, **kwargs):
    called["value"] = True
    raise AssertionError("Overpass should not be called when budget is exhausted")

  monkeypatch.setattr(the_galaxy.requests, "get", _unexpected_request)

  assert the_galaxy._fetch_navigation_hazards_from_overpass(route) == []
  assert called["value"] is False


def test_navigation_endpoint_exposes_only_tmap_key_presence(monkeypatch):
  client, _ = _params_client(monkeypatch, {
    "AMapKey1": "",
    "AMapKey2": "",
    "MapboxPublicKey": "pk.test",
    "MapboxSecretKey": "sk.test",
    "TMapApiKey": "tmap-test-key",
    "ApiCache_NavDestinations": "[]",
    "LanguageSetting": "main_ko",
    "IsMetric": True,
  }, "tici")
  monkeypatch.setattr(the_galaxy, "_get_navigation_last_position", lambda: {"latitude": 37.76516161, "longitude": 128.90139644})

  response = client.get("/api/navigation")
  payload = response.get_json()

  assert response.status_code == 200
  assert payload["hasTmapKey"] is True
  assert "tmapKey" not in payload


def test_normalize_tmap_poi_results_matches_verified_gangneung_station_shape():
  payload = {
    "searchPoiInfo": {
      "pois": {
        "poi": [{
          "name": "강릉역",
          "frontLat": "37.76516161",
          "frontLon": "128.90139644",
          "upperAddrName": "강원",
          "middleAddrName": "강릉시",
          "lowerAddrName": "교동",
          "roadName": "강릉대로",
          "id": "poi-gangneung-station",
        }]
      }
    }
  }

  results = the_galaxy._normalize_tmap_poi_results(payload)

  assert results == [{
    "name": "강릉역",
    "full_address": "강원 강릉시 교동",
    "address": "강원 강릉시 교동",
    "roadAddress": "강릉대로",
    "secondary": "강릉대로 · 강원 강릉시 교동",
    "latitude": 37.76516161,
    "longitude": 128.90139644,
    "provider": "tmap",
    "poiId": "poi-gangneung-station",
    "roadName": "강릉대로",
    "bizCategory": "",
  }]


def test_normalize_tmap_route_response_matches_verified_vehicle_route_shape():
  payload = {
    "features": [
      {
        "geometry": {"type": "Point", "coordinates": [128.90139644, 37.76516161]},
        "properties": {
          "totalDistance": 3034,
          "totalTime": 559,
          "description": "일반도로를 따라 20m 이동",
        },
      },
      {
        "geometry": {
          "type": "LineString",
          "coordinates": [
            [128.90139644, 37.76516161],
            [128.90090000, 37.76470000],
            [128.89980000, 37.76360000],
          ],
        },
        "properties": {},
      },
      {
        "geometry": {"type": "Point", "coordinates": [128.90070000, 37.76440000]},
        "properties": {"description": "교차로에서 우회전 후 강릉대로를 따라 187m 이동"},
      },
      {
        "geometry": {"type": "Point", "coordinates": [128.87689904, 37.75244038]},
        "properties": {"description": "도착"},
      },
    ]
  }

  routes = the_galaxy._normalize_tmap_route_response(payload)

  assert len(routes) == 1
  assert routes[0]["distance"] == 3034
  assert routes[0]["duration"] == 559
  assert routes[0]["geometry"]["type"] == "LineString"
  assert routes[0]["geometry"]["coordinates"][0] == [128.90139644, 37.76516161]
  assert routes[0]["geometry"]["coordinates"][-1] == [128.8998, 37.7636]
  assert routes[0]["legs"][0]["steps"][0]["maneuver"]["instruction"] == "일반도로를 따라 20m 이동"
  assert routes[0]["legs"][0]["steps"][-1]["maneuver"]["instruction"] == "도착"
  assert len(routes[0]["legs"][0]["annotation"]["congestion"]) == len(routes[0]["geometry"]["coordinates"]) - 1


def test_save_longitudinal_maneuver_status_writes_json_param_as_dict(monkeypatch):
  fake_params = WritableFakeParams()
  monkeypatch.setattr(the_galaxy, "params", fake_params)

  saved = the_galaxy._save_longitudinal_maneuver_status({
    "state": "armed",
    "history": ["", "Started"],
  })

  assert fake_params.writes == [("LongitudinalManeuverStatus", saved)]
  assert isinstance(fake_params.writes[0][1], dict)
  assert saved["history"] == ["Started"]


def test_save_lateral_maneuver_status_writes_json_param_as_dict(monkeypatch):
  fake_params = WritableFakeParams()
  monkeypatch.setattr(the_galaxy, "params", fake_params)

  saved = the_galaxy._save_lateral_maneuver_status({
    "state": "armed",
    "history": ["", "Started"],
  })

  assert fake_params.writes == [("LateralManeuverStatus", saved)]
  assert isinstance(fake_params.writes[0][1], dict)
  assert saved["history"] == ["Started"]


def test_galaxy_session_value_matches_cookie_format():
  assert the_galaxy._build_galaxy_session_value(
    "testGalaxySlug01",
    "a" * 64,
  ) == f"testGalaxySlug01%3A{'a' * 64}"


def test_configured_favorite_slot_values_only_reads_selected_keys(monkeypatch):
  fake_params = WritableFakeParams({
    "NavDesiresAllowed": False,
    "RedneckCruise": True,
    "UnusedToggle": True,
  })
  monkeypatch.setattr(the_galaxy, "params", fake_params)

  values = the_galaxy._configured_favorite_slot_values([
    {"enabled": True, "key": "NavDesiresAllowed"},
    {"enabled": False, "key": "RedneckCruise"},
    {"enabled": False, "key": None},
  ])

  assert values == {"NavDesiresAllowed": False, "RedneckCruise": True}


def test_favorite_values_endpoint_returns_current_selected_value(monkeypatch):
  client, _ = _params_client(monkeypatch, {"ForceOffroad": False}, "tici")
  monkeypatch.setattr(the_galaxy, "_get_favorite_slot_options", lambda: [{"key": "ForceOffroad"}])
  monkeypatch.setattr(
    the_galaxy,
    "normalize_favorite_slots",
    lambda *args, **kwargs: [{"enabled": True, "key": "ForceOffroad"}],
  )

  response = client.get("/api/favorites/values")

  assert response.status_code == 200
  assert response.get_json() == {"values": {"ForceOffroad": False}}


def test_device_settings_layout_asset_is_served_from_common_catalog(monkeypatch):
  client, _ = _params_client(monkeypatch, {}, "tici")

  with client.get("/assets/components/tools/device_settings_layout.json") as response:
    assert response.status_code == 200
    assert response.get_json() == the_galaxy.load_settings_catalog()


def test_favorite_slot_options_include_virtual_cruise_actions(monkeypatch):
  monkeypatch.setattr(the_galaxy, "_favorite_slot_options", None)
  monkeypatch.setattr(the_galaxy, "_get_param_type_info", lambda: (set(), {}))

  options = the_galaxy._get_favorite_slot_options()
  option_keys = {option["key"] for option in options}

  assert "__starpilot_favorite_action__:distance_decrease" in option_keys
  assert "__starpilot_favorite_action__:distance_increase" in option_keys


def test_rivian_angle_favorite_requires_detected_extreme_harness(monkeypatch):
  options = [
    {"key": "RivianAngleControl", "requiresCapability": "HasRivianAngleHarness"},
    {"key": "NonGatedFavorite", "requiresCapability": ""},
  ]
  monkeypatch.setattr(the_galaxy, "_get_favorite_slot_options", lambda: options)

  monkeypatch.setattr(the_galaxy, "_get_has_rivian_angle_harness", lambda: False)
  assert [option["key"] for option in the_galaxy._get_available_favorite_slot_options()] == ["NonGatedFavorite"]

  monkeypatch.setattr(the_galaxy, "_get_has_rivian_angle_harness", lambda: True)
  assert [option["key"] for option in the_galaxy._get_available_favorite_slot_options()] == [
    "RivianAngleControl",
    "NonGatedFavorite",
  ]


def test_favorite_action_endpoint_increments_virtual_button_counter(monkeypatch):
  client, _ = _params_client(monkeypatch, {}, "tici")
  fake_memory = WritableFakeParams()
  monkeypatch.setattr(the_galaxy, "params_memory", fake_memory)

  response = client.post("/api/favorites/action", json={"key": "__starpilot_favorite_action__:distance_increase"})

  assert response.status_code == 200
  assert fake_memory.get_int("FavoriteVirtualAccelCruiseCounter") == 1


def test_alpha_longitudinal_toggle_writes_and_requests_offroad_cycle(monkeypatch):
  client, fake_params = _params_client(monkeypatch, {
    "AlphaLongitudinalEnabled": False,
    "IsOnroad": False,
  }, "tici")
  monkeypatch.setattr(the_galaxy, "_get_alpha_longitudinal_available", lambda: True)

  response = client.put("/api/params", json={"key": "AlphaLongitudinalEnabled", "value": True})

  assert response.status_code == 200
  assert fake_params.values["AlphaLongitudinalEnabled"] is True
  assert fake_params.values["OnroadCycleRequested"] is True
  assert fake_params.writes == [
    ("AlphaLongitudinalEnabled", True),
    ("OnroadCycleRequested", True),
  ]


def test_alpha_longitudinal_toggle_rejects_onroad(monkeypatch):
  client, fake_params = _params_client(monkeypatch, {
    "AlphaLongitudinalEnabled": False,
    "IsOnroad": True,
  }, "tici")
  monkeypatch.setattr(the_galaxy, "_get_alpha_longitudinal_available", lambda: True)

  response = client.put("/api/params", json={"key": "AlphaLongitudinalEnabled", "value": True})

  assert response.status_code == 403
  assert response.get_json()["error"] == "Cannot change Alpha Longitudinal while driving."
  assert fake_params.writes == []


def test_alpha_longitudinal_toggle_rejects_unsupported_vehicle(monkeypatch):
  client, fake_params = _params_client(monkeypatch, {
    "AlphaLongitudinalEnabled": False,
    "IsOnroad": False,
  }, "tici")
  monkeypatch.setattr(the_galaxy, "_get_alpha_longitudinal_available", lambda: False)

  response = client.put("/api/params", json={"key": "AlphaLongitudinalEnabled", "value": True})

  assert response.status_code == 403
  assert response.get_json()["error"] == "Alpha Longitudinal is not available for the detected vehicle."
  assert fake_params.writes == []


def test_force_offroad_toggle_requires_live_park(monkeypatch):
  client, fake_params = _params_client(monkeypatch, {
    "ForceOffroad": False,
    "ForceOnroad": False,
    "IsOnroad": True,
  }, "tici")
  monkeypatch.setattr(the_galaxy, "_get_vehicle_parked", lambda: True)

  response = client.put("/api/params", json={"key": "ForceOffroad", "value": True})

  assert response.status_code == 200
  assert response.get_json()["updated"] == {"ForceOffroad": True, "ForceOnroad": False}
  assert fake_params.values["ForceOffroad"] is True
  assert fake_params.values["ForceOnroad"] is False


def test_force_offroad_toggle_rejects_when_not_parked(monkeypatch):
  client, fake_params = _params_client(monkeypatch, {
    "ForceOffroad": False,
    "IsOnroad": True,
  }, "tici")
  monkeypatch.setattr(the_galaxy, "_get_vehicle_parked", lambda: False)

  response = client.put("/api/params", json={"key": "ForceOffroad", "value": True})

  assert response.status_code == 403
  assert response.get_json()["error"] == "Force Offroad is only available while the vehicle is in Park."
  assert fake_params.writes == []


def test_curve_speed_controller_reset_clears_learned_data_offroad(monkeypatch):
  client, fake_params = _params_client(monkeypatch, {
    "IsOnroad": False,
    "CalibratedLateralAcceleration": 2.73,
    "CalibrationProgress": 48.0,
    "CurvatureData": {"0.01": {"average": 2.73, "count": 12}},
  }, "tici")

  response = client.post("/api/curve_speed_controller/reset")

  assert response.status_code == 200
  assert response.get_json()["updated"] == {
    "CalibratedLateralAcceleration": 2.0,
    "CalibrationProgress": 0.0,
  }
  assert fake_params.values["CalibratedLateralAcceleration"] == 2.0
  assert "CalibrationProgress" not in fake_params.values
  assert "CurvatureData" not in fake_params.values
  assert fake_params.removals == ["CalibrationProgress", "CurvatureData"]


def test_curve_speed_controller_reset_rejected_onroad(monkeypatch):
  client, fake_params = _params_client(monkeypatch, {
    "IsOnroad": True,
    "CalibratedLateralAcceleration": 2.73,
    "CalibrationProgress": 48.0,
    "CurvatureData": {"0.01": {"average": 2.73, "count": 12}},
  }, "tici")

  response = client.post("/api/curve_speed_controller/reset")

  assert response.status_code == 403
  assert response.get_json()["error"] == "Curve Speed Controller data can only be reset while parked."
  assert fake_params.writes == []
  assert fake_params.removals == []
