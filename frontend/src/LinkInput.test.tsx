// @vitest-environment jsdom
import { it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, waitFor } from "@testing-library/react";
import { LinkInput } from "./LinkInput";
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
it("keeps metadata-only YouTube links unavailable and offers source upload", async () => {
  const ready = vi.fn();
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok: true,
      json: async () => ({
        kind: "youtube",
        video_id: "abcdefghijk",
        title: "Interview",
        channel: "Channel",
        duration: 60,
        thumbnail: null,
        available: false,
        message: "Authorized source required",
        metadata_error: null,
      }),
    })),
  );
  render(
    <LinkInput
      url="https://youtu.be/abcdefghijk"
      source=""
      onUrl={vi.fn()}
      onSource={vi.fn()}
      onReady={ready}
      onUpload={vi.fn()}
    />,
  );
  expect(
    await screen.findByText("Interview", {}, { timeout: 2000 }),
  ).toBeTruthy();
  expect(screen.getByText("Authorized source required")).toBeTruthy();
  expect(
    screen.getByRole("button", { name: "Upload authorized source file" }),
  ).toBeTruthy();
  expect(ready).not.toHaveBeenCalledWith(true);
});
it("enables a checked source and invalidates it when the URL changes", async () => {
  const ready = vi.fn(),
    onUrl = vi.fn(),
    onSource = vi.fn(),
    onUpload = vi.fn();
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok: true,
      json: async () => ({
        kind: "direct",
        available: true,
        message: "Approved source is reachable",
      }),
    })),
  );
  const { rerender } = render(
    <LinkInput
      url="https://media.example.test/a.mp4"
      source=""
      onUrl={onUrl}
      onSource={onSource}
      onReady={ready}
      onUpload={onUpload}
    />,
  );
  await waitFor(() => expect(ready).toHaveBeenCalledWith(true), {
    timeout: 2000,
  });
  ready.mockClear();
  rerender(
    <LinkInput
      url="https://media.example.test/b.mp4"
      source=""
      onUrl={onUrl}
      onSource={onSource}
      onReady={ready}
      onUpload={onUpload}
    />,
  );
  expect(ready).toHaveBeenLastCalledWith(false);
});
