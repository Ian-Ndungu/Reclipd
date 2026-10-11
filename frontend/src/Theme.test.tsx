// @vitest-environment jsdom
import { it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { ThemeProvider, ThemeSelect } from "./Theme";
beforeEach(() => {
  const data = new Map<string, string>();
  vi.stubGlobal("localStorage", {
    getItem: (k: string) => data.get(k) ?? null,
    setItem: (k: string, v: string) => data.set(k, v),
    clear: () => data.clear(),
    removeItem: (k: string) => data.delete(k),
  });
});
afterEach(() => {
  cleanup();
  window.localStorage.clear();
  vi.unstubAllGlobals();
});
it("defaults to light and persists dark across remounts", () => {
  window.localStorage.clear();
  const view = render(
    <ThemeProvider>
      <ThemeSelect />
    </ThemeProvider>,
  );
  expect(document.documentElement.dataset.theme).toBe("light");
  fireEvent.change(screen.getByLabelText("Appearance"), {
    target: { value: "dark" },
  });
  expect(document.documentElement.dataset.theme).toBe("dark");
  expect(window.localStorage.getItem("reclipd-theme")).toBe("dark");
  view.unmount();
  render(
    <ThemeProvider>
      <ThemeSelect />
    </ThemeProvider>,
  );
  expect((screen.getByLabelText("Appearance") as HTMLSelectElement).value).toBe(
    "dark",
  );
});
it("follows system changes only while System is selected", () => {
  let callback = () => {};
  const media = {
    matches: true,
    addEventListener: vi.fn((_name, cb) => (callback = cb)),
    removeEventListener: vi.fn(),
  };
  vi.stubGlobal("matchMedia", () => media);
  render(
    <ThemeProvider>
      <ThemeSelect />
    </ThemeProvider>,
  );
  fireEvent.change(screen.getByLabelText("Appearance"), {
    target: { value: "system" },
  });
  expect(document.documentElement.dataset.theme).toBe("dark");
  media.matches = false;
  callback();
  expect(document.documentElement.dataset.theme).toBe("light");
  fireEvent.change(screen.getByLabelText("Appearance"), {
    target: { value: "dark" },
  });
  callback();
  expect(document.documentElement.dataset.theme).toBe("dark");
});
