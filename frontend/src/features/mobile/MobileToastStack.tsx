import { useEffect, useRef, useState } from "react";

import { useResponsiveLayout } from "../../lib/responsive";

type ToastKind = "success" | "error" | "info";
type MobileToast = { id: number; message: string; kind: ToastKind };

const MAX_VISIBLE_TOASTS = 3;
const TOAST_LIFETIME_MS = 4200;

function readSourceToast(): { element: HTMLElement; message: string; kind: ToastKind } | null {
  const element = document.querySelector<HTMLElement>(".toast:not([data-mobile-toast-copy])");
  const message = element?.textContent?.trim();
  if (!element || !message) return null;
  const kind: ToastKind = element.classList.contains("error")
    ? "error"
    : element.classList.contains("info")
      ? "info"
      : "success";
  return { element, message, kind };
}

/**
 * The desktop application deliberately retains its original single-toast host.
 * Phones mirror each source-toast mutation into a small bounded stack so a
 * second message does not replace the first before it can be read. This runtime
 * is presentation-only: it does not alter notification dispatch or desktop DOM.
 */
export function MobileToastStack() {
  const { isPhone } = useResponsiveLayout();
  const [toasts, setToasts] = useState<MobileToast[]>([]);
  const sequence = useRef(0);
  const lastCapture = useRef<{ element: HTMLElement | null; signature: string; at: number }>({ element: null, signature: "", at: 0 });

  useEffect(() => {
    if (!isPhone) {
      setToasts([]);
      return;
    }

    let captureQueued = false;
    const capture = () => {
      captureQueued = false;
      const source = readSourceToast();
      if (!source) return;
      const signature = `${source.kind}:${source.message}`;
      const now = performance.now();
      if (lastCapture.current.element === source.element
        && lastCapture.current.signature === signature
        && now - lastCapture.current.at < 120) return;
      lastCapture.current = { element: source.element, signature, at: now };
      const id = ++sequence.current;
      setToasts((current) => [...current, { id, message: source.message, kind: source.kind }].slice(-MAX_VISIBLE_TOASTS));
      window.setTimeout(() => {
        setToasts((current) => current.filter((entry) => entry.id !== id));
      }, TOAST_LIFETIME_MS);
    };
    const queueCapture = () => {
      if (captureQueued) return;
      captureQueued = true;
      queueMicrotask(capture);
    };

    const observer = new MutationObserver(queueCapture);
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      characterData: true,
      attributes: true,
      attributeFilter: ["class"],
    });
    queueCapture();
    return () => observer.disconnect();
  }, [isPhone]);

  if (!isPhone || !toasts.length) return null;
  return <section className="mobile-toast-stack" aria-label="Notifiche">
    {toasts.map((toast) => <div
      key={toast.id}
      className={`toast ${toast.kind}`}
      data-mobile-toast-copy="true"
      role={toast.kind === "error" ? "alert" : "status"}
    >{toast.message}</div>)}
  </section>;
}
