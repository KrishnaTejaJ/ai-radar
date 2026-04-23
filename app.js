const state = {
  data: null
};

const SECTION_META = {
  tailored:    { title: "Tailored For You",   icon: "🎯" },
  telecom:     { title: "Telecom & Networks", icon: "📡" },
  top_stories: { title: "Top Stories",        icon: "📰" },
  cautionary:  { title: "Cautionary Tales",   icon: "⚠️" },
  community:   { title: "Community Corner",   icon: "🗣️" },
};

const SOURCE_GROUPS = {
  tailored: {
    "Practitioners": ["Anthropic Engineering", "Sebastian Raschka", "Eugene Yan", "Chip Huyen", "Interconnects", "Pragmatic Engineer"],
    "Tools & Volume": ["Google Cloud AI", "Hugging Face Blog", "GitHub Python Trending", "Hacker News (AI/LLM)"],
  },
  telecom: {
    "Academic Preprints": ["arXiv: 5G + LLM", "arXiv: RAN anomaly", "arXiv: O-RAN"],
    "Industry News": ["Light Reading", "RCR Wireless", "Fierce Network"],
  },
  top_stories: null,
  cautionary: {
    "Primary Documentation": ["Anthropic Frontier Red Team", "Anthropic Research", "AI Incident Database"],
    "Analysis & Vendor": ["OWASP GenAI", "Schneier on Security", "DataRobot Blog", "CyberArk Engineering", "Future of Privacy Forum"],
  },
  community: {
    "Hacker News": ["Hacker News (≥100)", "Hacker News (≥50)"],
    "Lobsters": ["Lobsters (AI tag)"],
  },
};

function getRoute() {
  return window.location.hash.replace(/^#/, "") || "radar";
}

function escapeHtml(s) {
  if (s == null) return "";
  return String(s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function formatRelativeTime(iso) {
  if (!iso) return "";
  const diff = (new Date() - new Date(iso)) / 1000;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

function render() {
  const route = getRoute();
  const app = document.getElementById("app");

  if (!state.data) {
    app.innerHTML = `<div class="text-center py-20 text-gray-400 font-['Playfair_Display'] italic">Loading radar data...</div>`;
    return;
  }

  window.scrollTo(0, 0);

  if (route === "radar") {
    app.innerHTML = renderRadar();
  } else if (SECTION_META[route]) {
    app.innerHTML = renderDeepDive(route);
  } else if (route === "top-stories") {
    app.innerHTML = renderDeepDive("top_stories");
  } else {
    app.innerHTML = `<div class="text-center py-20"><p>Unknown section.</p><a href="#radar" class="text-blue-600 underline">Return to radar</a></div>`;
  }
}

// ============== FRONT PAGE ==============

function renderCard(item, isFeatured = false) {
  const titleClasses = isFeatured ? 'text-2xl mb-3' : 'text-lg mb-2';
  const url = item.url || "#";
  const source = escapeHtml(item.source);
  const published = item.published ? formatRelativeTime(item.published) : "";
  const timeStr = published ? ` · ${published}` : "";

  return `
    <a href="${url}" target="_blank" rel="noopener noreferrer" class="block bg-white p-5 border border-gray-200 rounded-sm hover:-translate-y-1 hover:shadow-md transition-all duration-200 ${isFeatured ? 'bg-gray-50 border-gray-300' : 'mb-4'}">
        <h3 class="font-['Playfair_Display'] ${titleClasses} font-bold leading-tight text-gray-900 break-words">${escapeHtml(item.title)}</h3>
        ${item.summary ? `<p class="text-sm text-gray-700 mb-3 leading-relaxed">${escapeHtml(item.summary)}</p>` : ''}
        <div class="text-[10px] font-bold text-gray-500 uppercase tracking-widest mt-auto">${source}${timeStr}</div>
    </a>
  `;
}

function renderSection(sectionKey, colorClass, dataObj) {
  const meta = SECTION_META[sectionKey];
  const items = dataObj?.top || [];
  const itemsHtml = items.length > 0
    ? items.map(item => renderCard(item, sectionKey === 'top_stories')).join('')
    : `<p class="text-sm text-gray-400 italic py-2">Nothing to report right now.</p>`;
  
  const routeHash = sectionKey === "top_stories" ? "top-stories" : sectionKey;
  
  return `
    <section class="mb-10">
        <div class="flex justify-between items-center mb-4 border-t-4 ${colorClass} pt-2">
            <h2 class="font-['Playfair_Display'] text-2xl font-bold flex items-center gap-2">
                ${meta.icon} <a href="#${routeHash}" class="hover:underline">${meta.title}</a>
            </h2>
            <a href="#${routeHash}" class="text-xs uppercase font-bold text-gray-400 hover:text-gray-900 tracking-wider">Deep Dive &rarr;</a>
        </div>
        <div class="space-y-4">
            ${itemsHtml}
        </div>
    </section>
  `;
}

function renderModelsLeaderboard() {
  const models = state.data.models?.all || [];
  const newEntrants = ["claude-3-5-sonnet"]; // In case data.json doesn't provide it, we can fallback or derive.
  // Actually we can check data.models.new_entrants?.all if it exists
  const backendNew = state.data.models?.new_entrants?.all || [];

  const sortedAll = [...models].sort((a,b) => (b.intelligence_index || 0) - (a.intelligence_index || 0));
  const sortedPaid = sortedAll.filter(m => m.license_type === 'proprietary');
  const sortedOpen = sortedAll.filter(m => m.license_type === 'open');

  const renderTable = (list, title) => {
    let rowsHtml = list.slice(0, 5).map((m, i) => {
      const isNew = backendNew.includes(m.slug) ? `<span class="bg-yellow-100 text-yellow-800 text-[9px] px-1 py-0.5 rounded ml-1 font-bold">NEW</span>` : "";
      return `
        <tr class="border-b border-gray-100 last:border-0 hover:bg-gray-50">
            <td class="py-2 text-xs text-gray-400 w-4">${i+1}</td>
            <td class="py-2 text-sm font-medium"><a href="${m.url}" target="_blank" class="hover:underline text-gray-900">${escapeHtml(m.name)}</a> ${isNew}</td>
            <td class="py-2 text-xs text-right text-gray-500 font-mono">${m.intelligence_index?.toFixed(1) || '—'}</td>
        </tr>
      `;
    }).join("");
    
    return `
      <div class="mb-6">
        <h4 class="text-xs font-bold uppercase tracking-widest text-gray-500 mb-2 border-b border-gray-200 pb-1">${title}</h4>
        <table class="w-full text-left">
            <thead class="hidden"><tr><th>#</th><th>Model</th><th>Score</th></tr></thead>
            <tbody>${rowsHtml || '<tr><td colspan="3" class="text-xs text-gray-400 italic py-2">No models found.</td></tr>'}</tbody>
        </table>
      </div>
    `;
  };

  return `
    <section class="mb-10 bg-gray-50 p-5 border border-gray-200">
        <div class="flex justify-between items-center mb-6 border-b border-gray-300 pb-2">
            <h2 class="font-['Playfair_Display'] text-2xl font-bold flex items-center gap-2">🤖 Models Leaderboard</h2>
        </div>
        ${renderTable(sortedAll, "Top 5 Overall")}
        ${renderTable(sortedPaid, "Top 5 Paid")}
        ${renderTable(sortedOpen, "Top 5 Open Source")}
        <div class="mt-4 text-[10px] text-gray-500 text-center uppercase tracking-widest">Ranked by Intelligence Index</div>
    </section>
  `;
}

function renderRadar() {
  const radar = state.data.radar || {};
  return `
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-10">
        <!-- Col 1: Tailored & Telecom -->
        <div class="flex flex-col gap-2">
            ${renderSection("tailored", "border-blue-600", radar.tailored)}
            ${renderSection("telecom", "border-purple-600", radar.telecom)}
        </div>

        <!-- Col 2: Top Stories -->
        <div class="flex flex-col gap-2 lg:px-6 lg:border-l lg:border-r border-gray-200">
            ${renderSection("top_stories", "border-gray-900", radar.top_stories)}
        </div>

        <!-- Col 3: Leaderboard, Cautionary, Community -->
        <div class="flex flex-col gap-2">
            ${renderModelsLeaderboard()}
            ${renderSection("cautionary", "border-red-600", radar.cautionary)}
            ${renderSection("community", "border-orange-400", radar.community)}
        </div>
    </div>
  `;
}

// ============== DEEP DIVE PAGES ==============

function renderDeepDive(sectionKey) {
  const meta = SECTION_META[sectionKey];
  const sourcesData = state.data.sources[sectionKey] || {};
  const groups = SOURCE_GROUPS[sectionKey];

  let html = `
    <div class="max-w-3xl mx-auto">
        <div class="mb-8 border-b-2 border-gray-900 pb-4">
            <a href="#radar" class="text-sm font-bold text-gray-500 hover:text-gray-900 uppercase tracking-wider mb-4 inline-block">&larr; Back to Radar</a>
            <h1 class="font-['Playfair_Display'] text-4xl font-black flex items-center gap-3">
                ${meta.icon} ${meta.title}
            </h1>
        </div>
  `;

  if (Object.keys(sourcesData).length === 0) {
    html += `<div class="text-gray-400 italic">No source items found for this cycle.</div></div>`;
    return html;
  }

  const renderSourceGroup = (sourceName, items) => {
    if (!items || items.length === 0) return "";
    let groupHtml = `
      <div class="mb-10">
        <h3 class="font-bold text-lg border-b border-gray-200 pb-1 mb-4 text-gray-800">${escapeHtml(sourceName)}</h3>
        <div class="space-y-4">
    `;
    items.forEach(item => {
      const url = item.url || "#";
      const timeStr = item.published ? formatRelativeTime(item.published) : "";
      groupHtml += `
        <article class="group">
            <a href="${url}" target="_blank" rel="noopener" class="block">
                <h4 class="font-['Playfair_Display'] text-xl font-bold group-hover:text-blue-700 transition-colors">${escapeHtml(item.title)}</h4>
                ${item.summary ? `<p class="mt-1 text-sm text-gray-600 leading-relaxed">${escapeHtml(item.summary)}</p>` : ''}
                <div class="mt-2 text-[11px] font-bold text-gray-400 uppercase tracking-wider">${timeStr}</div>
            </a>
        </article>
      `;
    });
    groupHtml += `</div></div>`;
    return groupHtml;
  };

  if (groups) {
    for (const [groupName, sourceNames] of Object.entries(groups)) {
      html += `<h2 class="text-sm font-black uppercase tracking-widest text-gray-400 mb-6 mt-12 bg-gray-50 py-1 px-2 inline-block">${groupName}</h2>`;
      for (const name of sourceNames) {
        if (sourcesData[name] && sourcesData[name].items) {
          html += renderSourceGroup(name, sourcesData[name].items);
        }
      }
    }
  } else {
    // Top stories has no subgroups, just render each source
    for (const [name, srcObj] of Object.entries(sourcesData)) {
       if (srcObj.items) {
         html += renderSourceGroup(name, srcObj.items);
       }
    }
  }

  html += `</div>`;
  return html;
}

// ============== BOOTSTRAP ==============

window.addEventListener("hashchange", render);

document.addEventListener("DOMContentLoaded", async () => {
  document.getElementById('date-display').innerText = new Date().toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });

  try {
    const response = await fetch("data.json", { cache: "no-cache" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    state.data = await response.json();
    
    if (state.data.meta && state.data.meta.last_updated) {
        document.getElementById('sync-display').innerText = `Synced ${formatRelativeTime(state.data.meta.last_updated)}`;
    }
    
    render();
  } catch (err) {
    document.getElementById("app").innerHTML = `
      <div class="text-center py-20">
        <h2 class="text-xl text-red-600 font-bold mb-2">Failed to load radar data</h2>
        <p class="text-gray-500">${escapeHtml(err.message)}</p>
      </div>
    `;
    document.getElementById("sync-display").innerText = "Sync Error";
  }
});