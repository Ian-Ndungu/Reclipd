// @vitest-environment jsdom
import { it, expect, afterEach, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { CaptionGallery } from "./StyleStudio";
import { StudioPreferences, readStudioDefaults } from "./StudioPreferences";
beforeEach(() => {
  for (const key of ["localStorage", "sessionStorage"]) {
    const data = new Map<string, string>();
    vi.stubGlobal(key, {
      getItem: (k: string) => data.get(k) ?? null,
      setItem: (k: string, v: string) => data.set(k, v),
      removeItem: (k: string) => data.delete(k),
      clear: () => data.clear(),
    });
  }
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});
it("filters caption previews and carries the preset into the project draft", () => {
  render(
    <MemoryRouter>
      <CaptionGallery />
    </MemoryRouter>,
  );
  fireEvent.change(screen.getByLabelText("Search styles or fonts"), {
    target: { value: "In the frame" },
  });
  expect(screen.getByRole("status").textContent).toBe("1 styles found");
  fireEvent.click(screen.getByRole("button", { name: "Use for new AI clips" }));
  expect(
    JSON.parse(window.sessionStorage.getItem("reclipd-draft")!).caption_preset,
  ).toBe("boxed");
});
it("stores defaults per account and rejects invalid stored values", () => {
  render(<StudioPreferences userId="one" />);
  fireEvent.change(screen.getByLabelText("Default export resolution"), {
    target: { value: "720" },
  });
  expect(readStudioDefaults("one").resolution).toBe(720);
  expect(readStudioDefaults("two").resolution).toBe(1080);
  window.localStorage.setItem(
    "reclipd-defaults:two",
    JSON.stringify({ resolution: 9999, caption_preset: "fake" }),
  );
  expect(readStudioDefaults("two")).toEqual({
    resolution: 1080,
    caption_preset: "bold",
  });
});
