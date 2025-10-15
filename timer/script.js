const languages = [
  {
    code: "ko",
    locale: "ko-KR",
    label: "한국어",
  },
  {
    code: "en",
    locale: "en-US",
    label: "English",
  },
];

const translations = {
  ko: {
    title: "귀여운 세계 시계",
    languageButton: "언어: 한국어",
    languageButtonAria: "언어 변경",
    activeCityLabel: "선택 도시",
    hours: "시",
    minutes: "분",
    seconds: "초",
    milliseconds: "밀리초",
    mapTitle: "세계 지도",
    mapSubtitle: "지도 위 귀여운 도시 아이콘을 눌러서 시간을 바꿔보세요!",
    dayLabel: "낮",
    nightLabel: "밤",
    viewTimeForPrefix: "",
    viewTimeForSuffix: "시간 보기",
    am: "AM",
    pm: "PM",
  },
  en: {
    title: "Adorable World Clock",
    languageButton: "Language: English",
    languageButtonAria: "Change language",
    activeCityLabel: "Active City",
    hours: "Hour",
    minutes: "Minute",
    seconds: "Second",
    milliseconds: "Millis",
    mapTitle: "World Map",
    mapSubtitle: "Tap the cute city bubbles to explore different time zones!",
    dayLabel: "Day",
    nightLabel: "Night",
    viewTimeForPrefix: "View time for",
    viewTimeForSuffix: "",
    am: "AM",
    pm: "PM",
  },
};

const cities = [
  {
    id: "seoul",
    timeZone: "Asia/Seoul",
    coords: { x: 66, y: 37 },
    names: {
      ko: "서울",
      en: "Seoul",
    },
  },
  {
    id: "tokyo",
    timeZone: "Asia/Tokyo",
    coords: { x: 70, y: 39 },
    names: {
      ko: "도쿄",
      en: "Tokyo",
    },
  },
  {
    id: "sydney",
    timeZone: "Australia/Sydney",
    coords: { x: 80, y: 76 },
    names: {
      ko: "시드니",
      en: "Sydney",
    },
  },
  {
    id: "dubai",
    timeZone: "Asia/Dubai",
    coords: { x: 56, y: 46 },
    names: {
      ko: "두바이",
      en: "Dubai",
    },
  },
  {
    id: "london",
    timeZone: "Europe/London",
    coords: { x: 44, y: 35 },
    names: {
      ko: "런던",
      en: "London",
    },
  },
  {
    id: "new-york",
    timeZone: "America/New_York",
    coords: { x: 27, y: 43 },
    names: {
      ko: "뉴욕",
      en: "New York",
    },
  },
  {
    id: "los-angeles",
    timeZone: "America/Los_Angeles",
    coords: { x: 19, y: 46 },
    names: {
      ko: "로스앤젤레스",
      en: "Los Angeles",
    },
  },
  {
    id: "sao-paulo",
    timeZone: "America/Sao_Paulo",
    coords: { x: 33, y: 68 },
    names: {
      ko: "상파울루",
      en: "Sao Paulo",
    },
  },
  {
    id: "johannesburg",
    timeZone: "Africa/Johannesburg",
    coords: { x: 50, y: 68 },
    names: {
      ko: "요하네스버그",
      en: "Johannesburg",
    },
  },
];

const cityLookup = new Map(cities.map((city) => [city.id, city]));

const languageToggleBtn = document.getElementById("language-toggle");
const clockCityEl = document.getElementById("clock-city");
const clockHoursEl = document.getElementById("clock-hours");
const clockMinutesEl = document.getElementById("clock-minutes");
const clockSecondsEl = document.getElementById("clock-seconds");
const clockMillisEl = document.getElementById("clock-millis");
const clockPeriodEl = document.getElementById("clock-period");
const clockOffsetEl = document.getElementById("clock-offset");
const clockDateEl = document.getElementById("clock-date");
const digits = {
  hours: document.querySelector('[data-segment="hours"]'),
  minutes: document.querySelector('[data-segment="minutes"]'),
  seconds: document.querySelector('[data-segment="seconds"]'),
};
const millisWrapper = document.querySelector(".clock-display__millis");
const markerLayer = document.getElementById("city-marker-layer");

const markerRegistry = new Map();
const offsetFormatterCache = new Map();
const dateFormatterCache = new Map();

let currentLanguageIndex = 0;
let activeCityId = "seoul";
let animationFrameId = null;
let previousParts = {
  hours: null,
  minutes: null,
  seconds: null,
};
let lastSecondForMarkers = null;

function getCurrentLanguage() {
  return languages[currentLanguageIndex];
}

function getTranslation() {
  return translations[getCurrentLanguage().code];
}

function getOffsetFormatter(timeZone) {
  if (!offsetFormatterCache.has(timeZone)) {
    offsetFormatterCache.set(
      timeZone,
      new Intl.DateTimeFormat("en-US", {
        timeZone,
        timeZoneName: "shortOffset",
      }),
    );
  }
  return offsetFormatterCache.get(timeZone);
}

function getDateFormatter(locale, timeZone) {
  const key = `${locale}|${timeZone}`;
  if (!dateFormatterCache.has(key)) {
    dateFormatterCache.set(
      key,
      new Intl.DateTimeFormat(locale, {
        timeZone,
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        weekday: "short",
      }),
    );
  }
  return dateFormatterCache.get(key);
}

function parseOffsetMinutes(value) {
  const match = value.match(/GMT([+-]\d{1,2})(?::?(\d{2}))?/i);
  if (!match) {
    return 0;
  }
  const sign = match[1].startsWith("-") ? -1 : 1;
  const hours = Math.abs(parseInt(match[1], 10));
  const minutes = match[2] ? parseInt(match[2], 10) : 0;
  return sign * (hours * 60 + minutes);
}

function getOffsetMinutes(timeZone, referenceDate) {
  const formatter = getOffsetFormatter(timeZone);
  const parts = formatter.formatToParts(referenceDate);
  const tzPart = parts.find((part) => part.type === "timeZoneName");
  if (!tzPart) {
    return 0;
  }
  return parseOffsetMinutes(tzPart.value);
}

function formatOffsetLabel(offsetMinutes) {
  const sign = offsetMinutes >= 0 ? "+" : "-";
  const absolute = Math.abs(offsetMinutes);
  const hours = String(Math.floor(absolute / 60)).padStart(2, "0");
  const minutes = String(absolute % 60).padStart(2, "0");
  return `GMT${sign}${hours}:${minutes}`;
}

function getCityTimeData(cityId, referenceDate) {
  const city = cityLookup.get(cityId);
  const offsetMinutes = getOffsetMinutes(city.timeZone, referenceDate);
  const utc = referenceDate.getTime() + referenceDate.getTimezoneOffset() * 60000;
  const localDate = new Date(utc + offsetMinutes * 60000);
  const hours24 = localDate.getHours();
  const hour12 = hours24 % 12 || 12;
  return {
    city,
    localDate,
    hours24,
    hour12,
    minutes: localDate.getMinutes(),
    seconds: localDate.getSeconds(),
    milliseconds: localDate.getMilliseconds(),
    period: hours24 >= 12 ? "pm" : "am",
    offsetMinutes,
  };
}

function buildCityMarkers() {
  markerLayer.innerHTML = "";
  markerRegistry.clear();
  cities.forEach((city) => {
    const button = document.createElement("button");
    button.className = "map-marker";
    button.style.left = `${city.coords.x}%`;
    button.style.top = `${city.coords.y}%`;
    button.dataset.cityId = city.id;
    button.dataset.timezone = city.timeZone;
    button.setAttribute("role", "listitem");
    button.setAttribute("aria-pressed", "false");
    button.addEventListener("click", () => {
      setActiveCity(city.id);
    });

    const dot = document.createElement("span");
    dot.className = "map-marker__dot";

    const label = document.createElement("span");
    label.className = "map-marker__label";
    label.dataset.offset = "+00:00";

    button.append(dot, label);
    markerLayer.append(button);
    markerRegistry.set(city.id, { button, label });
  });
}

function applyTranslations() {
  const language = getCurrentLanguage();
  const strings = getTranslation();
  document.documentElement.lang = language.code;
  document.title = strings.title;

  document.querySelectorAll("[data-i18n]").forEach((element) => {
    const key = element.getAttribute("data-i18n");
    if (strings[key]) {
      element.textContent = strings[key];
    }
  });

  languageToggleBtn.textContent = strings.languageButton;
  languageToggleBtn.setAttribute("aria-label", strings.languageButtonAria);

  updateCityLabels();
}

function updateCityLabels() {
  const language = getCurrentLanguage();
  const strings = getTranslation();
  cities.forEach((city) => {
    const entry = markerRegistry.get(city.id);
    if (!entry) {
      return;
    }
    const name = city.names[language.code];
    entry.label.textContent = name;
    let ariaLabel = name;
    if (strings.viewTimeForPrefix) {
      ariaLabel = `${strings.viewTimeForPrefix} ${name}`;
    } else if (strings.viewTimeForSuffix) {
      ariaLabel = `${name} ${strings.viewTimeForSuffix}`;
    }
    entry.button.setAttribute("aria-label", ariaLabel);
    if (city.id === activeCityId) {
      clockCityEl.textContent = name;
    }
  });
}

function setActiveCity(cityId) {
  if (!cityLookup.has(cityId)) {
    return;
  }
  activeCityId = cityId;
  markerRegistry.forEach((entry, id) => {
    const isActive = id === cityId;
    entry.button.classList.toggle("is-active", isActive);
    entry.button.setAttribute("aria-pressed", isActive ? "true" : "false");
  });
  updateCityLabels();
  previousParts = {
    hours: null,
    minutes: null,
    seconds: null,
  };
}

function triggerAnimation(target) {
  if (!target) {
    return;
  }
  target.classList.remove("is-animating");
  // Force repaint so the animation can retrigger.
  void target.offsetWidth;
  target.classList.add("is-animating");
}

function updateClock(referenceDate) {
  const language = getCurrentLanguage();
  const strings = getTranslation();
  const timeData = getCityTimeData(activeCityId, referenceDate);
  const cityName = timeData.city.names[language.code];
  const offsetLabel = formatOffsetLabel(timeData.offsetMinutes);
  const dateFormatter = getDateFormatter(language.locale, timeData.city.timeZone);
  const formattedDate = dateFormatter.format(referenceDate);

  clockCityEl.textContent = cityName;
  clockPeriodEl.textContent =
    strings[timeData.period] ?? strings.am;
  clockHoursEl.textContent = String(timeData.hour12).padStart(2, "0");
  clockMinutesEl.textContent = String(timeData.minutes).padStart(2, "0");
  clockSecondsEl.textContent = String(timeData.seconds).padStart(2, "0");
  clockMillisEl.textContent = String(timeData.milliseconds).padStart(3, "0");
  clockOffsetEl.textContent = offsetLabel;
  clockDateEl.textContent = formattedDate;

  if (previousParts.minutes !== null && timeData.minutes !== previousParts.minutes) {
    triggerAnimation(digits.minutes);
  }
  if (previousParts.hours !== null && timeData.hours24 !== previousParts.hours) {
    triggerAnimation(digits.hours);
  }
  if (previousParts.seconds !== null && timeData.seconds !== previousParts.seconds) {
    triggerAnimation(digits.seconds);
    triggerAnimation(millisWrapper);
  }

  previousParts = {
    hours: timeData.hours24,
    minutes: timeData.minutes,
    seconds: timeData.seconds,
  };

  if (lastSecondForMarkers !== timeData.seconds) {
    updateMarkers(referenceDate);
    lastSecondForMarkers = timeData.seconds;
  }
}

function updateMarkers(referenceDate) {
  const language = getCurrentLanguage();
  cities.forEach((city) => {
    const entry = markerRegistry.get(city.id);
    if (!entry) {
      return;
    }
    const timeData = getCityTimeData(city.id, referenceDate);
    const offsetLabel = formatOffsetLabel(timeData.offsetMinutes);
    entry.label.dataset.offset = offsetLabel.replace("GMT", "");
    const isDay = timeData.hours24 >= 6 && timeData.hours24 < 18;
    entry.button.classList.toggle("map-marker--day", isDay);
    entry.button.classList.toggle("map-marker--night", !isDay);
    entry.button.classList.toggle("is-active", city.id === activeCityId);
    entry.button.setAttribute(
      "aria-pressed",
      city.id === activeCityId ? "true" : "false",
    );
    entry.label.textContent = city.names[language.code];
  });
}

function tick() {
  updateClock(new Date());
  animationFrameId = window.requestAnimationFrame(tick);
}

function startTicker() {
  if (animationFrameId !== null) {
    return;
  }
  animationFrameId = window.requestAnimationFrame(tick);
}

function stopTicker() {
  if (animationFrameId !== null) {
    window.cancelAnimationFrame(animationFrameId);
    animationFrameId = null;
  }
}

languageToggleBtn.addEventListener("click", () => {
  currentLanguageIndex = (currentLanguageIndex + 1) % languages.length;
  applyTranslations();
});

document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    stopTicker();
  } else {
    previousParts = {
      hours: null,
      minutes: null,
      seconds: null,
    };
    lastSecondForMarkers = null;
    startTicker();
  }
});

buildCityMarkers();
applyTranslations();
setActiveCity(activeCityId);
startTicker();
