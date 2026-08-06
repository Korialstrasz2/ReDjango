import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const responsive = vi.hoisted(() => ({ isPhone: false }));

vi.mock("../lib/responsive", () => ({
  useResponsiveLayout: () => ({ isPhone: responsive.isPhone }),
}));

vi.mock("../lib/surfaces", () => ({
  useSurfaceBackground: () => "",
}));

import { Modal } from "./Modal";

describe("Modal backdrop defaults", () => {
  let host: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    responsive.isPhone = false;
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
  });

  afterEach(() => {
    act(() => root.unmount());
    host.remove();
    document.body.innerHTML = "";
    vi.restoreAllMocks();
  });

  function renderModal(onClose: () => void, props: Record<string, boolean> = {}) {
    act(() => {
      root.render(<Modal title="Test" onClose={onClose} {...props}>Contenuto</Modal>);
    });
    return document.querySelector<HTMLElement>(".modal-backdrop")!;
  }

  function clickBackdrop(backdrop: HTMLElement) {
    act(() => {
      backdrop.dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
    });
  }

  it("keeps wide and resizable desktop dialogs backdrop-closable by default", () => {
    const onClose = vi.fn();
    const backdrop = renderModal(onClose, { wide: true, resizable: true });
    clickBackdrop(backdrop);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("respects an explicit desktop closeOnBackdrop false", () => {
    const onClose = vi.fn();
    const backdrop = renderModal(onClose, { wide: true, closeOnBackdrop: false });
    clickBackdrop(backdrop);
    expect(onClose).not.toHaveBeenCalled();
  });

  it("keeps the stricter inferred default for phone full-screen editors", () => {
    responsive.isPhone = true;
    const onClose = vi.fn();
    const backdrop = renderModal(onClose, { wide: true });
    clickBackdrop(backdrop);
    expect(onClose).not.toHaveBeenCalled();
  });
});
