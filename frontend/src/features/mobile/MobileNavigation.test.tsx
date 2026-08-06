import { describe, expect, it } from "vitest";

import { isNavigationActive, managementNavigation, playerNavigation } from "../../lib/navigation";

describe("shared shell navigation", () => {
  it("keeps player route ordering shared by desktop and phone presentations", () => {
    expect(playerNavigation("/character/12").map(({ href, label, management }) => ({ href, label, management }))).toEqual([
      { href: "/", label: "Menu", management: false },
      { href: "/character/12", label: "PG", management: false },
      { href: "/skills", label: "Abilità", management: false },
      { href: "/competencies", label: "Competenze", management: false },
      { href: "/creation", label: "Creazione", management: false },
      { href: "/combat", label: "Combattimento", management: false },
      { href: "/travel", label: "Viaggio", management: false },
      { href: "/market", label: "Mercato", management: false },
      { href: "/lore", label: "Lore", management: false },
      { href: "/media", label: "Immagini", management: false },
      { href: "/guides", label: "Guide", management: false },
      { href: "/settings", label: "Impostazioni", management: false },
    ]);
  });

  it("adds admin-only management destinations without duplicating permission logic in mobile chrome", () => {
    expect(managementNavigation(false).some((item) => item.href === "/tools/players")).toBe(false);
    expect(managementNavigation(true).some((item) => item.href === "/tools/players")).toBe(true);
  });
});

describe("isNavigationActive", () => {
  it("uses exact matching for home and prefix matching for routed workspaces", () => {
    expect(isNavigationActive("/", "/")).toBe(true);
    expect(isNavigationActive("/skills/detail", "/skills")).toBe(true);
    expect(isNavigationActive("/market", "/")).toBe(false);
  });

  it("keeps the character destination active across character identifiers", () => {
    expect(isNavigationActive("/character/25", "/character/12")).toBe(true);
    expect(isNavigationActive("/character/25", "/characters")).toBe(true);
  });
});
