export const state = {
    user: null,
    route: "dashboard",
    personaggi: [],
    selectedPersonaggioId: null,
    activePersonaggioId: null,
    activePersonaggio: null,
    guides: [],
    selectedGuideName: null,
    mediaAssets: [],
    security: null,
    settingsData: null,
};

export function selectedPersonaggio() {
    return state.personaggi.find((personaggio) => personaggio.id === state.selectedPersonaggioId) || null;
}
