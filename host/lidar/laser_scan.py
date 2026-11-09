"""ROS-independent conversion. Missing/invalid bins are unknown (NaN), never clear space."""
import math


def ranges_metres(scan, bins=360, range_min=0.15, range_max=12.0):
    if not isinstance(bins, int) or not 2 <= bins <= 8192:
        raise ValueError("invalid bin count")
    if not (math.isfinite(range_min) and math.isfinite(range_max) and 0 < range_min < range_max):
        raise ValueError("invalid distance bounds")
    if not (len(scan.angles_deg) == len(scan.distances_mm) == len(scan.qualities)):
        raise ValueError("inconsistent scan")
    result = [math.nan] * bins
    for angle, distance, quality in zip(scan.angles_deg, scan.distances_mm, scan.qualities):
        metres = distance / 1000
        if not (math.isfinite(angle) and math.isfinite(metres) and quality > 0
                and range_min <= metres <= range_max):
            continue
        index = int(math.floor((angle % 360) / 360 * bins + 0.5)) % bins
        if math.isnan(result[index]) or metres < result[index]:
            result[index] = metres
    return result
