// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { legacyUploadProject as uploadProject } from "./api";
afterEach(() => vi.unstubAllGlobals());
function setup(status: number, responseText: string, maxBytes = 100) {
  vi.stubGlobal("fetch", vi.fn(async () => ({ok: true, json: async () => ({max_bytes: maxBytes})})));
  const send = vi.fn();
  vi.stubGlobal("XMLHttpRequest", class {
    status = status;
    responseText = responseText;
    upload = {};
    onload = () => {};
    open() {}
    send() { send(); this.onload(); }
  });
  const body = new FormData();
  body.set("file", new File(["video"], "test.mp4"));
  return { body, send };
}
it.each([
  [413, "<html>too large</html>", "exceeds the server upload limit"],
  [502, "<html>bad gateway</html>", "temporarily unavailable (502)"],
  [201, "<html>index</html>", "could not be confirmed"],
  [201, "null", "could not be confirmed"],
  [422, '{"detail":"File is empty"}', "File is empty"],
])("handles status %s without hiding the cause", async (status, text, message) => {
  const {body} = setup(status, text);
  await expect(uploadProject(body, vi.fn())).rejects.toThrow(message);
});
it("rejects oversized files before sending media", async () => {
  const {body, send} = setup(201, '{"id":"p"}', 1);
  await expect(uploadProject(body, vi.fn())).rejects.toThrow("upload limit");
  expect(send).not.toHaveBeenCalled();
});
it("accepts a real project response", async () => {
  const {body} = setup(201, '{"id":"p"}');
  await expect(uploadProject(body, vi.fn())).resolves.toEqual({id:"p"});
});

it("allows progressing uploads beyond ten minutes, but aborts stalled transfers", async () => {
  vi.useFakeTimers();
  try {
    const { body } = setup(201, '{"id":"p"}');
    let xhr: any;
    vi.stubGlobal("XMLHttpRequest", class {
      upload: any = {};
      status = 201;
      responseText = '{"id":"p"}';
      timeout = -1;
      abort = vi.fn();
      constructor() { xhr = this; }
      open() {}
      send() {}
    });
    const pending = uploadProject(body, vi.fn());
    const rejected = expect(pending).rejects.toThrow("stalled for five minutes");
    await vi.advanceTimersByTimeAsync(0);
    expect(xhr.timeout).toBe(0);
    for (let i = 0; i < 6; i++) {
      await vi.advanceTimersByTimeAsync(120000);
      xhr.upload.onprogress({lengthComputable:true, loaded:i+1, total:10});
    }
    expect(xhr.abort).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(300000);
    await rejected;
    expect(xhr.abort).toHaveBeenCalledOnce();
  } finally {
    vi.useRealTimers();
  }
});

it("clears the stall timer after a confirmed upload", async () => {
  vi.useFakeTimers();
  try {
    const {body} = setup(201, '{"id":"p"}');
    await expect(uploadProject(body, vi.fn())).resolves.toEqual({id:"p"});
    expect(vi.getTimerCount()).toBe(0);
  } finally {
    vi.useRealTimers();
  }
});
