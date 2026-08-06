import { type ReactNode } from "react";

import { Modal } from "./Modal";
import "./ConfirmationModal.css";

type Props = {
  title: string;
  message: ReactNode;
  confirmLabel: string;
  cancelLabel?: string;
  busy?: boolean;
  destructive?: boolean;
  onCancel: () => void;
  onConfirm: () => void;
};

export function ConfirmationModal({
  title,
  message,
  confirmLabel,
  cancelLabel = "Annulla",
  busy = false,
  destructive = false,
  onCancel,
  onConfirm,
}: Props) {
  return <Modal
    surface="confirmation"
    title={title}
    onClose={onCancel}
    closeOnBackdrop={false}
    className={`confirmation-modal ${destructive ? "destructive" : ""}`}
    footer={<>
      <button className="button secondary" type="button" data-modal-initial-focus onClick={onCancel}>{cancelLabel}</button>
      <button className={destructive ? "button primary confirmation-danger" : "button primary"} type="button" disabled={busy} onClick={onConfirm}>{confirmLabel}</button>
    </>}
  >
    <div className="confirmation-modal-copy">
      <span className="confirmation-modal-glyph" aria-hidden="true">{destructive ? "!" : "?"}</span>
      <div>{message}</div>
    </div>
  </Modal>;
}
