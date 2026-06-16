import { apiFetch } from "./api.js";
import { selectedCharacter, state } from "./store.js";

const views = {
    dashboard: document.querySelector("#view-dashboard"),
    characters: document.querySelector("#view-characters"),
    media: document.querySelector("#view-media"),
};

const titles = {
    dashboard: "Main Menu",
    characters: "Character Menu",
    media: "Media Vault",
};

const els = {
    title: document.querySelector("#view-title"),
    status: document.querySelector("#status-pill"),
    userChip: document.querySelector("#user-chip"),
    characterMetric: document.querySelector("#metric-characters"),
    mediaMetric: document.querySelector("#metric-media"),
    characterList: document.querySelector("#character-list"),
    characterForm: document.querySelector("#character-form"),
    deleteCharacter: document.querySelector("#delete-character"),
    mediaForm: document.querySelector("#media-form"),
    mediaGrid: document.querySelector("#media-grid"),
    mediaCount: document.querySelector("#media-count"),
};

const characterFields = {
    id: document.querySelector("#character-id"),
    name: document.querySelector("#character-name"),
    ancestry: document.querySelector("#character-ancestry"),
    archetype: document.querySelector("#character-archetype"),
    level: document.querySelector("#character-level"),
    notes: document.querySelector("#character-notes"),
    might: document.querySelector("#stat-might"),
    agility: document.querySelector("#stat-agility"),
    mind: document.querySelector("#stat-mind"),
    spirit: document.querySelector("#stat-spirit"),
    health: document.querySelector("#resource-health"),
    stamina: document.querySelector("#resource-stamina"),
    mana: document.querySelector("#resource-mana"),
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

function numberValue(input, fallback = 0) {
    const value = Number.parseInt(input.value, 10);
    return Number.isFinite(value) ? value : fallback;
}

function characterPayload() {
    return {
        name: characterFields.name.value.trim() || "New Character",
        ancestry: characterFields.ancestry.value.trim(),
        archetype: characterFields.archetype.value.trim(),
        level: numberValue(characterFields.level, 1),
        notes: characterFields.notes.value,
        stats: {
            might: numberValue(characterFields.might),
            agility: numberValue(characterFields.agility),
            mind: numberValue(characterFields.mind),
            spirit: numberValue(characterFields.spirit),
        },
        resources: {
            health: numberValue(characterFields.health),
            stamina: numberValue(characterFields.stamina),
            mana: numberValue(characterFields.mana),
        },
    };
}

function setCharacterForm(character) {
    const stats = character?.stats || {};
    const resources = character?.resources || {};
    characterFields.id.value = character?.id || "";
    characterFields.name.value = character?.name || "";
    characterFields.ancestry.value = character?.ancestry || "";
    characterFields.archetype.value = character?.archetype || "";
    characterFields.level.value = character?.level || 1;
    characterFields.notes.value = character?.notes || "";
    characterFields.might.value = stats.might ?? 1;
    characterFields.agility.value = stats.agility ?? 1;
    characterFields.mind.value = stats.mind ?? 1;
    characterFields.spirit.value = stats.spirit ?? 1;
    characterFields.health.value = resources.health ?? 10;
    characterFields.stamina.value = resources.stamina ?? 5;
    characterFields.mana.value = resources.mana ?? 0;
    els.deleteCharacter.disabled = !character;
}

function renderCharacters() {
    els.characterMetric.textContent = state.characters.length;
    if (!state.characters.length) {
        els.characterList.innerHTML = `<div class="empty-state" data-component-type="panel" data-theme="muted">No characters yet.</div>`;
        setCharacterForm(null);
        return;
    }

    if (!state.selectedCharacterId) {
        state.selectedCharacterId = state.characters[0].id;
    }

    els.characterList.innerHTML = state.characters.map((character) => {
        const isActive = character.id === state.selectedCharacterId;
        return `
        <button class="list-item ${isActive ? "active" : ""}" data-action="characters.select" data-character-id="${character.id}" data-component-type="button" data-state="${isActive ? "active" : "idle"}" data-theme="default" type="button">
            <strong>${escapeHtml(character.name)}</strong>
            <span>${escapeHtml(character.ancestry || "Unknown")} ${escapeHtml(character.archetype || "")}, level ${character.level}</span>
        </button>
    `;
    }).join("");

    els.characterList.querySelectorAll("[data-character-id]").forEach((button) => {
        button.addEventListener("click", () => {
            state.selectedCharacterId = Number(button.dataset.characterId);
            renderCharacters();
        });
    });

    setCharacterForm(selectedCharacter());
}

function renderMedia() {
    els.mediaMetric.textContent = state.mediaAssets.length;
    els.mediaCount.textContent = `${state.mediaAssets.length} file${state.mediaAssets.length === 1 ? "" : "s"}`;
    if (!state.mediaAssets.length) {
        els.mediaGrid.innerHTML = `<div class="empty-state" data-component-type="panel" data-theme="muted">No user media copies yet.</div>`;
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
                    <button class="danger-action" data-action="media.delete" data-component-type="button" data-delete-media="${asset.id}" data-theme="danger" type="button">Delete</button>
                </div>
            </article>
        `;
    }).join("");

    els.mediaGrid.querySelectorAll("[data-delete-media]").forEach((button) => {
        button.addEventListener("click", async () => {
            await apiFetch(`/api/media/${button.dataset.deleteMedia}/`, { method: "DELETE" });
            await loadMedia();
        });
    });
}

function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function formatBytes(bytes) {
    const size = Number(bytes || 0);
    if (size < 1024) return `${size} B`;
    if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
    return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

async function loadBootstrap() {
    const data = await apiFetch("/api/bootstrap/", { action: "core.bootstrap", screen: "dashboard" });
    state.user = data.user;
    els.userChip.textContent = `User side: ${state.user.username}`;
}

async function loadCharacters() {
    const data = await apiFetch("/api/characters/", { action: "characters.list", screen: "characters" });
    state.characters = data.characters;
    if (state.selectedCharacterId && !state.characters.some((character) => character.id === state.selectedCharacterId)) {
        state.selectedCharacterId = state.characters[0]?.id || null;
    }
    renderCharacters();
}

async function loadMedia() {
    const data = await apiFetch("/api/media/", { action: "media.list", screen: "media" });
    state.mediaAssets = data.assets;
    renderMedia();
}

async function saveCharacter(event) {
    event.preventDefault();
    const id = characterFields.id.value;
    const payload = characterPayload();
    if (id) {
        const data = await apiFetch(`/api/characters/${id}/`, {
            action: "characters.save",
            method: "PATCH",
            payload,
            screen: "characters",
        });
        state.characters = state.characters.map((character) => character.id === data.character.id ? data.character : character);
    } else {
        const data = await apiFetch("/api/characters/", {
            action: "characters.create",
            method: "POST",
            payload,
            screen: "characters",
        });
        state.characters = [...state.characters, data.character].sort((a, b) => a.name.localeCompare(b.name));
        state.selectedCharacterId = data.character.id;
    }
    renderCharacters();
    setStatus("Saved");
}

async function deleteSelectedCharacter() {
    const character = selectedCharacter();
    if (!character) return;
    const confirmed = window.confirm(`Delete ${character.name}?`);
    if (!confirmed) return;
    await apiFetch(`/api/characters/${character.id}/`, {
        action: "characters.delete",
        method: "DELETE",
        screen: "characters",
    });
    state.characters = state.characters.filter((item) => item.id !== character.id);
    state.selectedCharacterId = state.characters[0]?.id || null;
    renderCharacters();
    setStatus("Deleted");
}

async function uploadMedia(event) {
    event.preventDefault();
    const form = new FormData();
    form.set("file", document.querySelector("#media-file").files[0]);
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
    setStatus("Media copied");
}

function bindEvents() {
    document.querySelectorAll(".menu-item").forEach((button) => {
        button.addEventListener("click", () => navigate(button.dataset.route));
    });
    document.querySelectorAll("[data-route-target]").forEach((button) => {
        button.addEventListener("click", () => navigate(button.dataset.routeTarget));
    });
    document.querySelector("#new-character").addEventListener("click", () => {
        state.selectedCharacterId = null;
        renderCharacters();
        characterFields.name.focus();
    });
    els.characterForm.addEventListener("submit", saveCharacter);
    els.deleteCharacter.addEventListener("click", deleteSelectedCharacter);
    els.mediaForm.addEventListener("submit", uploadMedia);
}

async function boot() {
    try {
        bindEvents();
        setStatus("Loading");
        await loadBootstrap();
        await Promise.all([loadCharacters(), loadMedia()]);
        navigate("dashboard");
        setStatus("Ready");
    } catch (error) {
        console.error(error);
        setStatus(error.message || "Error");
    }
}

boot();
