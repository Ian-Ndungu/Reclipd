import {useEffect,useState} from 'react';
import {Link} from 'react-router-dom';
import {api} from './api';
export type CreditUsage={plan:string;unlimited:boolean;used_seconds:number;available_seconds:number|null;trial_seconds:number;free_seconds:number;paid_seconds:number;trial_expires_at:string;next_refresh_at:string;eligible:boolean;processing_history:{project_id:string;name:string;seconds:number;status:string;created_at:string}[];paid_grants:{remaining_seconds:number;expires_at:string}[]};
const minutes=(s:number)=>Math.floor(Math.max(0,s||0)/60).toLocaleString();
export function CreditOverview({usage}:{usage:CreditUsage}) {
 const [now,setNow]=useState(Date.now());
 useEffect(()=>{const timer=setInterval(()=>setNow(Date.now()),1000);return()=>clearInterval(timer);},[]);
 const remaining=Math.max(0,new Date(usage.trial_expires_at).getTime()-now);
 const countdown=`${Math.floor(remaining/86400000)}d ${Math.floor(remaining/3600000)%24}h ${Math.floor(remaining/60000)%60}m`;
 const date=(s:string)=>new Date(s).toLocaleString();
 return <>
  <div className="credit-grid">
   <article className="panel"><span className="eyebrow">AVAILABLE NOW</span><h2>{usage.unlimited?'Unlimited':minutes(usage.available_seconds||0)}</h2><p>{usage.unlimited?'Your account exemption remains active.':'Processing minutes across unexpired balances'}</p></article>
   <article className="panel"><span className="eyebrow">7-DAY TRIAL</span><h2>{minutes(usage.trial_seconds)} <small>min</small></h2><p>{remaining>0 && usage.eligible?`Expires in ${countdown}`:'Trial ended or unavailable'}</p><small>90 minutes · No card required · No rollover</small></article>
   <article className="panel"><span className="eyebrow">FREE FOREVER · $0</span><h2>{minutes(usage.free_seconds)} <small>min</small></h2><p>60 minutes each month after your trial</p><small>Next refresh: {date(usage.next_refresh_at)} · No rollover</small></article>
   <article className="panel"><span className="eyebrow">PURCHASED MINUTES</span><h2>{minutes(usage.paid_seconds)} <small>min</small></h2><p>Each purchase expires after 365 days.</p>{usage.paid_grants?.map((g,i)=><small key={i} style={{display:'block'}}>{minutes(g.remaining_seconds)} min · expires {date(g.expires_at)}</small>)}</article>
  </div>
 </>;
}
export function DashboardCredits(){
 const [usage,setUsage]=useState<CreditUsage|null>(null);
 useEffect(()=>{const load=()=>api<CreditUsage>('/usage').then(setUsage).catch(()=>{});void load();const timer=setInterval(()=>void load(),60000);return()=>clearInterval(timer);},[]);
 return usage && typeof usage.trial_seconds==='number'?<section><CreditOverview usage={usage}/><Link to="/studio/billing">View usage history and minute packs →</Link></section>:null;
}
