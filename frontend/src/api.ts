export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch("/api" + path, {
    ...options,
    credentials: "include",
    headers:
      options.body instanceof FormData
        ? options.headers
        : { "Content-Type": "application/json", ...options.headers },
  });
  if (!response.ok) {
    let message = "Something went wrong. Please try again.";
    try {
      const data = await response.json();
      message =
        typeof data.detail === "string"
          ? data.detail
          : JSON.stringify(data.detail);
    } catch {
      message = `Request failed (${response.status})`;
    }
    throw new Error(message);
  }
  return response.json();
}
export const json = (value: unknown) => JSON.stringify(value);
export const time = (seconds: number = 0) =>
  `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, "0")}`;

export async function legacyUploadProject<T>(
  body: FormData,
  onProgress: (percent: number) => void,
): Promise<T> {
  const limits = await api<{ max_bytes: number }>("/upload-limits");
  const file = body.get("file");
  if (file instanceof Blob && file.size > limits.max_bytes)
    throw new Error(`This file exceeds the ${Math.round(limits.max_bytes / 1024 / 1024)} MB upload limit. Choose a smaller file.`);
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/projects/upload");
    xhr.withCredentials = true;
    // Allow slow transfers; stop only when no progress arrives for five minutes.
    let idleTimer: ReturnType<typeof setTimeout>;
    const refreshDeadline = () => {
      clearTimeout(idleTimer);
      idleTimer = setTimeout(() => {
        reject(new Error("Upload stalled for five minutes. Check your connection and your projects before retrying."));
        xhr.abort();
      }, 300000);
    };
    xhr.onloadend = () => clearTimeout(idleTimer);
    xhr.upload.onload = refreshDeadline;
    xhr.upload.onprogress = (e) => {
      refreshDeadline();
      if (e.lengthComputable)
        onProgress(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onload = () => {
      clearTimeout(idleTimer);
      let data;
      try {
        data = JSON.parse(xhr.responseText);
      } catch {
        data = null;
      }
      const fallback = xhr.status === 413
        ? "This file exceeds the server upload limit. Choose a smaller file."
        : xhr.status === 401
          ? "Your session expired. Please sign in and upload again."
          : [502, 503, 504].includes(xhr.status)
            ? `The upload service is temporarily unavailable (${xhr.status}). Check your projects before retrying.`
            : `Upload could not be confirmed (${xhr.status}). Check your projects before retrying.`;
      if (xhr.status >= 200 && xhr.status < 300 && data && typeof data.id === "string") resolve(data);
      else
        reject(
          new Error(
            typeof data?.detail === "string"
              ? data.detail
              : fallback,
          ),
        );
    };
    xhr.onerror = () => {
      clearTimeout(idleTimer);
      reject(new Error("Upload connection lost. Check your projects before retrying."));
    };
    xhr.onabort = () => {
      clearTimeout(idleTimer);
      reject(new Error("Upload cancelled. Check your projects before retrying."));
    };
    xhr.ontimeout = () => reject(new Error("Upload timed out. Please retry."));
    xhr.timeout = 0;
    refreshDeadline();
    xhr.send(body);
  });
}

type UploadState = { id: string; offset: number; chunk_size: number; project_id?: string };

export async function uploadProject<T>(body: FormData, onProgress: (percent: number) => void): Promise<T> {
  const file = body.get("file");
  if (!(file instanceof File)) throw new Error("Select a video file.");
  const limits = await api<{max_bytes: number}>("/upload-limits");
  if (file.size > limits.max_bytes) throw new Error("This file exceeds the upload limit.");
  // Hash bounded samples, not a multi-gigabyte buffer, to find this browser's saved transfer.
  const sample = new Blob([file.name, String(file.size), String(file.lastModified),
    file.slice(0, 1024 * 1024), file.slice(-1024 * 1024)]);
  const digest = await crypto.subtle.digest("SHA-256", await sample.arrayBuffer());
  const fingerprint = Array.from(new Uint8Array(digest), b => b.toString(16).padStart(2, "0")).join("");
  let state = await api<UploadState>("/uploads", {method:"POST", body:json({
    name: body.get("name"), filename: file.name, size: file.size, fingerprint,
    rights_confirmed: body.get("rights_confirmed") === "true",
    config: JSON.parse(String(body.get("config") || "{}")),
  })});
  onProgress(Math.min(99, Math.floor(state.offset / file.size * 100)));
  let failures = 0;
  while (state.offset < file.size) {
    const offset = state.offset;
    try {
      state = await sendChunk(state.id, offset, file.slice(offset, offset + state.chunk_size),
        loaded => onProgress(Math.min(99, Math.floor((offset + loaded) / file.size * 100))));
      failures = 0;
    } catch (error) {
      if (error instanceof UploadError && error.permanent) throw error;
      if (++failures > 5) throw new Error("Upload paused after connection failures. Select the same file with the same options and retry to resume. Saved progress is kept for 24 hours.");
      await new Promise(resolve => setTimeout(resolve, Math.min(1000 * 2 ** failures, 15000)));
      state = await api<UploadState>("/uploads/" + state.id).catch(() => state);
    }
    onProgress(Math.min(99, Math.floor(state.offset / file.size * 100)));
  }
  onProgress(100);
  // Completion uses the session ID as the project ID, so repeating it cannot create duplicates.
  for (let attempt = 0; ; attempt++) {
    try {
      return await api<T>("/uploads/" + state.id + "/complete", {method:"POST"});
    } catch (error) {
      if (attempt >= 2) throw new Error("Upload saved, but project creation could not be confirmed. Check your projects before retrying.");
      await new Promise(resolve => setTimeout(resolve, 2000));
    }
  }
}

class UploadError extends Error {
  constructor(message: string, public permanent = false) { super(message); }
}

function sendChunk(id: string, offset: number, blob: Blob, progress: (loaded: number) => void): Promise<UploadState> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", "/api/uploads/" + id + "/" + offset);
    xhr.withCredentials = true;
    xhr.timeout = 300000;
    xhr.upload.onprogress = event => progress(Math.min(blob.size, event.loaded));
    xhr.onload = () => {
      let data;
      try { data = JSON.parse(xhr.responseText); } catch { data = null; }
      if (xhr.status >= 200 && xhr.status < 300 && data && Number.isInteger(data.offset)) resolve(data);
      else reject(new UploadError(data?.detail || "Chunk could not be saved.",
        [401, 403, 404, 410, 413, 415, 422].includes(xhr.status)));
    };
    xhr.onerror = xhr.ontimeout = () => reject(new UploadError("Upload connection interrupted."));
    const chunk = new FormData();
    chunk.set("file", blob, "chunk");
    xhr.send(chunk);
  });
}
