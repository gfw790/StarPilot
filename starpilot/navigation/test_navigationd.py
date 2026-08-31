from __future__ import annotations

from openpilot.starpilot.navigation.navigationd import Navigationd
from openpilot.starpilot.navigation.route_engine import Coordinate


class FakeParams:
  shared_values: dict[str, object] = {}

  def __init__(self, memory: bool = False):
    del memory
    self.values = self.shared_values

  def get(self, key, encoding=None, default=None):
    value = self.values.get(key, default)
    if encoding == "utf-8" and isinstance(value, bytes):
      return value.decode("utf-8")
    return value

  def get_bool(self, key):
    return bool(self.values.get(key, False))

  def put(self, key, value):
    self.values[key] = value

  def remove(self, key):
    self.values.pop(key, None)


class FakePubMaster:
  def __init__(self, services):
    self.services = services

  def send(self, service, msg):
    del service, msg


class FakeRatekeeper:
  def __init__(self, hz):
    self.hz = hz

  def keep_time(self):
    return None


class ImmediateThread:
  def __init__(self, target, daemon=False):
    self._target = target
    self.daemon = daemon

  def start(self):
    self._target()


class FakeRouteEngine:
  def __init__(self, name):
    self.name = name
    self.calls: list[dict[str, object]] = []

  def fetch_route(self, token, start, destination, bearing):
    self.calls.append({
      "token": token,
      "start": start,
      "destination": destination,
      "bearing": bearing,
    })
    return None


def make_navigationd(monkeypatch, params_values=None, *, mapbox_engine=None, tmap_engine=None):
  FakeParams.shared_values = dict(params_values or {})
  monkeypatch.setattr("openpilot.starpilot.navigation.navigationd.Params", FakeParams)
  monkeypatch.setattr("openpilot.starpilot.navigation.navigationd.messaging.PubMaster", FakePubMaster)
  monkeypatch.setattr("openpilot.starpilot.navigation.navigationd.Ratekeeper", FakeRatekeeper)
  monkeypatch.setattr("openpilot.starpilot.navigation.navigationd.threading.Thread", ImmediateThread)
  return Navigationd(route_engine=mapbox_engine, tmap_route_engine=tmap_engine)


def test_navigationd_defaults_to_mapbox_when_provider_missing(monkeypatch):
  mapbox_engine = FakeRouteEngine("mapbox")
  tmap_engine = FakeRouteEngine("tmap")
  nav = make_navigationd(monkeypatch, {"MapboxSecretKey": "mapbox-secret"}, mapbox_engine=mapbox_engine, tmap_engine=tmap_engine)
  nav._last_position = Coordinate(37.0, 127.0)
  nav._last_bearing = 90.0

  nav._start_route_fetch({"place_name": "Home", "latitude": 37.5, "longitude": 127.1})

  assert len(mapbox_engine.calls) == 1
  assert mapbox_engine.calls[0]["token"] == "mapbox-secret"
  assert tmap_engine.calls == []


def test_navigationd_selects_tmap_engine_when_destination_provider_is_tmap(monkeypatch):
  mapbox_engine = FakeRouteEngine("mapbox")
  tmap_engine = FakeRouteEngine("tmap")
  nav = make_navigationd(monkeypatch, {"MapboxSecretKey": "mapbox-secret", "TMapApiKey": "tmap-key"}, mapbox_engine=mapbox_engine, tmap_engine=tmap_engine)
  nav._last_position = Coordinate(37.0, 127.0)
  nav._last_bearing = 45.0

  nav._start_route_fetch({"place_name": "Seoul", "latitude": 37.5, "longitude": 127.1, "provider": "tmap"})

  assert mapbox_engine.calls == []
  assert len(tmap_engine.calls) == 1
  assert tmap_engine.calls[0]["token"] == "tmap-key"


def test_navigationd_unknown_provider_falls_back_to_mapbox(monkeypatch):
  mapbox_engine = FakeRouteEngine("mapbox")
  tmap_engine = FakeRouteEngine("tmap")
  nav = make_navigationd(monkeypatch, {"MapboxSecretKey": "mapbox-secret", "TMapApiKey": "tmap-key"}, mapbox_engine=mapbox_engine, tmap_engine=tmap_engine)
  nav._last_position = Coordinate(37.0, 127.0)

  nav._start_route_fetch({"place_name": "Fallback", "latitude": 37.5, "longitude": 127.1, "provider": "mystery"})

  assert len(mapbox_engine.calls) == 1
  assert mapbox_engine.calls[0]["token"] == "mapbox-secret"
  assert tmap_engine.calls == []


def test_navigationd_tmap_destination_without_key_exits_safely(monkeypatch):
  mapbox_engine = FakeRouteEngine("mapbox")
  tmap_engine = FakeRouteEngine("tmap")
  nav = make_navigationd(monkeypatch, {"MapboxSecretKey": "mapbox-secret"}, mapbox_engine=mapbox_engine, tmap_engine=tmap_engine)
  nav._last_position = Coordinate(37.0, 127.0)

  nav._start_route_fetch({"place_name": "No Key", "latitude": 37.5, "longitude": 127.1, "provider": "tmap"})

  assert mapbox_engine.calls == []
  assert tmap_engine.calls == []
