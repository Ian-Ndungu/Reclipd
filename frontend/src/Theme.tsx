import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
export type Theme = "light" | "dark" | "system";
const ThemeContext = createContext<{
  theme: Theme;
  setTheme: (theme: Theme) => void;
}>({ theme: "light", setTheme: () => {} });
export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(() => {
    try {
      const saved = window.localStorage.getItem("reclipd-theme");
      return saved === "dark" || saved === "system" ? saved : "light";
    } catch {
      return "light";
    }
  });
  useEffect(() => {
    const media = window.matchMedia?.("(prefers-color-scheme: dark)");
    const apply = () => {
      const resolved =
        theme === "system" ? (media?.matches ? "dark" : "light") : theme;
      document.documentElement.dataset.theme = resolved;
      document.documentElement.style.colorScheme = resolved;
    };
    apply();
    try {
      window.localStorage.setItem("reclipd-theme", theme);
    } catch {}
    media?.addEventListener("change", apply);
    return () => media?.removeEventListener("change", apply);
  }, [theme]);
  return (
    <ThemeContext.Provider value={{ theme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}
export const useTheme = () => useContext(ThemeContext);
export function ThemeSelect({onSave}: {onSave?: (theme:Theme)=>Promise<void>} = {}) {
  const [error,setError]=useState("");
  const [saving,setSaving]=useState(false);
  const { theme, setTheme } = useContext(ThemeContext);
  return (
    <label className="theme-control">
      <span>Appearance</span>
      <select
        aria-label="Appearance"
        value={theme}
        disabled={saving}
        onChange={async (e) => {
          const next=e.target.value as Theme;
          setSaving(true); setError("");
          try {if(onSave) await onSave(next); setTheme(next);}
          catch(e){setError((e as Error).message);}
          finally {setSaving(false);}
        }}
      >
        <option value="light">Light</option>
        <option value="dark">Dark</option>
        <option value="system">System</option>
      </select>
      {error && <span role="alert">{error}</span>}
    </label>
  );
}
