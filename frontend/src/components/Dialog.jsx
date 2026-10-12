import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";

// In-app replacements for window.prompt / window.confirm, which some
// browsers (embedded webviews, some in-app browsers) block or don't support.
//
//   const dialog = useDialog();
//   const name = await dialog.prompt({ title: "Rename", defaultValue: "A" }); // string | null
//   const ok = await dialog.confirm({ title: "Delete?", danger: true });      // boolean

const DialogContext = createContext(null);

export function DialogProvider({ children }) {
  const [request, setRequest] = useState(null);
  const nextId = useRef(0);

  const open = useCallback(
    (kind, options) =>
      new Promise((resolve) => setRequest({ id: ++nextId.current, kind, options, resolve })),
    [],
  );
  const api = useRef({
    prompt: (options) => open("prompt", options),
    confirm: (options) => open("confirm", options),
  }).current;

  const close = (value) => {
    request.resolve(value);
    setRequest(null);
  };

  return (
    <DialogContext.Provider value={api}>
      {children}
      {request && (
        <DialogBox
          key={request.id}
          kind={request.kind}
          {...request.options}
          onClose={close}
        />
      )}
    </DialogContext.Provider>
  );
}

export const useDialog = () => useContext(DialogContext);

function DialogBox({ kind, title, message, defaultValue = "", confirmLabel, danger, onClose }) {
  const [value, setValue] = useState(defaultValue);
  const cancelValue = kind === "prompt" ? null : false;

  useEffect(() => {
    // Capture phase so Escape closes only this dialog, not a modal underneath.
    const onKey = (e) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        onClose(cancelValue);
      }
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [onClose, cancelValue]);

  function submit(e) {
    e.preventDefault();
    if (kind === "prompt") {
      const trimmed = value.trim();
      if (trimmed) onClose(trimmed);
    } else {
      onClose(true);
    }
  }

  return (
    <div
      className="modal-backdrop modal-backdrop-top"
      onMouseDown={(e) => e.target === e.currentTarget && onClose(cancelValue)}
    >
      <form className="modal modal-small" onSubmit={submit} role="dialog" aria-modal="true" aria-label={title}>
        <h2>{title}</h2>
        {message && <p className="muted">{message}</p>}
        {kind === "prompt" && (
          <input
            className="input-block"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onFocus={(e) => e.target.select()}
            autoFocus
            maxLength={100}
          />
        )}
        <div className="modal-actions">
          <span className="spacer" />
          <button type="button" className="btn btn-ghost" onClick={() => onClose(cancelValue)}>Cancel</button>
          <button
            className={`btn ${danger ? "btn-danger-solid" : "btn-primary"}`}
            disabled={kind === "prompt" && !value.trim()}
            autoFocus={kind === "confirm"}
          >
            {confirmLabel ?? (kind === "prompt" ? "Save" : "OK")}
          </button>
        </div>
      </form>
    </div>
  );
}
