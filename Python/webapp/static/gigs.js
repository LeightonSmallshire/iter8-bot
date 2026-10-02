"use strict";

const GIGS = window.GIGS;
const DEFAULT_LOCATION = "Birmingham";
const AUTO_SEARCH_DELAY_MS = 500;

const form = document.getElementById("search-form");
const keywordInput = document.getElementById("keyword");
const locationSelect = document.getElementById("location");
const categorySelect = document.getElementById("category");
const fromInput = document.getElementById("from");
const toInput = document.getElementById("to");
const radiusInput = document.getElementById("radius");
const sortSelect = document.getElementById("sort");
const statusEl = document.getElementById("search-status");
const noticeEl = document.getElementById("notices");
const resultsEl = document.getElementById("results");
const attributionEl = document.getElementById("attribution");

const anyOption = document.createElement("option");
anyOption.value = "";
anyOption.textContent = "🌐 Anywhere";
locationSelect.appendChild(anyOption);
for (const name of GIGS.locations) {
  const option = document.createElement("option");
  option.value = name;
  option.textContent = name;
  locationSelect.appendChild(option);
}
if (GIGS.locations.includes(DEFAULT_LOCATION)) {
  locationSelect.value = DEFAULT_LOCATION;
}

const anyCategory = document.createElement("option");
anyCategory.value = "";
anyCategory.textContent = "🎪 Any category";
categorySelect.appendChild(anyCategory);
for (const category of GIGS.categories) {
  const option = document.createElement("option");
  option.value = category.code;
  option.textContent = category.label;
  categorySelect.appendChild(option);
}

function isoDate(date) {
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return date.getFullYear() + "-" + month + "-" + day;
}

function addDays(date, days) {
  const copy = new Date(date);
  copy.setDate(copy.getDate() + days);
  return copy;
}

const today = new Date();
if (!fromInput.value) fromInput.value = isoDate(today);
if (!toInput.value) toInput.value = isoDate(addDays(today, 7));
if (!radiusInput.value) radiusInput.value = "10";

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function setStatus(text, ok) {
  statusEl.textContent = text;
  statusEl.className = "status" + (ok === undefined ? "" : ok ? " ok" : " warn");
}

function gigCard(gig, sourceName) {
  const card = el("article", "gig-card");

  const head = el("div", "gig-head");
  if (gig.url) {
    const link = el("a", "gig-title", gig.title);
    link.href = gig.url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    head.appendChild(link);
  } else {
    head.appendChild(el("span", "gig-title", gig.title));
  }
  if (gig.price) head.appendChild(el("span", "gig-price", gig.price));
  card.appendChild(head);

  const meta = [];
  if (gig.date) {
    meta.push("📅 " + gig.date + (gig.start_time ? " · " + gig.start_time.slice(0, 5) : ""));
  }
  const place = [gig.venue, gig.town].filter(Boolean).join(", ");
  if (place) meta.push("📍 " + place);
  if (meta.length) card.appendChild(el("div", "gig-meta", meta.join("  ·  ")));

  if (gig.artists && gig.artists.length) {
    card.appendChild(el("div", "gig-artists", "🎤 " + gig.artists.join(", ")));
  }

  card.appendChild(el("span", "source-badge", "🎫 " + sourceName));
  return card;
}

function dateKey(gig) {
  const date = gig.date && /^\d{4}-\d{2}-\d{2}/.test(gig.date) ? gig.date : "9999-99-99";
  const time = gig.start_time && /^\d{2}:\d{2}/.test(gig.start_time) ? gig.start_time.slice(0, 5) : "99:99";
  return date + " " + time;
}

function priceValue(gig) {
  if (!gig.price) return Infinity;
  if (/free/i.test(gig.price)) return 0;
  const match = gig.price.replace(",", "").match(/\d+(?:\.\d+)?/);
  return match ? parseFloat(match[0]) : Infinity;
}

const COMPARATORS = {
  date: (a, b) =>
    dateKey(a).localeCompare(dateKey(b)) || a.gig.title.localeCompare(b.gig.title),
  "date-desc": (a, b) =>
    dateKey(b).localeCompare(dateKey(a)) || a.gig.title.localeCompare(b.gig.title),
  title: (a, b) => a.gig.title.localeCompare(b.gig.title),
  price: (a, b) =>
    priceValue(a.gig) - priceValue(b.gig) ||
    dateKey(a.gig).localeCompare(dateKey(b.gig)) ||
    a.gig.title.localeCompare(b.gig.title),
};

let lastResults = [];
let lastParams = "";

function renderNotices(messages) {
  noticeEl.innerHTML = "";
  noticeEl.hidden = messages.length === 0;
  if (!messages.length) return;

  const box = el("div", "source-warning");
  const lines = el("div", "source-warning-text");
  for (const message of messages) lines.appendChild(el("div", null, message));
  box.appendChild(lines);

  const retry = el("button", "retry", "↻ Retry now");
  retry.type = "button";
  retry.addEventListener("click", () => runSearch(true));
  box.appendChild(retry);
  noticeEl.appendChild(box);
}

function render() {
  const entries = [];
  const attribution = new Map();
  const messages = [];

  for (const result of lastResults) {
    if (result.error) {
      messages.push(
        "⚠️ " + result.source + ": " + result.error + (result.stale ? " (showing cached results)" : "")
      );
    }
    for (const gig of result.gigs) entries.push({ gig, source: result.source });
    if (result.attribution && !attribution.has(result.attribution_url)) {
      attribution.set(result.attribution_url, result.attribution);
    }
  }

  renderNotices(messages);

  const compare = COMPARATORS[sortSelect.value] || COMPARATORS.date;
  entries.sort(compare);

  resultsEl.innerHTML = "";
  if (!entries.length) {
    resultsEl.appendChild(el("p", "empty", "🔍 No gigs found. Try widening your search."));
  }
  for (const entry of entries) {
    resultsEl.appendChild(gigCard(entry.gig, entry.source));
  }

  attributionEl.innerHTML = "";
  attributionEl.hidden = attribution.size === 0;
  for (const [url, text] of attribution) {
    const link = el("a", null, "ℹ️ " + text);
    link.href = url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    attributionEl.appendChild(link);
  }

  const total = entries.length;
  if (total) {
    setStatus("✅ " + total + " gig" + (total === 1 ? "" : "s") + " found", true);
  } else {
    setStatus("⚠️ No gigs found", false);
  }
}

function buildParams() {
  const params = new URLSearchParams();
  for (const [name, value] of new FormData(form)) {
    if (String(value).trim()) params.set(name, String(value).trim());
  }
  return params;
}

let debounceTimer = null;
let searchSeq = 0;

function clearDebounce() {
  if (debounceTimer !== null) {
    clearTimeout(debounceTimer);
    debounceTimer = null;
  }
}

async function runSearch(force) {
  clearDebounce();
  const query = buildParams().toString();
  if (!force && query === lastParams && lastResults.length) return;

  const seq = ++searchSeq;
  setStatus("⏳ Searching…");
  renderNotices([]);

  try {
    const response = await fetch("/api/gigs?" + query);
    if (response.status === 401) {
      window.location.assign("/auth/login?next=" + encodeURIComponent("/gigs"));
      return;
    }

    const body = await response.text();
    let data = null;
    try {
      data = JSON.parse(body);
    } catch {
      data = null;
    }
    if (!response.ok || !data || !Array.isArray(data.results)) {
      throw new Error((data && data.error) || "Search failed (HTTP " + response.status + ").");
    }
    if (seq !== searchSeq) return;

    lastResults = data.results;
    lastParams = query;
    render();
  } catch (err) {
    if (seq !== searchSeq) return;
    renderNotices(["⚠️ " + (err && err.message ? err.message : "Search failed.")]);
    setStatus("⚠️ Search failed", false);
  }
}

function scheduleSearch() {
  clearDebounce();
  if (lastResults.length || noticeEl.hidden === false) renderNotices([]);
  setStatus("⏳ Updating…");
  debounceTimer = setTimeout(() => {
    debounceTimer = null;
    runSearch(false);
  }, AUTO_SEARCH_DELAY_MS);
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  runSearch(true);
});

keywordInput.addEventListener("input", scheduleSearch);
radiusInput.addEventListener("input", scheduleSearch);
locationSelect.addEventListener("change", scheduleSearch);
categorySelect.addEventListener("change", scheduleSearch);
fromInput.addEventListener("change", scheduleSearch);
toInput.addEventListener("change", scheduleSearch);

sortSelect.addEventListener("change", () => {
  if (lastResults.length) render();
});

runSearch(true);
