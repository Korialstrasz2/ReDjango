import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ProposalFieldRenderer } from "./FieldRenderer";
import type { AIChangeField } from "./types";

const field = (values: Partial<AIChangeField> & Pick<AIChangeField, "name" | "label" | "kind">): AIChangeField => ({
  group: "Test", required: false, nullable: false, readOnly: false, help: "", choices: [], ui: {}, ...values,
});

const render = async (fields: AIChangeField[], values: Record<string, unknown>, onChange = vi.fn()) => {
  const host = document.createElement("div"); document.body.append(host); const root = createRoot(host);
  await act(async () => root.render(<ProposalFieldRenderer fields={fields} values={values} errors={[]} disabled={false} onChange={onChange} />));
  return { host, root, onChange };
};

afterEach(() => { document.body.innerHTML = ""; vi.restoreAllMocks(); });

describe("ProposalFieldRenderer", () => {
  it("renders only server supplied choice labels", async () => {
    const { host, root } = await render([field({ name: "rarity", label: "Rarità", kind: "choice", choices: [{ value: "common", label: "Comune" }, { value: "rare", label: "Rara" }] })], { rarity: "rare" });
    expect([...host.querySelectorAll("option")].map((entry) => entry.textContent)).toEqual(["Comune", "Rara"]);
    expect((host.querySelector("select") as HTMLSelectElement).value).toBe("rare");
    await act(async () => root.unmount());
  });

  it("submits relation identifiers instead of labels", async () => {
    const onChange = vi.fn();
    const { host, root } = await render([field({ name: "familyId", label: "Famiglia", kind: "relation", choices: [{ value: 12, label: "Distruzione" }, { value: 19, label: "Illusione" }] })], { familyId: 12 }, onChange);
    const select = host.querySelector("select") as HTMLSelectElement;
    await act(async () => { select.value = "19"; select.dispatchEvent(new Event("change", { bubbles: true })); });
    expect(onChange).toHaveBeenCalledWith("familyId", 19);
    await act(async () => root.unmount());
  });

  it("shows unknown field kinds instead of silently dropping data", async () => {
    const { host, root } = await render([field({ name: "future", label: "Campo futuro", kind: "futureWidget" })], { future: "value" });
    expect(host.querySelector('[role="alert"]')?.textContent).toContain("futureWidget");
    expect(host.textContent).toContain("Campo futuro");
    await act(async () => root.unmount());
  });

  it("keeps invalid structured JSON local", async () => {
    const onChange = vi.fn();
    const { host, root } = await render([field({ name: "effects", label: "Effetti", kind: "structured", ui: { widget: "itemEffects" } })], { effects: [] }, onChange);
    const textarea = host.querySelector("textarea") as HTMLTextAreaElement;
    await act(async () => { textarea.value = "{"; textarea.dispatchEvent(new Event("input", { bubbles: true })); textarea.dispatchEvent(new Event("change", { bubbles: true })); });
    expect(host.textContent).toContain("JSON non valido");
    expect(onChange).not.toHaveBeenCalled();
    await act(async () => root.unmount());
  });
});
