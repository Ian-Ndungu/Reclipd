import type { Edits } from "./types";
export function splitAt(edits: Edits, position: number): Edits {
  const index = edits.segments.findIndex(
    (s) => position > s.start + 0.1 && position < s.end - 0.1,
  );
  if (index < 0) return edits;
  const current = edits.segments[index];
  return {
    ...edits,
    segments: [
      ...edits.segments.slice(0, index),
      { start: current.start, end: position },
      { start: position, end: current.end },
      ...edits.segments.slice(index + 1),
    ],
  };
}
export function totalDuration(edits: Edits) {
  return edits.segments.reduce((sum, s) => sum + s.end - s.start, 0);
}
export function activeWord(edits: Edits, position: number) {
  return edits.words.find((w) => position >= w.start && position < w.end);
}
