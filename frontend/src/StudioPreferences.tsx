import {api,json} from "./api";
import { useState } from "react";
import { presets } from "./types";
export type StudioDefaults = { caption_preset: string; resolution: 720 | 1080 };
const defaults: StudioDefaults = { caption_preset: "bold", resolution: 1080 };
export function readStudioDefaults(userId?: string): StudioDefaults {
  try {
    const data = JSON.parse(
      window.localStorage.getItem(`reclipd-defaults:${userId || "guest"}`) ||
        "{}",
    );
    return {
      caption_preset: presets.some((p) => p.id === data.caption_preset)
        ? data.caption_preset
        : "bold",
      resolution: data.resolution === 720 ? 720 : 1080,
    };
  } catch {
    return { ...defaults };
  }
}
export function StudioPreferences({ userId, synced=false, onSaved }: { userId?: string; synced?: boolean; onSaved?: ()=>Promise<void> }) {
  const [value, setValue] = useState(() => readStudioDefaults(userId));
  const [message, setMessage] = useState("");
  const [saving,setSaving]=useState(false);
  async function save(next: StudioDefaults) {
    setSaving(true);
    try {
      if(synced) await api("/me/preferences",{method:"PUT",body:json(next)});
      window.localStorage.setItem(
        `reclipd-defaults:${userId || "guest"}`,
        JSON.stringify(next),
      );
      setValue(next);
      setMessage(synced ? "Preferences saved to your account." : "Defaults saved for this account in this browser.");
      if(onSaved) await onSaved();
    } catch(e) {
      setMessage((e as Error).message || "Preferences could not be saved.");
    } finally {setSaving(false);}
  }
  return (
    <section className="panel settings-section">
      <h2>New project defaults</h2>
      <p className="muted">
        Start with your preferred captions and export quality. Existing projects
        stay unchanged.
      </p>
      <div className="form-grid">
        <label>
          Default caption style
          <select disabled={saving}
            value={value.caption_preset}
            onChange={(e) => save({ ...value, caption_preset: e.target.value })}
          >
            {presets.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Default export resolution
          <select disabled={saving}
            value={value.resolution}
            onChange={(e) =>
              save({
                ...value,
                resolution: Number(e.target.value) as 720 | 1080,
              })
            }
          >
            <option value={1080}>1080p · highest available quality</option>
            <option value={720}>720p · smaller files</option>
          </select>
        </label>
      </div>
      <p className="fine-print">
        Resolution depends on source quality. {synced ? "Preferences sync to your account across devices." : "Preferences are saved in this browser."} Manual projects start with captions off.
      </p>
      <button
        type="button" disabled={saving}
        className="button secondary"
        onClick={() => save({ ...defaults })}
      >
        Reset project defaults
      </button>
      <p role="status">{message}</p>
    </section>
  );
}
