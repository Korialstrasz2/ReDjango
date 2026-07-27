import { apiFetch } from "./api.js";
import { bindSettings, loadSettings } from "./features/settings.js";
import { selectedPersonaggio, state } from "./store.js";

const views = {
    dashboard: document.querySelector("#view-dashboard"),
    characters: document.querySelector("#view-characters"),
    personaggio: document.querySelector("#view-personaggio"),
    media: document.querySelector("#view-media"),
    guide: document.querySelector("#view-guide"),
    settings: document.querySelector("#view-settings"),
};

const titles = {
    dashboard: "Menu principale",
    characters: "Scegli personaggio",
    personaggio: "Scheda personaggio",
    media: "Archivio immagini",
    guide: "Guide",
    settings: "Impostazioni",
};

const els = {
    title: document.querySelector("#view-title"),
    status: document.querySelector("#status-pill"),
    userChip: document.querySelector("#user-chip"),
    characterMetric: document.querySelector("#metric-characters"),
    mediaMetric: document.querySelector("#metric-media"),
    activePersonaggioMetric: document.querySelector("#metric-active-personaggio"),
    personaggioCount: document.querySelector("#personaggio-count"),
    characterList: document.querySelector("#character-list"),
    personaggioPreview: document.querySelector("#personaggio-preview"),
    personaggioSheet: document.querySelector("#personaggio-sheet"),
    guideList: document.querySelector("#guide-list"),
    guideReader: document.querySelector("#guide-reader"),
    guideCount: document.querySelector("#guide-count"),
    mediaForm: document.querySelector("#media-form"),
    mediaGrid: document.querySelector("#media-grid"),
    mediaCount: document.querySelector("#media-count"),
};

function setStatus(text) {
    els.status.textContent = text;
}

function navigate(route) {
    state.route = route;
    Object.entries(views).forEach(([name, view]) => {
        const isActive = name === route;
        view.classList.toggle("active", isActive);
        view.dataset.state = isActive ? "active" : "idle";
    });
    document.querySelectorAll(".menu-item").forEach((button) => {
        const isActive = button.dataset.route === route;
        button.classList.toggle("active", isActive);
        button.dataset.state = isActive ? "active" : "idle";
    });
    els.title.textContent = titles[route];
}

function updatePersonaggioMetrics() {
    els.characterMetric.textContent = state.personaggi.length;
    els.personaggioCount.textContent = `${state.personaggi.length} disponibili`;
    els.activePersonaggioMetric.textContent = state.activePersonaggio?.name || "Nessuno";
}

function personaggioSubtitle(personaggio) {
    const races = personaggio.races?.length ? personaggio.races.join(" / ") : "Razza sconosciuta";
    return `${races}, livello ${personaggio.level}`;
}

function renderPersonaggioList() {
    updatePersonaggioMetrics();
    if (!state.personaggi.length) {
        els.characterList.innerHTML = `<div class="empty-state" data-component-type="panel" data-theme="muted">Non ci sono personaggi disponibili per questo giocatore.</div>`;
        els.personaggioPreview.innerHTML = `<div class="empty-state" data-component-type="panel" data-theme="muted">Crea o importa i dati iniziali per poter scegliere un personaggio.</div>`;
        return;
    }

    if (!state.selectedPersonaggioId) {
        state.selectedPersonaggioId = state.activePersonaggioId || state.personaggi[0].id;
    }

    els.characterList.innerHTML = state.personaggi.map((personaggio) => {
        const isSelected = personaggio.id === state.selectedPersonaggioId;
        const isActive = personaggio.id === state.activePersonaggioId;
        return `
            <button class="list-item ${isSelected ? "active" : ""}" data-action="personaggi.preview" data-personaggio-id="${personaggio.id}" data-component-type="button" data-state="${isSelected ? "active" : "idle"}" data-theme="default" type="button">
                <strong>${escapeHtml(personaggio.name)}</strong>
                <span>${escapeHtml(personaggioSubtitle(personaggio))}${isActive ? " · attivo" : ""}</span>
            </button>
        `;
    }).join("");

    renderPersonaggioPreview();
}

function renderPersonaggioPreview() {
    const personaggio = selectedPersonaggio();
    if (!personaggio) {
        els.personaggioPreview.innerHTML = `<div class="empty-state" data-component-type="panel" data-theme="muted">Scegli un personaggio per vederne l'anteprima.</div>`;
        return;
    }

    const isActive = personaggio.id === state.activePersonaggioId;
    els.personaggioPreview.innerHTML = `
        <header class="sheet-head" data-component-type="toolbar" data-theme="default">
            <div>
                <p class="eyebrow">${escapeHtml(personaggio.type || "personaggio")}</p>
                <h3>${escapeHtml(personaggio.name)}</h3>
                <p>${escapeHtml(personaggioSubtitle(personaggio))}</p>
            </div>
            <span class="status-pill" data-component-type="toast" data-theme="${isActive ? "success" : "muted"}">${isActive ? "Attivo" : "Disponibile"}</span>
        </header>
        <p class="detail-copy">${escapeHtml(personaggio.details || "Non sono ancora presenti dettagli.")}</p>
        <div class="sheet-stat-strip" data-component-type="grid" data-theme="default">
            ${renderValueChips(personaggio.primaryTotals || [])}
        </div>
        <div class="form-actions" data-component-type="toolbar" data-theme="default">
            <button class="primary-action" data-action="personaggi.select" data-component-type="button" data-select-personaggio="${personaggio.id}" data-theme="default" type="button">${isActive ? "Aggiorna i dati" : "Imposta come attivo"}</button>
            <button class="secondary-action" data-action="nav.openPersonaggioDetails" data-component-type="button" data-route-target="personaggio" data-theme="muted" type="button">Apri la scheda</button>
        </div>
    `;
}

function renderPersonaggioSheet() {
    updatePersonaggioMetrics();
    const personaggio = state.activePersonaggio;
    if (!personaggio) {
        els.personaggioSheet.innerHTML = `
            <div class="empty-state" data-component-type="panel" data-theme="muted">Nessun personaggio attivo selezionato.</div>
            <div class="form-actions" data-component-type="toolbar" data-theme="default">
                <button class="primary-action" data-action="nav.openPersonaggi" data-component-type="button" data-route-target="characters" data-theme="default" type="button">Scegli personaggio</button>
            </div>
        `;
        return;
    }

    els.personaggioSheet.innerHTML = `
        <header class="sheet-head" data-component-type="toolbar" data-theme="default">
            <div>
                <p class="eyebrow">${escapeHtml(personaggio.type || "giocabile")}</p>
                <h3>${escapeHtml(personaggio.name)}</h3>
                <p>${escapeHtml(personaggioSubtitle(personaggio))}</p>
            </div>
            <div class="sheet-meta">
                <span>${escapeHtml(String(personaggio.coins ?? 0))} monete</span>
                <span>${escapeHtml(personaggio.sex || "n/a")}</span>
            </div>
        </header>
        <p class="detail-copy">${escapeHtml(personaggio.details || "Non sono ancora presenti dettagli sul personaggio.")}</p>

        <section class="sheet-section" data-component-type="panel" data-theme="default">
            <h3>Valori principali</h3>
            <div class="sheet-stat-strip" data-component-type="grid" data-theme="default">
                ${renderValueChips(personaggio.primaryTotals || [])}
            </div>
        </section>

        <div class="sheet-grid" data-component-type="grid" data-theme="default">
            <section class="sheet-section" data-component-type="panel" data-theme="default">
                <h3>Caratteristiche</h3>
                <div class="compact-stat-grid" data-component-type="grid" data-theme="default">
                    ${renderValueRows(personaggio.characteristics || [])}
                </div>
            </section>
            <section class="sheet-section" data-component-type="panel" data-theme="default">
                <h3>Resistenze</h3>
                <div class="compact-stat-grid" data-component-type="grid" data-theme="default">
                    ${renderValueRows(personaggio.resistances || [])}
                </div>
            </section>
        </div>

        <div class="sheet-grid" data-component-type="grid" data-theme="default">
            <section class="sheet-section" data-component-type="panel" data-theme="default">
                <h3>Equipaggiamento</h3>
                ${renderEquipment(personaggio.equipment || [])}
            </section>
            <section class="sheet-section" data-component-type="panel" data-theme="default">
                <h3>Inventario</h3>
                ${renderInventory(personaggio.inventory || [])}
            </section>
        </div>

        <div class="sheet-grid" data-component-type="grid" data-theme="default">
            <section class="sheet-section" data-component-type="panel" data-theme="default">
                <h3>Abilità apprese</h3>
                ${renderSkills(personaggio.skills || [])}
            </section>
            <section class="sheet-section" data-component-type="panel" data-theme="default">
                <h3>Capacità</h3>
                ${renderAbilities(personaggio.abilities || [])}
            </section>
        </div>

        <div class="sheet-grid" data-component-type="grid" data-theme="default">
            <section class="sheet-section" data-component-type="panel" data-theme="default">
                <h3>Effetti attivi</h3>
                ${renderEffects(personaggio.effects || [])}
            </section>
            <section class="sheet-section" data-component-type="panel" data-theme="default">
                <h3>Note e reagenti</h3>
                ${renderNotes(personaggio)}
            </section>
        </div>
    `;
}

function renderValueChips(values) {
    if (!values.length) {
        return `<span class="muted">Nessun valore</span>`;
    }
    return values.map((item) => `
        <div class="value-chip" data-component-type="panel" data-theme="muted">
            <span>${escapeHtml(item.label)}</span>
            <strong>${escapeHtml(formatNumber(item.value))}</strong>
        </div>
    `).join("");
}

function renderValueRows(values) {
    if (!values.length) {
        return `<div class="empty-state" data-component-type="panel" data-theme="muted">Nessun valore disponibile.</div>`;
    }
    return values.map((item) => `
        <div class="stat-row">
            <span>${escapeHtml(item.label)}</span>
            <strong>${escapeHtml(formatNumber(item.value))}</strong>
        </div>
    `).join("");
}

function renderEquipment(entries) {
    if (!entries.length) {
        return `<div class="empty-state" data-component-type="panel" data-theme="muted">Nessun oggetto equipaggiato.</div>`;
    }
    return `<div class="object-list" data-component-type="list" data-theme="default">
        ${entries.map((entry) => `
            <div class="object-row">
                <span>${escapeHtml(entry.label)}</span>
                <strong>${escapeHtml(entry.item?.name || "Vuoto")}</strong>
                <small>${escapeHtml((entry.item?.types || []).join(" / "))}</small>
            </div>
        `).join("")}
    </div>`;
}

function renderInventory(entries) {
    if (!entries.length) {
        return `<div class="empty-state" data-component-type="panel" data-theme="muted">L'inventario è vuoto.</div>`;
    }
    return `<div class="object-list" data-component-type="list" data-theme="default">
        ${entries.map((entry) => `
            <div class="object-row">
                <span>Spazio ${entry.slot}</span>
                <strong>${escapeHtml(entry.item?.name || "Vuoto")}</strong>
                <small>${escapeHtml((entry.item?.types || []).join(" / "))}</small>
            </div>
        `).join("")}
    </div>`;
}

function renderSkills(skills) {
    if (!skills.length) {
        return `<div class="empty-state" data-component-type="panel" data-theme="muted">Nessuna abilità appresa.</div>`;
    }
    return `<div class="pill-grid" data-component-type="grid" data-theme="default">
        ${skills.map((skill) => `
            <div class="skill-pill">
                <strong>${escapeHtml(skill.nome)}</strong>
                <span>${escapeHtml(skill.famiglia || "Abilità")} #${escapeHtml(skill.numero || "")}</span>
            </div>
        `).join("")}
    </div>`;
}

function renderAbilities(abilities) {
    if (!abilities.length) {
        return `<div class="empty-state" data-component-type="panel" data-theme="muted">Nessuna capacità assegnata.</div>`;
    }
    return `<div class="ability-list" data-component-type="list" data-theme="default">
        ${abilities.map((ability) => `
            <article class="ability-row" data-component-type="panel" data-theme="default">
                <div>
                    <strong>${escapeHtml(ability.nome || ability.key)}</strong>
                    <span>${escapeHtml(ability.categoria || "abilita")} - grado ${escapeHtml(ability.grado ?? 1)}</span>
                </div>
                <p>${escapeHtml(ability.descrizione || "")}</p>
            </article>
        `).join("")}
    </div>`;
}

function renderEffects(effects) {
    if (!effects.length) {
        return `<div class="empty-state" data-component-type="panel" data-theme="muted">Nessun effetto attivo.</div>`;
    }
    return `<div class="object-list" data-component-type="list" data-theme="default">
        ${effects.map((effect) => `
            <div class="object-row">
                <span>${escapeHtml(effect.type || "effetto")}</span>
                <strong>${escapeHtml(effect.name)}</strong>
                <small>${escapeHtml(effect.description || "")}</small>
            </div>
        `).join("")}
    </div>`;
}

function renderNotes(personaggio) {
    const ingredients = personaggio.reagents?.ingredients || {};
    return `
        <div class="note-stack" data-component-type="list" data-theme="default">
            <p>${escapeHtml(personaggio.notes?.background || "Nessuna nota sul passato del personaggio.")}</p>
            <div class="stat-row">
                <span>Spazi per reagenti</span>
                <strong>${escapeHtml(personaggio.reagents?.slotMax ?? 0)}</strong>
            </div>
            <div class="object-list" data-component-type="list" data-theme="default">
                ${Object.entries(ingredients).map(([name, amount]) => `
                    <div class="object-row">
                        <span>Reagente</span>
                        <strong>${escapeHtml(name)}</strong>
                        <small>Quantità ${escapeHtml(amount)}</small>
                    </div>
                `).join("") || `<div class="empty-state" data-component-type="panel" data-theme="muted">Nessun reagente.</div>`}
            </div>
        </div>
    `;
}

function renderMedia() {
    els.mediaMetric.textContent = state.mediaAssets.length;
    els.mediaCount.textContent = `${state.mediaAssets.length} ${state.mediaAssets.length === 1 ? "immagine" : "immagini"}`;
    if (!state.mediaAssets.length) {
        els.mediaGrid.innerHTML = `<div class="empty-state" data-component-type="panel" data-theme="muted">L'archivio non contiene ancora immagini.</div>`;
        return;
    }

    els.mediaGrid.innerHTML = state.mediaAssets.map((asset) => {
        const isImage = (asset.mimeType || "").startsWith("image/");
        const preview = isImage
            ? `<img src="${asset.url}" alt="${escapeHtml(asset.title)}">`
            : `<span>${escapeHtml(asset.mimeType || "file")}</span>`;
        return `
            <article class="media-card" data-component-type="card" data-theme="media">
                <div class="media-preview" data-component-type="panel" data-theme="muted">${preview}</div>
                <div class="media-card-body">
                    <strong>${escapeHtml(asset.title)}</strong>
                    <span>${formatBytes(asset.sizeBytes)} - ${escapeHtml(asset.originalName)}</span>
                    <button class="danger-action" data-action="media.delete" data-component-type="button" data-delete-media="${asset.id}" data-theme="danger" type="button">Elimina</button>
                </div>
            </article>
        `;
    }).join("");

    els.mediaGrid.querySelectorAll("[data-delete-media]").forEach((button) => {
        button.addEventListener("click", async () => {
            await apiFetch(`/api/media/${button.dataset.deleteMedia}/`, {
                action: "media.delete",
                method: "DELETE",
                screen: "media",
            });
            await loadMedia();
        });
    });
}

function selectedGuide() {
    return state.guides.find((guide) => guide.name === state.selectedGuideName) || null;
}

function renderGuideBlock(block) {
    const type = block?.type || "paragraph";
    if (type === "heading") {
        return `<h4>${escapeHtml(block.text || "")}</h4>`;
    }
    if (type === "list") {
        const items = Array.isArray(block.items) ? block.items : [];
        return `<ul>${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
    }
    if (type === "code") {
        const language = block.language ? ` data-language="${escapeHtml(block.language)}"` : "";
        return `<pre class="guide-code"${language}><code>${escapeHtml(block.text || "")}</code></pre>`;
    }
    if (type === "callout") {
        return `
            <aside class="guide-callout" data-component-type="panel" data-theme="gold">
                <strong>${escapeHtml(block.title || "Nota")}</strong>
                <p>${escapeHtml(block.text || "")}</p>
            </aside>
        `;
    }
    return `<p>${escapeHtml(block.text || "")}</p>`;
}

function renderGuides() {
    els.guideCount.textContent = `${state.guides.length} ${state.guides.length === 1 ? "guida" : "guide"}`;
    if (!state.guides.length) {
        els.guideList.innerHTML = `<div class="empty-state" data-component-type="panel" data-theme="muted">Non ci sono guide disponibili.</div>`;
        els.guideReader.innerHTML = `<div class="empty-state" data-component-type="panel" data-theme="muted">Nessuna guida selezionata.</div>`;
        return;
    }

    if (!state.selectedGuideName || !state.guides.some((guide) => guide.name === state.selectedGuideName)) {
        state.selectedGuideName = state.guides[0].name;
    }

    els.guideList.innerHTML = state.guides.map((guide, index) => {
        const isActive = guide.name === state.selectedGuideName;
        return `
            <button class="list-item ${isActive ? "active" : ""}" data-action="guide.select" data-guide-index="${index}" data-component-type="button" data-state="${isActive ? "active" : "idle"}" data-theme="lore" type="button">
                <strong>${escapeHtml(guide.name)}</strong>
                <span>${escapeHtml(guide.category || "guida")}</span>
            </button>
        `;
    }).join("");

    const guide = selectedGuide();
    els.guideReader.innerHTML = `
        <header class="guide-reader-head" data-component-type="toolbar" data-theme="lore">
            <div>
                <p class="eyebrow">${escapeHtml(guide.category || "guida")}</p>
                <h3>${escapeHtml(guide.name)}</h3>
            </div>
        </header>
        <div class="guide-content" data-component-type="list" data-theme="lore">
            ${(guide.content || []).map(renderGuideBlock).join("")}
        </div>
    `;
}

function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function formatNumber(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) return String(value ?? 0);
    return Number.isInteger(number) ? String(number) : number.toFixed(1);
}

function formatBytes(bytes) {
    const size = Number(bytes || 0);
    if (size < 1024) return `${size} B`;
    if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
    return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

function ingestPersonaggioData(data) {
    state.giocatore = data.giocatore || null;
    state.personaggi = data.personaggi || [];
    state.activePersonaggio = data.activePersonaggio || null;
    state.activePersonaggioId = data.giocatore?.activePersonaggioId || state.activePersonaggio?.id || null;
    if (!state.selectedPersonaggioId || !state.personaggi.some((item) => item.id === state.selectedPersonaggioId)) {
        state.selectedPersonaggioId = state.activePersonaggioId || state.personaggi[0]?.id || null;
    }
}

async function loadBootstrap() {
    const data = await apiFetch("/api/bootstrap/", { action: "core.bootstrap", screen: "dashboard" });
    state.user = data.user;
    state.security = data.security || null;
    state.guides = data.guides || [];
    els.userChip.textContent = state.user.username;
    renderGuides();
}

async function loadPersonaggi() {
    const data = await apiFetch("/api/personaggi/", { action: "personaggi.list", screen: "personaggi" });
    ingestPersonaggioData(data);
    renderPersonaggioList();
    renderPersonaggioSheet();
}

async function selectPersonaggio(personaggioId) {
    const data = await apiFetch("/api/personaggi/select/", {
        action: "personaggi.select",
        method: "POST",
        payload: { personaggioId },
        screen: "personaggi",
    });
    ingestPersonaggioData(data);
    state.selectedPersonaggioId = personaggioId;
    renderPersonaggioList();
    renderPersonaggioSheet();
    navigate("personaggio");
    setStatus("Personaggio selezionato");
}

async function loadMedia() {
    try {
        const data = await apiFetch("/api/media/", { action: "media.list", screen: "media" });
        state.mediaAssets = data.assets || [];
    } catch {
        state.mediaAssets = [];
    }
    renderMedia();
}

async function uploadMedia(event) {
    event.preventDefault();
    const file = document.querySelector("#media-file").files[0];
    if (!file) return;
    const form = new FormData();
    form.set("file", file);
    await apiFetch("/api/media/", {
        action: "media.upload",
        body: form,
        method: "POST",
        payload: {
            notes: document.querySelector("#media-notes").value,
            title: document.querySelector("#media-title").value,
        },
        screen: "media",
    });
    els.mediaForm.reset();
    await loadMedia();
    setStatus("Immagine aggiunta");
}

function bindEvents() {
    document.querySelectorAll(".menu-item").forEach((button) => {
        button.addEventListener("click", () => navigate(button.dataset.route));
    });
    document.querySelectorAll("[data-route-target]").forEach((button) => {
        button.addEventListener("click", () => navigate(button.dataset.routeTarget));
    });
    els.characterList.addEventListener("click", (event) => {
        const button = event.target.closest("[data-personaggio-id]");
        if (!button) return;
        state.selectedPersonaggioId = Number(button.dataset.personaggioId);
        renderPersonaggioList();
    });
    els.personaggioPreview.addEventListener("click", (event) => {
        const selectButton = event.target.closest("[data-select-personaggio]");
        if (selectButton) {
            selectPersonaggio(Number(selectButton.dataset.selectPersonaggio));
            return;
        }
        const routeButton = event.target.closest("[data-route-target]");
        if (routeButton) {
            navigate(routeButton.dataset.routeTarget);
        }
    });
    els.personaggioSheet.addEventListener("click", (event) => {
        const routeButton = event.target.closest("[data-route-target]");
        if (routeButton) {
            navigate(routeButton.dataset.routeTarget);
        }
    });
    els.guideList.addEventListener("click", (event) => {
        const button = event.target.closest("[data-guide-index]");
        if (!button) return;
        state.selectedGuideName = state.guides[Number(button.dataset.guideIndex)]?.name || null;
        renderGuides();
    });
    els.mediaForm.addEventListener("submit", uploadMedia);
    bindSettings(state, {setStatus});
}

async function boot() {
    try {
        bindEvents();
        setStatus("Caricamento");
        await loadBootstrap();
        await Promise.all([loadPersonaggi(), loadMedia(), loadSettings(state)]);
        navigate("dashboard");
        setStatus("Pronto");
    } catch (error) {
        console.error(error);
        setStatus(error.message || "Errore");
    }
}

boot();
