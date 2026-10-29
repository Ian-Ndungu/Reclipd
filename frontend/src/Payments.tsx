import {useEffect, useRef, useState} from "react";
import {api,json} from "./api";
type Payment={reference:string;provider?:string;amount:number;currency:string;minutes:number;status:string;created_at:string};
type Billing={enabled:boolean;paypal_enabled?:boolean;mode:string;packs:{id:string;name:string;amount_usd:number;minutes:number;bonus_minutes?:number;bonus_purchases?:number}[];payments:Payment[]};
export function Payments({unlimited,onVerified}:{unlimited:boolean;onVerified:()=>void}) {
  const [data,setData]=useState<Billing|null>(null);
  const [message,setMessage]=useState("");
  const [busy,setBusy]=useState(false);
  const started=useRef(false);
  const load=()=>api<Billing>("/billing").then(setData);
  async function verify(reference:string,provider="paystack") {
    setBusy(true);setMessage(`Checking payment with ${provider==="paypal"?"PayPal":"Paystack"}…`);
    try {
      const p=await api<Payment>(`/billing/${provider==="paypal"?"paypal/":""}verify/${encodeURIComponent(reference)}`,{method:"POST"});
      setMessage(p.status==="success"?"Sandbox payment verified. Test processing minutes credited.":`Payment is ${p.status}. No new credits added.`);
      await load();onVerified();
    }catch(e){setMessage((e as Error).message);}finally{setBusy(false);}
  }
  useEffect(()=>{
    load().catch(e=>setMessage(e.message));
    if(started.current)return;
    started.current=true;
    const params=new URLSearchParams(window.location.search);
    const ref=params.get("paypal_reference")||params.get("reference");
    if(ref){
      void verify(ref,params.has("paypal_reference")?"paypal":"paystack");
      window.history.replaceState(null,"",window.location.pathname);
    } else if(params.has("paypal_cancelled")){
      setMessage("PayPal checkout cancelled. No credits have been added.");
      window.history.replaceState(null,"",window.location.pathname);
    }
  },[]);
  return <section className="panel" style={{padding:28,marginBottom:24}}>
    <span className="eyebrow">PAYMENTS · SANDBOX</span><h2>Processing minute packs</h2>
    <p>One-time packages in USD. Minutes expire 365 days after purchase. Sandbox purchases use test money; live payments remain disabled.</p>
    <p role="status">{message}</p>
    {!data?<p>Loading payment options…</p>:<>
      {!data.enabled&&!data.paypal_enabled&&<p className="notice">Checkout is not configured yet. PayPal sandbox credentials are needed to test a purchase.</p>}
      {unlimited&&<p>Your unlimited account does not need extra minutes.</p>}
      <div className="billing-overview">{data.packs?.map(pack=><article className="panel" key={pack.id}>
        <h3>{pack.name}</h3><p>{pack.minutes} minutes · ${pack.amount_usd.toLocaleString()} USD</p>
        {pack.bonus_minutes&&<p>+{pack.bonus_minutes} bonus minutes on each of your first {pack.bonus_purchases} successful Creator purchases.</p>}
        <button className="button primary" disabled={(!data.enabled&&!data.paypal_enabled)||busy||unlimited} onClick={async()=>{
          setBusy(true);setMessage("Opening sandbox checkout…");
          try{
            const result=await api<{authorization_url?:string;reference:string;needs_verification?:boolean}>(data.paypal_enabled?"/billing/paypal/checkout":"/billing/checkout",{method:"POST",body:json({pack_id:pack.id})});
            if(result.needs_verification)await verify(result.reference,"paypal");
            else if(result.authorization_url)window.location.assign(result.authorization_url);
            else throw new Error("Checkout could not be opened. Check payment history before retrying.");
          }catch(e){setMessage((e as Error).message);setBusy(false);}
        }}>{data.paypal_enabled?"PayPal · test checkout":data.enabled?"Test checkout":"Checkout unavailable"}</button>
      </article>)}</div>
      <h3>Payment history</h3>
      {!data.payments?.length?<p>No test payments yet.</p>:data.payments.map(p=><article key={p.reference} style={{padding:"16px 0",borderBottom:"1px solid var(--border)"}}>
        <strong>{p.currency} {p.amount.toLocaleString()} · {p.minutes} minutes</strong>
        <p>{new Date(p.created_at).toLocaleString()} · {p.status} · {p.provider==="paypal"?"PayPal":"Paystack"} sandbox</p>
        <small>Reference: {p.reference}</small>
        {p.status==="pending"&&<button className="button secondary" disabled={busy} onClick={()=>void verify(p.reference,p.provider)}>Check payment</button>}
      </article>)}
    </>}
  </section>;
}
