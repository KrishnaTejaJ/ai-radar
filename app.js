// =========================================================
// AI Radar — app.js (v2.1)
// Full implementation: radar + all 6 tab pages + model filters
// =========================================================

const state = {
  data: null,
  expandedSections: new Set(),
  expandedSources: new Set(),      // which source cards are open in tab views
  modelFilter: "all",              // all | paid | open  (used on #models page AND radar)
  modelSort: "intelligence_index", // intelligence_index | coding_index | price_blended
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

const FULL_WIDTH_SECTIONS = new Set(["tailored"]);

// Source grouping hints for tab pages (practitioners vs tools, news vs academic, etc.)
const SOURCE_GROUPS = {
  tailored: {
    "Practitioners": ["Anthropic Engineering", "Sebastian Raschka", "Eugene Yan", "Chip Huyen", "Interconnects", "Pragmatic Engineer"],
    "Tools & Volume": ["Google Cloud AI", "Hugging Face Blog", "GitHub Python Trending", "Hacker News (AI/LLM)"],
  },
  telecom: {
    "Academic Preprints": ["arXiv: 5G + LLM", "arXiv: RAN anomaly", "arXiv: O-RAN"],
    "Industry News": ["Light Reading", "RCR Wireless", "Fierce Network"],
  },
  top_stories: null,  // no grouping — flat list
  cautionary: {
    "Primary Documentation": ["Anthropic Frontier Red Team", "Anthropic Research", "AI Incident Database"],
    "Analysis & Vendor": ["OWASP GenAI", "Schneier on Security", "DataRobot Blog", "CyberArk Engineering", "Future of Privacy Forum"],
  },
  community: {
    "Hacker News": ["Hacker News (≥100)", "Hacker News (≥50)"],
    "Lobsters": ["Lobsters (AI tag)"],
  },
};

// =========================================================
// ROUTING
// =========================================================
function getRoute() {
  return window.location.hash.replace(/^#/, "") || "radar";
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

  window.scrollTo(0, 0);

  switch (route) {
    case "radar":
      app.innerHTML = renderRadar();
      attachRadarHandlers();
      break;
    case "tailored":
    case "telecom":
    case "cautionary":
    case "community":
      app.innerHTML = renderSectionPage(route);
      attachSectionPageHandlers();
      break;
    case "top-stories":
      app.innerHTML = renderSectionPage("top_stories");
      attachSectionPageHandlers();
      break;
    case "models":
      app.innerHTML = renderModelsPage();
      attachModelsHandlers();
      break;
    default:
      app.innerHTML = `<div class="error-state"><p>Unknown route: ${escapeHtml(route)}</p><a href="#radar">← back to radar</a></div>`;
  }
}

// =========================================================
// RADAR VIEW
// =========================================================
function renderRadar() {
  const data = state.data;
  document.getElementById("sync-indicator").textContent = `synced ${formatRelativeTime(data.meta.last_updated)}`;

  const sectionOrder = ["tailored", "telecom", "top_stories", "cautionary", "community"];
  let html = `<div class="radar-page">`;
  for (const section of sectionOrder) {
    html += renderRadarSection(section);
  }
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
  const spanClass = FULL_WIDTH_SECTIONS.has(section) ? " span-full" : "";

  let html = `
    <section class="radar-section${spanClass}" id="section-${section}">
      <div class="section-header">
        <h2><span class="section-icon">${meta.icon}</span>${meta.title}</h2>
        <a class="see-all" href="#${routeHash}">see all →</a>
      </div>
      <p class="section-tagline">${meta.tagline}</p>
      <div class="items">
  `;

  if (radar.top.length === 0) {
    html += `<div class="empty-state">No items this cycle. Check back after the next sync.</div>`;
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
  const { dimmed = false, showFeatured = false } = opts;
  const source = escapeHtml(item.source);
  const title = escapeHtml(item.title);
  const summary = escapeHtml(item.summary || "");
  const url = item.url;
  const discussionUrl = item.discussion_url;
  const published = item.published ? formatRelativeTime(item.published) : "";
  const isCommunity = section === "community";

  const badges = [];
  if (item.flags?.new) badges.push(`<span class="badge badge-new">NEW</span>`);
  if (showFeatured && item.flags?.featured) badges.push(`<span class="badge badge-featured">FEATURED</span>`);
  if (item.tag && TAG_LABELS[item.tag]) {
    badges.push(`<span class="badge badge-${item.tag}">${TAG_LABELS[item.tag]}</span>`);
  }

  const pointsBadge = isCommunity && item.points != null
    ? `<span class="badge badge-points">🔥 ${item.points}</span>`
    : "";

  const actionRow = isCommunity && discussionUrl
    ? `<div class="item-actions">
        <a href="${url}" target="_blank" rel="noopener" class="action-link">→ read</a>
        <a href="${discussionUrl}" target="_blank" rel="noopener" class="action-link">💬 ${item.num_comments || 0}</a>
      </div>`
    : `<div class="item-actions"><a href="${url}" target="_blank" rel="noopener" class="action-link">→ read</a></div>`;

  return `
    <article class="item-card${dimmed ? " item-dimmed" : ""}">
      ${badges.length || pointsBadge ? `
        <div class="item-badges-row">
          <div class="item-badges">${badges.join("")}</div>
          ${pointsBadge}
        </div>
      ` : ""}
      <h3 class="item-title"><a href="${url}" target="_blank" rel="noopener">${title}</a></h3>
      <div class="item-meta">
        <span class="item-source">${source}</span>
        ${published ? `<span class="item-time">· ${published}</span>` : ""}
      </div>
      ${summary ? `<p class="item-summary">${summary}</p>` : ""}
      ${actionRow}
    </article>
  `;
}

// =========================================================
// MODEL TRACKER — SHARED LOGIC (used on radar + deep page)
// =========================================================
function getFilteredSortedModels(models, filter, sort) {
  let filtered = models;
  if (filter === "paid") filtered = models.filter(m => m.license_type === "proprietary");
  else if (filter === "open") filtered = models.filter(m => m.license_type === "open");

  const sortKey = sort || "intelligence_index";
  filtered = [...filtered].sort((a, b) => {
    const av = a[sortKey];
    const bv = b[sortKey];
    if (av == null) return 1;
    if (bv == null) return -1;
    // Price: ascending (cheaper better). Others: descending (higher better).
    return sortKey === "price_blended" ? av - bv : bv - av;
  });
  return filtered;
}

function renderModelFilters(withSort = false) {
  const filter = state.modelFilter;
  const sort = state.modelSort;
  let html = `<div class="model-controls">`;
  html += `
    <div class="filter-pills" role="tablist" aria-label="Model filter">
      <button class="pill ${filter === 'all' ? 'active' : ''}" data-filter="all">All</button>
      <button class="pill ${filter === 'paid' ? 'active' : ''}" data-filter="paid">Paid</button>
      <button class="pill ${filter === 'open' ? 'active' : ''}" data-filter="open">Open</button>
    </div>
  `;
  if (withSort) {
    html += `
      <div class="sort-control">
        <label for="model-sort">Sort:</label>
        <select id="model-sort" class="sort-select">
          <option value="intelligence_index" ${sort === 'intelligence_index' ? 'selected' : ''}>Intelligence</option>
          <option value="coding_index"       ${sort === 'coding_index' ? 'selected' : ''}>Coding</option>
          <option value="price_blended"      ${sort === 'price_blended' ? 'selected' : ''}>Price</option>
        </select>
      </div>
    `;
  }
  html += `</div>`;
  return html;
}

function renderModelRow(m, rank, newEntrants) {
  const isNew = newEntrants.includes(m.slug);
  const license = m.license_type === "open"
    ? `<span class="license-badge license-open">OS</span>`
    : "";
  const newBadge = isNew ? `<span class="license-badge license-new">NEW</span>` : "";
  return `
    <a class="models-row models-item" href="${m.url}" target="_blank" rel="noopener">
      <span class="col-rank">${rank}</span>
      <span class="col-name">${escapeHtml(m.name)} ${license}${newBadge}</span>
      <span class="col-creator">${escapeHtml(m.creator)}</span>
      <span class="col-intel">${formatScore(m.intelligence_index)}</span>
      <span class="col-code">${formatScore(m.coding_index)}</span>
      <span class="col-price">${formatPrice(m.price_blended)}</span>
    </a>
  `;
}

function renderRadarModels() {
  const models = state.data.models?.all || [];
  const newEntrants = state.data.models?.new_entrants?.[state.modelFilter] || [];
  const filtered = getFilteredSortedModels(models, state.modelFilter, state.modelSort).slice(0, 5);

  let html = `
    <section class="radar-section span-full" id="section-models">
      <div class="section-header">
        <h2><span class="section-icon">🤖</span>Model Tracker</h2>
        <a class="see-all" href="#models">see all →</a>
      </div>
      <p class="section-tagline">Live scoreboard via Artificial Analysis</p>
      ${renderModelFilters(false)}
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
  if (filtered.length === 0) {
    html += `<div class="empty-state">No models match this filter.</div>`;
  } else {
    filtered.forEach((m, i) => { html += renderModelRow(m, i + 1, newEntrants); });
  }
  html += `</div></section>`;
  return html;
}

// =========================================================
// SECTION TAB PAGES
// =========================================================
function renderSectionPage(section) {
  const meta = SECTION_META[section];
  const sources = state.data.sources[section] || {};
  const groups = SOURCE_GROUPS[section];

  let html = `
    <div class="section-page">
      <a class="back-link" href="#radar">← back to radar</a>
      <div class="section-page-header">
        <h1>${meta.icon} ${meta.title}</h1>
        <p>${meta.tagline}</p>
      </div>
  `;

  if (Object.keys(sources).length === 0) {
    html += `<div class="empty-state">No data for this section.</div></div>`;
    return html;
  }

  if (groups) {
    for (const [groupName, sourceNames] of Object.entries(groups)) {
      const groupSources = sourceNames.filter(n => sources[n]).map(n => [n, sources[n]]);
      if (groupSources.length === 0) continue;
      html += `<div class="source-group">`;
      html += `<h2 class="source-group-title">${groupName}</h2>`;
      for (const [name, src] of groupSources) {
        html += renderSourceCard(section, name, src);
      }
      html += `</div>`;
    }
    // Any sources not in a group (shouldn't happen but defensive)
    const groupedNames = new Set(Object.values(groups).flat());
    const ungrouped = Object.entries(sources).filter(([n]) => !groupedNames.has(n));
    if (ungrouped.length > 0) {
      html += `<div class="source-group"><h2 class="source-group-title">Other</h2>`;
      for (const [name, src] of ungrouped) {
        html += renderSourceCard(section, name, src);
      }
      html += `</div>`;
    }
  } else {
    // Flat list (top_stories)
    html += `<div class="source-group">`;
    for (const [name, src] of Object.entries(sources)) {
      html += renderSourceCard(section, name, src);
    }
    html += `</div>`;
  }

  html += `</div>`;
  return html;
}

function renderSourceCard(section, sourceName, src) {
  const stateKey = `${section}:${sourceName}`;
  const isOpen = state.expandedSources.has(stateKey);
  const items = src.items || [];
  const tierMarker = src.tier === 1 ? `<span class="tier-star" title="Tier 1 — priority source">★</span> ` : "";
  const featuredCount = items.filter(i => i.flags?.featured).length;
  const newCount = items.filter(i => i.flags?.new).length;

  let meta = `${items.length} recent`;
  if (featuredCount > 0) meta += ` · ${featuredCount} on radar`;
  if (newCount > 0) meta += ` · ${newCount} today`;

  let html = `
    <div class="source-card${isOpen ? ' open' : ''}">
      <button class="source-card-header" data-source-key="${escapeAttr(stateKey)}">
        <span class="source-card-title">${tierMarker}${escapeHtml(sourceName)}</span>
        <span class="source-card-meta">${meta}</span>
        <span class="source-card-chevron">${isOpen ? '▾' : '▸'}</span>
      </button>
  `;
  if (isOpen) {
    if (items.length === 0) {
      html += `<div class="source-card-body"><div class="empty-state">No items.</div></div>`;
    } else {
      html += `<div class="source-card-body">`;
      for (const item of items) {
        html += renderItemCard(item, section, { showFeatured: true });
      }
      html += `</div>`;
    }
  }
  html += `</div>`;
  return html;
}

// =========================================================
// MODELS DEEP PAGE
// =========================================================
function renderModelsPage() {
  const models = state.data.models?.all || [];
  const newEntrants = state.data.models?.new_entrants?.[state.modelFilter] || [];
  const filtered = getFilteredSortedModels(models, state.modelFilter, state.modelSort);
  const displayed = filtered.slice(0, 10);  // deep page shows up to 10

  let html = `
    <div class="section-page models-deep-page">
      <a class="back-link" href="#radar">← back to radar</a>
      <div class="section-page-header">
        <h1>🤖 Model Tracker</h1>
        <p>Live scoreboard via Artificial Analysis. ${models.length} models tracked.</p>
      </div>
      ${renderModelFilters(true)}
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
  if (displayed.length === 0) {
    html += `<div class="empty-state">No models match this filter.</div>`;
  } else {
    displayed.forEach((m, i) => { html += renderModelRow(m, i + 1, newEntrants); });
  }
  html += `</div>`;

  if (filtered.length > displayed.length) {
    html += `<p class="models-footer-note">Showing top ${displayed.length} of ${filtered.length}. <a href="https://artificialanalysis.ai" target="_blank" rel="noopener">View full rankings →</a></p>`;
  }

  html += `</div>`;
  return html;
}

// =========================================================
// EVENT HANDLERS
// =========================================================
function attachRadarHandlers() {
  document.querySelectorAll(".expand-toggle").forEach(btn => {
    btn.addEventListener("click", () => {
      const section = btn.dataset.section;
      if (state.expandedSections.has(section)) state.expandedSections.delete(section);
      else state.expandedSections.add(section);
      render();
    });
  });
  // Model filter pills on radar
  document.querySelectorAll(".filter-pills .pill").forEach(btn => {
    btn.addEventListener("click", () => {
      state.modelFilter = btn.dataset.filter;
      render();
    });
  });
}

function attachSectionPageHandlers() {
  document.querySelectorAll(".source-card-header").forEach(btn => {
    btn.addEventListener("click", () => {
      const key = btn.dataset.sourceKey;
      if (state.expandedSources.has(key)) state.expandedSources.delete(key);
      else state.expandedSources.add(key);
      render();
    });
  });
}

function attachModelsHandlers() {
  document.querySelectorAll(".filter-pills .pill").forEach(btn => {
    btn.addEventListener("click", () => {
      state.modelFilter = btn.dataset.filter;
      render();
    });
  });
  const sortSelect = document.getElementById("model-sort");
  if (sortSelect) {
    sortSelect.addEventListener("change", (e) => {
      state.modelSort = e.target.value;
      render();
    });
  }
}

// =========================================================
// UTILITIES
// =========================================================
function escapeHtml(s) {
  if (s == null) return "";
  return String(s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}
function escapeAttr(s) { return escapeHtml(s); }

function formatRelativeTime(iso) {
  if (!iso) return "";
  const then = new Date(iso);
  const now = new Date();
  const diff = (now - then) / 1000;
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