export const state = {
    user: null,
    route: "dashboard",
    characters: [],
    selectedCharacterId: null,
    mediaAssets: [],
};

export function selectedCharacter() {
    return state.characters.find((character) => character.id === state.selectedCharacterId) || null;
}
