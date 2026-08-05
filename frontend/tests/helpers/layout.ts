import type { Page } from "@playwright/test";

export type OverflowOffender = {
  tag: string;
  className: string;
  left: number;
  right: number;
  width: number;
};

export type DocumentOverflow = {
  document: number;
  viewportWidth: number;
  offenders: OverflowOffender[];
};

export async function measureDocumentOverflow(page: Page): Promise<DocumentOverflow> {
  return page.evaluate(() => {
    const viewportWidth = document.documentElement.clientWidth;
    const documentOverflow = document.documentElement.scrollWidth - viewportWidth;
    const offenders = Array.from(document.querySelectorAll<HTMLElement>("body *"))
      .map((element) => ({ element, rect: element.getBoundingClientRect() }))
      .filter(({ rect }) => rect.right > viewportWidth + 1 || rect.left < -1)
      .map(({ element, rect }) => ({
        tag: element.tagName,
        className: typeof element.className === "string" ? element.className : "",
        left: Math.round(rect.left * 100) / 100,
        right: Math.round(rect.right * 100) / 100,
        width: Math.round(rect.width * 100) / 100,
      }))
      .slice(0, 20);
    return {
      document: documentOverflow,
      viewportWidth,
      offenders,
    };
  });
}
