"use client";
import {useEffect,useState} from "react";
import {ClipboardCheck,Send,LifeBuoy,UserRoundX,BarChart3,Bell,ShieldCheck,FileSignature} from "lucide-react";
import FeedbackMotion from "./FeedbackMotion";
import {explainError} from "./formErrors";
import PeopleOpsExtras from "./PeopleOpsExtras";
import BrandIllustration,{WelcomeAnimation} from "./BrandIllustration";
type Row=Record<string,any>;
type Area="offers"|"onboarding"|"announcements"|"helpdesk"|"exit"|"analytics"|"notifications"|"audit"|"assets";
const areas:[Area,string][]=[["offers","Offer letters"],["onboarding","Onboarding"],["announcements","Announcements"],["helpdesk","Helpdesk"],["exit","Exit management"],
 ["analytics","Analytics"],["notifications","Notifications"],["audit","Audit & security"],["assets","Assets & clearances"]];
const today=()=>new Date().toISOString().slice(0,10);
export default function PeopleOpsWorkspace({api,user}:{api:string;user:{id:number;name:string;role:string}}){
 const hr=["super_admin","admin","hr"].includes(user.role);
 const [tab,setTab]=useState<Area>("announcements");
 const [staff,setStaff]=useState<Row[]>([]);
 const [templates,setTemplates]=useState<Row[]>([]);
 const [offers,setOffers]=useState<Row[]>([]);
 const [tasks,setTasks]=useState<Row[]>([]);
 const [notices,setNotices]=useState<Row[]>([]);
 const [tickets,setTickets]=useState<Row[]>([]);
 const [allTickets,setAllTickets]=useState<Row[]>([]);
 const [exits,setExits]=useState<Row[]>([]);
 const [allExits,setAllExits]=useState<Row[]>([]);
 const [metrics,setMetrics]=useState<Row|null>(null);
 const [rules,setRules]=useState<Row[]>([]);
 const [notifications,setNotifications]=useState<Row[]>([]);
 const [audits,setAudits]=useState<Row[]>([]);
 const [info,setInfo]=useState("");const [error,setError]=useState("");const [busy,setBusy]=useState(false);
 const [draft,setDraft]=useState<Row>({});
 const [selected,setSelected]=useState("");
 const [reply,setReply]=useState("");
 const [exitEmployee,setExitEmployee]=useState("");
 const [exitReason,setExitReason]=useState("");
 const [exitNotice,setExitNotice]=useState("30");
 const [exitTemplates,setExitTemplates]=useState<Row[]>([]);
 const [templateTitle,setTemplateTitle]=useState("");
 const [templateRole,setTemplateRole]=useState("hr");
 const [editingExitTemplate,setEditingExitTemplate]=useState<number|null>(null);
 const [editExitTitle,setEditExitTitle]=useState("");
 const [editExitRole,setEditExitRole]=useState("hr");
 const [exitTasks,setExitTasks]=useState<Record<number,Row[]>>({});
 const [exitTaskNotes,setExitTaskNotes]=useState<Record<number,string>>({});
 async function call(path:string,method="GET",body?:unknown){
  const r=await fetch(api+"/people"+path,{method,credentials:"include",
   headers:{"Content-Type":"application/json"},body:body===undefined?undefined:JSON.stringify(body)});
  const j=await r.json().catch(()=>({}));
  if(!r.ok)throw Error(explainError(j,r.status));
  return j;
 }
 const get=(path:string)=>call(path).catch(()=>[]);
 async function refresh(){
  const [a,b,c,d,e,f,g,h,i,j,k,l]=await Promise.all([
   hr?fetch(api+"/employees",{credentials:"include"}).then(r=>r.ok?r.json():[]):Promise.resolve([]),
   hr?get("/offer-templates"):Promise.resolve([]),get("/offers"),get("/onboarding"),get("/announcements"),
   get("/tickets"),hr?get("/tickets?scope=all"):Promise.resolve([]),get("/exits"),
   hr?get("/exits?scope=all"):Promise.resolve([]),hr?call("/analytics").catch(()=>null):Promise.resolve(null),
   get("/notifications"),hr?get("/audit"):Promise.resolve([])]);
  setStaff(a);setTemplates(b);setOffers(c);setTasks(d);setNotices(e);setTickets(f);setAllTickets(g);setExits(h);
  setAllExits(i);setMetrics(j);setNotifications(k);setAudits(l);
  if(hr)setRules(await get("/notification-rules"));
 }
 useEffect(()=>{void refresh();if(hr)void fetch(api+"/exit-workflow/templates",{credentials:"include"})
  .then(r=>r.ok?r.json():[]).then(setExitTemplates).catch(()=>{})},[api,user.id]);
 async function save(fn:()=>Promise<unknown>,msg:string){
  setBusy(true);setError("");setInfo("");
  try{await fn();setInfo(msg);setDraft({});setSelected("");setReply("");await refresh()}
  catch(e){setError((e as Error).message)}finally{setBusy(false)}
 }
 const input=(key:string,label:string,required=false,type="text")=><label key={key}>{label}<input type={type} required={required}
  value={draft[key]??""} onChange={e=>setDraft(v=>({...v,[key]:e.target.value}))}/></label>;
 const emp=(key="employee_id")=><label>Employee<select required value={draft[key]??""} onChange={e=>setDraft(v=>({...v,[key]:e.target.value}))}>
  <option value="">Select employee</option>{staff.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select></label>;
 async function exitCall(path:string,method="GET",body?:unknown){
  const response=await fetch(api+"/exit-workflow"+path,{method,credentials:"include",
   headers:{"Content-Type":"application/json"},body:body===undefined?undefined:JSON.stringify(body)});
  const payload=await response.json().catch(()=>null);
  if(!response.ok)throw Error(explainError(payload,response.status));
  return payload;
 }
 async function initiateExit(e:React.FormEvent){
  e.preventDefault();
  await save(async()=>{
   await exitCall("/cases","POST",{employee_id:Number(exitEmployee),reason:exitReason,
     notice_days:Number(exitNotice),requested_date:today()});
   setExitEmployee("");setExitReason("");
  },"Exit case created. Employee and HR checklist tasks assigned.");
 }
 async function addExitTemplate(e:React.FormEvent){
  e.preventDefault();
  await save(async()=>{
   await exitCall("/templates","POST",{title:templateTitle,assignee_role:templateRole,active:true});
   setExitTemplates(await exitCall("/templates"));setTemplateTitle("");
  },"Exit checklist task configured.");
 }
 async function saveExitTemplate(id:number,active:boolean,title:string,role:string){
  await save(async()=>{
    await exitCall("/templates/"+id,"PUT",{title,assignee_role:role,active});
    setExitTemplates(await exitCall("/templates"));
    setEditingExitTemplate(null);
  },active?"Exit checklist template updated.":"Exit checklist template disabled for future exits.");
 }
 async function loadExitTasks(caseId:number){
  try{
   const items=await exitCall("/cases/"+caseId+"/tasks");
   setExitTasks(v=>({...v,[caseId]:items}));
  }catch(e){setError((e as Error).message)}
 }
 async function completeExitTask(caseId:number,taskId:number){
  await save(async()=>{
   await exitCall("/tasks/"+taskId+"/complete","POST",{note:exitTaskNotes[taskId]||""});
   await loadExitTasks(caseId);
  },"Exit task completed with the audit note.");
 }
 const submit=(path:string,data:Row,success:string)=>save(()=>call(path,"POST",data),success);
 return <div className="ops-area">
  <p className="ops-intro">Employee lifecycle workflows, approvals, announcements and HR support. Confidential workflows are available only to the employee or authorized HR staff.</p>
  <div className="time-tabs" role="tablist">{areas.filter(([id])=>hr||!["analytics","notifications","audit"].includes(id)).map(([id,label])=>
   <button key={id} role="tab" aria-selected={tab===id} className={tab===id?"active":""} onClick={()=>{setTab(id);setError("");setInfo("");setDraft({})}}>{label}</button>)}</div>
  {error&&<div role="alert" className="time-form-error">{error}</div>}
  {info&&<FeedbackMotion type={info.includes("accepted")?"congrats":"success"} compact message={info}/>}
  {busy&&<FeedbackMotion type="loading" compact message="Updating HRMS…"/>}
  {tab==="offers"&&<div className="ops-columns">
    <section className="employee-surface"><h3><FileSignature size={17}/> Offer letters</h3>
     {hr&&<><form className="ops-form" onSubmit={e=>{e.preventDefault();void submit("/offer-templates",
      {name:draft.template_name,content:draft.template_content},"Template created.")}}>
      <h4>Create offer template</h4>{input("template_name","Template name",true)}
      <label className="wide">Offer text with placeholders<textarea rows={5} minLength={30} required
       placeholder="Dear {{employee_name}}, we offer {{job_title}}…" value={draft.template_content||""}
       onChange={e=>setDraft(v=>({...v,template_content:e.target.value}))}/></label>
      <button className="employee-primary" disabled={busy}>Save template</button>
     </form><hr/><form className="ops-form" onSubmit={e=>{e.preventDefault();void submit("/offers",{
       employee_id:Number(draft.employee_id),template_id:Number(draft.template_id),title:draft.title,
       annual_ctc:Number(draft.annual_ctc),joining_date:draft.joining_date||today()
      },"Offer generated.")}}>
      <h4>Generate offer</h4>{emp()}
      <label>Template<select required value={draft.template_id||""} onChange={e=>setDraft(v=>({...v,template_id:e.target.value}))}>
       <option value="">Choose template</option>{templates.map(t=><option key={t.id} value={t.id}>{t.name}</option>)}</select></label>
      {input("title","Job title",true)}{input("annual_ctc","Annual CTC (INR)",true,"number")}
      <label>Joining date<input type="date" required value={draft.joining_date||today()} onChange={e=>setDraft(v=>({...v,joining_date:e.target.value}))}/></label>
      <button className="employee-primary" disabled={busy}>Generate offer</button></form></>}
     {!hr&&<p>Review any offer shared by HR. Typed-name acceptance records an internal consent, not a third-party qualified e-signature.</p>}
    </section>
    <section className="employee-surface"><h3>Offer history</h3><div className="ops-table">{offers.map(o=><div className="ops-row" key={o.id}>
     <strong>{o.title}</strong><span>#{o.employee_id} · {o.status}</span><a href={api+"/people/offers/"+o.id+".pdf"} download>PDF</a>
     {hr&&o.status==="draft"&&<button className="employee-primary" onClick={()=>void save(()=>call("/offers/"+o.id+"/send","POST"),"Offer sent.")}>Send offer</button>}
     {!hr&&o.status==="sent"&&<button className="employee-primary" onClick={()=>void save(()=>call("/offers/"+o.id+"/sign","POST",
       {printed_name:user.name,consent:true}),"Offer accepted and acknowledgement recorded.")}>Accept offer</button>}
    </div>)}</div></section>
   </div>}
  {tab==="onboarding"&&<div className="ops-columns">
   <section className="employee-surface"><h3><ClipboardCheck size={17}/> Onboarding checklist</h3>
    <div className="jellygit-onboarding-welcome"><WelcomeAnimation/><div><strong>Welcome to your JellyGit journey</strong><p className="muted">Complete your orientation, review company policies and meet your team.</p></div></div>
    {hr&&<form className="ops-form" onSubmit={e=>{e.preventDefault();void submit("/onboarding",{
      employee_id:Number(draft.employee_id),category:draft.category||"document",
      title:draft.title,due_date:draft.due_date||null,assigned_to:draft.assigned_to?Number(draft.assigned_to):null,
      asset_code:draft.asset_code||""},"Onboarding task created.")}}>
     {emp()}<label>Category<select value={draft.category||"document"} onChange={e=>setDraft(v=>({...v,category:e.target.value}))}>
      {["document","asset","induction","hr","it"].map(c=><option key={c}>{c}</option>)}</select></label>
     {input("title","Task title",true)}{input("asset_code","Asset code (optional)")}
     {input("due_date","Due date",false,"date")}
     <label>Responsible person<select value={draft.assigned_to||""} onChange={e=>setDraft(v=>({...v,assigned_to:e.target.value}))}>
      <option value="">HR team</option>{staff.map(e=><option key={e.id} value={e.id}>{e.name}</option>)}</select></label>
     <button className="employee-primary">Assign task</button>
     <button type="button" className="employee-cancel" disabled={!draft.employee_id} onClick={()=>void save(()=>call("/onboarding/orientation/"+draft.employee_id,"POST"),"Seven-step welcome orientation initialized.")}>Start welcome orientation (7 steps)</button></form>}
   </section>
   <section className="employee-surface"><h3>Open and completed tasks</h3>
    <p className="muted">Welcome journey: {tasks.filter(t=>t.status==="completed").length} of {tasks.length} tasks completed</p>
    <progress max={Math.max(1,tasks.length)} value={tasks.filter(t=>t.status==="completed").length} style={{width:"100%"}} aria-label="Onboarding progress"/>
    <div className="ops-table">{tasks.map(t=><div className="ops-row" key={t.id}>
    <strong>{t.title}</strong><span>{t.category} · {t.status} · #{t.employee_id}</span>
    {t.asset_code&&<small>Asset: {t.asset_code}</small>}
    {t.status==="pending"&&(hr||t.assigned_to===user.id)&&<button className="employee-primary" onClick={()=>void save(()=>call("/onboarding/"+t.id+"/complete","POST"),"Task completed.")}>Complete</button>}
   </div>)}{!tasks.length&&<div className="jellygit-empty-state"><BrandIllustration asset="empty-folder-state" alt="" className="jellygit-empty-art"/><p>No onboarding tasks yet.</p></div>}</div></section>
  </div>}
  {tab==="announcements"&&<div className="ops-columns">
   <section className="employee-surface"><h3><Send size={17}/> Announcements and policies</h3>
    {hr&&<div className="jellygit-template-download"><BrandIllustration asset="welcome-card-template" alt="Welcome to the Team card design" className="jellygit-template-art"/><div><strong>New-joiner announcement design</strong><p className="muted">This exported card is a visual reference. Edit the original Canva design to replace the sample text before publishing.</p><a href="/assets/welcome-card-template.webp" download="jellygit-welcome-template.webp">Download card template</a></div></div>}
    {hr&&<form className="ops-form" onSubmit={e=>{e.preventDefault();void submit("/announcements",{
      title:draft.title,body:draft.body,requires_ack:!!draft.requires_ack},"Announcement published.")}}>
      {input("title","Title",true)}
      <label className="wide">Announcement<textarea minLength={12} required rows={4} value={draft.body||""}
       onChange={e=>setDraft(v=>({...v,body:e.target.value}))}/></label>
      <label className="wide ops-check"><input type="checkbox" checked={!!draft.requires_ack}
       onChange={e=>setDraft(v=>({...v,requires_ack:e.target.checked}))}/>Require employee acknowledgement</label>
      <button className="employee-primary">Publish</button></form>}
   </section>
   <section className="employee-surface"><h3>Company feed</h3><div className="ops-table">{notices.map(n=><article className="ops-row" key={n.id}>
     <strong>{n.title}</strong><p>{n.body}</p>
     {n.requires_ack&&!n.acknowledged&&<button className="employee-primary" onClick={()=>void save(()=>call("/announcements/"+n.id+"/ack","POST"),"Acknowledged.")}>Acknowledge</button>}
     {n.acknowledged&&<small>Acknowledged</small>}
    </article>)}{!notices.length&&<p>No announcements yet.</p>}</div></section>
  </div>}
  {tab==="helpdesk"&&<div className="ops-columns">
   <section className="employee-surface"><h3><LifeBuoy size={17}/> HR helpdesk</h3>
    <form className="ops-form" onSubmit={e=>{e.preventDefault();void submit("/tickets",{
     category:draft.category||"other",subject:draft.subject,description:draft.description},"Helpdesk ticket opened.")}}>
     <label>Category<select value={draft.category||"other"} onChange={e=>setDraft(v=>({...v,category:e.target.value}))}>
     {["payroll","leave","attendance","benefits","it","other"].map(c=><option key={c}>{c}</option>)}</select></label>
     {input("subject","Subject",true)}
     <label className="wide">Question or concern<textarea minLength={12} required rows={4} value={draft.description||""}
      onChange={e=>setDraft(v=>({...v,description:e.target.value}))}/></label>
     <button className="employee-primary">Create ticket</button></form>
   </section>
   <section className="employee-surface"><h3>{hr?"HR ticket queue":"My tickets"}</h3><div className="ops-table">{(hr?allTickets:tickets).map(t=><article className="ops-row" key={t.id}>
    <strong>{t.subject} · {t.status}</strong><small>{t.category} · Employee #{t.employee_id}</small><p>{t.description}</p>
    {t.hr_response&&<p>HR: {t.hr_response}</p>}
    {hr&&t.status!=="closed"&&<><textarea placeholder="HR response" value={selected===String(t.id)?reply:""}
      onChange={e=>{setSelected(String(t.id));setReply(e.target.value)}}/>
      <button className="employee-primary" disabled={busy||selected!==String(t.id)||reply.length<5}
       onClick={()=>void save(()=>call("/tickets/"+t.id+"/review","POST",{status:"resolved",reply}),"Ticket resolved.")}>Resolve</button></>}
   </article>)}</div></section>
  </div>}
  {tab==="exit"&&<div className="ops-columns">
   <section className="employee-surface"><h3><UserRoundX size={17}/> Exit request</h3>
    {!hr&&<form className="ops-form" onSubmit={e=>{e.preventDefault();void submit("/exits",{
      reason:draft.reason,notice_days:Number(draft.notice_days||0),
      requested_date:draft.requested_date||today()},"Resignation request submitted.")}}>
      <label className="wide">Resignation reason<textarea minLength={10} required rows={4} value={draft.reason||""}
       onChange={e=>setDraft(v=>({...v,reason:e.target.value}))}/></label>
      {input("notice_days","Notice period (days)",true,"number")}
      <label>Request date<input type="date" value={draft.requested_date||today()}
       onChange={e=>setDraft(v=>({...v,requested_date:e.target.value}))}/></label>
      <button className="employee-primary">Request resignation</button></form>}
    {hr&&<><p className="muted">Select an employee to begin their exit, then assign the configured employee and HR checklist tasks.</p>
     <form className="ops-form ops-compact-form" onSubmit={initiateExit}>
      <label>Employee<select required value={exitEmployee} onChange={e=>setExitEmployee(e.target.value)}>
       <option value="">Select an active employee</option>{staff.filter(p=>p.status==="active").map(p=><option key={p.id} value={p.id}>{p.name}</option>)}
      </select></label>
      <label>Notice period (days)<input type="number" required min="0" max="365" value={exitNotice} onChange={e=>setExitNotice(e.target.value)}/></label>
      <label className="wide">Reason for exit<textarea required minLength={10} rows={3} value={exitReason} onChange={e=>setExitReason(e.target.value)} placeholder="Enter at least ten characters explaining the exit…"/></label>
      <div className="ops-form-actions"><button className="employee-primary" disabled={busy||!exitEmployee||exitReason.trim().length<10}>Start employee exit</button></div>
     </form>
     <details className="employee-surface exit-config-panel"><summary>Configure exit tasks</summary>
      <p className="muted">These tasks are automatically assigned whenever an exit case is opened. HR tasks go to HR; employee tasks go to the departing employee.</p>
      <div className="exit-task-list">{exitTemplates.map((x,i)=><div key={x.id??"default"+i} className="ops-row">
        {editingExitTemplate===x.id&&x.id!=null?<div className="ops-form">
         <label>Task name<input required minLength={5} maxLength={180} value={editExitTitle}
           onChange={e=>setEditExitTitle(e.target.value)}/></label>
         <label>Assigned to<select value={editExitRole} onChange={e=>setEditExitRole(e.target.value)}>
          <option value="hr">HR team</option><option value="employee">Exiting employee</option>
         </select></label>
         <button type="button" className="employee-primary" disabled={busy||editExitTitle.trim().length<5}
           onClick={()=>void saveExitTemplate(x.id,x.active,editExitTitle.trim(),editExitRole)}>Save template</button>
         <button type="button" className="employee-cancel" onClick={()=>setEditingExitTemplate(null)}>Cancel</button>
        </div>:<>
         <strong>{x.title}</strong> <small>· {x.assignee_role==="hr"?"HR":"Employee"} · {x.active?"Active":"Disabled"}</small>
         {x.id!=null&&<><button type="button" className="employee-cancel" disabled={busy}
          onClick={()=>{setEditingExitTemplate(x.id);setEditExitTitle(x.title);setEditExitRole(x.assignee_role)}}>
          Edit</button>
         <button type="button" className="employee-cancel" disabled={busy}
          onClick={()=>void saveExitTemplate(x.id,!x.active,x.title,x.assignee_role)}>
          {x.active?"Disable":"Enable"}</button></>}
        </>}
       </div>)}</div>
      <form className="ops-form ops-compact-form" onSubmit={addExitTemplate}>
       <label>New task name<input required minLength={5} maxLength={180} value={templateTitle} onChange={e=>setTemplateTitle(e.target.value)} placeholder="e.g. Confirm returned access badge"/></label>
       <label>Assigned to<select value={templateRole} onChange={e=>setTemplateRole(e.target.value)}><option value="hr">HR team</option><option value="employee">Exiting employee</option></select></label>
       <div className="ops-form-actions"><button className="employee-primary" disabled={busy||templateTitle.trim().length<5}>Add checklist task</button></div>
      </form>
     </details>
     <p className="muted">Final settlement requires documented asset, IT and Finance clearance. This process does not send a payment.</p>
    </>}
   </section>
   <section className="employee-surface"><h3>Exit cases</h3><div className="ops-table">{(hr?allExits:exits).map(x=><div className="ops-row" key={x.id}>
     <strong>Case #{x.id} · {x.status}</strong><span>{staff.find(p=>p.id===x.employee_id)?.name||"Employee #"+x.employee_id} · Last day {x.planned_last_day}</span><p>{x.reason}</p>
      <div className="exit-task-controls"><button className="employee-cancel" type="button" onClick={()=>void loadExitTasks(x.id)}>View assigned exit tasks</button>
       {(exitTasks[x.id]||[]).map(t=><div className="exit-task-entry" key={t.id}>
        <strong>{t.title}</strong><small>{t.assignee_role==="hr"?"HR task":"Employee task"} · {t.status}</small>
        {t.status==="pending"&&<><label>Completion note<input placeholder="Explain what was completed" minLength={5} maxLength={1000}
          value={exitTaskNotes[t.id]||""} onChange={e=>setExitTaskNotes(old=>({...old,[t.id]:e.target.value}))}/></label>
         <button className="employee-primary" type="button" disabled={busy||(exitTaskNotes[t.id]||"").trim().length<5}
          onClick={()=>void completeExitTask(x.id,t.id)}>Complete task</button></>}
       </div>)}
      </div>
     {hr&&x.status!=="settled"&&x.status!=="rejected"&&<><label>F&F amount<input type="number" min="0" step=".01" value={selected===String(x.id)?draft.amount||"":""}
      onFocus={()=>setSelected(String(x.id))} onChange={e=>setDraft(v=>({...v,amount:e.target.value}))}/></label>
      <button className="employee-primary" onClick={()=>void save(()=>call("/exits/"+x.id+"/review","POST",{
       status:"approved",clearance_assets:false,clearance_it:false,clearance_finance:false}),"Exit request approved.")}>Approve</button>
      <button className="employee-cancel" onClick={()=>void save(()=>call("/exits/"+x.id+"/review","POST",{status:"rejected"}),"Exit request rejected.")}>Reject</button>
      <button className="employee-primary" disabled={selected!==String(x.id)||draft.amount===""||draft.amount===undefined}
       onClick={()=>void save(()=>call("/exits/"+x.id+"/review","POST",{
        status:"settled",clearance_assets:true,clearance_it:true,clearance_finance:true,
        final_settlement_inr:Number(draft.amount),final_settlement_note:"HR reviewed all clearances and F&F draft."}),"Clearances recorded and settlement finalized.")}>Confirm clearances & F&F</button>
     </>}
    </div>)}</div></section>
  </div>}
  {tab==="analytics"&&hr&&<section className="employee-surface"><h3><BarChart3 size={17}/> Workforce analytics</h3>
   {metrics&&<><div className="ops-metrics">{[["Active employees",metrics.active_headcount],["Inactive",metrics.inactive_headcount],
    ["Pending leave",metrics.pending_leave],["Open helpdesk",metrics.open_tickets],["Inactive share",metrics.attrition_proxy_pct+"%"]].map(([label,value])=><div key={String(label)}><span>{label}</span><strong>{value}</strong></div>)}</div>
    <p className="field-help">{metrics.note}</p>
    <div className="ops-columns"><div><h4>Department distribution</h4>{metrics.departments?.map((d:Row)=><div className="ops-row" key={d.department}>{d.department}: {d.employees} employees</div>)}</div>
    <div><h4>Published payroll cost</h4>{metrics.published_monthly_net?.map((p:Row)=><div className="ops-row" key={p.period}>{p.period} · ₹{Number(p.net).toLocaleString("en-IN")}</div>)}</div></div></>}
   </section>}
  {tab==="notifications"&&hr&&<section className="employee-surface"><h3><Bell size={17}/> Notification channel rules</h3>
   <p className="field-help">Rules control notification queues. Email/SMS/push/WhatsApp are not marked as delivered without provider connections.</p>
   <div className="ops-table">{["approval","birthday","document_renewal","helpdesk","offer","exit"].map(event=>{
    const config=rules.find(r=>r.event===event)||{event,email:true,sms:false,push:false,whatsapp:false};
    return <div className="ops-row" key={event}><strong>{event.replace(/_/g," ")}</strong>{(["email","sms","push","whatsapp"] as const).map(ch=>
     <label key={ch} className="ops-check"><input type="checkbox" checked={Boolean(config[ch])}
      onChange={e=>void save(()=>call("/notification-rules","PUT",{...config,[ch]:e.target.checked}),"Notification rule updated.")}/>{ch}</label>)}</div>
   })}</div>
   <h3>My notification queue</h3><div className="ops-table">{notifications.map(n=><div className="ops-row" key={n.id}><strong>{n.subject}</strong><span>{n.channel} · {n.status}</span><small>{n.body}</small></div>)}</div>
  </section>}
  {tab==="assets"&&<PeopleOpsExtras api={api} user={user}/>}
  {tab==="audit"&&hr&&<section className="employee-surface"><h3><ShieldCheck size={17}/> HR change audit</h3>
   <p className="field-help">Append-only event records for new People Operations workflows. Existing legacy endpoints need an expanded audit migration.</p>
   <div className="ops-table">{audits.map(a=><div className="ops-row" key={a.id}><strong>{a.kind} · {a.action}</strong><span>Object #{a.object_id} · Actor #{a.actor_id}</span><small>{String(a.created_at||"").slice(0,19)}</small></div>)}</div>
   <p>SSO requires an organization identity provider. 2FA enrollment/login enforcement is a separate security rollout and is not enabled by this release.</p>
  </section>}
 </div>;
}
