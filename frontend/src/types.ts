export type User = {
  id: string;
  name: string;
  email: string;
  is_admin: boolean;
  used_seconds: number;
  preferences?: {onboarding_completed?: boolean; caption_preset?: string; resolution?: 720 | 1080; theme?: "light" | "dark" | "system"};
};
export type Word = { start: number; end: number; word: string };
export type CaptionStyle = {
  preset:
    | "bold"
    | "minimal"
    | "neon"
    | "pop"
    | "boxed"
    | "editorial"
    | "podcast"
    | "documentary"
    | "typewriter"
    | "studio"
    | "mint"
    | "coral"
    | "lavender"
    | "mono"
    | "serif"
    | "headline"
    | "lecture"
    | "cinema"
    | "contrast"
    | "soft";
  enabled: boolean;
  custom_font_id?: string | null;
  font:
    | "DejaVu Sans"
    | "Liberation Sans"
    | "Liberation Serif"
    | "Liberation Mono"
    | "DejaVu Serif"
    | "DejaVu Sans Mono"
    | "Lato"
    | "FreeSans"
    | "FreeSerif"
    | "FreeMono"
    | "Carlito"
    | "Caladea"
    | "Inter"
    | "Poppins"
    | "Montserrat"
    | "Anton"
    | "Bebas Neue"
    | "Oswald"
    | "DM Sans";
  size: number;
  weight: 400 | 700;
  color: string;
  emphasis_color: string;
  stroke: number;
  shadow: number;
  stroke_color?: string;
  background?: boolean;
  background_color?: string;
  letter_spacing?: number;
  placement: "top" | "center" | "bottom";
  animation: "none" | "highlight" | "fade";
};
export type Edits = {
  segments: { start: number; end: number }[];
  captions: CaptionStyle;
  words: Word[];
  reframe: "auto" | "manual" | "fit";
  focus_x: number;
  resolution: 720 | 1080;
  headline: string;
  show_headline?: boolean;
  watermark?: boolean;
  volume?: number;
  brightness?: number;
  contrast?: number;
  saturation?: number;
  flip_horizontal?: boolean;
  speed?: number;
  fade_in?: number;
  fade_out?: number;
  transition?: "none" | "fade" | "dissolve" | "slideleft" | "slideright" | "wipeleft" | "wiperight";
  transition_duration?: number;
  brand_kit_id?: string | null;
  logo_asset_id?: string | null;
};
export type Clip = {
  id: string;
  project_id: string;
  title: string;
  start: number;
  end: number;
  score: number;
  description: string;
  reasons: string[];
  headlines: { text: string; source: string; tone: string }[];
  edits: Edits;
  revision: number;
};
export type Project = {
  id: string;
  name: string;
  status: string;
  progress: number;
  stage: string;
  error: string | null;
  created_at: string;
  media: { duration?: number; width?: number; height?: number };
  config: { clip_count: number; workflow?: "ai" | "manual" };
  analysis: { warnings?: string[]; ranking_method?: string };
  clips?: Clip[];
  transcript?: Word[];
};
export type ExportJob = {
  id: string;
  clip_id: string;
  status: string;
  progress: number;
  error: string | null;
  created_at: string;
};
export type Brand = {
  id: string;
  name: string;
  config: {
    captions: CaptionStyle;
    resolution: 720 | 1080;
    logo_asset_id?: string | null;
  };
};
export const defaultCaption: CaptionStyle = {
  preset: "bold",
  enabled: true,
  font: "DejaVu Sans",
  size: 64,
  weight: 700,
  color: "#FFFFFF",
  emphasis_color: "#4D8DFF",
  stroke: 3,
  shadow: 2,
  placement: "bottom",
  animation: "highlight",
};
export const presets: {
  id: CaptionStyle["preset"];
  name: string;
  desc: string;
  style: Partial<CaptionStyle>;
}[] = [
  {
    id: "bold",
    name: "Bold statement",
    desc: "Confident. Clear. Impossible to miss.",
    style: {
      size: 72,
      weight: 700,
      stroke: 3,
      color: "#FFFFFF",
      emphasis_color: "#4D8DFF",
    },
  },
  {
    id: "minimal",
    name: "Clean minimal",
    desc: "Let the story do the talking.",
    style: {
      font: "Liberation Sans",
      size: 50,
      weight: 400,
      stroke: 1,
      shadow: 1,
      emphasis_color: "#FFFFFF",
    },
  },
  {
    id: "neon",
    name: "Neon blue",
    desc: "A little electric energy.",
    style: {
      color: "#75B5FF",
      emphasis_color: "#FFFFFF",
      stroke: 2,
      shadow: 4,
    },
  },
  {
    id: "pop",
    name: "Creator pop",
    desc: "A bright accent for your best words.",
    style: { size: 70, emphasis_color: "#B7F36B", stroke: 4 },
  },
  {
    id: "boxed",
    name: "In the frame",
    desc: "High contrast. Every background.",
    style: { size: 54, stroke: 0, shadow: 0, emphasis_color: "#8CB9FF", background: true, background_color: "#111827" },
  },
];

export const fontFamilies: CaptionStyle["font"][] = [
  "DejaVu Sans",
  "Liberation Sans",
  "Liberation Serif",
  "Liberation Mono",
  "DejaVu Serif",
  "DejaVu Sans Mono",
  "Lato",
  "FreeSans",
  "FreeSerif",
  "FreeMono",
  "Carlito",
  "Caladea",
];

presets.push(
  {
    id: "editorial",
    name: "Editorial",
    desc: "Caladea with a quiet fade.",
    style: {
      font: "Caladea",
      size: 58,
      color: "#FFFFFF",
      emphasis_color: "#D7E5FF",
      stroke: 1,
      shadow: 1,
      animation: "fade",
      weight: 400,
    },
  },
  {
    id: "podcast",
    name: "Podcast",
    desc: "Lato with word emphasis.",
    style: {
      font: "Lato",
      size: 68,
      color: "#FFFFFF",
      emphasis_color: "#76B6FF",
      stroke: 3,
      shadow: 1,
      animation: "highlight",
      weight: 700,
    },
  },
  {
    id: "documentary",
    name: "Documentary",
    desc: "FreeSerif with steady, readable captions.",
    style: {
      font: "FreeSerif",
      size: 55,
      color: "#F3F0E8",
      emphasis_color: "#FFFFFF",
      stroke: 1,
      shadow: 1,
      animation: "none",
      weight: 400,
    },
  },
  {
    id: "typewriter",
    name: "Typewriter",
    desc: "FreeMono with word emphasis.",
    style: {
      font: "FreeMono",
      size: 52,
      color: "#FFFFFF",
      emphasis_color: "#8CE6D0",
      stroke: 1,
      shadow: 1,
      animation: "highlight",
      weight: 400,
    },
  },
  {
    id: "studio",
    name: "Studio",
    desc: "Carlito with word emphasis.",
    style: {
      font: "Carlito",
      size: 64,
      color: "#FFFFFF",
      emphasis_color: "#5FA0FF",
      stroke: 2,
      shadow: 1,
      animation: "highlight",
      weight: 700,
    },
  },
  {
    id: "mint",
    name: "Fresh mint",
    desc: "FreeSans with word emphasis.",
    style: {
      font: "FreeSans",
      size: 70,
      color: "#FFFFFF",
      emphasis_color: "#79E5C5",
      stroke: 3,
      shadow: 1,
      animation: "highlight",
      weight: 700,
    },
  },
  {
    id: "coral",
    name: "Coral pop",
    desc: "Lato with word emphasis.",
    style: {
      font: "Lato",
      size: 72,
      color: "#FFFFFF",
      emphasis_color: "#FF947D",
      stroke: 3,
      shadow: 1,
      animation: "highlight",
      weight: 700,
    },
  },
  {
    id: "lavender",
    name: "Lavender",
    desc: "DejaVu Sans with a quiet fade.",
    style: {
      font: "DejaVu Sans",
      size: 64,
      color: "#E4DAFF",
      emphasis_color: "#FFFFFF",
      stroke: 2,
      shadow: 1,
      animation: "fade",
      weight: 700,
    },
  },
  {
    id: "mono",
    name: "Mono focus",
    desc: "DejaVu Sans Mono with word emphasis.",
    style: {
      font: "DejaVu Sans Mono",
      size: 54,
      color: "#FFFFFF",
      emphasis_color: "#99C8FF",
      stroke: 2,
      shadow: 1,
      animation: "highlight",
      weight: 400,
    },
  },
  {
    id: "serif",
    name: "Classic serif",
    desc: "DejaVu Serif with a quiet fade.",
    style: {
      font: "DejaVu Serif",
      size: 60,
      color: "#FFFFFF",
      emphasis_color: "#C7DFFF",
      stroke: 2,
      shadow: 1,
      animation: "fade",
      weight: 400,
    },
  },
  {
    id: "headline",
    name: "Big headline",
    desc: "Liberation Sans with steady, readable captions.",
    style: {
      font: "Liberation Sans",
      size: 88,
      color: "#FFFFFF",
      emphasis_color: "#FFFFFF",
      stroke: 4,
      shadow: 1,
      animation: "none",
      weight: 700,
    },
  },
  {
    id: "lecture",
    name: "Lecture notes",
    desc: "Carlito with word emphasis.",
    style: {
      font: "Carlito",
      size: 52,
      color: "#FFFFFF",
      emphasis_color: "#98D3FF",
      stroke: 1,
      shadow: 1,
      animation: "highlight",
      weight: 400,
    },
  },
  {
    id: "cinema",
    name: "Cinema",
    desc: "Caladea with a quiet fade.",
    style: {
      font: "Caladea",
      size: 50,
      color: "#F3F0E8",
      emphasis_color: "#F3F0E8",
      stroke: 1,
      shadow: 1,
      animation: "fade",
      weight: 400,
    },
  },
  {
    id: "contrast",
    name: "High contrast",
    desc: "FreeSans with steady, readable captions.",
    style: {
      font: "FreeSans",
      size: 76,
      color: "#FFFFFF",
      emphasis_color: "#FFFFFF",
      stroke: 6,
      shadow: 1,
      animation: "none",
      weight: 700,
    },
  },
  {
    id: "soft",
    name: "Soft spoken",
    desc: "Lato with a quiet fade.",
    style: {
      font: "Lato",
      size: 54,
      color: "#DCE8F5",
      emphasis_color: "#FFFFFF",
      stroke: 1,
      shadow: 1,
      animation: "fade",
      weight: 400,
    },
  },
);

fontFamilies.push(
  "Inter",
  "Poppins",
  "Montserrat",
  "Anton",
  "Bebas Neue",
  "Oswald",
  "DM Sans",
);
