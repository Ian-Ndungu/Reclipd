// @vitest-environment jsdom
import { it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { Editor } from "./Editor";
import { defaultCaption } from "./types";
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});
it("plays short proxies and maps split playback back to source timestamps", async () => {
  const play = vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue();
  vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => {});
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => ({
      ok: true,
      json: async () =>
        url.includes("/clips/")
          ? {
              clip: {
                id: "c",
                title: "Test clip",
                revision: 0,
                headlines: [],
                edits: {
                  segments: [
                    { start: 100, end: 110 },
                    { start: 200, end: 210 },
                  ],
                  captions: defaultCaption,
                  words: [],
                  reframe: "auto",
                  focus_x: 0.5,
                  resolution: 1080,
                  headline: "",
                },
              },
              project: { id: "p", media: { duration: 300 } },
            }
          : [],
    })),
  );
  const { container } = render(
    <MemoryRouter initialEntries={["/studio/clips/c"]}>
      <Routes>
        <Route path="/studio/clips/:id" element={<Editor />} />
      </Routes>
    </MemoryRouter>,
  );
  await screen.findByText("Test clip");
  const fonts = screen.getByLabelText("Font family") as HTMLSelectElement;
  expect(fonts.options.length).toBe(19);
  fireEvent.click(screen.getByRole("button", { name: /Editorial/ }));
  expect(fonts.value).toBe("Caladea");
  const video = container.querySelector("video")!;
  expect(video.getAttribute("src")).toContain("start=100&end=110");
  fireEvent.loadedMetadata(video);
  expect(video.currentTime).toBe(0);
  fireEvent.click(screen.getByRole("button", { name: "Play" }));
  expect(play).toHaveBeenCalled();
  fireEvent.playing(video);
  video.currentTime = 4;
  fireEvent.timeUpdate(video);
  expect(
    (screen.getByLabelText("Clip playhead") as HTMLInputElement).value,
  ).toBe("4");
  expect((screen.getByLabelText("Clip playhead") as HTMLInputElement).max).toBe("20");
  fireEvent.change(screen.getByLabelText("Clip playhead"), {target: {value: "15"}});
  const second = container.querySelector("video")!;
  expect(second.getAttribute("src")).toContain("start=200&end=210");
  fireEvent.timeUpdate(second); // Loading events must not overwrite the pending seek.
  fireEvent.loadedMetadata(second);
  expect(second.currentTime).toBe(5);
  fireEvent.canPlay(second);
  expect(play.mock.calls.length).toBeGreaterThan(1);
  fireEvent.ended(second);
  expect(screen.getByRole("button", { name: "Play" })).toBeTruthy();
  Object.defineProperty(second, "ended", {value: true});
  fireEvent.click(screen.getByRole("button", {name: "Play"}));
  const firstAgain = container.querySelector("video")!;
  expect(firstAgain.getAttribute("src")).toContain("start=100&end=110");
  fireEvent.loadedMetadata(firstAgain);
  fireEvent.canPlay(firstAgain);
  fireEvent.playing(firstAgain);
  fireEvent.ended(firstAgain);
  const nextCut = container.querySelector("video")!;
  expect(nextCut.getAttribute("src")).toContain("start=200&end=210");
  fireEvent.loadedMetadata(nextCut);
  expect(nextCut.currentTime).toBe(0);
  fireEvent.canPlay(nextCut);
  expect(play.mock.calls.length).toBeGreaterThan(3);

  const cutButton = screen.getByRole("button", {name: "Seek within cut 2"});
  vi.spyOn(cutButton, "getBoundingClientRect").mockReturnValue({left: 0, width: 100} as DOMRect);
  fireEvent.click(cutButton, {clientX: 50, detail: 1});
  fireEvent.loadedMetadata(nextCut);
  expect(nextCut.currentTime).toBe(5);
  expect((container.querySelector(".timeline-playhead") as HTMLElement).style.left).toBe("75%");
  Object.defineProperty(nextCut, "readyState", {value: 4});
  nextCut.currentTime = 5;
  fireEvent.timeUpdate(nextCut);
  nextCut.currentTime = 6; // Split must read the video clock, not a stale UI update.
  fireEvent.click(screen.getByRole("button", {name: "Split at playhead"}));
  expect(screen.getByText("Cut 3")).toBeTruthy();
  expect((screen.getByLabelText("Clip playhead") as HTMLInputElement).value).toBe("16");
  expect(container.querySelector("video")!.getAttribute("src")).toContain("start=206&end=210");
  expect((screen.getByRole("button", {name: "Split at playhead"}) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole("button", {name: "Undo"}));
  expect(screen.queryByText("Cut 3")).toBeNull();
  expect((screen.getByLabelText("Clip playhead") as HTMLInputElement).value).toBe("16");
  fireEvent.click(screen.getByRole("button", {name: "Redo"}));
  expect(screen.getByText("Cut 3")).toBeTruthy();
});
