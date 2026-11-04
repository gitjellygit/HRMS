"use client";
import {useCallback,useEffect,useState} from "react";
import {BarChart3,Bell,ShieldCheck,History,Plug,KeyRound} from "lucide-react";
import FeedbackMotion from "./FeedbackMotion";
type Row=Record<string,any>;
type User={id:number;role:string};
type Tab="notifications"|"security"|"analytics"|"audit"|"integrations";
export default function PlatformWorkspace({api,user}:{api:string;user:User}){
 const hr=["super_admin","admin","hr"].includes(user.role);
 const [tab,setTab]=useState<Tab>("notifications");
 const [busy,setBusy]=useState(false),[error,setError]=useState(""),[notice,setNotice]=useState("");
 const [notifications,setNotifications]=useState<Row[]>([]),[rules,setRules]=useState<Row[]>([]);
 const [preferences,setPreferences]=useState<Row>({email:true,sms:false,whatsapp:false,push:false});
 const [analytics,setAnalytics]=useState<Row|null>(null),[audit,setAudit]=useState<Row[]>([]),
  [integrations,setIntegrations]=useState<Row|null>(null),[mfa,setMfa]=useState<Row>({enabled:false});
 const [setup,setSetup]=useState<Row|null>(null);
 const [password,setPassword]=useState(""),[otp,setOtp]=useState("");
 const [year,setYear]=useState(String(new Date().getFullYear()));
 const call=useCallback(async(path:string,method="GET",body?:unknown)=>{
  const r=await fetch(api+path,{method,credentials:"include",headers:{"Content-Type":"application/json"},
   body:body!==undefined?JSON.stringify(body):undefined});
  const data=await r.json().catch(()=>({}));
  if(!r.ok){
   const d=data.detail;
   throw Error(typeof d==="string"?d:d?.message||(Array.isArray(d)?d.map((x:Row)=>x.msg).join("; "):"Action could not be completed"));
  }
  return data;
 },[api]);
 const load=useCallback(async()=>{
  const entries=[call("/platform/notifications"),call("/platform/notification-preferences"),call("/security/2fa"),
    ...(hr?[call("/platform/analytics?year="+year),call("/platform/audit"),
       call("/platform/notification-rules"),call("/platform/integrations")]:[])];
  const rs=await Promise.allSettled(entries);
  const v=(i:number,otherwise:any)=>rs[i]?.status==="fulfilled"?(rs[i] as PromiseFulfilledResult<any>).value:otherwise;
  setNotifications(v(0,[]));setPreferences(v(1,{email:true,sms:false,push:false,whatsapp:false}));setMfa(v(2,{enabled:false}));
  if(hr){setAnalytics(v(3,null));setAudit(v(4,[]));setRules(v(5,[]));setIntegrations(v(6,null))}
 },[call,year,hr]);
 useEffect(()=>{void load()},[load]);
 async function execute(fn:()=>Promise<unknown>,ok:string){
  setError("");setNotice("");setBusy(true);
  try{await fn();setNotice(ok);await load()}catch(e){setError((e as Error).message)}finally{setBusy(false)}
 }
 return <div className="ops-workspace">
  <div className="ops-heading"><ShieldCheck size={21}/><div><h2>Insights, security & notifications</h2><p>Reporting, audit history, preferences and authenticator security.</p></div></div>
  <nav className="ops-tabs">{([
   ["notifications","Notifications",Bell],["security","Two-factor security",KeyRound],
   ...(hr?[["analytics","Analytics",BarChart3],["audit","Audit trail",History],["integrations","Integrations",Plug]]:[])
   ] as [Tab,string,any][]).map(([id,label,Icon])=><button key={id} className={tab===id?"active":""} onClick={()=>{setTab(id);setError("");setNotice("")}}><Icon size={16}/>{label}</button>)}</nav>
  {error&&<div className="time-form-error" role="alert">{error}</div>}
  {notice&&<FeedbackMotion type="success" compact message={notice}/>}
  {busy&&<FeedbackMotion type="loading" compact message="Updating security and settings…"/>}

  {tab==="notifications"&&<div className="ops-columns">
   <section className="employee-surface"><h3>My notification preferences</h3>
    <p className="muted">Email is available when company SMTP is configured. SMS, WhatsApp and push remain adapter placeholders until providers are connected.</p>
    <div className="ops-form">{(["email","sms","push","whatsapp"] as const).map(k=>
     <label className="ops-check" key={k}><input type="checkbox" checked={Boolean(preferences[k])} onChange={e=>setPreferences(v=>({...v,[k]:e.target.checked}))}/>{k.toUpperCase()}</label>)}
     <button className="employee-primary" disabled={busy} onClick={()=>void execute(()=>call("/platform/notification-preferences","PUT",preferences),"Notification preferences saved.")}>Save preferences</button></div>
    {hr&&<><h3>Notification events</h3><div className="ops-list">{rules.map(r=><div key={r.id}><strong>{r.event}</strong><span>{r.enabled?"Enabled":"Disabled"} · {["email","sms","push","whatsapp"].filter(k=>r[k]).join(", ")}</span></div>)}</div>
      <button className="employee-cancel" disabled={busy} onClick={()=>void execute(()=>call("/platform/notifications/scan","POST"),"Birthday and document-expiry reminders queued.")}>Scan reminders now</button>
      <button className="employee-cancel" disabled={busy} onClick={()=>void execute(()=>call("/platform/notifications/deliver-email","POST"),"Email notification queue processed.")}>Deliver queued email via SMTP</button>
     </>}
   </section><section className="employee-surface"><h3>My notifications</h3><div className="ops-list">{notifications.map(x=><div key={x.id}><strong>{x.subject}</strong><span>{x.message}</span><small>{x.event} · {x.created_at?.slice(0,10)} · {x.status}</small></div>)}{!notifications.length&&<p>No notifications yet.</p>}</div></section>
  </div>}

  {tab==="security"&&<div className="ops-columns"><section className="employee-surface">
   <h3>Authenticator two-factor authentication</h3>
   <p className="muted">Protect password login with a 6-digit code from an authenticator app. Keep recovery access with HR until the recovery-code workflow is available.</p>
   <p>{mfa.enabled?"Two-factor authentication is active.":"Two-factor authentication is not enabled yet."}</p>
   {!mfa.enabled?<><label className="ops-field">Current password<input type="password" autoComplete="current-password" value={password} onChange={e=>setPassword(e.target.value)}/></label>
    <button className="employee-primary" disabled={busy||!password} onClick={()=>void execute(async()=>setSetup(await call("/security/2fa/setup","POST",{current_password:password})),"Authenticator enrollment started.")}>Set up authenticator</button>
    {setup&&<div className="ops-mfa-secret"><strong>Enter this setup key into your authenticator app:</strong><code>{setup.manual_secret}</code><p>Use the generated 6-digit code to activate.</p>
     <label>Authenticator code<input inputMode="numeric" maxLength={6} value={otp} onChange={e=>setOtp(e.target.value)}/></label>
     <button className="employee-primary" disabled={busy||otp.length!==6} onClick={()=>void execute(async()=>{await call("/security/2fa/verify","POST",{code:otp});setSetup(null);setPassword("");setOtp("")},"Two-factor authentication enabled.")}>Verify and enable</button></div>}
   </>:<><label className="ops-field">Current password<input type="password" value={password} onChange={e=>setPassword(e.target.value)}/></label>
    <label className="ops-field">Authenticator code<input inputMode="numeric" maxLength={6} value={otp} onChange={e=>setOtp(e.target.value)}/></label>
    <button className="employee-cancel" disabled={busy||!password||otp.length!==6} onClick={()=>void execute(async()=>{await call("/security/2fa/disable","POST",{current_password:password,code:otp});setPassword("");setOtp("")},"Two-factor authentication disabled.")}>Disable 2FA</button>
   </>}
  </section><section className="employee-surface"><h3>Identity security information</h3>
   <p>When 2FA is enabled, future logins require your email, password and current authenticator code.</p>
   <p>Enterprise SSO is not configured. Connecting Google Workspace, Microsoft Entra or another OIDC provider needs client ID, issuer, tenant verification and a dedicated security review.</p>
   <p>Payroll, ID numbers and personal documents are visible only through authorized accounts. Production requires encrypted storage and a managed secrets service.</p>
  </section></div>}

  {tab==="analytics"&&hr&&<div className="employee-surface"><div className="ops-heading"><h3>HR analytics</h3><label>Year<input type="number" min={2020} max={2100} value={year} onChange={e=>setYear(e.target.value)}/></label></div>
   {analytics?<><div className="ops-metrics">
     {([["Active employees",analytics.headcount],["New joiners",analytics.joiners],["Approved exits",analytics.approved_exits],
       ["Attrition estimate",analytics.attrition_ratio_pct+"%"]] as const).map(([name,value])=>
       <div key={name}><span>{name}</span><strong>{value}</strong></div>)}
    </div>
    <div className="ops-columns">
     <div><h3>Headcount by department</h3><div className="ops-list">{Object.entries(analytics.by_department||{}).map(([key,v])=><div key={key}><strong>{key}</strong><span>{String(v)} employees</span></div>)}</div></div>
     <div><h3>Attendance & leave</h3><div className="ops-list">{Object.entries(analytics.attendance_sessions_by_month||{}).map(([key,v])=><div key={key}><strong>{key}</strong><span>{String(v)} punch sessions</span></div>)}
       {Object.entries(analytics.approved_leaves_by_type||{}).map(([key,v])=><div key={key}><strong>{key}</strong><span>{String(v)} approved leave requests</span></div>)}</div></div>
     <div><h3>Payroll cost trend</h3><div className="ops-list">{Object.entries(analytics.net_payroll_by_month||{}).map(([key,v])=><div key={key}><strong>{key}</strong><span>Net ₹{Number(v).toLocaleString("en-IN")}</span></div>)}</div></div>
    </div><p className="field-help">{analytics.scope_note}</p></>:<p>No HR analytics available.</p>}
  </div>}

  {tab==="audit"&&hr&&<section className="employee-surface"><h3>Audit history</h3>
   <p className="muted">Recent tracked changes, approvals and external-data exports. Read-only.</p>
   <div className="ops-list">{audit.map(a=><div key={a.id}><strong>{a.action}</strong><span>Resource: {a.resource} · Actor #{a.actor_id||"System"}</span><small>{a.created_at} {a.reason&&"· "+a.reason}</small></div>)}{!audit.length&&<p>No audit events recorded.</p>}</div>
  </section>}

  {tab==="integrations"&&hr&&<section className="employee-surface"><h3>Integration readiness</h3>
   <p className="muted">Only the configured adapters can execute external actions. An unconfigured provider is not presented as connected.</p>
   <div className="ops-list">{Object.entries(integrations||{}).map(([k,v])=><div key={k}><strong>{k.toUpperCase()}</strong><span>{(v as Row).mode||"Not configured"}</span><small>{(v as Row).configured?"Configured":"Not connected"}</small></div>)}</div>
  </section>}
 </div>;
}
