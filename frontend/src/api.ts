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

export async function uploadProject<T>(
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
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable)
        onProgress(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onload = () => {
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
    xhr.onerror = () =>
      reject(new Error("Upload connection lost. Please retry."));
    xhr.ontimeout = () => reject(new Error("Upload timed out. Please retry."));
    xhr.timeout = 600000;
    xhr.send(body);
  });
}
