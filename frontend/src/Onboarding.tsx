import {useState} from "react";
import {useNavigate} from "react-router-dom";
import {Scissors, WandSparkles, Captions, Download, ArrowRight} from "lucide-react";
import {api,json} from "./api";
import {readDraft,saveDraft} from "./draft";

export function Onboarding({onComplete}:{onComplete:()=>Promise<void>}) {
  const navigate=useNavigate();
  const [step,setStep]=useState(0),[workflow,setWorkflow]=useState<"ai"|"manual">(readDraft().workflow || "ai");
  const [busy,setBusy]=useState(false),[error,setError]=useState("");
  async function finish(skip=false) {
    setBusy(true);setError("");
    try {
      await api("/me/preferences",{method:"PUT",body:json({onboarding_completed:true})});
      if(!skip) saveDraft({...readDraft(),workflow,...(workflow==="manual"?{mode:"upload"}:{})});
      await onComplete();navigate(skip?"/studio":"/studio/new",{replace:true});
    } catch(e){setError((e as Error).message);} finally{setBusy(false);}
  }
  return <section className="onboarding">
    <div className="onboarding-heading"><span className="eyebrow">Welcome to RECLIPD</span><p>Step {step+1} of 2</p></div>
    <div className="onboarding-progress" aria-hidden="true"><span style={{width:step?"100%":"50%"}}/></div>
    <h1>{step===0?"Your next great clip starts here.":"Make it yours. Then share it."}</h1>
    <p>{step===0?"Choose how you want to create. You can switch workflows for every project.":"Review your footage, refine your style, and export when you’re ready."}</p>
    {step===0?<fieldset className="onboarding-options"><legend>How would you like to start?</legend>
      {([["ai","Find highlights with AI","Upload a video or import a supported link. Set your instructions and let RECLIPD suggest clips.",WandSparkles],
        ["manual","Edit a video yourself","Upload your footage and choose your own cuts, speed, filters, and transitions.",Scissors]] as const).map(([value,title,description,Icon])=>
        <label key={value} className={workflow===value?"selected":""}><input type="radio" name="workflow" value={value} checked={workflow===value} onChange={()=>setWorkflow(value)}/><Icon aria-hidden="true"/><strong>{title}</strong><span>{description}</span></label>)}
    </fieldset>:<div className="onboarding-options">
      <article><Scissors aria-hidden="true"/><h2>Review your cuts</h2><p>Preview and trim clips in the editor. AI suggestions are a starting point; you stay in control.</p></article>
      <article><Captions aria-hidden="true"/><h2>Set your style</h2><p>Customize available captions, fonts, colors, and framing. Save a brand kit for a consistent look.</p></article>
      <article><Download aria-hidden="true"/><h2>Export with confidence</h2><p>Review quality, credit cost, and watermark settings before exporting your MP4.</p></article>
    </div>}
    <aside>New eligible accounts receive 90 trial processing minutes for 7 days, then 60 free minutes monthly. No card required. Check Billing for your actual balance. Only import footage you own or have permission to use; source availability varies.</aside>
    {error&&<p role="alert" className="field-error">{error}</p>}
    <footer><button disabled={busy} onClick={()=>finish(true)}>Skip introduction</button><div>{step>0&&<button disabled={busy} onClick={()=>setStep(0)}>Back</button>}
      <button className="primary" disabled={busy} onClick={()=>step===0?setStep(1):finish()}>{busy?"Saving…":step===0?"Continue":"Create my first project"}<ArrowRight size={18}/></button></div></footer>
  </section>;
}
