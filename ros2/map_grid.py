"""OccupancyGrid의 읽기 전용 2D 변환. ROS 초기화·구독·지도 확정·이동 없음."""
from array import array
import math
from host.map_review import Grid, MAX_CELLS

PLANAR_TOLERANCE = 1e-6


def from_occupancy_grid(message):
    """ROS 메시지와 같은 속성을 읽습니다. 셀은 0만 free, -1/1..100은 막힘입니다."""
    try:
        info = message.info
        if (type(info.width) is not int or type(info.height) is not int
                or info.width <= 0 or info.height <= 0 or info.width * info.height > MAX_CELLS):
            raise ValueError("invalid map dimensions")
        data = message.data
        if not isinstance(data, (array, list, tuple)) or len(data) != info.width * info.height:
            raise ValueError("invalid map data")
        position, orientation = info.origin.position, info.origin.orientation
        values = (position.x, position.y, position.z, orientation.x, orientation.y,
                  orientation.z, orientation.w)
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in values):
            raise ValueError("invalid map pose")
        x, y, z, qx, qy, qz, qw = values
        norm = qx*qx + qy*qy + qz*qz + qw*qw
        if (abs(norm - 1) > PLANAR_TOLERANCE or abs(z) > PLANAR_TOLERANCE
                or abs(qx) > PLANAR_TOLERANCE or abs(qy) > PLANAR_TOLERANCE):
            raise ValueError("normalized planar map pose required")
        yaw = math.atan2(2*qw*qz, qw*qw - qz*qz)
        return Grid(info.width, info.height, info.resolution, (x, y, yaw), tuple(data), message.header.frame_id)
    except (AttributeError, TypeError, OverflowError) as error:
        raise ValueError("invalid occupancy grid") from error
