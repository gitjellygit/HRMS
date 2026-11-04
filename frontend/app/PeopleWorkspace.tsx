"use client";
import {useCallback,useEffect,useState} from "react";
import {FileSignature,ClipboardCheck,Megaphone,Headset,LogOut,Download} from "lucide-react";
import FeedbackMotion from "./FeedbackMotion";
type Row=Record<string,any>;
type User={id:number;name:string;role:string};
type Tab="offers"|"onboard"|"announcements"|"helpdesk"|"exits";
const today=()=>new Date().toISOString().slice(0,10);
const OFFER_BODY="Dear $employee_name,\n\nWe are delighted to offer you the position of $job_title at $company_name. Your proposed monthly salary is INR $monthly_salary_inr. Your start date is $start_date.\n\nPlease review the terms and acknowledge your acceptance in the HRMS portal.\n\nRegards,\nHuman Resources";
export default function PeopleWorkspace({api,user}:{api:string;user:User}){
 const isHR=["super_admin","admin","hr"].includes(user.role);
 const finance=isHR||user.role==="accountant";
 const [tab,setTab]=useState<Tab>("offers"),[busy,setBusy]=useState(false),
       [error,setError]=useState(""),[notice,setNotice]=useState("");
 const [staff,setStaff]=useState<Row[]>([]),[templates,setTemplates]=useState<Row[]>([]),
       [offers,setOffers]=useState<Row[]>([]),[tasks,setTasks]=useState<Row[]>([]),
       [assets,setAssets]=useState<Row[]>([]),[announcements,setAnnouncements]=useState<Row[]>([]),
       [acknowledgements,setAcknowledgements]=useState<Row[]>([]),
       [tickets,setTickets]=useState<Row[]>([]),[exits,setExits]=useState<Row[]>([]);
 const [templateForm,setTemplateForm]=useState({name:"Standard JellyGit Offer",body:OFFER_BODY});
 const [offerForm,setOfferForm]=useState({employee_id:"",template_id:"",title:"",salary_inr:"",start_date:today()});
 const [signName,setSignName]=useState(user.name);
 const [taskForm,setTaskForm]=useState({employee_id:"",title:"",category:"documents",assigned_to:"",due_date:today()});
 const [assetForm,setAssetForm]=useState({employee_id:"",asset_name:"",serial_number:""});
 const [announce,setAnnounce]=useState({title:"",body:""});
 const [ticketForm,setTicketForm]=useState({subject:"",category:"other",description:""});
 const [message,setMessage]=useState("");
 const [selectedTicket,setSelectedTicket]=useState<number|null>(null);
 const [messages,setMessages]=useState<Row[]>([]);
 const [exitForm,setExitForm]=useState({requested_last_day:today(),reason:""});
 const [exitReview,setExitReview]=useState({notice_days:"30",approved_last_day:""});
 const [selectedExit,setSelectedExit]=useState<number|null>(null);
 const [clearances,setClearances]=useState<Row[]>([]);
 const [settlement,setSettlement]=useState({unpaid_salary:"0",leave_encashment:"0",gratuity:"0",recovery:"0"});
 const call=useCallback(async(path:string,method="GET",body?:unknown)=>{
   const r=await fetch(api+"/people"+path,{method,credentials:"include",headers:{"Content-Type":"application/json"},
     body:body!==undefined?JSON.stringify(body):undefined});
   const data=await r.json().catch(()=>({}));
   if(!r.ok){
    const d=data.detail;throw Error(typeof d==="string"?d:d?.message||
      (Array.isArray(d)?d.map((x:Row)=>x.msg).join("; "):"Unable to complete request"));
   }
   return data;
 },[api]);
 const load=useCallback(async()=>{
  const tasks=[call("/offers"),call("/onboarding/tasks"),call("/onboarding/assets"),
    call("/announcements"),call("/policy-acknowledgements"),call("/helpdesk"),call("/exits"),
    ...(isHR?[call("/offer-templates"),fetch(api+"/employees",{credentials:"include"}).then(r=>r.ok?r.json():[])]:[])];
  const r=await Promise.allSettled(tasks);
  const v=(i:number)=>r[i].status==="fulfilled"?(r[i] as PromiseFulfilledResult<any>).value:[];
  setOffers(v(0));setTasks(v(1));setAssets(v(2));setAnnouncements(v(3));
  setAcknowledgements(v(4));setTickets(v(5));setExits(v(6));
  if(isHR){setTemplates(v(7));setStaff(v(8))}
 },[api,call,isHR]);
 useEffect(()=>{void load()},[load]);
 async function execute(action:()=>Promise<unknown>,success:string){
  setBusy(true);setError("");setNotice("");
  try{await action();setNotice(success);await load()}
  catch(e){setError((e as Error).message)}finally{setBusy(false)}
 }
 async function getPdf(offerId:number){
  const r=await fetch(api+"/people/offers/"+offerId+"/pdf",{credentials:"include"});
  if(!r.ok){setError("Offer document unavailable.");return}
  const blob=await r.blob();const link=window.document.createElement("a");
  const object=URL.createObjectURL(blob);link.href=object;link.download="offer-"+offerId+".pdf";
  link.click();URL.revokeObjectURL(object);
 }
 async function showTicket(id:number){
  setSelectedTicket(id);
  try{setMessages(await call("/helpdesk/"+id+"/messages"))}catch(e){setError((e as Error).message)}
 }
 async function showClearances(id:number){
  setSelectedExit(id);
  try{setClearances(await call("/exits/"+id+"/clearances"))}catch(e){setError((e as Error).message)}
 }
 const input=(key:string,value:string,change:(s:string)=>void,label:string,kind="text",required=true)=>
  <label key={key}>{label}<input name={key} type={kind} required={required} value={value} onChange={e=>change(e.target.value)}/></label>;
 return <div className="ops-workspace">
  <div className="ops-heading"><ClipboardCheck size={21}/><div><h2>People operations</h2><p>Offers, onboarding, company communications, HR support and employee exits.</p></div></div>
  <nav className="ops-tabs">{([["offers","Offer letters",FileSignature],["onboard","Onboarding",ClipboardCheck],
   ["announcements","Announcements",Megaphone],["helpdesk","HR helpdesk",Headset],["exits","Exit management",LogOut]] as [Tab,string,any][])
   .map(([id,label,Icon])=><button key={id} className={tab===id?"active":""} onClick={()=>{setTab(id);setNotice("");setError("")}}><Icon size={16}/>{label}</button>)}</nav>
  {error&&<div role="alert" className="time-form-error">{error}</div>}
  {notice&&<FeedbackMotion type={notice.includes("accepted")?"congrats":"success"} compact message={notice}/>}
  {busy&&<FeedbackMotion type="loading" compact message="Saving changes…"/>}

  {tab==="offers"&&<div className="ops-columns">
   <section className="employee-surface"><h3>{isHR?"Create offer template":"My offer letters"}</h3>
    {isHR&&<><form className="ops-form" onSubmit={e=>{e.preventDefault();void execute(()=>call("/offer-templates","POST",templateForm),"Offer template created.")}}>
      {input("name",templateForm.name,v=>setTemplateForm(s=>({...s,name:v})),"Template name")}
      <label className="wide">Letter template body<textarea rows={8} minLength={50} required value={templateForm.body}
        onChange={e=>setTemplateForm(s=>({...s,body:e.target.value}))}/><small>Allowed placeholders: $employee_name, $job_title, $monthly_salary_inr, $start_date, $company_name</small></label>
      <button className="employee-primary" disabled={busy}>Save template</button></form>
     <h3>Issue offer</h3>
     <form className="ops-form" onSubmit={e=>{e.preventDefault();void execute(()=>call("/offers","POST",{
      ...offerForm,employee_id:Number(offerForm.employee_id),template_id:Number(offerForm.template_id),
      salary_inr:Number(offerForm.salary_inr)}),"Offer letter issued.")}}>
      <label>Employee<select required value={offerForm.employee_id} onChange={e=>setOfferForm(s=>({...s,employee_id:e.target.value}))}><option value="">Select employee</option>{staff.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select></label>
      <label>Template<select required value={offerForm.template_id} onChange={e=>setOfferForm(s=>({...s,template_id:e.target.value}))}><option value="">Select template</option>{templates.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select></label>
      {(["title","salary_inr","start_date"] as const).map(k=>input(k,offerForm[k],v=>setOfferForm(s=>({...s,[k]:v})),k.replace(/_/g," "),k==="start_date"?"date":k==="salary_inr"?"number":"text"))}
      <button className="employee-primary" disabled={busy}>Issue offer</button>
     </form></>}
    <p className="field-help">Offer acceptance is an authenticated typed-name acknowledgement. Qualified electronic signatures require a vendor integration.</p>
   </section>
   <section className="employee-surface"><h3>My offers</h3>
    {isHR&&<button className="employee-cancel" onClick={()=>void call("/offers?scope=all").then(setOffers).catch(e=>setError(e.message))}>Show all offers</button>}
    <div className="ops-list">{offers.map(o=><div key={o.id}><strong>{o.title} · ₹{Number(o.salary_inr).toLocaleString("en-IN")}/month</strong>
      <span>Start: {o.start_date} · {o.status}</span>
      <button className="employee-cancel" onClick={()=>void getPdf(o.id)}><Download size={14}/> Offer PDF</button>
      {o.status==="issued"&&o.employee_id===user.id&&<div className="ops-form">
       <label>Type your full legal name<input value={signName} onChange={e=>setSignName(e.target.value)}/></label>
       <button className="employee-primary" onClick={()=>void execute(()=>call("/offers/"+o.id+"/accept","POST",{signed_name:signName,consent:true}),"Offer accepted with your recorded consent.")}>Accept offer</button>
      </div>}
    </div>)}{!offers.length&&<p>No offer letters yet.</p>}</div>
   </section>
  </div>}

  {tab==="onboard"&&<div className="ops-columns">
   <section className="employee-surface"><h3>Onboarding checklist</h3>
    {isHR&&<form className="ops-form" onSubmit={e=>{e.preventDefault();void execute(()=>call("/onboarding/tasks","POST",{
       ...taskForm,employee_id:Number(taskForm.employee_id),
       assigned_to:taskForm.assigned_to?Number(taskForm.assigned_to):null}),"Onboarding task assigned.")}}>
     <label>New employee<select value={taskForm.employee_id} required onChange={e=>setTaskForm(s=>({...s,employee_id:e.target.value}))}><option value="">Select employee</option>{staff.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select></label>
     <label>Task category<select value={taskForm.category} onChange={e=>setTaskForm(s=>({...s,category:e.target.value}))}>{["documents","assets","induction","access","other"].map(x=><option key={x}>{x}</option>)}</select></label>
     {input("title",taskForm.title,v=>setTaskForm(s=>({...s,title:v})),"Task description")}
     <label>Task owner<select value={taskForm.assigned_to} onChange={e=>setTaskForm(s=>({...s,assigned_to:e.target.value}))}><option value="">HR default</option>{staff.map(x=><option value={x.id} key={x.id}>{x.name}</option>)}</select></label>
     {input("due_date",taskForm.due_date,v=>setTaskForm(s=>({...s,due_date:v})),"Due date","date")}
     <button className="employee-primary" disabled={busy}>Add checklist item</button>
    </form>}
    {isHR&&<button className="employee-cancel" onClick={()=>void call("/onboarding/tasks?employee_id="+taskForm.employee_id).then(setTasks).catch(e=>setError(e.message))}>View selected employee checklist</button>}
    <div className="ops-list">{tasks.map(t=><div key={t.id}><strong>{t.title}</strong><span>{t.category} · {t.status} · Due {t.due_date||"—"}</span>
      {t.status==="pending"&&(isHR||t.assigned_to===user.id)&&<button className="employee-cancel" disabled={busy} onClick={()=>void execute(()=>call("/onboarding/tasks/"+t.id+"/complete","POST"),"Checklist task completed.")}>Mark completed</button>}
     </div>)}{!tasks.length&&<p>No checklist tasks assigned.</p>}</div>
   </section>
   <section className="employee-surface"><h3>Asset allocation</h3>
    {isHR&&<form className="ops-form" onSubmit={e=>{e.preventDefault();void execute(()=>call("/onboarding/assets","POST",{
      ...assetForm,employee_id:Number(assetForm.employee_id)}),"Asset allocated.")}}>
      <label>Employee<select required value={assetForm.employee_id} onChange={e=>setAssetForm(v=>({...v,employee_id:e.target.value}))}><option value="">Select employee</option>{staff.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select></label>
      {(["asset_name","serial_number"] as const).map(k=>input(k,assetForm[k],v=>setAssetForm(s=>({...s,[k]:v})),k.replace(/_/g," ")))}
      <button className="employee-primary" disabled={busy}>Allocate asset</button>
     </form>}
    <div className="ops-list">{assets.map(a=><div key={a.id}><strong>{a.asset_name}</strong><span>Serial: {a.serial_number} · {a.returned_at?"Returned":"Issued"}</span>
      {isHR&&!a.returned_at&&<button className="employee-cancel" onClick={()=>void execute(()=>call("/onboarding/assets/"+a.id+"/return","POST"),"Asset returned.")}>Record return</button>}
    </div>)}{!assets.length&&<p>No assets assigned.</p>}</div>
   </section>
  </div>}

  {tab==="announcements"&&<div className="ops-columns">
   <section className="employee-surface"><h3>Company notices</h3>
    {isHR&&<form className="ops-form" onSubmit={e=>{e.preventDefault();void execute(()=>call("/announcements","POST",{...announce,published:true}),"Announcement published.")}}>
      {input("title",announce.title,v=>setAnnounce(s=>({...s,title:v})),"Title")}
      <label className="wide">Announcement<textarea required minLength={10} rows={4} value={announce.body} onChange={e=>setAnnounce(s=>({...s,body:e.target.value}))}/></label>
      <button className="employee-primary" disabled={busy}>Publish notice</button>
     </form>}
    <div className="ops-list">{announcements.map(a=><div key={a.id}><strong>{a.title}</strong><span>{a.body}</span></div>)}{!announcements.length&&<p>No announcements.</p>}</div>
   </section>
   <section className="employee-surface"><h3>Policy acknowledgements</h3><p className="muted">Review the company policies before acknowledging them.</p>
    <div className="ops-list">{acknowledgements.map(p=><div key={p.id}><strong>{p.title}</strong><span>{p.category} · Effective {p.effective_date}</span>
     {p.acknowledged?<small>Acknowledged</small>:<button className="employee-cancel" disabled={busy} onClick={()=>void execute(()=>call("/policy-acknowledgements/"+p.id,"POST"),"Policy acknowledgement recorded.")}>Acknowledge policy</button>}
    </div>)}{!acknowledgements.length&&<p>No active policies requiring acknowledgement.</p>}</div>
   </section>
  </div>}

  {tab==="helpdesk"&&<div className="ops-columns">
   <section className="employee-surface"><h3>Open an HR support ticket</h3>
    <form className="ops-form" onSubmit={e=>{e.preventDefault();void execute(()=>call("/helpdesk","POST",ticketForm),"HR ticket submitted.")}}>
     {input("subject",ticketForm.subject,v=>setTicketForm(s=>({...s,subject:v})),"Subject")}
     <label>Category<select value={ticketForm.category} onChange={e=>setTicketForm(s=>({...s,category:e.target.value}))}>{["payroll","leave","attendance","it","documents","other"].map(k=><option key={k}>{k}</option>)}</select></label>
     <label className="wide">Issue description<textarea required minLength={10} rows={4} value={ticketForm.description} onChange={e=>setTicketForm(s=>({...s,description:e.target.value}))}/></label>
     <button className="employee-primary" disabled={busy}>Create ticket</button>
    </form>
    <div className="ops-list">{tickets.map(t=><div key={t.id}><strong>#{t.id} {t.subject}</strong>
     <span>{t.category} · {t.status}</span><button className="employee-cancel" onClick={()=>void showTicket(t.id)}>Open conversation</button>
     {isHR&&t.status!=="closed"&&<button className="employee-cancel" onClick={()=>void execute(()=>call("/helpdesk/"+t.id+"/close","POST"),"Ticket closed.")}>Close ticket</button>}
    </div>)}{!tickets.length&&<p>No tickets yet.</p>}</div>
    {isHR&&<button className="employee-cancel" onClick={()=>void call("/helpdesk?scope=all").then(setTickets).catch(e=>setError(e.message))}>Show all HR tickets</button>}
   </section>
   <section className="employee-surface"><h3>Ticket conversation</h3>
    {selectedTicket?<><div className="ops-list">{messages.map((m,i)=><div key={i}><strong>Employee #{m.author_id}</strong><span>{m.body}</span></div>)}{!messages.length&&<p>No replies yet.</p>}</div>
     <form className="ops-form" onSubmit={e=>{e.preventDefault();void execute(async()=>{await call("/helpdesk/"+selectedTicket+"/messages","POST",{body:message});setMessage("");await showTicket(selectedTicket)},"Reply sent.")}}>
      <label className="wide">Reply<textarea rows={3} required minLength={2} value={message} onChange={e=>setMessage(e.target.value)}/></label>
      <button className="employee-primary" disabled={busy}>Send reply</button>
     </form></>:<p>Select a ticket to view messages.</p>}
   </section>
  </div>}

  {tab==="exits"&&<div className="ops-columns">
   <section className="employee-surface"><h3>Resignation & notice period</h3>
    <form className="ops-form" onSubmit={e=>{e.preventDefault();void execute(()=>call("/exits","POST",exitForm),"Resignation request submitted.")}}>
     {input("requested_last_day",exitForm.requested_last_day,v=>setExitForm(s=>({...s,requested_last_day:v})),"Requested last working day","date")}
     <label className="wide">Reason<textarea rows={3} required minLength={10} value={exitForm.reason} onChange={e=>setExitForm(s=>({...s,reason:e.target.value}))}/></label>
     <button className="employee-primary" disabled={busy}>Submit resignation</button>
    </form>
    {finance&&<button className="employee-cancel" onClick={()=>void call("/exits?scope=all").then(setExits).catch(e=>setError(e.message))}>Show all exit cases</button>}
    <div className="ops-list">{exits.map(x=><div key={x.id}><strong>Exit #{x.id} · Employee #{x.employee_id}</strong>
      <span>Requested: {x.requested_last_day} · Approved: {x.approved_last_day||"—"} · {x.status}</span>
      {isHR&&x.status==="pending"&&<><div className="ops-form">
       {input("notice_days",exitReview.notice_days,v=>setExitReview(s=>({...s,notice_days:v})),"Notice days","number")}
       {input("approved_last_day",exitReview.approved_last_day,v=>setExitReview(s=>({...s,approved_last_day:v})),"Last day override (optional)","date",false)}
      </div><div className="ops-actions">
       <button className="employee-primary" onClick={()=>void execute(()=>call("/exits/"+x.id+"/review","POST",{approved:true,notice_days:Number(exitReview.notice_days),
        approved_last_day:exitReview.approved_last_day||null}),"Resignation reviewed and clearance started.")}>Approve exit</button>
       <button className="employee-cancel" onClick={()=>void execute(()=>call("/exits/"+x.id+"/review","POST",{approved:false,notice_days:0}),"Resignation rejected.")}>Reject</button>
      </div></>}
      <button className="employee-cancel" onClick={()=>void showClearances(x.id)}>View clearance checklist</button>
    </div>)}{!exits.length&&<p>No exit requests.</p>}</div>
   </section>
   <section className="employee-surface"><h3>Clearance & full and final</h3>{selectedExit?<><h4>Exit #{selectedExit} clearances</h4>
     <div className="ops-list">{clearances.map(c=><div key={c.id}><strong>{c.department}</strong><span>{c.status}</span>
       {isHR&&c.status==="pending"&&<button className="employee-cancel" onClick={()=>void execute(async()=>{await call("/exits/"+selectedExit+"/clearances","POST",{department:c.department,approved:true,note:"Clearance verified"});await showClearances(selectedExit)},"Clearance approved.")}>Mark cleared</button>}
      </div>)}</div>
     {finance&&<form className="ops-form" onSubmit={e=>{e.preventDefault();void execute(()=>call("/exits/"+selectedExit+"/settlement","PUT",Object.fromEntries(
      Object.entries(settlement).map(([k,v])=>[k,Number(v)]))),"F&F draft saved (not paid).")}}>
      {(["unpaid_salary","leave_encashment","gratuity","recovery"] as const).map(k=>input(k,settlement[k],v=>setSettlement(s=>({...s,[k]:v})),k.replace(/_/g," "), "number"))}
      <button className="employee-primary" disabled={busy}>Save F&F draft</button>
     </form>}
     {isHR&&<button className="employee-cancel" disabled={busy} onClick={()=>void execute(()=>call("/exits/"+selectedExit+"/settlement/approve","POST"),"F&F approved. Payment still requires finance processing.")}>Approve F&F after all clearances</button>}
    </>:<p>Select an exit request to review department clearance and settlement.</p>}</section>
  </div>}
 </div>;
}
