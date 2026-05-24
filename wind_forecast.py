"""

Bay Area kite/wind forecast — fetches 72 hours of hourly wind (knots + direction)

from Open-Meteo (free, no API key) for four spots and saves JSON output.

"""



import json

import sys

from datetime import datetime

from pathlib import Path



import requests



# Gradient anchors: wind speed (knots) -> RGB. Smooth blend from 0–30 kts; 30+ stays purple.

WIND_COLOR_STOPS = (

    (0.0, (255, 255, 255)),    # white

    (3.0, (173, 216, 230)),    # light blue

    (8.0, (60, 179, 113)),     # green

    (12.0, (255, 165, 0)),     # orange

    (18.0, (139, 0, 0)),       # dark red

    (26.0, (128, 0, 128)),     # purple begins

    (30.0, (75, 0, 130)),      # deep purple at 30 kts

)

MAX_GRADIENT_KTS = 30.0

PURPLE_ABOVE_MAX = (75, 0, 130)



# Two-letter weekday labels for the date row (Mo, Tu, … Sa, Su)

WEEKDAY_LABELS = ("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su")

# Each table row: (label in first column, key in column dicts)

TABLE_ROWS = (

    ("Date", "date"),

    ("Hour", "hour"),

    ("Wind (kts)", "wind_kts"),

    ("Dir (deg)", "wind_dir"),

)



# Forecast spots in display order (Open-Meteo uses model grid points near each coordinate)

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

        # Harbor entrance — 37° 29' 35.89" N, 122° 29' 6.0" W

        "latitude": 37.0 + 29 / 60 + 35.89 / 3600,

        "longitude": -(122.0 + 29 / 60 + 6.0 / 3600),

    },

    {

        "name": "Waddell Creek",

        "latitude": 37.093991877735,

        "longitude": -122.28054683283537,

    },

)



# How many hours of forecast we want

HOURS_TO_SHOW = 72



# Open-Meteo forecast API (free, no sign-up required)

API_URL = "https://api.open-meteo.com/v1/forecast"

TIMEZONE = "America/Los_Angeles"



# Where we will write the saved forecast

OUTPUT_FILE = Path("wind_forecast.json")





def fetch_wind_forecasts(locations):

    """

    Ask Open-Meteo for hourly wind at 10 m for every location in one request.

    Returns a list of API response dicts in the same order as locations.

    """

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

    if isinstance(data, list):

        return data

    return [data]





def build_forecast_records(api_data):

    """

    Turn the API's parallel time/speed/direction arrays into a list of dicts,

    limited to the next 72 hours.

    """

    hourly = api_data["hourly"]

    times = hourly["time"]

    speeds = hourly["wind_speed_10m"]

    directions = hourly["wind_direction_10m"]



    records = []

    for time_str, speed_knots, direction_deg in zip(times, speeds, directions):

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

    """Convert API timestamp like '2026-05-23T14:00' into a datetime object."""

    return datetime.fromisoformat(time_str)





def format_date_label(dt):

    """e.g. Sa 5/23"""

    weekday = WEEKDAY_LABELS[dt.weekday()]

    return f"{weekday} {dt.month}/{dt.day}"





def format_hour_label(dt):

    """e.g. 01:00 (24-hour clock, always two digits for the hour)"""

    return dt.strftime("%H:00")





def _lerp(a, b, t):

    """Linear blend between two numbers; t is 0.0 at a and 1.0 at b."""

    return a + (b - a) * t





def _lerp_rgb(color_a, color_b, t):

    """Blend two RGB tuples."""

    return tuple(int(_lerp(color_a[i], color_b[i], t)) for i in range(3))





def wind_speed_rgb(speed_knots):

    """

    Map wind speed to an RGB color along the 0–30 kt gradient.

    Speeds above 30 kt use deep purple.

    """

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

    """Turn on ANSI color support in Windows terminals (no-op elsewhere)."""

    if sys.platform != "win32":

        return

    try:

        import ctypes



        handle = ctypes.windll.kernel32.GetStdHandle(-11)

        mode = ctypes.c_ulong()

        ctypes.windll.kernel32.GetConsoleMode(handle, ctypes.byref(mode))

        mode.value |= 0x0004  # ENABLE_VIRTUAL_TERMINAL_PROCESSING

        ctypes.windll.kernel32.SetConsoleMode(handle, mode)

    except (AttributeError, OSError):

        pass





def colorize_text(text, rgb, background=True):

    """

    Wrap text in 24-bit ANSI color codes.

    Uses a dark or light foreground so numbers stay readable on the background.

    """

    red, green, blue = rgb

    luminance = 0.299 * red + 0.587 * green + 0.114 * blue

    if luminance > 160:

        fg = (0, 0, 0)

    else:

        fg = (255, 255, 255)



    if background:

        return f"\033[48;2;{red};{green};{blue}m\033[38;2;{fg[0]};{fg[1]};{fg[2]}m{text}\033[0m"

    return f"\033[38;2;{red};{green};{blue}m{text}\033[0m"





def format_wind_kts(speed):

    """Wind speed for the table cell, one decimal place."""

    if speed is None:

        return "n/a"

    return f"{speed:.1f}"





def format_wind_direction(degrees):

    """

    Wind direction as whole degrees (0–360).



    Open-Meteo uses meteorological convention: degrees clockwise from north,

    where the value is the direction the wind is coming FROM (not blowing toward).

    """

    if degrees is None:

        return "n/a"

    return str(int(round(degrees)))





def build_forecast_table(records):

    """

    Build table rows (date, hour, wind speed, wind direction) per forecast hour.

    Returns (row definitions, list of column dicts).

    """

    columns = []

    for record in records:

        dt = _parse_local_time(record["time"])

        columns.append(

            {

                "date": format_date_label(dt),

                "hour": format_hour_label(dt),

                "wind_kts": format_wind_kts(record["wind_speed_knots"]),

                "wind_dir": format_wind_direction(

                    record["wind_direction_degrees"]

                ),

            }

        )

    return TABLE_ROWS, columns





def table_row_values(columns, field):

    """Pull one row of cell values from the column dicts."""

    return [col[field] for col in columns]





def build_location_payload(location, api_data, records):

    """Build one location block for JSON export."""

    row_defs, columns = build_forecast_table(records)

    payload = {

        "name": location["name"],

        "latitude": location["latitude"],

        "longitude": location["longitude"],

        "hours": len(records),

        "forecast": records,

        "table": {

            "rows": [

                [label, *table_row_values(columns, field)]

                for label, field in row_defs

            ],

        },

    }

    # Open-Meteo returns the model grid-cell center (may differ slightly from request)

    if "latitude" in api_data and "longitude" in api_data:

        payload["model_grid_latitude"] = api_data["latitude"]

        payload["model_grid_longitude"] = api_data["longitude"]

    return payload





def save_to_json(location_payloads):

    """Write all location forecasts to a single JSON file."""

    output = {

        "units": {

            "wind_speed": "knots",

            "wind_direction": "degrees (meteorological, 0–360)",

        },

        "source": "Open-Meteo (https://open-meteo.com)",

        "timezone": TIMEZONE,

        "hours_per_location": HOURS_TO_SHOW,

        "locations": location_payloads,

    }



    OUTPUT_FILE.write_text(json.dumps(output, indent=2), encoding="utf-8")

    return OUTPUT_FILE





def print_forecast_table(location_name, records, show_color_legend=False):

    """

    Print a wide table: each column is one hour; rows = date, hour, wind, direction.

    The first column labels each row.

    """

    row_defs, columns = build_forecast_table(records)



    col_widths = []

    for index in range(len(columns)):

        cells = []

        for label, field in row_defs:

            cells.append(label)

            cells.append(columns[index][field])

        col_widths.append(max(len(cell) for cell in cells))



    label_width = max(len(label) for label, _ in row_defs)



    def format_row(label, values, color_speeds=None):

        label_cell = label.ljust(label_width)

        data_cells = []

        for index, value in enumerate(values):

            padded = value.rjust(col_widths[index])

            if color_speeds is not None:

                rgb = wind_speed_rgb(color_speeds[index])

                padded = colorize_text(padded, rgb, background=True)

            data_cells.append(padded)

        return label_cell + "  " + "  ".join(data_cells)



    wind_speeds = [record["wind_speed_knots"] for record in records]



    print(f"\n{'=' * 72}")

    print(f"Wind forecast: {location_name}")

    print(f"Next {len(records)} hours, local time ({TIMEZONE})")

    if show_color_legend:

        print("Wind speeds use a 0–30 kt color gradient (30+ kt = deep purple)")

    print()



    for label, field in row_defs:

        values = table_row_values(columns, field)

        if field == "wind_kts":

            print(format_row(label, values, color_speeds=wind_speeds))

        else:

            print(format_row(label, values))





def main():

    enable_terminal_colors()

    print("Fetching wind forecasts from Open-Meteo...")

    print(f"Locations: {', '.join(loc['name'] for loc in LOCATIONS)}")



    api_results = fetch_wind_forecasts(LOCATIONS)

    location_payloads = []



    for index, location in enumerate(LOCATIONS):

        records = build_forecast_records(api_results[index])

        print_forecast_table(

            location["name"],

            records,

            show_color_legend=(index == 0),

        )

        location_payloads.append(

            build_location_payload(location, api_results[index], records)

        )



    saved_path = save_to_json(location_payloads)

    print(f"\nSaved {len(LOCATIONS)} locations to: {saved_path.resolve()}")





if __name__ == "__main__":

    main()


