(function () {
  const WEATHER_CODES = {
    0:  { label: "Clear sky", icon: "☀" },
    1:  { label: "Mainly clear", icon: "🌤" },
    2:  { label: "Partly cloudy", icon: "⛅" },
    3:  { label: "Overcast", icon: "☁" },
    45: { label: "Fog", icon: "🌫" },
    48: { label: "Depositing rime fog", icon: "🌫" },
    51: { label: "Light drizzle", icon: "🌦" },
    53: { label: "Moderate drizzle", icon: "🌦" },
    55: { label: "Dense drizzle", icon: "🌧" },
    56: { label: "Light freezing drizzle", icon: "🌧" },
    57: { label: "Dense freezing drizzle", icon: "🌧" },
    61: { label: "Slight rain", icon: "🌧" },
    63: { label: "Moderate rain", icon: "🌧" },
    65: { label: "Heavy rain", icon: "🌧" },
    66: { label: "Light freezing rain", icon: "🌧" },
    67: { label: "Heavy freezing rain", icon: "🌧" },
    71: { label: "Slight snow fall", icon: "🌨" },
    73: { label: "Moderate snow fall", icon: "🌨" },
    75: { label: "Heavy snow fall", icon: "❄" },
    77: { label: "Snow grains", icon: "❄" },
    80: { label: "Slight rain showers", icon: "🌦" },
    81: { label: "Moderate rain showers", icon: "🌦" },
    82: { label: "Violent rain showers", icon: "⛈" },
    85: { label: "Slight snow showers", icon: "🌨" },
    86: { label: "Heavy snow showers", icon: "❄" },
    95: { label: "Thunderstorm", icon: "⛈" },
    96: { label: "Thunderstorm with hail", icon: "⛈" },
    99: { label: "Thunderstorm with hail", icon: "⛈" },
  };

  function weatherCodeMeta(code) {
    return WEATHER_CODES[code] || { label: "Weather unavailable", icon: "•" };
  }

  function dayName(dateString) {
    const date = new Date(dateString + "T12:00:00");
    return date.toLocaleDateString("en-GB", { weekday: "short" });
  }

  function formatNumber(value, suffix) {
    if (value === null || value === undefined || Number.isNaN(value)) {
      return "—";
    }
    return String(Math.round(value)) + suffix;
  }

  function createNode(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function replaceContent(container, children) {
    container.textContent = "";
    children.forEach(function (child) {
      container.appendChild(child);
    });
  }

  function buildCurrent(data) {
    const codeMeta = weatherCodeMeta(data.current.weathercode);

    const currentCard = createNode("div", "weather-current");
    const top = createNode("div", "weather-current-top");
    const left = createNode("div", "");
    left.appendChild(createNode("div", "weather-current-temp", formatNumber(data.current.temperature_2m, "°C")));

    const summary = createNode("div", "weather-current-summary");
    summary.appendChild(createNode("span", "weather-icon", codeMeta.icon));
    summary.appendChild(createNode("span", "", codeMeta.label));
    left.appendChild(summary);

    top.appendChild(left);
    currentCard.appendChild(top);

    const stats = createNode("div", "weather-current-grid");
    [
      ["Humidity", formatNumber(data.current.relative_humidity_2m, "%")],
      ["Wind", formatNumber(data.current.windspeed_10m, " km/h")],
      ["Precip.", formatNumber(data.current.precipitation, " mm")],
      ["Updated", "Live"],
    ].forEach(function (entry) {
      const card = createNode("div", "weather-stat");
      card.appendChild(createNode("div", "weather-stat-label", entry[0]));
      card.appendChild(createNode("div", "weather-stat-value", entry[1]));
      stats.appendChild(card);
    });
    currentCard.appendChild(stats);

    return currentCard;
  }

  function buildForecast(data) {
    const strip = createNode("div", "weather-forecast");

    data.daily.time.slice(0, 3).forEach(function (time, index) {
      const meta = weatherCodeMeta(data.daily.weathercode[index]);
      const dayCard = createNode("div", "weather-forecast-day");
      dayCard.appendChild(createNode("div", "weather-forecast-name", dayName(time)));
      dayCard.appendChild(createNode("div", "weather-icon", meta.icon));
      dayCard.appendChild(createNode("div", "weather-forecast-precip", formatNumber(data.daily.precipitation_sum[index], " mm rain")));
      dayCard.appendChild(
        createNode(
          "div",
          "weather-forecast-temp",
          formatNumber(data.daily.temperature_2m_max[index], "°") + " / " +
            formatNumber(data.daily.temperature_2m_min[index], "°")
        )
      );
      strip.appendChild(dayCard);
    });

    return strip;
  }

  function renderFallback(container) {
    replaceContent(container, [
      createNode("p", "sidebar-message", "Live weather is temporarily unavailable. Please try again later."),
    ]);
  }

  async function hydrateWidget(host) {
    const container = host.querySelector(".weather-widget");
    if (!container) return;

    const latitude = host.dataset.latitude;
    const longitude = host.dataset.longitude;
    const timezone = host.dataset.timezone || "Africa/Accra";
    const location = host.dataset.location;

    if (location) {
      const label = host.querySelector(".section-label");
      if (label) label.textContent = "Weather Context \u00b7 " + location;
    }

    const url = "https://api.open-meteo.com/v1/forecast" +
      "?latitude=" + encodeURIComponent(latitude) +
      "&longitude=" + encodeURIComponent(longitude) +
      "&current=temperature_2m,precipitation,weathercode,windspeed_10m,relative_humidity_2m" +
      "&daily=precipitation_sum,temperature_2m_max,temperature_2m_min,weathercode" +
      "&timezone=" + encodeURIComponent(timezone) +
      "&forecast_days=3";

    try {
      const response = await fetch(url, { method: "GET" });
      if (!response.ok) throw new Error("Weather request failed");
      const data = await response.json();
      if (!data.current || !data.daily || !Array.isArray(data.daily.time)) {
        throw new Error("Weather payload incomplete");
      }

      replaceContent(container, [
        buildCurrent(data),
        buildForecast(data),
      ]);
    } catch (error) {
      console.warn("WeatherWidget:", error.message);
      renderFallback(container);
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-weather-widget]").forEach(function (widget) {
      hydrateWidget(widget);
    });
  });
})();
