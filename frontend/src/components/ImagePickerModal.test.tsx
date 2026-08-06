import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  notify: vi.fn(),
  onClose: vi.fn(),
  onSelect: vi.fn(),
  asset: {
    id: 7,
    title: "Immagine test",
    originalName: "test.png",
    url: "/media/test.png",
    thumbnailUrl: "/media/test-thumb.png",
    mimeType: "image/png",
    sizeBytes: 1024,
    notes: "",
    folder: "",
    usageType: "map",
    categoryId: 3,
    category: "Mappe",
    categorySlug: "mappe",
    group: "Combattimento",
    source: "upload",
    limitedVisibility: false,
    createdAt: null,
    canDelete: true,
    canMove: true,
    canSetLimitedVisibility: true,
  },
  category: {
    id: 3,
    name: "Mappe",
    slug: "mappe",
    description: "",
    usageTypes: ["map"],
    order: 1,
  },
}));

vi.mock("../App", () => ({
  useApp: () => ({
    media: [mocks.asset],
    mediaCategories: [mocks.category],
    notify: mocks.notify,
  }),
}));

vi.mock("../lib/api", () => ({
  convertImageToWebp: vi.fn(),
  uploadMedia: vi.fn(),
}));

vi.mock("../lib/responsive", () => ({
  useResponsiveLayout: () => ({ isPhone: false }),
}));

import { ImagePickerModal } from "./ImagePickerModal";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const click = async (element: Element) => {
  await act(async () => {
    element.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
  });
};

const flushFrames = async () => {
  await act(async () => {
    await new Promise<void>((resolve) => window.requestAnimationFrame(() => window.requestAnimationFrame(() => resolve())));
  });
};

describe("ImagePickerModal preview stack", () => {
  let host: HTMLDivElement;
  let root: Root;

  beforeEach(async () => {
    mocks.notify.mockReset();
    mocks.onClose.mockReset();
    mocks.onSelect.mockReset();
    document.body.innerHTML = "";
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
    await act(async () => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <ImagePickerModal
            selectedId={null}
            usageType="map"
            defaultGroup="Combattimento"
            defaultTitle="Mappa"
            onSelect={mocks.onSelect}
            onClose={mocks.onClose}
          />
        </QueryClientProvider>,
      );
    });
    await flushFrames();
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    document.body.innerHTML = "";
  });

  it("uses the shared modal stack and restores the persistent card trigger", async () => {
    const picker = document.querySelector<HTMLElement>("[role='dialog'][aria-label=\"Scegli un'immagine\"]");
    const cardTrigger = document.querySelector<HTMLButtonElement>('[aria-label="Azioni per Immagine test"]');
    expect(picker).not.toBeNull();
    expect(cardTrigger).not.toBeNull();

    await click(cardTrigger!);
    const open = Array.from(document.querySelectorAll<HTMLButtonElement>("button")).find((button) => button.textContent?.trim() === "Apri");
    expect(open).toBeDefined();
    await click(open!);
    await flushFrames();

    const preview = document.querySelector<HTMLElement>('[role="dialog"][aria-label="Anteprima Immagine test"]');
    expect(preview).not.toBeNull();
    expect(preview?.hasAttribute("data-modal-top")).toBe(true);
    expect(picker?.getAttribute("aria-hidden")).toBe("true");
    expect((picker as HTMLElement & { inert: boolean }).inert).toBe(true);
    expect(preview?.querySelector<HTMLButtonElement>('button[aria-label="Chiudi"]')).toBe(document.activeElement);

    await act(async () => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true, cancelable: true }));
    });
    await flushFrames();

    expect(document.querySelector('[role="dialog"][aria-label="Anteprima Immagine test"]')).toBeNull();
    expect(picker?.hasAttribute("data-modal-top")).toBe(true);
    expect(picker?.hasAttribute("aria-hidden")).toBe(false);
    expect(cardTrigger).toBe(document.activeElement);
    expect(mocks.onClose).not.toHaveBeenCalled();
  });
});
