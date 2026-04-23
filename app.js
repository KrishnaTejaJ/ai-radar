// =========================================================
// AI Radar — app.js
// Vanilla JS, hash routing, reads data.json once, renders views
// =========================================================

const state = {
  data: null,
  expandedSections: new Set(),
};

const SECTION_META = {
  tailored:    { title: "Tailored For You",   icon: "🎯", tagline: "Practitioner thinkers and tooling for your NetPresso stack" },
  telecom:     { title: "Telecom & Networks", icon: "📡", tagline: "Industry news and academic preprints on 5G, RAN, and telco AI" },
  top_stories: { title: "Top Stories",        icon: "📰", tagline: "Broad AI signal — what's hot right now" },
  cautionary:  { title: "Cautionary Tales",   icon: "⚠️",  tagline: "Failure modes, security incidents, and safety research" },
  community:   { title: "Community Pulse",    icon: "🗣️", tagline: "What practitioners are discussing on HN and Lobsters" },
};

const TAG_LABELS = {
  build:         "BUILD",
  "write-about": "WRITE ABOUT",
  watch:         "WATCH",
};

// =========================================================
// ROUTING
// =========================================================
function getRoute() {
  const hash = window.location.hash.replace(/^#/, "") || "radar";
  return hash;
}

function setActiveNav(route) {
  document.querySelectorAll(".nav a").forEach(a => {
    a.classList.toggle("active", a.dataset.route === route);
  });
}

function render() {
  const route = getRoute();
  setActiveNav(route);
  const app = document.getElementById("app");

  if (!state.data) {
    app.innerHTML = `<div class="loading-state"><p>Loading radar…</p></div>`;
    return;
  }

  // Scroll to top on route change
  window.scrollTo(0, 0);

  switch (route) {
    case "radar":
      app.innerHTML = renderRadar();
      attachRadarHandlers();
      break;
    case "tailored":
    case "telecom":
    case "top-stories":
    case "cautionary":
    case "community":
      app.innerHTML = renderSectionStub(route);
      break;
    case "models":
      app.innerHTML = renderModelsStub();
      break;
    default:
      app.innerHTML = `<div class="error-state"><p>Unknown route: ${escapeHtml(route)}</p><a href="#radar">← back to radar</a></div>`;
  }
}

// =========================================================
// RADAR VIEW (main page)
// =========================================================
function renderRadar() {
  const data = state.data;
  const syncAgo = formatRelativeTime(data.meta.last_updated);
  document.getElementById("sync-indicator").textContent = `synced ${syncAgo}`;

  const sectionOrder = ["tailored", "telecom", "top_stories", "cautionary", "community"];

  let html = `<div class="radar-page">`;

  // Render each content section
  for (const section of sectionOrder) {
    html += renderRadarSection(section);
  }

  // Model Tracker gets its own dedicated mini-section on the radar
  html += renderRadarModels();

  html += `</div>`;
  return html;
}

function renderRadarSection(section) {
  const meta = SECTION_META[section];
  const radar = state.data.radar[section] || { top: [], expand: [] };
  const routeHash = section === "top_stories" ? "top-stories" : section;
  const isExpanded = state.expandedSections.has(section);
  const hasExpand = radar.expand && radar.expand.length > 0;

  let html = `
    <section class="radar-section" id="section-${section}">
      <div class="section-header">
        <h2>
          <span class="section-icon">${meta.icon}</span>
          ${meta.title}
        </h2>
        <a class="see-all" href="#${routeHash}">see all →</a>
      </div>
      <p class="section-tagline">${meta.tagline}</p>
      <div class="items">
  `;

  if (radar.top.length === 0) {
    html += `<div class="empty-state">No items today. Check back after the next sync.</div>`;
  } else {
    for (const item of radar.top) {
      html += renderItemCard(item, section);
    }
  }

  if (hasExpand) {
    if (isExpanded) {
      html += `<div class="expand-items">`;
      for (const item of radar.expand) {
        html += renderItemCard(item, section, { dimmed: true });
      }
      html += `</div>`;
      html += `<button class="expand-toggle" data-section="${section}">↑ show less</button>`;
    } else {
      html += `<button class="expand-toggle" data-section="${section}">↓ show ${radar.expand.length} more from this week</button>`;
    }
  }

  html += `</div></section>`;
  return html;
}

function renderItemCard(item, section, opts = {}) {
  const { dimmed = false } = opts;
  const source = escapeHtml(item.source);
  const title = escapeHtml(item.title);
  const summary = escapeHtml(item.summary || "");
  const url = item.url;
  const discussionUrl = item.discussion_url;
  const published = item.published ? formatRelativeTime(item.published) : "";
  const isCommunity = section === "community";

  // Flags → badges
  const badges = [];
  if (item.flags?.new) badges.push(`<span class="badge badge-new">NEW</span>`);
  if (item.tag && TAG_LABELS[item.tag]) {
    badges.push(`<span class="badge badge-${item.tag}">${TAG_LABELS[item.tag]}</span>`);
  }

  // Community items: 🔥 points badge
  const pointsBadge = isCommunity && item.points != null
    ? `<span class="badge badge-points">🔥 ${item.points}</span>`
    : "";

  // Action row for community (both article + discussion)
  const actionRow = isCommunity && discussionUrl
    ? `
      <div class="item-actions">
        <a href="${url}" target="_blank" rel="noopener" class="action-link">→ read</a>
        <a href="${discussionUrl}" target="_blank" rel="noopener" class="action-link">💬 ${item.num_comments || 0}</a>
      </div>
    `
    : `
      <div class="item-actions">
        <a href="${url}" target="_blank" rel="noopener" class="action-link">→ read</a>
      </div>
    `;

  return `
    <article class="item-card${dimmed ? " item-dimmed" : ""}">
      <div class="item-badges-row">
        <div class="item-badges">${badges.join("")}</div>
        ${pointsBadge}
      </div>
      <h3 class="item-title">${title}</h3>
      <div class="item-meta">
        <span class="item-source">${source}</span>
        ${published ? `<span class="item-time">· ${published}</span>` : ""}
      </div>
      ${summary ? `<p class="item-summary">${summary}</p>` : ""}
      ${actionRow}
    </article>
  `;
}

function renderRadarModels() {
  const models = state.data.models?.all || [];
  const top5 = models.slice(0, 5);

  let html = `
    <section class="radar-section" id="section-models">
      <div class="section-header">
        <h2>
          <span class="section-icon">🤖</span>
          Model Tracker
        </h2>
        <a class="see-all" href="#models">see all →</a>
      </div>
      <p class="section-tagline">Live scoreboard via Artificial Analysis</p>
      <div class="models-table">
        <div class="models-row models-header">
          <span class="col-rank">#</span>
          <span class="col-name">Model</span>
          <span class="col-creator">Creator</span>
          <span class="col-intel">Intel</span>
          <span class="col-code">Code</span>
          <span class="col-price">Price</span>
        </div>
  `;

  if (top5.length === 0) {
    html += `<div class="empty-state">Model data unavailable. Check AA_API_KEY.</div>`;
  } else {
    top5.forEach((m, i) => {
      const license = m.license_type === "open"
        ? `<span class="license-badge license-open">OS</span>`
        : "";
      html += `
        <a class="models-row models-item" href="${m.url}" target="_blank" rel="noopener">
          <span class="col-rank">${i + 1}</span>
          <span class="col-name">${escapeHtml(m.name)} ${license}</span>
          <span class="col-creator">${escapeHtml(m.creator)}</span>
          <span class="col-intel">${formatScore(m.intelligence_index)}</span>
          <span class="col-code">${formatScore(m.coding_index)}</span>
          <span class="col-price">${formatPrice(m.price_blended)}</span>
        </a>
      `;
    });
  }

  html += `</div></section>`;
  return html;
}

// =========================================================
// STUB VIEWS (to be filled in next message)
// =========================================================
function renderSectionStub(route) {
  const sectionKey = route === "top-stories" ? "top_stories" : route;
  const meta = SECTION_META[sectionKey];
  return `
    <div class="section-page">
      <a class="back-link" href="#radar">← back to radar</a>
      <div class="section-page-header">
        <h1>${meta.icon} ${meta.title}</h1>
        <p>${meta.tagline}</p>
      </div>
      <div class="stub">
        <p><strong>Deep view coming soon.</strong></p>
        <p>This tab will show all sources for this section, expandable to their recent 5 items each, with featured-in-radar markers.</p>
        <p><a href="#radar">← back to radar</a></p>
      </div>
    </div>
  `;
}

function renderModelsStub() {
  return `
    <div class="section-page">
      <a class="back-link" href="#radar">← back to radar</a>
      <div class="section-page-header">
        <h1>🤖 Model Tracker</h1>
        <p>Live scoreboard via Artificial Analysis</p>
      </div>
      <div class="stub">
        <p><strong>Full leaderboard coming soon.</strong></p>
        <p>This tab will show top 5 with filters (All / Paid / Open) and sorts (Intelligence / Coding / Price).</p>
      </div>
    </div>
  `;
}

// =========================================================
// EVENT HANDLERS
// =========================================================
function attachRadarHandlers() {
  document.querySelectorAll(".expand-toggle").forEach(btn => {
    btn.addEventListener("click", () => {
      const section = btn.dataset.section;
      if (state.expandedSections.has(section)) {
        state.expandedSections.delete(section);
      } else {
        state.expandedSections.add(section);
      }
      render();
    });
  });
}

// =========================================================
// UTILITIES
// =========================================================
function escapeHtml(s) {
  if (s == null) return "";
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function formatRelativeTime(iso) {
  if (!iso) return "";
  const then = new Date(iso);
  const now = new Date();
  const diff = (now - then) / 1000;  // seconds
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  const days = Math.floor(diff / 86400);
  if (days < 30) return `${days}d ago`;
  if (days < 365) return `${Math.floor(days / 30)}mo ago`;
  return `${Math.floor(days / 365)}y ago`;
}

function formatScore(n) {
  if (n == null) return "—";
  return typeof n === "number" ? n.toFixed(1) : String(n);
}

function formatPrice(n) {
  if (n == null) return "—";
  return `$${typeof n === "number" ? n.toFixed(2) : n}`;
}

// =========================================================
// BOOTSTRAP
// =========================================================
window.addEventListener("hashchange", render);

document.addEventListener("DOMContentLoaded", async () => {
  try {
    const response = await fetch("data.json", { cache: "no-cache" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    state.data = await response.json();
    render();
  } catch (err) {
    document.getElementById("app").innerHTML = `
      <div class="error-state">
        <h2>Failed to load radar data</h2>
        <p>${escapeHtml(err.message)}</p>
        <p>Try refreshing, or check that <code>data.json</code> is present.</p>
      </div>
    `;
    document.getElementById("sync-indicator").textContent = "error";
  }
});