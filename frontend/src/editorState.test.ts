import { describe, it, expect } from "vitest";
import { activeWord, splitAt, totalDuration } from "./editorState";
import { defaultCaption, type Edits } from "./types";
const edits: Edits = {
  segments: [{ start: 10, end: 40 }],
  captions: defaultCaption,
  words: [{ word: "hello", start: 10, end: 11 }],
  reframe: "auto",
  focus_x: 0.5,
  resolution: 1080,
  headline: "",
};
describe("non-destructive timeline", () => {
  it("splits a segment without changing source duration or mutating history", () => {
    const next = splitAt(edits, 25);
    expect(next.segments).toEqual([
      { start: 10, end: 25 },
      { start: 25, end: 40 },
    ]);
    expect(totalDuration(next)).toBe(30);
    expect(edits.segments).toHaveLength(1);
  });
  it("ignores a split outside a retained segment or at its edge", () => {
    expect(splitAt(edits, 5)).toBe(edits);
    expect(splitAt(edits, 10)).toBe(edits);
  });
  it("uses word timestamps with an exclusive end boundary", () => {
    expect(activeWord(edits, 10.5)?.word).toBe("hello");
    expect(activeWord(edits, 11)).toBeUndefined();
  });
});
