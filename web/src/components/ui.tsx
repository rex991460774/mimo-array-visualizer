import { AlertTriangle, Check, CheckCircle2, Info, X, XCircle } from "lucide-react";
import {
  type ButtonHTMLAttributes,
  type ReactNode,
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";

type ButtonVariant = "default" | "primary" | "ghost" | "danger";

export function Button({
  variant = "default",
  size,
  icon,
  active,
  className = "",
  children,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: "sm";
  icon?: ReactNode;
  active?: boolean;
}) {
  const iconOnly = !children;
  const classes = [
    "btn",
    variant !== "default" ? variant : "",
    size ?? "",
    iconOnly ? "icon" : "",
    active ? "active" : "",
    className,
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <button type="button" className={classes} aria-pressed={active === undefined ? undefined : active} {...rest}>
      {icon}
      {children}
    </button>
  );
}

export function Segmented<T extends string>({
  value,
  options,
  onChange,
  label,
}: {
  value: T;
  options: { value: T; label: ReactNode; title?: string }[];
  onChange: (value: T) => void;
  label?: string;
}) {
  return (
    <div className="segmented" role="group" aria-label={label}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          title={option.title}
          aria-pressed={option.value === value}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

/**
 * Numeric input that commits on Enter/blur and reverts invalid text,
 * matching the desktop tool's "restore last valid value" behaviour.
 */
export function NumberInput({
  value,
  onCommit,
  parse,
  format = (v) => String(v),
  className = "input num",
  invalidTitle,
  ...rest
}: {
  value: number;
  onCommit: (value: number) => void;
  parse: (text: string) => number | null;
  format?: (value: number) => string;
  className?: string;
  invalidTitle?: string;
} & Omit<React.InputHTMLAttributes<HTMLInputElement>, "value" | "onChange">) {
  const [text, setText] = useState(format(value));
  const [invalid, setInvalid] = useState(false);
  const focused = useRef(false);

  useEffect(() => {
    if (!focused.current) setText(format(value));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  const commit = () => {
    const parsed = parse(text);
    if (parsed === null) {
      setText(format(value));
      setInvalid(false);
      return;
    }
    setInvalid(false);
    if (parsed !== value) onCommit(parsed);
    setText(format(parsed));
  };

  return (
    <input
      {...rest}
      className={className + (invalid ? " invalid" : "")}
      value={text}
      inputMode="decimal"
      title={invalid ? invalidTitle : rest.title}
      aria-invalid={invalid || undefined}
      onFocus={(event) => {
        focused.current = true;
        event.currentTarget.select();
      }}
      onChange={(event) => {
        setText(event.target.value);
        setInvalid(parse(event.target.value) === null);
      }}
      onBlur={() => {
        focused.current = false;
        commit();
      }}
      onKeyDown={(event) => {
        if (event.key === "Enter") {
          commit();
          (event.target as HTMLInputElement).blur();
        } else if (event.key === "Escape") {
          setText(format(value));
          setInvalid(false);
          (event.target as HTMLInputElement).blur();
        }
        event.stopPropagation();
      }}
    />
  );
}

export function Callout({
  tone = "neutral",
  title,
  children,
}: {
  tone?: "neutral" | "info" | "success" | "warning" | "danger";
  title?: ReactNode;
  children?: ReactNode;
}) {
  const icon =
    tone === "success" ? (
      <CheckCircle2 size={16} />
    ) : tone === "warning" ? (
      <AlertTriangle size={16} />
    ) : tone === "danger" ? (
      <XCircle size={16} />
    ) : (
      <Info size={16} />
    );
  return (
    <div className={`callout ${tone}`} role={tone === "danger" ? "alert" : undefined}>
      {icon}
      <div>
        {title && <div style={{ fontWeight: 600, marginBottom: children ? 2 : 0 }}>{title}</div>}
        {children}
      </div>
    </div>
  );
}

export function Dialog({
  title,
  onClose,
  children,
  footer,
  size,
}: {
  title: ReactNode;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  size?: "wide" | "medium";
}) {
  const titleId = useId();
  const panel = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    panel.current?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        onClose();
      }
    };
    window.addEventListener("keydown", onKey, true);
    return () => {
      window.removeEventListener("keydown", onKey, true);
      previous?.focus?.();
    };
  }, [onClose]);

  return createPortal(
    <div
      className="dialog-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        ref={panel}
        className={`dialog ${size ?? ""}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
      >
        <div className="dialog-header">
          <h2 id={titleId}>{title}</h2>
          <span style={{ flex: 1 }} />
          <Button variant="ghost" icon={<X size={16} />} onClick={onClose} aria-label="Close" />
        </div>
        <div className="dialog-body">{children}</div>
        {footer && <div className="dialog-footer">{footer}</div>}
      </div>
    </div>,
    document.body,
  );
}

export function Menu({
  trigger,
  children,
  align = "right",
}: {
  trigger: (props: { open: boolean; toggle: () => void }) => ReactNode;
  children: (close: () => void) => ReactNode;
  align?: "left" | "right";
}) {
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState<React.CSSProperties>({});
  const anchor = useRef<HTMLDivElement>(null);
  const close = useCallback(() => setOpen(false), []);
  // Fixed positioning keeps the menu visible inside scrollable bars.
  const toggle = useCallback(() => {
    const rect = anchor.current?.getBoundingClientRect();
    if (rect) {
      setPosition(
        align === "left"
          ? { position: "fixed", top: rect.bottom + 4, left: rect.left, right: "auto" }
          : { position: "fixed", top: rect.bottom + 4, right: window.innerWidth - rect.right, left: "auto" },
      );
    }
    setOpen((value) => !value);
  }, [align]);
  useEffect(() => {
    if (!open) return;
    const onDown = (event: MouseEvent) => {
      if (!anchor.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && setOpen(false);
    const onResize = () => setOpen(false);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    window.addEventListener("resize", onResize);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
      window.removeEventListener("resize", onResize);
    };
  }, [open]);
  return (
    <div className="menu-anchor" ref={anchor}>
      {trigger({ open, toggle })}
      {open && (
        <div className="menu" role="menu" style={position}>
          {children(close)}
        </div>
      )}
    </div>
  );
}

export function MenuItem({
  icon,
  children,
  onSelect,
  checked,
  disabled,
}: {
  icon?: ReactNode;
  children: ReactNode;
  onSelect: () => void;
  checked?: boolean;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      className="menu-item"
      role={checked === undefined ? "menuitem" : "menuitemradio"}
      aria-checked={checked}
      disabled={disabled}
      onClick={onSelect}
    >
      {icon}
      <span>{children}</span>
      {checked && <Check size={14} className="menu-check" />}
    </button>
  );
}

/** Hidden file input driven by a callback. */
export function useFilePicker(accept: string, onFile: (file: File) => void) {
  const input = useRef<HTMLInputElement | null>(null);
  const callback = useRef(onFile);
  callback.current = onFile;
  useEffect(() => {
    const element = document.createElement("input");
    element.type = "file";
    element.accept = accept;
    element.style.display = "none";
    element.addEventListener("change", () => {
      const file = element.files?.[0];
      element.value = "";
      if (file) callback.current(file);
    });
    document.body.appendChild(element);
    input.current = element;
    return () => element.remove();
  }, [accept]);
  return useCallback(() => input.current?.click(), []);
}

export function Spinner() {
  return <span className="spinner" aria-hidden="true" />;
}
