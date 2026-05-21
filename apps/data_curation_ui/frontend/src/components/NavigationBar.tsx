import { buttonLabel, UiLanguage } from "../api";

interface Props {
  uiLang: UiLanguage;
  index: number;
  total: number;
  onNavigate: (index: number) => Promise<void>;
}

export default function NavigationBar({ uiLang, index, total, onNavigate }: Props) {
  async function jump() {
    const raw = (document.getElementById("jump-index") as HTMLInputElement | null)?.value ?? "";
    const next = Number.parseInt(raw, 10);
    if (Number.isNaN(next)) return;
    await onNavigate(next);
  }

  return (
    <div className="navigation-bar">
      <button onClick={() => onNavigate(index - 1)} disabled={index <= 0}>
        {buttonLabel(uiLang, "previous")}
      </button>
      <button onClick={() => onNavigate(index + 1)} disabled={index >= total - 1}>
        {buttonLabel(uiLang, "next")}
      </button>
      <label>
        Jump to index
        <input id="jump-index" type="number" min={0} max={Math.max(0, total - 1)} defaultValue={index} />
      </label>
      <button onClick={jump}>{buttonLabel(uiLang, "go")}</button>
      <span>
        Current index: <strong>{index}</strong> / {Math.max(0, total - 1)}
      </span>
    </div>
  );
}
