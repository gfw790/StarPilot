import requests

from starpilot.navigation.route_engine import Coordinate
from starpilot.navigation.tmap_route_engine import TMapRouteEngine


class FakeResponse:
  def __init__(self, payload, status_code=200):
    self._payload = payload
    self.status_code = status_code

  def raise_for_status(self):
    if self.status_code >= 400:
      raise requests.HTTPError(f"status={self.status_code}")

  def json(self):
    return self._payload


class FakeSession:
  def __init__(self, response=None, error=None):
    self.response = response
    self.error = error
    self.calls = []

  def post(self, url, **kwargs):
    self.calls.append((url, kwargs))
    if self.error is not None:
      raise self.error
    return self.response


def make_tmap_response():
  return {
    "features": [
      {
        "geometry": {"type": "Point", "coordinates": [126.9780, 37.5665]},
        "properties": {
          "totalDistance": 320,
          "totalTime": 40,
          "description": "출발 후 직진",
          "pointType": "SP",
          "turnType": 11,
        },
      },
      {
        "geometry": {
          "type": "LineString",
          "coordinates": [
            [126.9780, 37.5665],
            [126.9784, 37.5665],
            [126.9784, 37.5665],
            [126.9788, 37.5668],
          ],
        },
        "properties": {},
      },
      {
        "geometry": {"type": "Point", "coordinates": [126.9788, 37.5668]},
        "properties": {
          "description": "우회전",
          "distance": 140,
          "time": 18,
          "turnType": 13,
          "speedLimit": 50,
        },
      },
      {
        "geometry": {
          "type": "LineString",
          "coordinates": [
            [126.9788, 37.5668],
            [126.9790, 37.5670],
            [126.9795, 37.5674],
          ],
        },
        "properties": {},
      },
      {
        "geometry": {"type": "Point", "coordinates": [126.9795, 37.5674]},
        "properties": {
          "description": "목적지",
          "pointType": "EP",
          "turnType": 201,
        },
      },
    ]
  }


def test_fetch_route_builds_navigation_route():
  session = FakeSession(response=FakeResponse(make_tmap_response()))
  engine = TMapRouteEngine(session=session)

  route = engine.fetch_route(
    "test-key",
    Coordinate(latitude=37.5665, longitude=126.9780),
    {"name": "Test", "latitude": 37.5674, "longitude": 126.9795, "provider": "tmap"},
    None,
  )

  assert route is not None
  assert route.distance == 320
  assert route.duration == 40
  assert route.geometry[0] == Coordinate(latitude=37.5665, longitude=126.9780)
  assert route.geometry[-1] == Coordinate(latitude=37.5674, longitude=126.9795)
  assert len(route.geometry) == 5
  assert len(route.steps) >= 3
  assert route.steps[0].instruction == "출발 후 직진"
  assert route.steps[1].instruction == "우회전"
  assert route.steps[1].distance == 140
  assert route.steps[1].duration == 18
  assert route.steps[1].maneuver.modifier == "right"
  assert route.steps[-1].instruction == "목적지"
  assert route.maxspeed is not None
  assert route.maxspeed[route.steps[1].along_geometry_index] == 13.88888888888889


def test_fetch_route_supports_progress_and_instruction_payload():
  session = FakeSession(response=FakeResponse(make_tmap_response()))
  engine = TMapRouteEngine(session=session)
  route = engine.fetch_route(
    "test-key",
    Coordinate(latitude=37.5665, longitude=126.9780),
    {"name": "Test", "latitude": 37.5674, "longitude": 126.9795},
    None,
  )

  assert route is not None

  progress = route.get_progress(Coordinate(latitude=37.5666, longitude=126.9782), 10.0)
  assert progress is not None
  assert progress.remaining_distance >= 0

  instruction = route.build_instruction_payload(progress)
  assert instruction is not None
  assert instruction["maneuverPrimaryText"]


def test_fetch_route_returns_none_on_http_error():
  session = FakeSession(error=requests.Timeout("timeout"))
  engine = TMapRouteEngine(session=session)

  route = engine.fetch_route(
    "test-key",
    Coordinate(latitude=37.5665, longitude=126.9780),
    {"name": "Test", "latitude": 37.5674, "longitude": 126.9795},
    None,
  )

  assert route is None


def test_fetch_route_returns_none_on_empty_route():
  session = FakeSession(response=FakeResponse({"features": []}))
  engine = TMapRouteEngine(session=session)

  route = engine.fetch_route(
    "test-key",
    Coordinate(latitude=37.5665, longitude=126.9780),
    {"name": "Test", "latitude": 37.5674, "longitude": 126.9795},
    None,
  )

  assert route is None


def test_fetch_route_returns_none_on_malformed_geometry():
  session = FakeSession(
    response=FakeResponse({
      "features": [
        {
          "geometry": {"type": "Point", "coordinates": [126.9780, 37.5665]},
          "properties": {"totalDistance": 320, "totalTime": 40},
        },
      ]
    })
  )
  engine = TMapRouteEngine(session=session)

  route = engine.fetch_route(
    "test-key",
    Coordinate(latitude=37.5665, longitude=126.9780),
    {"name": "Test", "latitude": 37.5674, "longitude": 126.9795},
    None,
  )

  assert route is None


def test_fetch_route_returns_none_without_api_key():
  session = FakeSession(response=FakeResponse(make_tmap_response()))
  engine = TMapRouteEngine(session=session)

  route = engine.fetch_route(
    "",
    Coordinate(latitude=37.5665, longitude=126.9780),
    {"name": "Test", "latitude": 37.5674, "longitude": 126.9795},
    None,
  )

  assert route is None
  assert session.calls == []
