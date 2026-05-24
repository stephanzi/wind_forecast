/**
 * Bay Area wind forecast — combined 72-hour table for four spots.
 */

const HOURS_TO_SHOW = 72;
const TIMEZONE = "America/Los_Angeles";
const API_URL = "https://api.open-meteo.com/v1/forecast";

const WEEKDAY_LABELS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"];

const LOCATIONS = [
  {
    name: "Crissy Field",
    latitude: 37.806662797805316,
    longitude: -122.45196668011417,
  },
  {
    name: "Mussel Rock",
    latitude: 37.66726819773798,
    longitude: -122.49778761412684,
  },
  {
    name: "Half Moon Bay Inlet",
    latitude: 37 + 29 / 60 + 35.89 / 3600,
    longitude: -(122 + 29 / 60 + 6 / 3600),
  },
  {
    name: "Waddell Creek",
    latitude: 37.093991877735,
    longitude: -122.28054683283537,
  },
];

const WIND_COLOR_STOPS = [
  [0, [255, 255, 255]],
  [3, [173, 216, 230]],
  [8, [60, 179, 113]],
  [12, [255, 165, 0]],
  [18, [139, 0, 0]],
  [26, [128, 0, 128]],
  [30, [75, 0, 130]],
];
const MAX_GRADIENT_KTS = 30;
const PURPLE_ABOVE_MAX = [75, 0, 130];

const statusEl = document.getElementById("status");
const rootEl = document.getElementById("forecast-root");
const refreshBtn = document.getElementById("refresh-btn");

refreshBtn.addEventListener("click", () => loadForecast());

function lerp(a, b, t) {
  return a + (b - a) * t;
}

function lerpRgb(colorA, colorB, t) {
  return colorA.map((value, index) => Math.round(lerp(value, colorB[index], t)));
}

function windSpeedRgb(speedKnots) {
  if (speedKnots == null || Number.isNaN(speedKnots)) {
    return [128, 128, 128];
  }
  const speed = Number(speedKnots);
  if (speed >= MAX_GRADIENT_KTS) {
    return PURPLE_ABOVE_MAX;
  }
  if (speed <= 0) {
    return WIND_COLOR_STOPS[0][1];
  }
  for (let index = 0; index < WIND_COLOR_STOPS.length - 1; index += 1) {
    const [speedLow, colorLow] = WIND_COLOR_STOPS[index];
    const [speedHigh, colorHigh] = WIND_COLOR_STOPS[index + 1];
    if (speed <= speedHigh) {
      if (speedHigh === speedLow) {
        return colorHigh;
      }
      const fraction = (speed - speedLow) / (speedHigh - speedLow);
      return lerpRgb(colorLow, colorHigh, fraction);
    }
  }
  return PURPLE_ABOVE_MAX;
}

function rgbToCss([r, g, b]) {
  return `rgb(${r}, ${g}, ${b})`;
}

function textColorForBackground([r, g, b]) {
  const luminance = 0.299 * r + 0.587 * g + 0.114 * b;
  return luminance > 160 ? "#111" : "#fff";
}

function formatDateParts(timeStr) {
  const [datePart] = timeStr.split("T");
  const [year, month, day] = datePart.split("-").map(Number);
  const date = new Date(Date.UTC(year, month - 1, day, 12, 0, 0));
  const dayIndex = date.getUTCDay();
  const weekday = WEEKDAY_LABELS[dayIndex === 0 ? 6 : dayIndex - 1];
  return { weekday, monthDay: `${month}/${day}` };
}

function formatHourLabel(timeStr) {
  return timeStr.split("T")[1].slice(0, 2);
}

function windArrowStyle(degreesFrom) {
  if (degreesFrom == null || Number.isNaN(degreesFrom)) {
    return null;
  }
  const toDeg = (Number(degreesFrom) + 180) % 360;
  return `transform: rotate(${toDeg}deg)`;
}

function buildRecords(apiData) {
  const hourly = apiData.hourly;
  const records = [];
  for (let index = 0; index < hourly.time.length && index < HOURS_TO_SHOW; index += 1) {
    records.push({
      time: hourly.time[index],
      windSpeedKnots: hourly.wind_speed_10m[index],
      windDirectionDegrees: hourly.wind_direction_10m[index],
    });
  }
  return records;
}

function buildCombinedColumns(allRecords) {
  const baseRecords = allRecords[0];
  return baseRecords.map((baseRecord, hourIndex) => {
    const { weekday, monthDay } = formatDateParts(baseRecord.time);
    return {
      weekday,
      monthDay,
      hour: formatHourLabel(baseRecord.time),
      locations: allRecords.map((records) => ({
        windKts:
          records[hourIndex].windSpeedKnots == null
            ? "n/a"
            : records[hourIndex].windSpeedKnots.toFixed(1),
        windSpeedRaw: records[hourIndex].windSpeedKnots,
        windDirectionDegrees: records[hourIndex].windDirectionDegrees,
      })),
    };
  });
}

function buildCombinedTableHtml(columns) {
  let html = '<div class="table-scroll"><table class="forecast-table">';

  html += '<tr><th scope="row" class="row-label">Date</th>';
  for (const col of columns) {
    html += `<td class="date-cell"><span class="dow">${col.weekday}</span><span class="dom">${col.monthDay}</span></td>`;
  }
  html += "</tr>";

  html += '<tr><th scope="row" class="row-label">Hour</th>';
  for (const col of columns) {
    html += `<td class="hour-cell">${col.hour}</td>`;
  }
  html += "</tr>";

  for (let locIndex = 0; locIndex < LOCATIONS.length; locIndex += 1) {
    const location = LOCATIONS[locIndex];
    html += `<tr><th scope="row" class="row-label">${location.name} Wind (kts)</th>`;
    for (const col of columns) {
      const loc = col.locations[locIndex];
      const rgb = windSpeedRgb(loc.windSpeedRaw);
      const bg = rgbToCss(rgb);
      const fg = textColorForBackground(rgb);
      html += `<td class="wind-cell" style="background:${bg};color:${fg}">${loc.windKts}</td>`;
    }
    html += "</tr>";

    html += `<tr><th scope="row" class="row-label">${location.name} Dir</th>`;
    for (const col of columns) {
      const loc = col.locations[locIndex];
      const style = windArrowStyle(loc.windDirectionDegrees);
      if (style) {
        html += `<td class="dir-cell"><span class="wind-arrow" style="${style}" aria-hidden="true">↑</span></td>`;
      } else {
        html += '<td class="dir-cell">·</td>';
      }
    }
    html += "</tr>";
  }

  html += "</table></div>";
  return html;
}

async function fetchForecasts() {
  const params = new URLSearchParams({
    latitude: LOCATIONS.map((loc) => loc.latitude).join(","),
    longitude: LOCATIONS.map((loc) => loc.longitude).join(","),
    hourly: "wind_speed_10m,wind_direction_10m",
    wind_speed_unit: "kn",
    forecast_days: "3",
    timezone: TIMEZONE,
  });

  const response = await fetch(`${API_URL}?${params.toString()}`);
  if (!response.ok) {
    throw new Error(`Open-Meteo returned ${response.status}`);
  }

  const data = await response.json();
  return Array.isArray(data) ? data : [data];
}

function setStatus(message, isError = false) {
  statusEl.textContent = message;
  statusEl.classList.toggle("error", isError);
}

async function loadForecast() {
  refreshBtn.disabled = true;
  setStatus("Loading forecast…");

  try {
    const apiResults = await fetchForecasts();
    const allRecords = LOCATIONS.map((_loc, index) => buildRecords(apiResults[index]));
    const columns = buildCombinedColumns(allRecords);
    const updatedAt = new Date().toLocaleString("en-US", {
      timeZone: TIMEZONE,
      dateStyle: "medium",
      timeStyle: "short",
    });

    rootEl.innerHTML = `
      <section class="forecast-card">
        ${buildCombinedTableHtml(columns)}
      </section>
    `;

    setStatus(`Updated ${updatedAt} (${TIMEZONE})`);
  } catch (error) {
    console.error(error);
    rootEl.innerHTML = "";
    setStatus(`Could not load forecast: ${error.message}`, true);
  } finally {
    refreshBtn.disabled = false;
  }
}

loadForecast();
