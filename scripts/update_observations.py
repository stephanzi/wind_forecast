"""Fetch NDBC buoy readings and write docs/current_observations.json for the static site."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wind_forecast import fetch_ndbc_observation  # noqa: E402

OUTPUT = ROOT / "docs" / "current_observations.json"
NDBC_STATIONS = ("46026", "46012", "46042")


def main():
    stations = {}
    for station_id in NDBC_STATIONS:
        try:
            direction_deg, speed_knots = fetch_ndbc_observation(station_id)
            stations[station_id] = {
                "direction_degrees": direction_deg,
                "speed_knots": speed_knots,
            }
        except Exception as error:
            stations[station_id] = {"error": str(error)}

    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "source": "NOAA NDBC (https://www.ndbc.noaa.gov)",
        "stations": stations,
    }
    OUTPUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
