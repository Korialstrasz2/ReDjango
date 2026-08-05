import { useMemo, useSyncExternalStore } from "react";

export const PHONE_NARROW_MAX_WIDTH = 479;
export const PHONE_MAX_WIDTH = 767;
export const TABLET_MAX_WIDTH = 1199;

export type ResponsiveLayoutCategory = "phone-narrow" | "phone" | "tablet" | "desktop";

export type ResponsiveLayoutState = {
  category: ResponsiveLayoutCategory;
  isPhone: boolean;
  isTablet: boolean;
  isDesktop: boolean;
  hasCoarsePointer: boolean;
  hasNoHover: boolean;
  isLandscape: boolean;
  prefersReducedMotion: boolean;
};

const MEDIA_QUERIES = {
  phoneNarrow: `(max-width: ${PHONE_NARROW_MAX_WIDTH}px)`,
  phone: `(max-width: ${PHONE_MAX_WIDTH}px)`,
  tablet: `(max-width: ${TABLET_MAX_WIDTH}px)`,
  coarsePointer: "(pointer: coarse)",
  noHover: "(hover: none)",
  landscape: "(orientation: landscape)",
  reducedMotion: "(prefers-reduced-motion: reduce)",
} as const;

const SERVER_SNAPSHOT = "desktop:0:0:0:0";

export function responsiveCategoryFromWidth(width: number): ResponsiveLayoutCategory {
  const normalized = Number.isFinite(width) ? Math.max(0, width) : TABLET_MAX_WIDTH + 1;
  if (normalized <= PHONE_NARROW_MAX_WIDTH) return "phone-narrow";
  if (normalized <= PHONE_MAX_WIDTH) return "phone";
  if (normalized <= TABLET_MAX_WIDTH) return "tablet";
  return "desktop";
}

function matches(query: string): boolean {
  return typeof window !== "undefined"
    && typeof window.matchMedia === "function"
    && window.matchMedia(query).matches;
}

function getSnapshot(): string {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") return SERVER_SNAPSHOT;
  const category: ResponsiveLayoutCategory = matches(MEDIA_QUERIES.phoneNarrow)
    ? "phone-narrow"
    : matches(MEDIA_QUERIES.phone)
      ? "phone"
      : matches(MEDIA_QUERIES.tablet)
        ? "tablet"
        : "desktop";
  return [
    category,
    matches(MEDIA_QUERIES.coarsePointer) ? "1" : "0",
    matches(MEDIA_QUERIES.noHover) ? "1" : "0",
    matches(MEDIA_QUERIES.landscape) ? "1" : "0",
    matches(MEDIA_QUERIES.reducedMotion) ? "1" : "0",
  ].join(":");
}

function subscribe(listener: () => void): () => void {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") return () => undefined;
  const mediaLists = Object.values(MEDIA_QUERIES).map((query) => window.matchMedia(query));
  mediaLists.forEach((mediaList) => {
    if (typeof mediaList.addEventListener === "function") mediaList.addEventListener("change", listener);
    else mediaList.addListener(listener);
  });
  return () => mediaLists.forEach((mediaList) => {
    if (typeof mediaList.removeEventListener === "function") mediaList.removeEventListener("change", listener);
    else mediaList.removeListener(listener);
  });
}

export function useResponsiveLayout(): ResponsiveLayoutState {
  const snapshot = useSyncExternalStore(subscribe, getSnapshot, () => SERVER_SNAPSHOT);
  return useMemo(() => {
    const [categoryValue, coarse, noHover, landscape, reducedMotion] = snapshot.split(":");
    const category = categoryValue as ResponsiveLayoutCategory;
    return {
      category,
      isPhone: category === "phone" || category === "phone-narrow",
      isTablet: category === "tablet",
      isDesktop: category === "desktop",
      hasCoarsePointer: coarse === "1",
      hasNoHover: noHover === "1",
      isLandscape: landscape === "1",
      prefersReducedMotion: reducedMotion === "1",
    };
  }, [snapshot]);
}
