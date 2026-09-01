import json
from dataclasses import dataclass
from pathlib import Path

from openpilot.starpilot.navigation.route_engine import Coordinate, bearing_between_two_points, minimum_distance
@dataclass(frozen=True)
class CameraMatch:
  id: str
  road: str
  location: str
  speed_limit: int
  distance_m: float
  osm_way_id: int | None = None
  osm_distance_m: float | None = None
  osm_name: str | None = None
  osm_highway: str | None = None
  osm_maxspeed: str | None = None
  osm_oneway: str | None = None
  osm_match_confidence: str | None = None


class CameraMatcher:
  def __init__(self) -> None:
    db_path = Path(__file__).with_name("camera_db.json")

    with db_path.open("r", encoding="utf-8-sig") as f:
      self.cameras = json.load(f)

  def find_nearest(self, position: Coordinate) -> CameraMatch | None:
    if not self.cameras:
      return None

    nearest = None
    nearest_distance = float("inf")

    for camera in self.cameras:
      camera_position = Coordinate(
        float(camera["lat"]),
        float(camera["lon"]),
      )

      distance = position.distance_to(camera_position)

      if distance < nearest_distance:
        nearest_distance = distance
        nearest = camera

    if nearest is None:
      return None

    return CameraMatch(
      id=str(nearest["id"]),
      road=str(nearest["road"]),
      location=str(nearest["location"]),
      speed_limit=int(nearest["speed_limit"]),
      distance_m=nearest_distance,
      osm_way_id=nearest.get("osm_way_id"),
      osm_distance_m=nearest.get("osm_distance_m"),
      osm_name=nearest.get("osm_name"),
      osm_highway=nearest.get("osm_highway"),
      osm_maxspeed=nearest.get("osm_maxspeed"),
      osm_oneway=nearest.get("osm_oneway"),
      osm_match_confidence=nearest.get("osm_match_confidence"),
    )
  def find_ahead(
    self,
    position: Coordinate,
    bearing: float,
    geometry: list[Coordinate],
    max_angle_diff: float = 75.0,
    max_route_distance: float = 50.0,
  ) -> CameraMatch | None:
    nearest = None
    nearest_distance = float("inf")

    normalized_bearing = (bearing + 360.0) % 360.0

    for camera in self.cameras:
      camera_position = Coordinate(
        float(camera["lat"]),
        float(camera["lon"]),
      )

      # 1. 차량 진행방향 앞쪽인지 확인
      camera_bearing = bearing_between_two_points(position, camera_position)
      bearing_diff = abs(normalized_bearing - camera_bearing)
      bearing_diff = min(bearing_diff, 360.0 - bearing_diff)

      if bearing_diff > max_angle_diff:
        continue

      # 2. 실제 TMAP 주행경로 근처에 있는 카메라인지 확인
      route_distance = self.distance_from_route(camera, geometry)

      if route_distance > max_route_distance:
        continue

      # 3. 조건을 통과한 카메라 중 가장 가까운 카메라 선택
      distance = position.distance_to(camera_position)

      if distance < nearest_distance:
        nearest_distance = distance
        nearest = camera

    if nearest is None:
      return None

    return CameraMatch(
      id=str(nearest["id"]),
      road=str(nearest["road"]),
      location=str(nearest["location"]),
      speed_limit=int(nearest["speed_limit"]),
      distance_m=nearest_distance,
      osm_way_id=nearest.get("osm_way_id"),
      osm_distance_m=nearest.get("osm_distance_m"),
      osm_name=nearest.get("osm_name"),
      osm_highway=nearest.get("osm_highway"),
      osm_maxspeed=nearest.get("osm_maxspeed"),
      osm_oneway=nearest.get("osm_oneway"),
      osm_match_confidence=nearest.get("osm_match_confidence"),
    )
  def distance_from_route(self, camera: dict, geometry: list[Coordinate]) -> float:
    if len(geometry) < 2:
      return float("inf")

    camera_position = Coordinate(
      float(camera["lat"]),
      float(camera["lon"]),
    )

    return min(
      minimum_distance(geometry[i], geometry[i + 1], camera_position)
      for i in range(len(geometry) - 1)
    )