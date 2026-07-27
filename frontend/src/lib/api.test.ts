import { afterEach, describe, expect, it, vi } from "vitest";

import { convertImageToWebp } from "./api";

describe("combat map WebP conversion", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("keeps the decoded pixel dimensions and encodes at 75 percent quality", async () => {
    const close = vi.fn();
    const bitmap = { width: 1448, height: 1086, close } as unknown as ImageBitmap;
    const drawImage = vi.fn();
    let requestedType = "";
    let requestedQuality = 0;
    const canvas = {
      width: 0,
      height: 0,
      getContext: vi.fn(() => ({ drawImage })),
      toBlob: (callback: BlobCallback, type?: string, quality?: number) => {
        requestedType = type || "";
        requestedQuality = quality || 0;
        callback(new Blob(["webp-map"], { type: "image/webp" }));
      },
    };
    vi.stubGlobal("createImageBitmap", vi.fn(async () => bitmap));
    vi.stubGlobal("document", { createElement: vi.fn(() => canvas) });

    const source = new File(["png-map"], "bosco.png", { type: "image/png" });
    const converted = await convertImageToWebp(source, .75);

    expect(canvas.width).toBe(1448);
    expect(canvas.height).toBe(1086);
    expect(drawImage).toHaveBeenCalledWith(bitmap, 0, 0, 1448, 1086);
    expect(requestedType).toBe("image/webp");
    expect(requestedQuality).toBe(.75);
    expect(converted.name).toBe("bosco.webp");
    expect(converted.type).toBe("image/webp");
    expect(close).toHaveBeenCalledOnce();
  });
});
