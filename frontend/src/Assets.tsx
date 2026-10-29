import { useEffect, useState } from "react";
import { Upload } from "lucide-react";
import { api } from "./api";
import { ErrorBox } from "./App";
export type Asset = {
  id: string;
  kind: "logo" | "font";
  name: string;
  family: string | null;
};
export function AssetUploader({
  onUploaded,
}: { onUploaded?: () => void } = {}) {
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [message, setMessage] = useState("");
  return (
    <form
      className="panel"
      onSubmit={async (e) => {
        e.preventDefault();
        setBusy(true);
        setMessage("");
        setError("");
        const data = new FormData(e.currentTarget);
        try {
          const a = await api<Asset>("/assets", { method: "POST", body: data });
          onUploaded?.();
          setMessage(
            `${a.name} uploaded. It is now available in the clip editor.`,
          );
        } catch (e) {
          setError((e as Error).message);
        } finally {
          setBusy(false);
        }
      }}
    >
      <h3>Bring your own brand</h3>
      <p className="muted">
        Upload a logo or a font you are licensed to embed. Up to 10 MB per
        asset.
      </p>
      <div className="form-grid">
        <label>
          Asset type
          <select name="kind">
            <option value="logo">Logo image (PNG / JPEG / WebP)</option>
            <option value="font">Custom font (TTF / OTF)</option>
          </select>
        </label>
        <label>
          File
          <input
            name="file"
            type="file"
            required
            accept=".png,.jpg,.jpeg,.webp,.ttf,.otf"
          />
        </label>
      </div>
      <label className="checkbox">
        <input name="rights_confirmed" type="checkbox" value="true" required />I
        have permission to use and embed this asset.
      </label>
      <button className="button secondary" disabled={busy}>
        <Upload size={16} />
        {busy ? "Uploading…" : "Upload asset"}
      </button>
      <ErrorBox error={error} />
      <p role="status">{message}</p>
    </form>
  );
}
export function BrandAssetFields({
  logoId,
  fontId,
}: { logoId?: string | null; fontId?: string | null } = {}) {
  const [logo, setLogo] = useState(logoId || ""),
    [font, setFont] = useState(fontId || "");
  const [assets, setAssets] = useState<Asset[]>([]);
  useEffect(() => {
    api<Asset[]>("/assets")
      .then(setAssets)
      .catch(() => {});
  }, []);
  return (
    <>
      <label>
        Logo
        <select
          name="logo_asset_id"
          value={logo}
          onChange={(e) => setLogo(e.target.value)}
        >
          <option value="">No logo</option>
          {assets
            .filter((a) => a.kind === "logo")
            .map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
        </select>
      </label>
      <label>
        Custom font
        <select
          name="custom_font_id"
          value={font}
          onChange={(e) => setFont(e.target.value)}
        >
          <option value="">Use built-in font</option>
          {assets
            .filter((a) => a.kind === "font")
            .map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
        </select>
      </label>
    </>
  );
}
