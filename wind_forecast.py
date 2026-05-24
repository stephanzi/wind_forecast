"""
Bay Area kite/wind forecast — 72-hour combined table for four spots.
Fetches from Open-Meteo (free, no API key) and saves JSON output.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import requests

# Gradient anchors: wind speed (knots) -> RGB. Smooth blend from 0–30 kts; 30+ stays purple.
WIND_COLOR_STOPS = (
    (0.0, (255, 255, 255)),
    (3.0, (173, 216, 230)),
    (8.0, (60, 179, 113)),
    (12.0, (255, 165, 0)),
    (18.0, (139, 0, 0)),
    (26.0, (128, 0, 128)),
    (30.0, (75, 0, 130)),
)
MAX_GRADIENT_KTS = 30.0
PURPLE_ABOVE_MAX = (75, 0, 130)

WEEKDAY_LABELS = ("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su")
# 8-point arrows for direction wind is blowing toward (0° = north)
WIND_ARROWS = ("↑", "↗", "→", "↘", "↓", "↙", "←", "↖")

LOCATIONS = (
    {
        "name": "Crissy Field",
        "latitude": 37.806662797805316,
        "longitude": -122.45196668011417,
    },
    {
        "name": "Mussel Rock",
        "latitude": 37.66726819773798,
        "longitude": -122.49778761412684,
    },
    {
        "name": "Half Moon Bay Inlet",
        "latitude": 37.0 + 29 / 60 + 35.89 / 3600,
        "longitude": -(122.0 + 29 / 60 + 6.0 / 3600),
    },
    {
        "name": "Waddell Creek",
        "latitude": 37.093991877735,
        "longitude": -122.28054683283537,
    },
)

HOURS_TO_SHOW = 72
API_URL = "https://api.open-meteo.com/v1/forecast"
TIMEZONE = "America/Los_Angeles"
OUTPUT_FILE = Path("wind_forecast.json")


def fetch_wind_forecasts(locations):
    """Fetch hourly wind for all locations in one Open-Meteo request."""
    params = {
        "latitude": ",".join(str(loc["latitude"]) for loc in locations),
        "longitude": ",".join(str(loc["longitude"]) for loc in locations),
        "hourly": "wind_speed_10m,wind_direction_10m",
        "wind_speed_unit": "kn",
        "forecast_days": 3,
        "timezone": TIMEZONE,
    }
    response = requests.get(API_URL, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()
    return data if isinstance(data, list) else [data]


def build_forecast_records(api_data):
    """Build up to 72 hourly records from one API response."""
    hourly = api_data["hourly"]
    records = []
    for time_str, speed_knots, direction_deg in zip(
        hourly["time"],
        hourly["wind_speed_10m"],
        hourly["wind_direction_10m"],
    ):
        records.append(
            {
                "time": time_str,
                "wind_speed_knots": speed_knots,
                "wind_direction_degrees": direction_deg,
            }
        )
        if len(records) >= HOURS_TO_SHOW:
            break
    return records


def _parse_local_time(time_str):
    return datetime.fromisoformat(time_str)


def format_date_parts(dt):
    """Split date into weekday and month/day for a narrow two-line column."""
    weekday = WEEKDAY_LABELS[dt.weekday()]
    return weekday, f"{dt.month}/{dt.day}"


def format_hour_label(dt):
    """Compact hour label (24-hour)."""
    return dt.strftime("%H")


def _lerp(a, b, t):
    return a + (b - a) * t


def _lerp_rgb(color_a, color_b, t):
    return tuple(int(_lerp(color_a[i], color_b[i], t)) for i in range(3))


def wind_speed_rgb(speed_knots):
    if speed_knots is None:
        return (128, 128, 128)
    speed = float(speed_knots)
    if speed >= MAX_GRADIENT_KTS:
        return PURPLE_ABOVE_MAX
    if speed <= 0:
        return WIND_COLOR_STOPS[0][1]
    for index in range(len(WIND_COLOR_STOPS) - 1):
        speed_low, color_low = WIND_COLOR_STOPS[index]
        speed_high, color_high = WIND_COLOR_STOPS[index + 1]
        if speed <= speed_high:
            if speed_high == speed_low:
                return color_high
            fraction = (speed - speed_low) / (speed_high - speed_low)
            return _lerp_rgb(color_low, color_high, fraction)
    return PURPLE_ABOVE_MAX


def enable_terminal_colors():
    if sys.platform != "win32":
        return
    try:
        import ctypes

        handle = ctypes.windll.kernel32.GetStdHandle(-11)
        mode = ctypes.c_ulong()
        ctypes.windll.kernel32.GetConsoleMode(handle, ctypes.byref(mode))
        mode.value |= 0x0004
        ctypes.windll.kernel32.SetConsoleMode(handle, mode)
    except (AttributeError, OSError):
        pass


def colorize_text(text, rgb, background=True):
    red, green, blue = rgb
    luminance = 0.299 * red + 0.587 * green + 0.114 * blue
    fg = (0, 0, 0) if luminance > 160 else (255, 255, 255)
    if background:
        return f"\033[48;2;{red};{green};{blue}m\033[38;2;{fg[0]};{fg[1]};{fg[2]}m{text}\033[0m"
    return f"\033[38;2;{red};{green};{blue}m{text}\033[0m"


def format_wind_kts(speed):
    if speed is None:
        return "n/a"
    return f"{speed:.1f}"


def format_wind_arrow(degrees_from):
    """
    Arrow pointing where the wind is blowing (opposite of meteorological 'from').
    """
    if degrees_from is None:
        return "·"
    to_deg = (float(degrees_from) + 180) % 360
    index = int(round(to_deg / 45)) % 8
    return WIND_ARROWS[index]


def build_combined_columns(location_records_list):
    """
    One column per hour. Shared date/hour; each location adds wind + arrow rows.
    """
    base_records = location_records_list[0]
    columns = []

    for hour_index, base_record in enumerate(base_records):
        dt = _parse_local_time(base_record["time"])
        weekday, month_day = format_date_parts(dt)
        column = {
            "weekday": weekday,
            "month_day": month_day,
            "hour": format_hour_label(dt),
            "locations": [],
        }
        for records in location_records_list:
            record = records[hour_index]
            column["locations"].append(
                {
                    "wind_kts": format_wind_kts(record["wind_speed_knots"]),
                    "wind_speed_raw": record["wind_speed_knots"],
                    "wind_arrow": format_wind_arrow(
                        record["wind_direction_degrees"]
                    ),
                    "wind_direction_degrees": record["wind_direction_degrees"],
                }
            )
        columns.append(column)

    return columns


def build_row_definitions():
    """Header rows (date, hour) then wind + direction row per location."""
    rows = [
        ("Date", "date"),
        ("Hour", "hour"),
    ]
    for location in LOCATIONS:
        rows.append((f"{location['name']} Wind (kts)", "wind_kts"))
        rows.append((f"{location['name']} Dir", "wind_dir"))
    return rows


def compute_column_widths(columns, row_defs):
    widths = []
    for index in range(len(columns)):
        max_width = 2
        loc_idx = 0
        for _row_label, field in row_defs:
            if field == "date":
                cell = f"{columns[index]['weekday']}\n{columns[index]['month_day']}"
            elif field == "hour":
                cell = columns[index]["hour"]
            elif field == "wind_kts":
                cell = columns[index]["locations"][loc_idx]["wind_kts"]
            elif field == "wind_dir":
                cell = columns[index]["locations"][loc_idx]["wind_arrow"]
                loc_idx += 1
            else:
                continue
            for line in str(cell).split("\n"):
                max_width = max(max_width, len(line))
        widths.append(max_width)
    return widths


def build_combined_table_rows(columns, row_defs):
    """Build printable/exportable row arrays for the combined table."""
    rows = []
    location_index = 0
    for row_label, field in row_defs:
        if field == "date":
            values = [
                f"{col['weekday']}\n{col['month_day']}" for col in columns
            ]
        elif field == "hour":
            values = [col["hour"] for col in columns]
        elif field == "wind_kts":
            values = [
                col["locations"][location_index]["wind_kts"] for col in columns
            ]
        elif field == "wind_dir":
            values = [
                col["locations"][location_index]["wind_arrow"] for col in columns
            ]
            location_index += 1
        else:
            continue
        rows.append([row_label, *values])
    return rows


def build_location_payload(location, api_data, records):
    return {
        "name": location["name"],
        "latitude": location["latitude"],
        "longitude": location["longitude"],
        "hours": len(records),
        "forecast": records,
        **(
            {
                "model_grid_latitude": api_data["latitude"],
                "model_grid_longitude": api_data["longitude"],
            }
            if "latitude" in api_data and "longitude" in api_data
            else {}
        ),
    }


def save_to_json(location_payloads, combined_rows):
    output = {
        "units": {
            "wind_speed": "knots",
            "wind_direction": "arrow shows direction wind is blowing toward",
        },
        "source": "Open-Meteo (https://open-meteo.com)",
        "timezone": TIMEZONE,
        "hours_per_location": HOURS_TO_SHOW,
        "combined_table": {"rows": combined_rows},
        "locations": location_payloads,
    }
    OUTPUT_FILE.write_text(json.dumps(output, indent=2), encoding="utf-8")
    return OUTPUT_FILE


def print_combined_forecast_table(all_records):
    """Print one wide table: date/hour on top, then each location's wind + arrow."""
    row_defs = build_row_definitions()
    columns = build_combined_columns(all_records)
    col_widths = compute_column_widths(columns, row_defs)
    label_width = max(len(label) for label, _ in row_defs)

    def pad_cell(text, width):
        if "\n" in text:
            lines = text.split("\n")
            return "\n".join(line.rjust(width) for line in lines)
        return text.rjust(width)

    def print_data_line(label, values, color_speeds=None, show_label=True):
        label_cell = label.ljust(label_width) if show_label else " " * label_width
        cells = []
        for index, value in enumerate(values):
            padded = pad_cell(value, col_widths[index])
            if color_speeds is not None:
                padded = colorize_text(padded, wind_speed_rgb(color_speeds[index]))
            cells.append(padded)
        print(f"{label_cell}  " + "  ".join(cells))

    print(f"\n{'=' * 72}")
    print("Bay Area wind forecast — combined view")
    print(f"Next {len(columns)} hours, local time ({TIMEZONE})")
    print("Arrows point where wind is blowing. Colors: 0–30 kt gradient.\n")

    location_index = 0
    for row_label, field in row_defs:
        if field == "date":
            weekdays = [col["weekday"] for col in columns]
            month_days = [col["month_day"] for col in columns]
            print_data_line(row_label, weekdays)
            print_data_line("", month_days, show_label=False)
            continue

        if field == "hour":
            values = [col["hour"] for col in columns]
            print_data_line(row_label, values)
            continue

        values = [
            col["locations"][location_index]["wind_kts"]
            if field == "wind_kts"
            else col["locations"][location_index]["wind_arrow"]
            for col in columns
        ]
        if field == "wind_kts":
            speeds = [
                col["locations"][location_index]["wind_speed_raw"]
                for col in columns
            ]
            print_data_line(row_label, values, color_speeds=speeds)
        else:
            print_data_line(row_label, values)
            location_index += 1


def main():
    enable_terminal_colors()
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except (AttributeError, OSError):
            pass
    print("Fetching wind forecasts from Open-Meteo...")
    print(f"Locations: {', '.join(loc['name'] for loc in LOCATIONS)}")

    api_results = fetch_wind_forecasts(LOCATIONS)
    all_records = []
    location_payloads = []

    for location, api_data in zip(LOCATIONS, api_results):
        records = build_forecast_records(api_data)
        all_records.append(records)
        location_payloads.append(build_location_payload(location, api_data, records))

    print_combined_forecast_table(all_records)

    columns = build_combined_columns(all_records)
    row_defs = build_row_definitions()
    combined_rows = build_combined_table_rows(columns, row_defs)
    saved_path = save_to_json(location_payloads, combined_rows)
    print(f"\nSaved {len(LOCATIONS)} locations to: {saved_path.resolve()}")


if __name__ == "__main__":
    main()
