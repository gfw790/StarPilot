import json
from dataclasses import dataclass
from pathlib import Path

from openpilot.starpilot.navigation.route_engine import Coordinate, bearing_between_two_points

@dataclass(frozen=True)
class CameraMatch:
  id: str
  road: str
  location: str
  speed_limit: int
  distance_m: float


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
    )
  def find_ahead(self, position: Coordinate, bearing: float, max_angle_diff: float = 75.0) -> CameraMatch | None:
    nearest = None
    nearest_distance = float("inf")

    normalized_bearing = (bearing + 360.0) % 360.0

    for camera in self.cameras:
      camera_position = Coordinate(
        float(camera["lat"]),
        float(camera["lon"]),
      )

      camera_bearing = bearing_between_two_points(position, camera_position)
      bearing_diff = abs(normalized_bearing - camera_bearing)
      bearing_diff = min(bearing_diff, 360.0 - bearing_diff)

      if bearing_diff > max_angle_diff:
        continue

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
    )
