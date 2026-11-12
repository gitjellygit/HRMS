"use client";
import {explainError} from "./formErrors";
import {useCallback,useEffect,useRef,useState} from "react";
import {Clock3,CalendarDays,MapPin,FileClock,Users,BriefcaseBusiness,Settings2,AlertCircle} from "lucide-react";
import FeedbackMotion from "./FeedbackMotion";
import PunchControl from "./PunchControl";
import {TIME_ZONES,zonedLocalToIso} from "./timeZones";
type Row=Record<string,any>;
type Tab="today"|"requests"|"shifts"|"timesheets"|"policies";
const today=()=>new Date().toLocaleDateString("en-CA");
const kindName=(value:string)=>value==="on_duty"?"Official work outside office":value.replace(/_/g," ").replace(/\b\w/g,c=>c.toUpperCase());
const dateForInput=(v:string)=>new Date(v).toISOString().slice(0,16);
const initialPolicy={location:"all",grace_minutes:15,half_day_under_hours:4,overtime_after_hours:9,
 auto_deduct:false,geo_required:false,office_lat:"",office_lon:"",radius_meters:250};
export default function TimeWorkspace({api,user}:{api:string;user:{id:number;role:string}}){
 const isHR=["super_admin","admin","hr"].includes(user.role);
 const isApprover=isHR||user.role==="manager";
 const [tab,setTab]=useState<Tab>("today");
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState("");
 const [errorField,setErrorField]=useState("");
 const [notice,setNotice]=useState("");
 const [daily,setDaily]=useState<Row[]>([]);
 const [policy,setPolicy]=useState<Row>(initialPolicy);
 const [shifts,setShifts]=useState<Row[]>([]);
 const [rosters,setRosters]=useState<Row[]>([]);
 const [requests,setRequests]=useState<Row[]>([]);
 const [approvals,setApprovals]=useState<Row[]>([]);
 const [timesheets,setTimesheets]=useState<Row[]>([]);
 const [timesheetApprovals,setTimesheetApprovals]=useState<Row[]>([]);
 const [projectAssignments,setProjectAssignments]=useState<Row[]>([]);
 const [assignmentEmployee,setAssignmentEmployee]=useState("");
 const [assignmentProject,setAssignmentProject]=useState("");
 const [staff,setStaff]=useState<Row[]>([]);
 const [projectOptions,setProjectOptions]=useState<Row[]>([]);
 const [requestForm,setRequestForm]=useState<Row>({kind:"wfh",work_date:today(),end_date:"",
   reason:"",hours:"",proposed_in:"",proposed_out:"",target_employee_id:""});
 const [shiftForm,setShiftForm]=useState({name:"General",start_time:"09:00",end_time:"18:00",break_minutes:"60",timezone:"America/New_York"});
 const [requestZone,setRequestZone]=useState("America/New_York");
 const [geoHelp,setGeoHelp]=useState(false);
 const [geoLocating,setGeoLocating]=useState(false);
 const [rosterForm,setRosterForm]=useState({employee_id:"",shift_id:"",work_date:today()});
 const [timeForm,setTimeForm]=useState({work_date:today(),task:"",hours:"",project_id:"",note:""});
 const [editingTimesheetId,setEditingTimesheetId]=useState<number|null>(null);
 const focusRef=useRef<HTMLDivElement|null>(null);
 const [validatedGeo,setValidatedGeo]=useState(false);
 const call=useCallback(async(path:string,method="GET",body?:unknown)=>{
  const res=await fetch(api+"/time"+path,{method,credentials:"include",headers:{"Content-Type":"application/json"},
   body:body!==undefined?JSON.stringify(body):undefined});
  const data=await res.json().catch(()=>({}));
  if(!res.ok){
   const detail=data.detail;
   const message=typeof detail==="string"?detail:detail?.message||(
    Array.isArray(detail)?detail.map((e:Row)=>e.msg).join("; "):explainError(data,res.status));
   const field=detail?.field||(Array.isArray(detail)?String(detail[0]?.loc?.at(-1)||""):"");
   throw Object.assign(new Error(message),{field});
  }
  return data;
 },[api]);
 const load=useCallback(async()=>{
  const fetches=await Promise.allSettled([
   call("/daily"),call("/policy"),call("/shifts"),call("/roster"),call("/requests"),call("/requests?scope=approvals"),
   call("/timesheets"),
   isHR?fetch(api+"/employees",{credentials:"include"}).then(r=>r.ok?r.json():[]):Promise.resolve([]),
   fetch(api+"/project-management/projects",{credentials:"include"}).then(r=>r.ok?r.json():[]),
   isApprover?call("/timesheets?scope=approvals"):Promise.resolve([]),
   call("/project-assignments")
  ]);
  const value=(n:number)=>fetches[n].status==="fulfilled"?(fetches[n] as PromiseFulfilledResult<any>).value:undefined;
  setDaily(value(0)||[]);setPolicy(value(1)||initialPolicy);setShifts(value(2)||[]);
  setRosters(value(3)||[]);setRequests(value(4)||[]);setApprovals(value(5)||[]);
  setTimesheets(value(6)||[]);setStaff(value(7)||[]);setProjectOptions(value(8)||[]);
  setTimesheetApprovals(value(9)||[]);setProjectAssignments(value(10)||[]);
 },[call,api,isHR,isApprover]);
 useEffect(()=>{void load()},[load]);
 function clear(){setError("");setErrorField("");setNotice("")}
 function showError(err:unknown,field?:string){
  const e=err as Error&{field?:string};setError(e.message||"Please check the highlighted field.");
  setErrorField(e.field||field||"");requestAnimationFrame(()=>focusRef.current?.querySelector<HTMLElement>(
   e.field?'[name="'+e.field+'"]':'[aria-invalid="true"]')?.focus());
 }
 async function execute(run:()=>Promise<unknown>,success:string){
  clear();setBusy(true);
  try{await run();setNotice(success);await load()}catch(e){showError(e)}finally{setBusy(false)}
 }
 const requestOptions=[["wfh","Work from home"],["on_duty","Official work outside office"],["regularization","Missed punch correction"],
   ["overtime","Overtime"],["shift_swap","Shift swap"]];
 async function submitRequest(e:React.FormEvent){
  e.preventDefault();
  if(requestForm.reason.trim().length<10){setError("Please explain this request (10+ characters).");setErrorField("reason");return}
  let proposedIn:string|null=null;
  let proposedOut:string|null=null;
  if(requestForm.kind==="regularization"){
   try{
    proposedIn=zonedLocalToIso(requestForm.proposed_in,requestZone);
    proposedOut=zonedLocalToIso(requestForm.proposed_out,requestZone);
    if(Date.parse(proposedOut)<=Date.parse(proposedIn))throw Error("Punch-out must be later than punch-in.");
   }catch(err){showError(err,"proposed_in");return}
  }
  await execute(()=>call("/requests","POST",{
    kind:requestForm.kind,work_date:requestForm.work_date,end_date:requestForm.end_date||null,
    reason:requestForm.reason,hours:requestForm.hours===""?null:Number(requestForm.hours),
    target_employee_id:requestForm.target_employee_id?Number(requestForm.target_employee_id):null,
    proposed_in:proposedIn,
    proposed_out:proposedOut
   }),"Request sent to your reporting manager for review.");
 }
 async function punchGPS(){
  clear();setBusy(true);
  try{
   if(!navigator.geolocation){throw Object.assign(new Error("GPS is not available on this device."),{field:"location"})}
   const coordinates=await new Promise<GeolocationPosition>((resolve,reject)=>
    navigator.geolocation.getCurrentPosition(resolve,reject,{enableHighAccuracy:true,timeout:15000,maximumAge:0}));
   await call("/punch","POST",{lat:coordinates.coords.latitude,lon:coordinates.coords.longitude,
     accuracy_m:coordinates.coords.accuracy,consent:true});
   setValidatedGeo(true);setNotice("GPS attendance recorded.");await load();
  }catch(e){showError(e,"location")}finally{setBusy(false)}
 }
 return <div className="time-workspace" ref={focusRef}>
  <div className="time-intro"><div><h2>Time & attendance</h2><p>Shifts, requests, overtime, work from home and timesheets, all in one place.</p></div></div>
  <div className="time-tabs" role="tablist" aria-label="Time and attendance sections">
   {([
      {id:"today" as Tab,label:"Attendance",Icon:Clock3},
      {id:"requests" as Tab,label:"Requests",Icon:FileClock},
      {id:"shifts" as Tab,label:"Shifts & roster",Icon:Users},
      {id:"timesheets" as Tab,label:"Timesheets",Icon:BriefcaseBusiness},
      ...(isHR?[{id:"policies" as Tab,label:"Rules & GPS",Icon:Settings2}]:[])
     ]).map(({id,label,Icon})=>
    <button role="tab" aria-selected={tab===id} className={tab===id?"active":""} key={id} onClick={()=>{setTab(id);clear()}}><Icon size={16}/>{label}</button>)}
  </div>
  {error&&<div className="time-form-error" role="alert"><AlertCircle size={17}/><div><strong>Check the highlighted field</strong><p>{error}</p></div></div>}
  {notice&&<FeedbackMotion type={notice==="Request approved."?"congrats":"success"} compact message={notice}/>}
  {busy&&<FeedbackMotion type="loading" compact message="Saving your changes…"/>}

  {tab==="today"&&<div className="time-columns">
   <section className="employee-surface"><h3>Check in / check out</h3><p className="muted">One active attendance session per employee. Every punch is tracked.</p>
    {policy.geo_required?<div className="time-geo"><MapPin size={18}/><p>Office GPS attendance is required. Your browser asks for location only when you press the button; no continuous tracking.</p><button className="employee-primary" disabled={busy} onClick={punchGPS}>Verify location & punch</button>{validatedGeo&&<span>Location verified for the last punch</span>}</div>
    :<PunchControl api={api} onChanged={()=>{setNotice("Attendance recorded successfully.");void load()}}/>}
    <p className="field-help">Mobile web browsers are supported. Biometric imports require a separately configured device integration.</p>
   </section>
   <section className="employee-surface"><h3>Daily attendance summary</h3><p className="muted">Late / half-day flags are preliminary classifications, not automatic salary deductions.</p>
    <div className="time-day-list">{daily.length?daily.slice(0,20).map(d=><div key={d.date}><strong>{d.date}</strong><span>{d.sessions} sessions · {d.hours}h{d.overtime_hours>0?" · OT "+d.overtime_hours+"h":""}</span><small>{d.open?"On shift":d.late?"Late mark":d.half_day?"Half day":"Complete"}</small></div>):<p>No punch sessions yet.</p>}</div>
   </section>
  </div>}

  {tab==="requests"&&<div className="time-columns">
   <section className="employee-surface"><h3>Submit a time request</h3>
    <form className="time-form" onSubmit={submitRequest} noValidate>
     <label>Request type<select name="kind" value={requestForm.kind} onChange={e=>setRequestForm(v=>({...v,kind:e.target.value}))}>{requestOptions.map(([id,label])=><option key={id} value={id}>{label}</option>)}</select></label>
     <p className="time-request-description wide">{requestForm.kind==="on_duty"?"Use this when your manager sends you to a client site or another approved work location. This is not a normal office punch.":requestForm.kind==="wfh"?"Request approval to work remotely from home.":requestForm.kind==="regularization"?"Correct a missing or incorrect attendance punch; choose the timezone where you worked.":requestForm.kind==="overtime"?"Request approval for extra working hours.":"Request to exchange an assigned shift with a colleague."}</p>
     <label>Work date<input name="work_date" type="date" required value={requestForm.work_date} onChange={e=>setRequestForm(v=>({...v,work_date:e.target.value}))}/></label>
     {["wfh","on_duty"].includes(requestForm.kind)&&<label>End date (optional)<input name="end_date" type="date" min={requestForm.work_date} value={requestForm.end_date} onChange={e=>setRequestForm(v=>({...v,end_date:e.target.value}))}/></label>}
     {requestForm.kind==="overtime"&&<label>Overtime hours<input name="hours" type="number" min=".25" max="24" step=".25" required aria-invalid={errorField==="hours"} value={requestForm.hours} onChange={e=>setRequestForm(v=>({...v,hours:e.target.value}))}/></label>}
     {requestForm.kind==="regularization"&&<><label>Time zone (daylight saving automatic)<select name="timezone" value={requestZone} onChange={e=>setRequestZone(e.target.value)}>{TIME_ZONES.map(([id,label])=><option key={id} value={id}>{label}</option>)}</select><small className="time-hint">Choose the work location, not your laptop clock. EST/EDT and CST/CDT change automatically by date.</small></label><label>Corrected punch-in<input name="proposed_in" type="datetime-local" required aria-invalid={errorField==="proposed_in"} value={requestForm.proposed_in} onChange={e=>setRequestForm(v=>({...v,proposed_in:e.target.value}))}/></label><label>Corrected punch-out<input name="proposed_out" type="datetime-local" required aria-invalid={errorField==="proposed_out"} value={requestForm.proposed_out} onChange={e=>setRequestForm(v=>({...v,proposed_out:e.target.value}))}/></label></>}
     {requestForm.kind==="shift_swap"&&<label>Colleague's employee ID<input name="target_employee_id" type="number" min="1" required value={requestForm.target_employee_id} onChange={e=>setRequestForm(v=>({...v,target_employee_id:e.target.value}))}/></label>}
     <label className="wide">Reason <span className="required">*</span><textarea name="reason" required minLength={10} maxLength={1000} rows={3} aria-invalid={errorField==="reason"} value={requestForm.reason} onChange={e=>setRequestForm(v=>({...v,reason:e.target.value}))} placeholder="Why is this request needed?"/></label>
     <button className="employee-primary" disabled={busy}>Send for manager approval</button>
    </form>
   </section>
   <section className="employee-surface"><h3>My requests</h3><div className="time-list">{requests.length?requests.map(r=><div key={r.id}><strong>{kindName(r.kind)}</strong><span>{r.work_date} · {r.reason}</span><small className={"time-state "+r.status}>{r.status}</small></div>):<p>No requests submitted.</p>}</div>
    {requests.filter(r=>r.kind==="shift_swap"&&r.target_employee_id===user.id&&r.status==="pending_colleague").map(r=><div className="time-swap-consent" key={r.id}><strong>Shift swap invitation</strong><p>Employee #{r.employee_id} requests a shift swap on {r.work_date}.</p><div className="time-row-actions"><button className="employee-primary" onClick={()=>void execute(()=>call("/requests/"+r.id+"/colleague-response?accept=true","POST"),"Colleague swap accepted; sent to manager.")}>Accept swap</button><button className="employee-cancel" onClick={()=>void execute(()=>call("/requests/"+r.id+"/colleague-response?accept=false","POST"),"Shift swap declined.")}>Decline</button></div></div>)}
    {isApprover&&<><h3>Awaiting my review</h3><div className="time-list">{approvals.length?approvals.filter(r=>r.employee_id!==user.id).map(r=><div key={r.id}><strong>{kindName(r.kind)} · Employee #{r.employee_id}</strong><span>{r.work_date} · {r.reason}</span><div className="time-row-actions"><button className="employee-primary" disabled={busy} onClick={()=>void execute(()=>call("/requests/"+r.id+"/review?approve=true","POST"),"Request approved.")}>Approve</button><button className="employee-cancel" disabled={busy} onClick={()=>void execute(()=>call("/requests/"+r.id+"/review?approve=false","POST"),"Request rejected.")}>Reject</button></div></div>):<p>No approvals pending.</p>}</div></>}
   </section>
  </div>}

  {tab==="shifts"&&<div className="time-columns">
   <section className="employee-surface"><h3>Shift templates</h3>
    {isHR&&<form className="time-form" onSubmit={e=>{e.preventDefault();void execute(()=>call("/shifts","POST",{...shiftForm,break_minutes:Number(shiftForm.break_minutes)}),"Shift added.")}}>
     <label>Shift name<input name="name" required minLength={2} value={shiftForm.name} onChange={e=>setShiftForm(v=>({...v,name:e.target.value}))}/></label>
     <label>Start<input name="start_time" type="time" required value={shiftForm.start_time} onChange={e=>setShiftForm(v=>({...v,start_time:e.target.value}))}/></label>
     <label>End<input name="end_time" type="time" required value={shiftForm.end_time} onChange={e=>setShiftForm(v=>({...v,end_time:e.target.value}))}/></label>
     <label>Break minutes<input name="break_minutes" type="number" min="0" max="240" value={shiftForm.break_minutes} onChange={e=>setShiftForm(v=>({...v,break_minutes:e.target.value}))}/></label>
     <label>Shift time zone<select name="timezone" value={shiftForm.timezone} onChange={e=>setShiftForm(v=>({...v,timezone:e.target.value}))}>{TIME_ZONES.map(([id,label])=><option key={id} value={id}>{label}</option>)}</select><small className="time-hint">Shift hours are local to this zone; daylight saving is automatic.</small></label>
     <button className="employee-primary" disabled={busy}>Create shift</button>
    </form>}
    <div className="time-list">{shifts.length?shifts.map(s=><div key={s.id}><strong>{s.name}</strong><span>{s.start_time}–{s.end_time} · {s.break_minutes} min break · {TIME_ZONES.find(([id])=>id===s.timezone)?.[1]||s.timezone||"India (IST)"}</span></div>):<p>No shifts configured.</p>}</div>
   </section>
   <section className="employee-surface"><h3>{isHR?"Assign a roster":"My roster"}</h3>
    {isHR&&<form className="time-form" onSubmit={e=>{e.preventDefault();void execute(()=>call("/roster","PUT",{employee_id:Number(rosterForm.employee_id),shift_id:Number(rosterForm.shift_id),work_date:rosterForm.work_date}),"Roster saved.")}}>
     <label>Employee<select name="employee_id" required value={rosterForm.employee_id} onChange={e=>setRosterForm(v=>({...v,employee_id:e.target.value}))}><option value="">Select an employee</option>{staff.filter(e=>e.status==="active").map(e=><option key={e.id} value={e.id}>{e.name}</option>)}</select></label>
     <label>Shift<select name="shift_id" required value={rosterForm.shift_id} onChange={e=>setRosterForm(v=>({...v,shift_id:e.target.value}))}><option value="">Select a shift</option>{shifts.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
     <label>Work date<input name="work_date" type="date" value={rosterForm.work_date} onChange={e=>setRosterForm(v=>({...v,work_date:e.target.value}))}/></label>
     <button className="employee-primary" disabled={busy}>Assign shift</button>
    </form>}
    <div className="time-list">{rosters.map(r=><div key={r.id}><strong>{r.work_date}</strong><span>{r.shift_name} · {TIME_ZONES.find(([id])=>id===r.timezone)?.[1]||r.timezone||"India (IST)"}</span></div>)}{!rosters.length&&<p>No roster assigned for your account.</p>}</div>
   </section>
  </div>}

  {tab==="timesheets"&&<div className="time-columns timesheet-workspace-grid">
   <section className="employee-surface timesheet-log-card"><h3>Log work hours</h3><form className="time-form" onSubmit={e=>{e.preventDefault();void execute(async()=>{
     const body={...timeForm,hours:Number(timeForm.hours),project_id:timeForm.project_id?Number(timeForm.project_id):null};
     await call(editingTimesheetId?"/timesheets/"+editingTimesheetId:"/timesheets",editingTimesheetId?"PUT":"POST",body);
     setEditingTimesheetId(null);setTimeForm({work_date:today(),task:"",hours:"",project_id:"",note:""});
    },editingTimesheetId?"Timesheet draft updated. Submit it when ready.":"Timesheet entry saved.")}}>
    <label>Work date<input type="date" name="work_date" value={timeForm.work_date} onChange={e=>setTimeForm(v=>({...v,work_date:e.target.value}))}/></label>
    <label>Project (optional)<select name="project_id" value={timeForm.project_id} onChange={e=>setTimeForm(v=>({...v,project_id:e.target.value}))}><option value="">Internal / unassigned task</option>{projectOptions.filter(p=>isHR||p.sourced_by_id===user.id||
      projectAssignments.some(a=>a.project_id===p.id&&a.employee_id===user.id&&a.active))
      .map(p=><option value={p.id} key={p.id}>{p.name}</option>)}</select></label>
    <label><span className="field-label-line">Task <span className="required" aria-hidden="true">*</span></span><input name="task" required minLength={3} aria-invalid={errorField==="task"} value={timeForm.task} onChange={e=>setTimeForm(v=>({...v,task:e.target.value}))} placeholder="e.g. QA review / Sprint planning"/></label>
    <label><span className="field-label-line">Hours <span className="required" aria-hidden="true">*</span></span><input name="hours" required min=".25" max="24" step=".25" type="number" aria-invalid={errorField==="hours"} value={timeForm.hours} onChange={e=>setTimeForm(v=>({...v,hours:e.target.value}))}/></label>
    <label className="wide">Notes <span className="field-optional">(optional)</span><textarea rows={3} maxLength={1000} value={timeForm.note} onChange={e=>setTimeForm(v=>({...v,note:e.target.value}))}/></label>
    <div className="time-form-actions wide"><button className="employee-primary" disabled={busy}>{editingTimesheetId?"Update draft timesheet":"Save hours"}</button>
    {editingTimesheetId&&<button type="button" className="employee-cancel" onClick={()=>{
      setEditingTimesheetId(null);setTimeForm({work_date:today(),task:"",hours:"",project_id:"",note:""});
    }}>Cancel editing</button>}</div>
   </form></section>
   <section className="employee-surface timesheet-entries-card"><h3>My time entries</h3><div className="time-list">{timesheets.length?timesheets.map(t=><div key={t.id}><strong>{t.task} · {t.hours}h</strong><span>{t.work_date} · {t.note||"No notes"}</span><small>{t.status}</small>{(t.status==="draft"||t.status==="rejected")&&<button className="employee-cancel" disabled={busy}
    onClick={()=>{setTimeForm({work_date:t.work_date,task:t.task,hours:String(t.hours),project_id:String(t.project_id||""),note:t.note||""});
     setEditingTimesheetId(t.id);
     if(t.status==="rejected")setNotice("Update the rejected timesheet draft, then submit it again.");}}>
    Edit details</button>}
    {t.status==="draft"&&<button className="employee-cancel" disabled={busy} onClick={()=>void execute(()=>call("/timesheets/"+t.id+"/submit","POST"),"Timesheet submitted to manager/HR for approval.")}>Submit</button>}</div>):<div className="timesheet-empty-state"><strong>No time entries yet</strong><p>Saved work hours will appear here. You can edit drafts and submit them for review.</p></div>}</div></section>
   {isApprover&&<section className="employee-surface timesheet-review-card"><h3>Timesheets awaiting review</h3>
    <p className="field-help">Only approved hours can be included in verified project billing. Approval requires a specific reason.</p>
    <div className="time-list">{timesheetApprovals.map(t=><div key={t.id}>
     <strong>{t.task} · {t.hours}h · Employee #{t.employee_id}</strong>
     <span>{t.work_date} · Project #{t.project_id||"Internal"}</span>
     <button disabled={busy} className="employee-primary" onClick={()=>{
      const reason=window.prompt("Reason for approving these hours (at least 10 characters)");
      if(reason?.trim()&&reason.trim().length>=10)void execute(()=>call("/timesheets/"+t.id+"/review","POST",
       {approve:true,reason:reason.trim()}),"Timesheet approved for billing review.");
      else if(reason!==null)setError("Provide a review reason with at least 10 characters.");
     }}>Approve hours</button>
     <button disabled={busy} className="employee-cancel" onClick={()=>{
      const reason=window.prompt("Reason for rejecting these hours (at least 10 characters)");
      if(reason?.trim()&&reason.trim().length>=10)void execute(()=>call("/timesheets/"+t.id+"/review","POST",
       {approve:false,reason:reason.trim()}),"Timesheet rejected and returned for correction.");
      else if(reason!==null)setError("Provide a rejection reason with at least 10 characters.");
     }}>Reject</button>
    </div>)}{!timesheetApprovals.length&&<div className="timesheet-empty-state"><strong>All caught up</strong><p>Submitted timesheets that need your approval will appear here.</p></div>}</div>
   </section>}
   {isHR&&<section className="employee-surface timesheet-assignments-card"><h3>Project assignments</h3>
    <p className="field-help">Assign employees to client projects so they can submit billable work hours.</p>
    <form className="time-form" onSubmit={e=>{e.preventDefault();void execute(()=>call("/project-assignments","PUT",
      {employee_id:Number(assignmentEmployee),project_id:Number(assignmentProject),active:true}),
      "Employee assigned to project.")}}>
     <label>Employee<select required value={assignmentEmployee} onChange={e=>setAssignmentEmployee(e.target.value)}>
      <option value="">Select employee</option>{staff.map(x=><option value={x.id} key={x.id}>{x.name}</option>)}
     </select></label>
     <label>Project<select required value={assignmentProject} onChange={e=>setAssignmentProject(e.target.value)}>
      <option value="">Select project</option>{projectOptions.map(x=><option value={x.id} key={x.id}>{x.name}</option>)}
     </select></label>
     <button className="employee-primary" disabled={busy||!assignmentEmployee||!assignmentProject}>Assign employee</button>
    </form>
    {projectAssignments.map(a=><div key={a.employee_id+"-"+a.project_id} className="ops-row">
     <span>Employee #{a.employee_id} · Project #{a.project_id} · {a.active?"Assigned":"Inactive"}</span>
     {a.active&&<button className="employee-cancel" disabled={busy}
      onClick={()=>void execute(()=>call("/project-assignments","PUT",{
       employee_id:a.employee_id,project_id:a.project_id,active:false}),"Project assignment deactivated.")}>Remove</button>}
    </div>)}
   </section>}
  </div>}

  {tab==="policies"&&isHR&&<section className="employee-surface"><h3>Attendance and GPS rules</h3><p className="muted">Set attendance thresholds and optionally verify office punches happen near your office. These rules do not automatically deduct salary.</p>
   <form className="time-form policy" onSubmit={e=>{e.preventDefault();void execute(()=>call("/policy","PUT",{
    ...policy,office_lat:policy.office_lat===""?null:Number(policy.office_lat),
    office_lon:policy.office_lon===""?null:Number(policy.office_lon),
    grace_minutes:Number(policy.grace_minutes),half_day_under_hours:Number(policy.half_day_under_hours),
    overtime_after_hours:Number(policy.overtime_after_hours),radius_meters:Number(policy.radius_meters)
   }),"Attendance rules saved.")}}>
    {([["grace_minutes","Late grace (minutes)"],["half_day_under_hours","Half-day below hours"],["overtime_after_hours","Overtime threshold (hours)"],["radius_meters","Office radius (meters)"]] as const).map(([key,label])=><label key={key}>{label}<input type="number" name={key} min="0" required value={policy[key]??""} onChange={e=>setPolicy(v=>({...v,[key]:e.target.value}))}/></label>)}
    <div className="time-gps-setup wide"><label className="time-check"><input type="checkbox" checked={Boolean(policy.geo_required)} onChange={e=>setPolicy(v=>({...v,geo_required:e.target.checked}))}/> Verify office location when punching in/out</label><button type="button" className="time-help-trigger" title="When enabled, employees must share their device location. HR sets the office location and permitted distance. GPS accuracy can vary indoors." onClick={()=>setGeoHelp(v=>!v)}>What does this do?</button>{geoHelp&&<p className="time-hint">Employees must allow location access when punching in or out. The system checks that they are near the office. Remote work uses an approved time request instead.</p>}</div>
    {policy.geo_required&&<div className="time-gps-location wide"><div><strong>Where is your office?</strong><p className="time-hint">While at the office, choose “Use my current location”. Otherwise copy the coordinates from a map service. Hover over either field for an explanation.</p></div><div className="time-gps-fields"><label title="Latitude is the north/south coordinate, between -90 and 90. Example: 40.7128.">Latitude (north / south)<input name="office_lat" type="number" min="-90" max="90" step="any" required aria-invalid={errorField==="office_lat"} placeholder="e.g. 40.7128" value={policy.office_lat??""} onChange={e=>setPolicy(v=>({...v,office_lat:e.target.value}))}/></label><label title="Longitude is the east/west coordinate, between -180 and 180. Example: -74.0060.">Longitude (east / west)<input name="office_lon" type="number" min="-180" max="180" step="any" required aria-invalid={errorField==="office_lon"} placeholder="e.g. -74.0060" value={policy.office_lon??""} onChange={e=>setPolicy(v=>({...v,office_lon:e.target.value}))}/></label></div><button type="button" className="employee-cancel" disabled={geoLocating} onClick={()=>{if(!navigator.geolocation){showError(new Error("Your browser does not support GPS location."));return}setGeoLocating(true);navigator.geolocation.getCurrentPosition(p=>{setPolicy(v=>({...v,office_lat:String(p.coords.latitude),office_lon:String(p.coords.longitude)}));setGeoLocating(false);setNotice("Office coordinates filled from your current location. Review and save the rules.");},()=>{setGeoLocating(false);showError(new Error("Could not get your location. Allow location access or enter the office coordinates manually."))},{enableHighAccuracy:true,timeout:15000})}}>{geoLocating?"Locating…":"Use my current location"}</button></div>}
    <label className="time-check wide"><input type="checkbox" checked={Boolean(policy.auto_deduct)} onChange={e=>setPolicy(v=>({...v,auto_deduct:e.target.checked}))}/> Record intended auto-deduction policy (not wired to payroll)</label>
    <div className="time-form-actions wide"><button className="employee-primary" disabled={busy}>Save attendance rules</button></div>
   </form>
   <p className="field-help">The biometric endpoint accepts signed, idempotent vendor events if you configure HRMS_BIOMETRIC_SHARED_TOKEN. Vendor mapping/reconciliation remains a separate integration.</p>
  </section>}
 </div>;
}
