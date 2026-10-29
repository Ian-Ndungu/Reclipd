import {useEffect, useRef} from "react";
import {Download, LoaderCircle, X, Scissors, LockKeyhole} from "lucide-react";
import type {Edits} from "./types";

export function ExportDialog({open, title, edits, quote, busy, error, canRemoveWatermark, onWatermark, onClose, onConfirm}: {
  open: boolean; title: string; edits: Edits;
  quote: {seconds:number; reused:boolean} | null;
  busy: boolean; error: string; canRemoveWatermark: boolean;
  onWatermark: (checked:boolean)=>void; onClose: ()=>void; onConfirm: ()=>void;
}) {
  const dialog=useRef<HTMLDialogElement>(null);
  useEffect(()=>{
    if(open && !dialog.current?.open) dialog.current?.showModal();
    if(!open && dialog.current?.open) dialog.current.close();
  },[open]);
  const cuts=edits.segments;
  const overlap=edits.transition && edits.transition!=="none" && cuts.length>1
    ? Math.min(edits.transition_duration ?? .3, ...cuts.map(s=>(s.end-s.start)/2)) : 0;
  const duration=(cuts.reduce((n,s)=>n+s.end-s.start,0)-overlap*(cuts.length-1))/(edits.speed ?? 1);
  return <dialog ref={dialog} className="export-dialog" aria-labelledby="export-dialog-title"
    onCancel={e=>{e.preventDefault();if(!busy) onClose();}}>
    <header><div><span className="eyebrow">Ready to share</span><h2 id="export-dialog-title">Export your clip</h2></div>
      <button className="icon-button" aria-label="Close export" disabled={busy} onClick={onClose}><X size={20}/></button></header>
    <p className="export-clip-title">{title}</p>
    <dl className="export-details">
      <div><dt>Format</dt><dd>MP4 · vertical 9:16</dd></div>
      <div><dt>Quality</dt><dd>Up to {edits.resolution}p</dd></div>
      <div><dt>Duration</dt><dd>{duration.toFixed(1)} seconds</dd></div>
      <div><dt>Captions</dt><dd>{edits.captions.enabled ? "Enabled" : "Off"}</dd></div>
      <div><dt>Audio</dt><dd>{edits.volume === 0 ? "Muted" : "Source audio, if available"}</dd></div>
      <div><dt>Credit cost</dt><dd>{quote ? quote.reused ? "No charge · reuse existing export" : quote.seconds ? `${(quote.seconds/60).toFixed(3)} minutes` : "No additional charge" : "Calculating…"}</dd></div>
    </dl>
    <section className="watermark-card" data-selected={!canRemoveWatermark || edits.watermark !== false}>
      <label className="watermark-card-control">
        <span className="watermark-card-icon" aria-hidden="true"><Scissors size={20}/></span>
        <span className="watermark-card-copy"><strong>RECLIPD watermark</strong><span>Animated signature · Top left</span></span>
        <input type="checkbox" aria-label="Include RECLIPD watermark"
          checked={!canRemoveWatermark || edits.watermark !== false}
          disabled={busy || !canRemoveWatermark}
          onChange={e=>onWatermark(e.target.checked)}/>
      </label>
      <div className="watermark-card-footer">
        <span className="watermark-card-signature" aria-hidden="true"><Scissors size={13}/> RECLIPD</span>
        <span className="watermark-card-status">{!canRemoveWatermark ? <><LockKeyhole size={12}/> Included on Free</> : edits.watermark === false ? "Clean export" : "Included in export"}</span>
      </div>
      {!canRemoveWatermark && <p className="watermark-card-note">Watermark removal is available with a paid package.</p>}
    </section>
    <p className="fine-print">Quality depends on your source. Your latest edits will be saved before export; you can follow progress in Export history.</p>
    {error && <p role="alert" className="error-box">{error}</p>}
    <footer><button className="button secondary" disabled={busy} onClick={onClose}>Back to editing</button>
      <button className="button primary" disabled={busy || !quote} onClick={onConfirm}>
        {busy ? <LoaderCircle size={16} className="spin"/> : <Download size={16}/>}
        {busy ? "Starting export…" : quote?.reused ? "Open existing export" : "Confirm export"}
      </button></footer>
  </dialog>;
}
