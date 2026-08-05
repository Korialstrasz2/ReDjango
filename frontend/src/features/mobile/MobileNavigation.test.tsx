import { afterEach, describe, expect, it } from "vitest";

import { isMobileNavigationActive, readDesktopShellNavigation } from "./MobileNavigation";

afterEach(() => {
  document.body.innerHTML = "";
});

describe("readDesktopShellNavigation", () => {
  it("derives player and role-filtered management links from the desktop shell", () => {
    document.body.innerHTML = `
      <aside class="side-nav">
        <nav class="nav-list">
          <a href="/"><span aria-hidden="true">⌂</span><span class="nav-label">Menu</span></a>
          <a href="/character/12"><span aria-hidden="true">⚔</span><span class="nav-label">PG</span></a>
          <div class="nav-management-section">
            <a href="/tools"><span aria-hidden="true">◆</span><span class="nav-label">Strumenti</span></a>
          </div>
        </nav>
      </aside>
    `;

    expect(readDesktopShellNavigation()).toEqual([
      { href: "/", label: "Menu", icon: "⌂", management: false },
      { href: "/character/12", label: "PG", icon: "⚔", management: false },
      { href: "/tools", label: "Strumenti", icon: "◆", management: true },
    ]);
  });
});

describe("isMobileNavigationActive", () => {
  it("uses exact matching for home and prefix matching for routed workspaces", () => {
    expect(isMobileNavigationActive("/", "/")).toBe(true);
    expect(isMobileNavigationActive("/skills/detail", "/skills")).toBe(true);
    expect(isMobileNavigationActive("/market", "/")).toBe(false);
  });

  it("keeps the character destination active across character identifiers", () => {
    expect(isMobileNavigationActive("/character/25", "/character/12")).toBe(true);
    expect(isMobileNavigationActive("/character/25", "/characters")).toBe(true);
  });
});
