export type ProjectDraft = {
  resolution?: 720 | 1080;
  workflow?: "ai" | "manual";
  content_category?: string;
  instructions?: string;
  caption_preset?: string;
  language?: string | null;
  aspect_ratio?: string;
  url?: string;
  source?: string;
  name?: string;
  clip_count?: number;
  min_duration?: number;
  max_duration?: number;
  mode?: string;
};
export function readDraft(): ProjectDraft {
  try {
    return JSON.parse(window.sessionStorage.getItem("reclipd-draft") || "{}") || {};
  } catch {
    return {};
  }
}
export function saveDraft(draft: ProjectDraft) {
  try {
    window.sessionStorage.setItem("reclipd-draft", JSON.stringify(draft));
  } catch {}
}
export function clearDraft() {
  try {
    window.sessionStorage.removeItem("reclipd-draft");
  } catch {}
}
