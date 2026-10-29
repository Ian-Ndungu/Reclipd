// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { uploadProject } from "./api";
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); vi.useRealTimers(); });

it("resumes from a saved offset and retries a lost response without resending saved bytes", async () => {
  vi.useFakeTimers();
  vi.stubGlobal("crypto", {subtle:{digest:async () => new Uint8Array(32).buffer}});
  Object.defineProperty(Blob.prototype, "arrayBuffer", {configurable:true, value:async () => new ArrayBuffer(0)});
  const paths: string[] = [];
  let checks = 0;
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    paths.push(url);
    const data = url.endsWith("upload-limits") ? {max_bytes:100}
      : url.endsWith("/complete") ? {id:"project"}
      : {id:"session", offset:checks++ === 0 ? 4 : 8, chunk_size:4};
    return {ok:true, json:async () => data};
  }));
  const sent: string[] = [];
  vi.stubGlobal("XMLHttpRequest", class {
    upload = {};
    onerror = () => {};
    onload = () => {};
    status = 200;
    responseText = '{"id":"session","offset":10,"chunk_size":4}';
    open(_method: string, url: string) { sent.push(url); }
    send() { if(sent.length === 1) this.onerror(); else this.onload(); }
  });
  const body = new FormData();
  body.set("file", new File(["0123456789"], "test.mp4"));
  body.set("name","Test");
  body.set("rights_confirmed","true");
  const progress = vi.fn();
  const promise = uploadProject(body, progress);
  await vi.runAllTimersAsync();
  await expect(promise).resolves.toEqual({id:"project"});
  expect(sent).toEqual(["/api/uploads/session/4", "/api/uploads/session/8"]);
  expect(paths).toContain("/api/uploads/session");
  expect(progress).toHaveBeenLastCalledWith(100);
});
