import { apiFetch } from "../api.js";


const UI_SETTING_KEYS = new Set([
    "appearance.theme",
    "appearance.font_family",
    "appearance.font_scale",
    "appearance.density",
    "accessibility.reduced_motion",
    "dice.color",
    "dice.animation",
    "dice.sound",
    "branding.app_name",
    "branding.subtitle",
    "appearance.accent_color",
    "appearance.gold_color",
    "appearance.sidebar_color",
]);

const VALID_FONTS = new Set(["system", "serif", "accessible"]);
const VALID_DENSITIES = new Set(["comfortable", "compact"]);
const VALID_DICE_COLORS = new Set(["crimson", "emerald", "sapphire", "obsidian"]);
const HEX_COLOR = /^#[0-9a-f]{6}$/i;


function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function titleCase(value) {
    return String(value || "")
        .replaceAll("_", " ")
        .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function safeColor(value, fallback) {
    return HEX_COLOR.test(String(value || "")) ? value : fallback;
}

function colorWithAlpha(value, alpha, fallback) {
    const color = safeColor(value, fallback);
    const red = Number.parseInt(color.slice(1, 3), 16);
    const green = Number.parseInt(color.slice(3, 5), 16);
    const blue = Number.parseInt(color.slice(5, 7), 16);
    const safeAlpha = Math.min(1, Math.max(0, Number(alpha)));
    return `rgba(${red}, ${green}, ${blue}, ${safeAlpha})`;
}

function safeBackgroundImage(value) {
    if (!value) return "none";
    try {
        const url = new URL(value, window.location.origin);
        if (url.origin !== window.location.origin || !["http:", "https:"].includes(url.protocol)) return "none";
        return `url("${url.href.replaceAll('"', "%22")}")`;
    } catch {
        return "none";
    }
}

function safeBackgroundPosition(value) {
    const position = String(value || "").trim();
    const token = "(?:left|center|right|top|bottom|[0-9]{1,3}%)";
    return new RegExp(`^${token}(?: ${token})?$`).test(position) ? position : "center center";
}

export function applyUiSettings(ui = {}, themes = []) {
    const root = document.documentElement;
    const selectedTheme = themes.find((theme) => theme.slug === ui["appearance.theme"]) || themes[0] || null;
    const theme = selectedTheme?.slug || "parchment";
    const font = VALID_FONTS.has(ui["appearance.font_family"]) ? ui["appearance.font_family"] : "system";
    const density = VALID_DENSITIES.has(ui["appearance.density"]) ? ui["appearance.density"] : "comfortable";
    const diceColor = VALID_DICE_COLORS.has(ui["dice.color"]) ? ui["dice.color"] : "crimson";
    const fontScale = Math.min(130, Math.max(85, Number(ui["appearance.font_scale"]) || 100));

    root.dataset.appTheme = theme;
    root.dataset.font = font;
    root.dataset.density = density;
    root.dataset.reducedMotion = ui["accessibility.reduced_motion"] ? "true" : "false";
    root.dataset.diceColor = diceColor;
    root.dataset.diceAnimation = ui["dice.animation"] === false ? "false" : "true";
    root.dataset.diceSound = ui["dice.sound"] === false ? "false" : "true";
    root.style.fontSize = `${fontScale}%`;
    const colors = selectedTheme?.colors || {};
    const panelOpacity = selectedTheme?.panelOpacity ?? 1;
    const overlayOpacity = selectedTheme?.overlayOpacity ?? 0.72;
    const backgroundColor = safeColor(colors.background, "#f4f2ec");
    root.style.setProperty("--bg", backgroundColor);
    root.style.setProperty("--panel", colorWithAlpha(colors.panel, panelOpacity, "#ffffff"));
    root.style.setProperty("--panel-strong", colorWithAlpha(colors.panelStrong, panelOpacity, "#f9faf8"));
    root.style.setProperty("--ink", safeColor(colors.text, "#202521"));
    root.style.setProperty("--muted", safeColor(colors.mutedText, "#6e746e"));
    root.style.setProperty("--line", safeColor(colors.line, "#d8ddd3"));
    root.style.setProperty("--accent", safeColor(colors.accent, safeColor(ui["appearance.accent_color"], "#2f6f62")));
    root.style.setProperty("--accent-strong", safeColor(colors.accentStrong, "#214f47"));
    root.style.setProperty("--gold", safeColor(colors.gold, safeColor(ui["appearance.gold_color"], "#af7d2f")));
    root.style.setProperty("--sidebar-bg", safeColor(colors.sidebar, safeColor(ui["appearance.sidebar_color"], "#1f2a27")));
    root.style.setProperty("--theme-view-overlay", colorWithAlpha(backgroundColor, overlayOpacity, "#f4f2ec"));
    root.style.setProperty("--theme-background-position", safeBackgroundPosition(selectedTheme?.backgroundPosition));
    root.style.setProperty("--theme-background-blur", `${Math.min(20, Math.max(0, Number(selectedTheme?.backgroundBlur) || 0))}px`);
    Object.entries(selectedTheme?.backgrounds || {}).forEach(([screen, url]) => {
        if (/^[a-z]+$/.test(screen)) {
            root.style.setProperty(`--theme-bg-${screen}`, safeBackgroundImage(url));
        }
    });

    const appName = String(ui["branding.app_name"] || "ReDjango").slice(0, 120);
    const subtitle = String(ui["branding.subtitle"] || "La rinascita di The Elder Django").slice(0, 180);
    const title = document.querySelector("#brand-title");
    const subtitleElement = document.querySelector("#brand-subtitle");
    if (title) title.textContent = appName;
    if (subtitleElement) subtitleElement.textContent = subtitle;
    document.title = appName;
}

function renderRoleHierarchy(security) {
    const currentRank = Number(security?.roleRank || 0);
    return (security?.hierarchy || []).map((level) => {
        const available = currentRank >= Number(level.rank || 0);
        const current = level.id === security.role;
        return `
            <article class="security-level ${available ? "available" : "locked"} ${current ? "current" : ""}" data-component-type="card" data-theme="${current ? "gold" : "muted"}">
                <div class="security-level-head">
                    <strong>${escapeHtml(level.label)}</strong>
                    <span>${current ? "Attuale" : available ? "Incluso" : "Bloccato"}</span>
                </div>
                <p>${escapeHtml(level.description)}</p>
            </article>
        `;
    }).join("");
}

function renderChoiceOptions(setting) {
    return (setting.choices || []).map((choice) => {
        const value = typeof choice === "object" ? choice.value : choice;
        const label = typeof choice === "object" ? choice.label : titleCase(choice);
        return `<option value="${escapeHtml(value)}" ${value === setting.value ? "selected" : ""}>${escapeHtml(label)}</option>`;
    }).join("");
}

function renderControl(setting) {
    const disabled = setting.editable ? "" : " disabled";
    const common = `data-setting-key="${escapeHtml(setting.key)}" data-setting-type="${escapeHtml(setting.valueType)}"${disabled}`;
    if (setting.valueType === "bool") {
        return `
            <label class="settings-toggle">
                <input type="checkbox" ${common} ${setting.value ? "checked" : ""}>
                <span aria-hidden="true"></span>
                <em>${setting.value ? "Sì" : "No"}</em>
            </label>
        `;
    }
    if (setting.valueType === "select") {
        return `<select ${common}>${renderChoiceOptions(setting)}</select>`;
    }
    if (setting.valueType === "color") {
        return `<input type="color" value="${escapeHtml(setting.value)}" ${common}>`;
    }
    if (setting.valueType === "int") {
        const minimum = setting.constraints?.minimum ?? "";
        const maximum = setting.constraints?.maximum ?? "";
        return `<input type="number" value="${escapeHtml(setting.value)}" min="${escapeHtml(minimum)}" max="${escapeHtml(maximum)}" ${common}>`;
    }
    if (setting.valueType === "json") {
        return `<textarea rows="4" ${common}>${escapeHtml(JSON.stringify(setting.value, null, 2))}</textarea>`;
    }
    return `<input type="text" value="${escapeHtml(setting.value)}" maxlength="240" ${common}>`;
}

function roleLabel(role) {
    return {
        user: "Giocatore",
        master: "Master",
        admin: "Amministratore",
    }[role] || role;
}

function categoryLabel(category) {
    const labels = {
        appearance: "Aspetto",
        aspetto: "Aspetto",
        accessibility: "Accessibilità",
        accessibilità: "Accessibilità",
        dice: "Dadi",
        dadi: "Dadi",
        master: "Sessione",
        sessione: "Sessione",
        branding: "Identità",
        identità: "Identità",
        "admin appearance": "Aspetto globale",
        "aspetto globale": "Aspetto globale",
        navigation: "Navigazione",
        navigazione: "Navigazione",
        security: "Sicurezza",
        sicurezza: "Sicurezza",
        features: "Funzioni",
        funzioni: "Funzioni",
    };
    return labels[category] || titleCase(category);
}

function renderSetting(setting, showRoleLabels) {
    const tag = showRoleLabels
        ? `<span class="role-tag" data-role-level="${escapeHtml(setting.minimumRole)}">${escapeHtml(roleLabel(setting.minimumRole))}</span>`
        : "";
    const sourceLabel = setting.isOverride ? "Valore personale" : "Valore predefinito";
    const managedLabel = setting.editable ? "" : " · Gestita da un livello superiore";
    return `
        <article class="setting-card" data-component-type="card" data-theme="${setting.minimumRole}">
            <div class="setting-copy">
                <div class="setting-heading">
                    <strong>${escapeHtml(setting.label)}</strong>
                    ${tag}
                </div>
                <p>${escapeHtml(setting.description)}</p>
                <small>${sourceLabel}${managedLabel}</small>
            </div>
            <div class="setting-control">${renderControl(setting)}</div>
        </article>
    `;
}

function renderSections(settings, showRoleLabels) {
    const sections = new Map();
    settings.forEach((setting) => {
        if (!sections.has(setting.category)) sections.set(setting.category, []);
        sections.get(setting.category).push(setting);
    });
    return [...sections.entries()].map(([category, entries]) => `
        <section class="settings-section" data-component-type="panel" data-theme="default">
            <header>
                ${showRoleLabels ? `<p class="eyebrow">Livello ${escapeHtml(roleLabel(entries[0]?.minimumRole || "user"))}</p>` : ""}
                <h3>${escapeHtml(categoryLabel(category))}</h3>
            </header>
            <div class="settings-list" data-component-type="list" data-theme="default">
                ${entries.map((setting) => renderSetting(setting, showRoleLabels)).join("")}
            </div>
        </section>
    `).join("");
}

function renderPrivilegedNavigation(security) {
    const container = document.querySelector("#privileged-menu");
    if (!container) return;
    if (!security?.showAdminLink) {
        container.innerHTML = "";
        return;
    }
    const note = security.canUseDjangoAdmin
        ? "Apri l'amministrazione Django"
        : "Sono richiesti l'accesso Django e i permessi dello staff";
    container.innerHTML = `
        <a class="menu-item admin-menu-link" data-component-type="button" data-theme="gold" href="${escapeHtml(security.adminUrl || "/admin/")}" title="${escapeHtml(note)}">Amministrazione</a>
    `;
}

export function renderSettings(state) {
    const data = state.settingsData;
    const accessPanel = document.querySelector("#settings-access");
    const roleGrid = document.querySelector("#settings-role-grid");
    const sections = document.querySelector("#settings-sections");
    const roleBadge = document.querySelector("#settings-current-role");
    const settingsHelp = document.querySelector("#settings-help");
    if (!data) {
        if (sections) sections.innerHTML = `<div class="empty-state" data-component-type="panel" data-theme="muted">Caricamento delle impostazioni.</div>`;
        return;
    }

    const security = data.security || {};
    const showRoleLabels = security.showRoleLabels === true;
    const currentLevel = (security.hierarchy || []).find((level) => level.id === security.role);
    if (accessPanel) accessPanel.hidden = !showRoleLabels;
    if (roleGrid) roleGrid.innerHTML = showRoleLabels ? renderRoleHierarchy(security) : "";
    if (sections) sections.innerHTML = renderSections(data.settings || [], showRoleLabels);
    if (roleBadge) {
        roleBadge.hidden = !showRoleLabels;
        roleBadge.textContent = currentLevel?.label || roleLabel(security.role || "admin");
    }
    if (settingsHelp) {
        settingsHelp.textContent = showRoleLabels
            ? "Temi, valori globali e definizioni complete si modificano dall'Amministrazione."
            : "Le preferenze vengono applicate subito e salvate sul tuo profilo.";
    }
    renderPrivilegedNavigation(security);
}

function readFormValues(form) {
    const values = {};
    form.querySelectorAll("[data-setting-key]:not([disabled])").forEach((control) => {
        const key = control.dataset.settingKey;
        const type = control.dataset.settingType;
        if (type === "bool") values[key] = control.checked;
        else if (type === "int") values[key] = Number(control.value);
        else if (type === "json") {
            try {
                values[key] = JSON.parse(control.value);
            } catch {
                values[key] = control.value;
            }
        } else values[key] = control.value;
    });
    return values;
}

function previewSettings(state, form) {
    const preview = {...(state.settingsData?.ui || {})};
    const values = readFormValues(form);
    Object.entries(values).forEach(([key, value]) => {
        if (UI_SETTING_KEYS.has(key)) preview[key] = value;
    });
    applyUiSettings(preview, state.settingsData?.themes || []);
}

export async function loadSettings(state) {
    state.settingsData = await apiFetch("/api/settings/", {
        action: "settings.list",
        screen: "settings",
    });
    state.security = state.settingsData.security || state.security;
    applyUiSettings(state.settingsData.ui || {}, state.settingsData.themes || []);
    renderSettings(state);
}

export function bindSettings(state, {setStatus}) {
    const form = document.querySelector("#settings-form");
    if (!form) return;
    form.addEventListener("change", (event) => {
        if (event.target.matches('input[data-setting-type="bool"]')) {
            const label = event.target.closest(".settings-toggle")?.querySelector("em");
            if (label) label.textContent = event.target.checked ? "Sì" : "No";
        }
        previewSettings(state, form);
    });
    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        try {
            setStatus("Salvataggio impostazioni");
            state.settingsData = await apiFetch("/api/settings/", {
                action: "settings.save",
                method: "POST",
                payload: {settings: readFormValues(form)},
                screen: "settings",
            });
            state.security = state.settingsData.security || state.security;
            applyUiSettings(state.settingsData.ui || {}, state.settingsData.themes || []);
            renderSettings(state);
            setStatus("Impostazioni salvate");
        } catch (error) {
            setStatus(error.message || "Errore nelle impostazioni");
        }
    });
}
