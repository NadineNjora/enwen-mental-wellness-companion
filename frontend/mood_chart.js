"use strict";

(() => {
  const list = document.querySelector("#mood-history-list");
  if (!list) return;
  const ns = "http://www.w3.org/2000/svg";
  const names = { 5: ["", "Very low", "Low", "Okay", "Good", "Great"],
    10: ["", "Very low", "Low", "Down", "A little low", "In between", "Okay", "Pretty good", "Good", "Very good", "Great"] };
  const panel = document.createElement("section");
  panel.className = "enwen-trend";
  panel.setAttribute("aria-labelledby", "mood-trend-title");
  const heading = document.createElement("h4"); heading.id = "mood-trend-title";
  heading.textContent = "Your moods, over time 🌱";
  const summary = document.createElement("p"); summary.className = "muted";
  const viewport = document.createElement("div"); viewport.className = "enwen-trend-scroll";
  viewport.tabIndex = 0; viewport.setAttribute("role", "region");
  viewport.setAttribute("aria-label", "Complete mood history charts. Scroll horizontally on small screens.");
  const detail = document.createElement("p"); detail.className = "small-note";
  detail.textContent = "Every saved check-in keeps its original score. Earlier entries are out of 5; newer entries are out of 10. The panels use the same dates, with separate score scales. Lines connect recorded check-ins, not measurements between them. Times are Nairobi (EAT).";
  panel.append(heading, summary, viewport, detail); list.before(panel);
  function node(tag, attrs = {}, text) {
    const element = document.createElementNS(ns, tag);
    for (const [key, value] of Object.entries(attrs)) element.setAttribute(key, String(value));
    if (text !== undefined) element.textContent = text;
    return element;
  }
  function date(time, full = false) {
    return new Date(time).toLocaleString("en-KE", { timeZone: "Africa/Nairobi",
      day: "numeric", month: "short", ...(full ? {year: "numeric"} : {}),
      hour: "2-digit", minute: "2-digit", hour12: false });
  }
  function clear(message = "Your first saved check-in will start your graph.") {
    viewport.replaceChildren(); viewport.hidden = true; detail.hidden = true;
    summary.textContent = message;
  }
  function render(entries) {
    const points = entries.map(entry => ({score: entry.mood_score, scale: entry.scale_max,
      time: typeof entry.created_at === "string" ? Date.parse(entry.created_at) : NaN}));
    if (points.some(p => ![5, 10].includes(p.scale) || !Number.isInteger(p.score)
      || p.score < 1 || p.score > p.scale || !Number.isFinite(p.time))) {
      clear("The graph could not read these records. Please refresh your history."); return;
    }
    points.sort((a, b) => a.time - b.time);
    if (!points.length) { clear(); return; }
    const start = points[0].time, end = points[points.length - 1].time;
    summary.textContent = points.length + " saved check-in" + (points.length === 1 ? "" : "s")
      + " · " + date(start, true) + " to " + date(end, true);
    viewport.replaceChildren();
    for (const scale of [5, 10]) {
      const group = points.filter(p => p.scale === scale);
      if (!group.length) continue;
      const label = document.createElement("h5");
      label.className = "trend-scale-heading";
      label.textContent = (scale === 5 ? "Earlier check-ins · " : "Current check-ins · ")
        + "1–" + scale + " scale · " + group.length + " entries";
      const width = 780, height = scale === 5 ? 310 : 420;
      const left = 128, right = width - 32, top = 24, bottom = height - 75;
      const x = time => start === end ? (left + right) / 2 : left + (time - start) / (end - start) * (right - left);
      const y = score => bottom - (score - 1) / (scale - 1) * (bottom - top);
      const titleId = "mood-chart-title-" + scale, descId = "mood-chart-description-" + scale;
      const svg = node("svg", {viewBox: "0 0 " + width + " " + height, role: "img", "aria-labelledby": titleId + " " + descId});
      svg.append(node("title", {id: titleId}, "Recorded moods on the original 1 to " + scale + " scale"),
        node("desc", {id: descId}, group.length + " check-ins. Dates span " + date(start, true)
          + " to " + date(end, true) + ". Original scores are retained; full records follow below."));
      for (let score = 1; score <= scale; score++) svg.append(
        node("line", {x1: left, y1: y(score), x2: right, y2: y(score), class: "trend-grid"}),
        node("text", {x: left - 12, y: y(score) + 4, "text-anchor": "end", class: "trend-label"}, score + " · " + names[scale][score]));
      if (group.length > 1) svg.append(node("polyline", {points: group.map(p => x(p.time) + "," + y(p.score)).join(" "), fill: "none", class: "trend-line"}));
      for (const point of group) {
        const dot = node("circle", {cx: x(point.time), cy: y(point.score), r: 5.5, class: scale === 5 ? "trend-dot trend-dot-earlier" : "trend-dot"});
        dot.append(node("title", {}, date(point.time, true) + " EAT: " + point.score + "/" + scale + " · " + names[scale][point.score]));
        svg.append(dot);
      }
      const ticks = start === end ? [start] : [start, start + (end - start) / 2, end];
      ticks.forEach((time, i) => svg.append(node("text", {x: x(time), y: bottom + 29,
        "text-anchor": ticks.length === 1 ? "middle" : i === 0 ? "start" : i === 2 ? "end" : "middle",
        class: "trend-label"}, date(time))));
      svg.append(node("text", {x: (left + right) / 2, y: height - 12, "text-anchor": "middle", class: "trend-label"}, "Date and time · Nairobi (EAT)"));
      viewport.append(label, svg);
    }
    viewport.hidden = false; detail.hidden = false;
  }
  window.enwenMoodChart = Object.freeze({clear, render}); clear();
})();
