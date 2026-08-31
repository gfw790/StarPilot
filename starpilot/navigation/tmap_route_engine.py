from __future__ import annotations

import math
from typing import Any

import requests

from openpilot.common.constants import CV
from openpilot.common.swaglog import cloudlog
from openpilot.starpilot.navigation.route_engine import Coordinate, NavigationRoute

TMAP_ROUTES_URL = "https://apis.openapi.sk.com/tmap/routes"
TMAP_ROUTE_TIMEOUT_SECONDS = 10

# Based on the current official SK Open API docs snippet for the TMAP car route API:
# 11 = straight, 12 = left turn, 13 = right turn, 185-187 = waypoint, 201 = destination,
# 211-212 = crosswalk-related guide points. Other turnType values are handled heuristically
# from the human-readable instruction text so navigationd keeps working even when the
# response includes provider-specific codes we do not explicitly enumerate here.
TMAP_TURN_TYPE_MAP: dict[int, tuple[str, str]] = {
  11: ("continue", "straight"),
  12: ("turn", "left"),
  13: ("turn", "right"),
  185: ("arrive", "straight"),
  186: ("arrive", "straight"),
  187: ("arrive", "straight"),
  201: ("arrive", "straight"),
  211: ("continue", "straight"),
  212: ("continue", "left"),
}


def _safe_float(value: Any, default: float = 0.0) -> float:
  try:
    parsed = float(value)
  except (TypeError, ValueError):
    return default
  return parsed if math.isfinite(parsed) else default


def _normalize_coordinate(longitude: Any, latitude: Any) -> Coordinate | None:
  longitude_value = _safe_float(longitude, float("nan"))
  latitude_value = _safe_float(latitude, float("nan"))
  if not math.isfinite(longitude_value) or not math.isfinite(latitude_value):
    return None
  if abs(longitude_value) < 1e-6 and abs(latitude_value) < 1e-6:
    return None
  return Coordinate(latitude_value, longitude_value)


def _coordinate_dict(coordinate: Coordinate) -> dict[str, float]:
  return {"latitude": coordinate.latitude, "longitude": coordinate.longitude}


def _tmap_request_headers(app_key: str) -> dict[str, str]:
  return {
    "accept": "application/json",
    "appKey": app_key,
    "content-type": "application/json",
  }


def _build_tmap_route_payload(start: Coordinate, destination: dict[str, Any]) -> dict[str, object]:
  return {
    "startX": start.longitude,
    "startY": start.latitude,
    "endX": float(destination["longitude"]),
    "endY": float(destination["latitude"]),
    "reqCoordType": "WGS84GEO",
    "resCoordType": "WGS84GEO",
    "searchOption": "0",
    "trafficInfo": "Y",
    "startName": "Current Location",
    "endName": str(destination.get("name") or destination.get("place_name") or "Destination"),
  }


def _extract_instruction(properties: dict[str, Any]) -> str:
  for key in ("description", "name", "guidePointName", "instructions"):
    value = str(properties.get(key) or "").strip()
    if value:
      return value
  return ""


def _normalize_speed_limit(maxspeed_raw: Any) -> list[dict[str, float | str]]:
  if isinstance(maxspeed_raw, list):
    limits: list[dict[str, float | str]] = []
    for item in maxspeed_raw:
      if not isinstance(item, dict):
        continue
      speed = _safe_float(item.get("speed"), 0.0)
      unit = str(item.get("unit") or "").strip().lower()
      if speed <= 0.0 or unit not in ("km/h", "kph", "mph"):
        continue
      limits.append({"speed": speed, "unit": "mph" if unit == "mph" else "km/h"})
    return limits

  speed_value = _safe_float(maxspeed_raw, 0.0)
  if speed_value <= 0.0:
    return []
  return [{"speed": speed_value, "unit": "km/h"}]


def _extract_step_speed_limit(properties: dict[str, Any]) -> float:
  for key in ("speedLimit", "maxSpeed", "roadLimitSpeed", "safeRoadSpeed", "recommendedSpeed"):
    value = _safe_float(properties.get(key), 0.0)
    if value > 0.0:
      return value * CV.KPH_TO_MS
  return 0.0


def _direction_from_instruction(text: str) -> str:
  normalized = text.casefold()
  if "u-turn" in normalized or "uturn" in normalized or "유턴" in normalized:
    return "u-turn"
  if any(token in normalized for token in ("slight left", "keep left", "좌측", "좌편", "왼쪽", "left ramp", "left fork")):
    return "slight left"
  if any(token in normalized for token in ("slight right", "keep right", "우측", "우편", "오른쪽", "right ramp", "right fork")):
    return "slight right"
  if any(token in normalized for token in ("left", "좌회전")):
    return "left"
  if any(token in normalized for token in ("right", "우회전")):
    return "right"
  if any(token in normalized for token in ("straight", "continue", "직진")):
    return "straight"
  return "straight"


def _maneuver_from_properties(properties: dict[str, Any], instruction: str, *, point_type: str) -> tuple[str, str]:
  turn_type_raw = properties.get("turnType")
  try:
    turn_type = int(turn_type_raw) if turn_type_raw is not None else None
  except (TypeError, ValueError):
    turn_type = None

  if turn_type in TMAP_TURN_TYPE_MAP:
    return TMAP_TURN_TYPE_MAP[turn_type]

  normalized = instruction.casefold()
  direction = _direction_from_instruction(instruction)

  if "destination" in normalized or "arrive" in normalized or "도착" in normalized or "목적지" in normalized:
    return "arrive", "straight"
  if point_type == "sp" or "출발" in normalized or "head " in normalized or normalized.startswith("start"):
    return "depart", "straight"
  if "roundabout" in normalized or "rotary" in normalized or "로터리" in normalized:
    return "roundabout", direction
  if "merge" in normalized or "합류" in normalized:
    return "merge", direction
  if "fork" in normalized or "분기" in normalized:
    return "fork", direction
  if "u-turn" in normalized or "uturn" in normalized or "유턴" in normalized:
    return "turn", "u-turn"
  if "left" in normalized or "right" in normalized or "좌회전" in normalized or "우회전" in normalized:
    return "turn", direction
  if "continue" in normalized or "straight" in normalized or "직진" in normalized:
    return "continue", "straight"
  return "continue", direction


def _fallback_instruction(maneuver_type: str, modifier: str, coordinate: Coordinate, *, is_last: bool) -> str:
  if is_last or maneuver_type == "arrive":
    return "Your destination is ahead"
  if maneuver_type == "depart":
    return "Head to the route"
  if maneuver_type == "turn" and modifier == "left":
    return "Turn left"
  if maneuver_type == "turn" and modifier == "right":
    return "Turn right"
  if maneuver_type == "turn" and modifier == "u-turn":
    return "Make a U-turn"
  if maneuver_type == "merge":
    return "Merge ahead"
  if maneuver_type == "fork":
    return "Keep on the fork"
  if maneuver_type == "roundabout":
    return "Enter the roundabout"
  if modifier == "slight left":
    return "Keep left"
  if modifier == "slight right":
    return "Keep right"
  return f"Continue via {coordinate.latitude:.5f},{coordinate.longitude:.5f}"


def _point_sort_key(step: dict[str, Any]) -> tuple[float, int]:
  return float(step["cumulative_distance"]), int(step["order"])


def _dedupe_and_collect_geometry(features: list[dict[str, Any]]) -> list[Coordinate]:
  geometry: list[Coordinate] = []
  for feature in features:
    if not isinstance(feature, dict):
      continue
    geometry_data = feature.get("geometry") or {}
    if geometry_data.get("type") != "LineString":
      continue

    for point in geometry_data.get("coordinates") or []:
      if not isinstance(point, (list, tuple)) or len(point) < 2:
        continue
      coordinate = _normalize_coordinate(point[0], point[1])
      if coordinate is None:
        continue
      if not geometry or geometry[-1] != coordinate:
        geometry.append(coordinate)
  return geometry


def _geometry_cumulative_distances(geometry: list[Coordinate]) -> list[float]:
  cumulative = [0.0]
  for index in range(1, len(geometry)):
    cumulative.append(cumulative[-1] + geometry[index - 1].distance_to(geometry[index]))
  return cumulative


def _closest_geometry_index(geometry: list[Coordinate], point: Coordinate) -> int:
  return min(range(len(geometry)), key=lambda idx: point.distance_to(geometry[idx]))


def _extract_point_steps(features: list[dict[str, Any]], geometry: list[Coordinate], cumulative_distances: list[float]) -> list[dict[str, Any]]:
  point_steps: list[dict[str, Any]] = []
  for order, feature in enumerate(features):
    if not isinstance(feature, dict):
      continue
    geometry_data = feature.get("geometry") or {}
    if geometry_data.get("type") != "Point":
      continue

    coordinates = geometry_data.get("coordinates") or []
    if not isinstance(coordinates, (list, tuple)) or len(coordinates) < 2:
      continue

    coordinate = _normalize_coordinate(coordinates[0], coordinates[1])
    if coordinate is None:
      continue

    properties = feature.get("properties") or {}
    point_type = str(properties.get("pointType") or "").strip().casefold()
    instruction = _extract_instruction(properties)
    maneuver_type, modifier = _maneuver_from_properties(properties, instruction, point_type=point_type)
    closest_index = _closest_geometry_index(geometry, coordinate)

    point_steps.append({
      "order": order,
      "coordinate": coordinate,
      "instruction": instruction,
      "maneuver": maneuver_type,
      "modifier": modifier,
      "distance": _safe_float(properties.get("distance"), 0.0),
      "duration": _safe_float(properties.get("time"), 0.0),
      "speedLimitMs": _extract_step_speed_limit(properties),
      "cumulative_distance": cumulative_distances[closest_index],
      "pointType": point_type,
    })

  return point_steps


def _synthesize_endpoint_steps(geometry: list[Coordinate], total_distance: float, total_duration: float) -> list[dict[str, Any]]:
  if len(geometry) < 2:
    return []
  return [
    {
      "order": -1,
      "coordinate": geometry[0],
      "instruction": "Head to the route",
      "maneuver": "depart",
      "modifier": "straight",
      "distance": total_distance,
      "duration": total_duration,
      "speedLimitMs": 0.0,
      "cumulative_distance": 0.0,
      "pointType": "sp",
    },
    {
      "order": 10 ** 9,
      "coordinate": geometry[-1],
      "instruction": "Your destination is ahead",
      "maneuver": "arrive",
      "modifier": "straight",
      "distance": 0.0,
      "duration": 0.0,
      "speedLimitMs": 0.0,
      "cumulative_distance": total_distance,
      "pointType": "ep",
    },
  ]


def _ensure_boundary_steps(point_steps: list[dict[str, Any]], geometry: list[Coordinate], total_distance: float, total_duration: float) -> list[dict[str, Any]]:
  if not point_steps:
    return _synthesize_endpoint_steps(geometry, total_distance, total_duration)

  steps = sorted(point_steps, key=_point_sort_key)
  if steps[0]["cumulative_distance"] > 3.0:
    steps.insert(0, {
      "order": -1,
      "coordinate": geometry[0],
      "instruction": "Head to the route",
      "maneuver": "depart",
      "modifier": "straight",
      "distance": 0.0,
      "duration": 0.0,
      "speedLimitMs": 0.0,
      "cumulative_distance": 0.0,
      "pointType": "sp",
    })

  last_step = steps[-1]
  if last_step["maneuver"] != "arrive":
    steps.append({
      "order": last_step["order"] + 1,
      "coordinate": geometry[-1],
      "instruction": "Your destination is ahead",
      "maneuver": "arrive",
      "modifier": "straight",
      "distance": 0.0,
      "duration": 0.0,
      "speedLimitMs": 0.0,
      "cumulative_distance": total_distance,
      "pointType": "ep",
    })
  return steps


def _finalize_step_metrics(point_steps: list[dict[str, Any]], total_distance: float, total_duration: float) -> list[dict[str, Any]]:
  if not point_steps:
    return []

  steps = sorted(point_steps, key=_point_sort_key)
  safe_total_distance = max(total_distance, 1.0)
  finalized: list[dict[str, Any]] = []
  for index, step in enumerate(steps):
    next_cumulative = total_distance if index == len(steps) - 1 else float(steps[index + 1]["cumulative_distance"])
    fallback_distance = max(0.0, next_cumulative - float(step["cumulative_distance"]))
    distance = float(step["distance"]) if float(step["distance"]) > 0.0 else fallback_distance

    if index == len(steps) - 1 and step["maneuver"] == "arrive":
      distance = 0.0

    duration = float(step["duration"])
    if duration <= 0.0:
      duration = total_duration * min(distance / safe_total_distance, 1.0) if total_duration > 0.0 else 0.0
    if index == len(steps) - 1 and step["maneuver"] == "arrive":
      duration = 0.0

    instruction = str(step["instruction"] or "").strip()
    if not instruction:
      instruction = _fallback_instruction(step["maneuver"], step["modifier"], step["coordinate"], is_last=index == len(steps) - 1)

    finalized.append({
      "maneuver": step["maneuver"],
      "modifier": step["modifier"],
      "instruction": instruction,
      "distance": distance,
      "duration": duration,
      "location": _coordinate_dict(step["coordinate"]),
      "bannerInstructions": [],
      "speedLimitMs": float(step["speedLimitMs"]),
    })

  return finalized


def _build_route_data(payload: dict[str, Any]) -> dict[str, Any] | None:
  features = payload.get("features")
  if not isinstance(features, list) or not features:
    return None

  geometry = _dedupe_and_collect_geometry(features)
  if len(geometry) < 2:
    return None

  cumulative_distances = _geometry_cumulative_distances(geometry)
  total_distance = 0.0
  total_duration = 0.0
  for feature in features:
    if not isinstance(feature, dict):
      continue
    properties = feature.get("properties") or {}
    if total_distance <= 0.0:
      total_distance = _safe_float(properties.get("totalDistance"), 0.0)
    if total_duration <= 0.0:
      total_duration = _safe_float(properties.get("totalTime"), 0.0)

  total_distance = max(total_distance, cumulative_distances[-1])
  point_steps = _extract_point_steps(features, geometry, cumulative_distances)
  point_steps = _ensure_boundary_steps(point_steps, geometry, total_distance, total_duration)
  steps = _finalize_step_metrics(point_steps, total_distance, total_duration)
  if not steps:
    return None

  maxspeed = _normalize_speed_limit(payload.get("maxspeed"))
  if not maxspeed:
    step_speed_limits = [step["speedLimitMs"] for step in steps if step["speedLimitMs"] > 0.0]
    if step_speed_limits:
      maxspeed = [{"speed": round(speed_ms * CV.MS_TO_KPH, 3), "unit": "km/h"} for speed_ms in step_speed_limits]

  return {
    "geometry": [_coordinate_dict(coordinate) for coordinate in geometry],
    "steps": [
      {
        "maneuver": step["maneuver"],
        "instruction": step["instruction"],
        "distance": step["distance"],
        "duration": step["duration"],
        "location": step["location"],
        "modifier": step["modifier"],
        "bannerInstructions": step["bannerInstructions"],
      }
      for step in steps
    ],
    "totalDistance": total_distance,
    "totalDuration": total_duration,
    "maxspeed": maxspeed,
  }


class TMapRouteEngine:
  def __init__(self, session: Any = requests):
    self._session = session

  def fetch_route(self, token: str, start: Coordinate, destination: dict[str, Any], bearing: float | None = None) -> NavigationRoute | None:
    del bearing

    if not token:
      cloudlog.warning("navigationd: TMAP route fetch skipped because TMapApiKey is missing")
      return None

    try:
      payload = _build_tmap_route_payload(start, destination)
    except (KeyError, TypeError, ValueError) as exc:
      cloudlog.warning(f"navigationd: invalid TMAP destination payload: {exc}")
      return None

    try:
      response = self._session.post(
        TMAP_ROUTES_URL,
        params={"version": "1", "format": "json"},
        headers=_tmap_request_headers(token),
        json=payload,
        timeout=TMAP_ROUTE_TIMEOUT_SECONDS,
      )
      response.raise_for_status()
      data = response.json()
    except requests.RequestException as exc:
      cloudlog.warning(f"navigationd: TMAP route request failed: {type(exc).__name__}: {exc}")
      return None
    except ValueError as exc:
      cloudlog.warning(f"navigationd: TMAP route response was not valid JSON: {exc}")
      return None

    route_data = _build_route_data(data if isinstance(data, dict) else {})
    if route_data is None:
      cloudlog.warning("navigationd: TMAP route response did not contain a usable route")
      return None

    route = NavigationRoute.from_route_data(route_data)
    if route is None:
      cloudlog.warning("navigationd: TMAP route could not be converted into NavigationRoute")
    return route
