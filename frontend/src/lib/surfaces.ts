import { createContext, useContext } from "react";

/**
 * Gli sfondi che il tema attivo assegna a ogni superficie, indicizzati per
 * chiave: le stesse di backend/core/theme_surfaces.py.
 *
 * Vive in un contesto separato da quello dell'app perché lo leggono anche
 * Modal e ToolDrawer, che stanno sotto components/ e non devono dipendere da
 * App.tsx (che a sua volta li importa).
 */
export const ThemeSurfacesContext = createContext<Record<string, string>>({});

/** L'immagine della superficie, oppure "" se il tema non ne ha assegnata una.
 * Nessuna superficie eredita lo sfondo di un'altra: vuoto significa vuoto. */
export function useSurfaceBackground(surface?: string): string {
  const surfaces = useContext(ThemeSurfacesContext);
  return (surface && surfaces[surface]) || "";
}
