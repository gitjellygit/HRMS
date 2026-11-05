"use client";
import { useEffect, useState } from "react";
import Login from "./Login";
import {explainError} from "./formErrors";
import EmployeeManagement from "./EmployeeManagement";
import CoreWorkspace from "./CoreWorkspace";
import HRDesk from "./HRDesk";
import LeaveWorkspace from "./LeaveWorkspace";
import ProjectsManagement from "./ProjectsManagement";
import PunchControl from "./PunchControl";
import BonusSummary from "./BonusSummary";
import CompanyPolicies from "./CompanyPolicies";
import AttendanceByDay from "./AttendanceByDay";
import ChangePassword from "./ChangePassword";
import RoleOverview from "./RoleOverview";
import NotificationCenter from "./NotificationCenter";
import TimeWorkspace from "./TimeWorkspace";
import PayrollWorkspace from "./PayrollWorkspace";
import FinanceWorkspace from "./FinanceWorkspace";
import GovernancePanel from "./GovernancePanel";
import PeopleOpsWorkspace from "./PeopleOpsWorkspace";
import PerformanceWorkspace from "./PerformanceWorkspace";
import { LayoutDashboard, Bell, Users, Clock3, CalendarDays, BriefcaseBusiness, Wallet, Award, LogOut, GitBranch, Building2, UserRound, ShieldCheck, FileDown, ClipboardList, Settings2 } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
type Employee = { id:number; name:string; email:string; role:string; designation:string; department:string; joining_date:string; status:string };
type User = Employee & {must_change_password?:boolean};
type Entry = Record<string, any>;
const sections = [
  { id:"dashboard",label:"Overview",Icon:LayoutDashboard },
  { id:"notifications",label:"Notifications",Icon:Bell },
  { id:"employees",label:"Employees",Icon:Users },
  { id:"attendance",label:"Attendance",Icon:Clock3 },
  { id:"time",label:"Time & shifts",Icon:FileDown },
  { id:"payroll",label:"Payroll & expenses",Icon:Wallet },
  { id:"finance",label:"Finance & invoicing",Icon:Wallet },
  { id:"governance",label:"Admin approvals",Icon:ShieldCheck },
  { id:"people",label:"People operations",Icon:ClipboardList },
  { id:"leaves",label:"Leave requests",Icon:CalendarDays },
  { id:"projects",label:"Projects",Icon:BriefcaseBusiness },
  { id:"bonuses",label:"Bonuses",Icon:Wallet },
  { id:"appraisals",label:"Appraisals",Icon:Award },
  { id:"performance",label:"Performance & growth",Icon:Award },
  { id:"hrdesk",label:"HR overview",Icon:ClipboardList },
  { id:"policies",label:"Policies",Icon:Settings2 },
  { id:"organization",label:"Organization",Icon:Building2 },
  { id:"orgchart",label:"Org chart",Icon:GitBranch },
  { id:"profile",label:"My profile",Icon:UserRound },
  { id:"approvals",label:"Profile requests",Icon:ShieldCheck },
  { id:"bulk",label:"Bulk data & expiries",Icon:FileDown },
];
export default function Home() {
  const [ready,setReady] = useState(false);
  const [user,setUser] = useState<User|null>(null);
  const [section,setSection] = useState("dashboard");
  const [selectedEmployeeId,setSelectedEmployeeId] = useState<number|null>(null);
  const [rows,setRows] = useState<Entry[]>([]);
  const [employees,setEmployees] = useState<Employee[]>([]);
  const [stats,setStats] = useState<Entry>({});
  const [form,setForm] = useState(false);
  const [fields,setFields] = useState<Entry>({});
  const [error,setError] = useState("");
  const [loading,setLoading] = useState(false);
  const [passwordNotice,setPasswordNotice]=useState("");
  const [theme,setTheme]=useState<"light"|"dark">("light");
  const [profileMenu,setProfileMenu]=useState(false);
  const [success,setSuccess]=useState("");
  const [hasPhoto,setHasPhoto]=useState(false);
  const [avatarVersion,setAvatarVersion]=useState(0);
  const [attendanceVersion,setAttendanceVersion]=useState(0);
  const canHR = user?.role === "super_admin" || user?.role === "admin" || user?.role === "hr";
  const canFinance = canHR || user?.role === "accountant";
  const canSeeEmployees = canFinance;
  const visible = sections.filter(s=>{
    if(["employees","bonuses"].includes(s.id)&&!canSeeEmployees)return false;
    if(s.id==="finance"&&!canFinance)return false;
    if(s.id==="governance"&&!canHR)return false;
    if(["organization","bulk","hrdesk"].includes(s.id)&&!canHR)return false;
    if(s.id==="approvals"&&!canHR)return false;
    return true;
  });
  async function request(path:string,method="GET",body?:Entry) {
    const response = await fetch(API+path,{method,credentials:"include",headers:{"Content-Type":"application/json"},body:body?JSON.stringify(body):undefined});
    if(!response.ok){ const detail=await response.json().catch(()=>null); throw Error(explainError(detail,response.status)); }
    return response.json();
  }
  useEffect(()=>{const stored=localStorage.getItem("jellygit-theme");const selected=stored==="dark"?"dark":"light";setTheme(selected);document.documentElement.dataset.theme=selected},[]);
  function changeTheme(next:"light"|"dark"){setTheme(next);document.documentElement.dataset.theme=next;localStorage.setItem("jellygit-theme",next);setProfileMenu(false)}
  async function refresh(id=section) {
    try {
      setError("");
      const data=await request(id==="dashboard"?"/dashboard":"/"+id);
      const people=user && ["super_admin","admin","hr","accountant"].includes(user.role)
        ?await request("/employees").catch(()=>[]) : [];
      if(id==="dashboard")setStats(data);else setRows(data);
      setEmployees(people);
    } catch(e){setError((e as Error).message);}
  }
  useEffect(()=>{request("/me").then(setUser).catch(()=>{}).finally(()=>setReady(true));},[]);
  useEffect(()=>{
    if(!user||user.must_change_password)return;
    fetch(API+"/me/presence",{credentials:"include"}).then(r=>r.ok?r.json():null).then(v=>{if(v){setHasPhoto(v.has_photo)}}).catch(()=>{});
  },[user]);
  useEffect(()=>{if(user&&!user.must_change_password&&!["organization","orgchart","profile","approvals","bulk","employee-record","hrdesk","leaves","projects","policies","performance","payroll","people","time","finance","governance","notifications"].includes(section))refresh(section);},[user,section]);
  async function logout(){try{await request("/auth/logout","POST");}finally{setUser(null);setRows([]);setSection("dashboard");}}
  async function changePresence(status:string){
   try{await request("/me/presence","PUT",{status});}catch(e){setError((e as Error).message)}
  }
  async function uploadAvatar(file:File|undefined){
   if(!file)return;
   if(file.size>2*1024*1024){setError("Choose a PNG/JPEG image under 2 MB.");return}
   const body=new FormData();body.append("photo",file);
   try{
    const response=await fetch(API+"/me/photo",{method:"POST",credentials:"include",body});
    if(!response.ok)throw Error("Could not upload profile photo.");
    setHasPhoto(true);setAvatarVersion(v=>v+1);
   }catch(e){setError((e as Error).message)}
  }
  function completePasswordChange(){
   setPasswordNotice("Password successfully changed. Please sign in again using your new password.");
   setUser(null);setRows([]);setSection("dashboard");
  }
  async function submit(e:React.FormEvent<HTMLFormElement>){
    e.preventDefault();setLoading(true);setError("");
    const fd=new FormData(e.currentTarget);const data=Object.fromEntries(fd.entries());
    try {
      if(section==="bonuses"&&!/^\\d{4}-(0[1-9]|1[0-2])$/.test(String(data.period||""))){
       setError("Period (YYYY-MM): enter a complete year and month, such as 2026-11. You entered "+(data.period||"an empty value")+".");
       document.querySelector<HTMLInputElement>('input[name="period"]')?.focus();return;
      }
      if(section==="bonuses"&&(!Number.isFinite(Number(data.amount))||Number(data.amount)<=0)){
       setError("Amount (INR): enter a number greater than zero.");return;
      }
      if(section==="leaves"&&String(data.end_date)<String(data.start_date)){
       setError("Leave end date: choose a date on or after the leave start date.");return;
      }
      const endpoint=section==="leaves"?"/leaves":section==="employees"?"/employees":section==="projects"?"/projects":section==="bonuses"?"/bonuses":"/appraisals";
      const upload=fd.get("document");
      delete data.document;
      const result=await request(endpoint,"POST",data);
      if(section==="employees" && upload instanceof File && upload.size>0){
        const payload=new FormData();payload.set("document",upload);
        const response=await fetch(API+"/employees/"+result.id+"/documents",{method:"POST",credentials:"include",body:payload});
        if(!response.ok){setError("Employee created but document upload failed. Please retry the upload.");setForm(false);await refresh();return;}
      }
      setForm(false);setFields({});await refresh();setSuccess("Saved successfully. Your record has been added.");
    }catch(err){setError((err as Error).message)}finally{setLoading(false)}
  }
  async function action(path:string,body?:Entry){
    setLoading(true);setError("");
    try{await request(path,body?"PATCH":"POST",body);await refresh();setSuccess("Action completed successfully.");}catch(err){setError((err as Error).message)}finally{setLoading(false)}
  }
  const names:Record<string,string> = Object.fromEntries(employees.map(e=>[String(e.id),e.name]));
  const formMap:Record<string,[string,string,string?][]> = {
    employees:[["name","Full name"],["email","Work email","email"],["password","Temporary password (12+ characters)","password"],["role","Role","role"],["designation","Designation"],["department","Department"],["phone","Phone"],["joining_date","Joining date","date"],["employee_code","Employee ID"],["work_location","Work location"],["employment_type","Employment type"],["manager_name","Reporting manager"],["emergency_contact","Emergency contact"]],
    leaves:[["leave_type","Leave type","leave"],["start_date","From","date"],["end_date","To","date"],["reason","Reason"]],
    projects:[["name","Project name"],["client","Client"],["description","Description"]],
    bonuses:[["employee_id","Employee","employee"],["amount","Amount (INR)","number"],["period","Period (YYYY-MM)"],["reason","Reason"]],
    appraisals:[["employee_id","Employee","employee"],["period","Review period"],["rating","Rating (1–5)","rating"],["feedback","Feedback"]]
  };
  const headings:Record<string,string[]> = {
    employees:["Name","Email","Department","Designation","Role","Status","Documents"],
    attendance:["Employee","Punch in","Punch out","Hours"],
    leaves:["Employee","Type","From","To","Status","Action"],
    projects:["Project","Client","Status"],
    bonuses:["Employee","Period","Amount","Reason","Status","Action"],
    appraisals:["Employee","Period","Rating","Feedback"]
  };
  function humanDate(value?:string){return value?new Date(value).toLocaleString("en-IN",{dateStyle:"medium",timeStyle:"short"}):"—"}
  function cell(row:Entry,key:string){
    if(key==="Documents"&&!canHR)return "—";
    if(key==="Documents")return <button className="secondary" onClick={async()=>{
      try {
        const docs=await request("/employees/"+row.id+"/documents");
        if(!docs.length){alert("No documents uploaded");return;}
        const choice=docs.length===1?docs[0]:docs[Number(prompt(docs.map((d:Entry,i:number)=>(i+1)+". "+d.name).join("\\n")+"\\nEnter document number:"))-1];
        if(choice)window.open(API+"/documents/"+choice.id,"_blank","noopener,noreferrer");
      }catch(err){setError((err as Error).message)}
    }}>View docs</button>;
    if(key==="Name")return row.name;
    if(key==="Email")return row.email;
    if(key==="Department")return row.department || "—";
    if(key==="Designation")return row.designation || "—";
    if(key==="Role")return row.role;
    if(key==="Employee")return names[String(row.employee_id)]|| (row.employee_id===user?.id?user?.name:"Employee #"+row.employee_id);
    if(key==="Punch in")return humanDate(row.punch_in);
    if(key==="Punch out")return humanDate(row.punch_out);
    if(key==="Hours")return row.punch_out?((new Date(row.punch_out).getTime()-new Date(row.punch_in).getTime())/3600000).toFixed(2):"Working";
    if(key==="Type")return row.leave_type;
    if(key==="From")return row.start_date;
    if(key==="To")return row.end_date;
    if(key==="Action" && section==="leaves" && canHR && row.status==="pending")return <div className="actions"><button className="secondary" onClick={()=>action("/leaves/"+row.id,{status:"approved"})}>Approve</button><button className="secondary" onClick={()=>action("/leaves/"+row.id,{status:"rejected"})}>Reject</button></div>;
    if(key==="Action" && section==="bonuses" && (user?.role==="admin"||user?.role==="accountant") && row.status!=="paid")return <button className="secondary" onClick={()=>action("/bonuses/"+row.id,{status:row.status==="planned"?"approved":"paid"})}>{row.status==="planned"?"Approve":"Mark paid"}</button>;
    if(key==="Status")return <span className={"pill "+row.status}>{row.status}</span>;
    if(key==="Project")return row.name;
    if(key==="Client")return row.client||"—";

    if(key==="Period")return row.period;
    if(key==="Amount")return "₹"+Number(row.amount).toLocaleString("en-IN");
    if(key==="Reason")return row.reason;
    if(key==="Rating")return row.rating+"/5";
    if(key==="Feedback")return row.feedback||"—";
    return "—";
  }
  if(!ready)return <div className="login-wrap">Loading workspace…</div>;
  if(!user)return <Login api={API} onLogin={u=>{setPasswordNotice("");setUser(u)}} initialNotice={passwordNotice}/>;
  if(user.must_change_password)return <ChangePassword api={API} required onComplete={completePasswordChange}/>;
  return <div className="shell"><aside className="sidebar"><div className="brand">Jelly<span>Git</span> HRMS</div><nav className="menu">{visible.map(({id,label,Icon})=><button key={id} onClick={()=>{setSection(id);setForm(false);setError("")}} className={section===id?"active":""}><Icon size={18}/>{label}</button>)}<button onClick={logout}><LogOut size={18}/>Sign out</button></nav></aside><main className="content"><div className="top"><div><h1 className="title">{section==="employee-record"?"Employee master record":sections.find(s=>s.id===section)?.label}</h1><div className="muted">Your team, in one place</div></div><div className="hrms-header-actions"><NotificationCenter api={API} onNavigate={setSection}/><div className="hrms-user-widget">
    <button type="button" className="hrms-profile-trigger" aria-label="Profile and appearance" aria-expanded={profileMenu} onClick={()=>setProfileMenu(v=>!v)}>
      {hasPhoto?<img src={API+"/me/photo?v="+avatarVersion} alt="Profile"/>:<span>{user.name.trim().split(/\\s+/).map(x=>x[0]).slice(0,2).join("").toUpperCase()}</span>}
    </button>
    {profileMenu&&<div className="hrms-profile-menu" role="menu" aria-label="Profile settings">
      <strong>{user.name}</strong><small>{user.role}</small>
      <button type="button" onClick={()=>{setSection("profile");setProfileMenu(false)}}>My profile</button>
      <button type="button" onClick={()=>changeTheme(theme==="light"?"dark":"light")}>{theme==="light"?"Switch to dark mode":"Switch to light mode"}</button>
      <label className="hrms-photo-change">Change profile photo<input type="file" accept="image/png,image/jpeg" onChange={e=>{void uploadAvatar(e.target.files?.[0]);setProfileMenu(false)}}/></label>
    </div>}
    <div className="hrms-user-meta"><strong>{user.name}</strong><small>{user.role}</small></div>
  </div></div></div>{error&&<div className="error" role="alert">{error}</div>}{success&&<div className="app-global-success" role="status">{success}<button type="button" onClick={()=>setSuccess("")} aria-label="Dismiss">×</button></div>}
    {section==="notifications"?<NotificationCenter api={API} viewAll onNavigate={setSection} onBack={()=>setSection("dashboard")}/> :section==="governance"?<GovernancePanel api={API} user={user}/> :section==="finance"?<FinanceWorkspace api={API} user={user}/> :section==="performance"?<PerformanceWorkspace api={API} user={user}/> :section==="payroll"?<PayrollWorkspace api={API} user={user}/> :section==="people"?<PeopleOpsWorkspace api={API} user={user}/> :section==="time"?<TimeWorkspace api={API} user={user}/> :section==="policies"?<CompanyPolicies api={API} user={user}/>:section==="projects"?<ProjectsManagement api={API} canCreate={Boolean(canHR)}/>:section==="leaves"?<LeaveWorkspace api={API} user={user}/>:section==="hrdesk"?<HRDesk api={API}/>:section==="employees"?<EmployeeManagement api={API} canCreate={Boolean(canHR)} currentRole={user.role} onOpenEmployee={id=>{setSelectedEmployeeId(id);setSection("employee-record")}}/>:
    ["employee-record","organization","orgchart","profile","approvals","bulk"].includes(section)?
      <CoreWorkspace api={API} mode={(section==="employee-record"?"profile":section==="organization"?"organization":section==="orgchart"?"orgchart":section==="profile"?"profile":section==="approvals"?"approvals":"bulk")}
        user={user as any} employeeId={section==="employee-record"?selectedEmployeeId:null}
        onBack={section==="employee-record"?()=>{setSection("employees");setSelectedEmployeeId(null)}:undefined}
        onPasswordChanged={completePasswordChange}/>:
    section==="dashboard"?<><div className="grid">{[["Team members",stats.employees??"—"],["Active projects",stats.active_projects??0],["Leave approvals",stats.pending_leaves??"—"],["My pending requests",stats.my_pending_leaves??0]].map(([name,value])=><div className="card" key={name}><div className="muted">{name}</div><h3>{value}</h3></div>)}</div><section className="panel"><h2>Quick actions</h2><p className="muted">Punch in or out, submit a leave request, or check your current work.</p><div className="overview-quick-actions"><PunchControl api={API} onChanged={()=>{setAttendanceVersion(v=>v+1);void refresh("dashboard")}}/><div className="overview-shortcuts"><button className="secondary" onClick={()=>{setSection("leaves");setForm(true)}}>Request leave</button><button className="secondary" onClick={()=>setSection("projects")}>View projects</button>{canHR&&<button className="secondary" onClick={()=>setSection("employees")}>Manage employees</button>}</div></div></section><RoleOverview api={API} role={user.role} onNavigate={setSection} refreshKey={attendanceVersion}/><BonusSummary api={API}/>{canSeeEmployees&&<section className="panel"><div className="section-head"><div><h2>Recently added employees</h2><p className="muted" style={{fontSize:13,marginBottom:0}}>Latest employee accounts created in HRMS</p></div><button className="secondary" onClick={()=>setSection("employees")}>View all</button></div>{employees.length?<div className="table-wrap"><table><thead><tr><th>Employee</th><th>ID</th><th>Designation</th><th>Department</th><th>Status</th></tr></thead><tbody>{employees.slice(0,5).map(e=><tr key={e.id}><td><strong>{e.name}</strong><div className="muted" style={{fontSize:12}}>{e.email}</div></td><td>{(e as Employee & {employee_code?:string}).employee_code||"—"}</td><td>{e.designation||"—"}</td><td>{e.department||"—"}</td><td><span className={"pill "+e.status}>{e.status}</span></td></tr>)}</tbody></table></div>:<div className="empty">No employees added yet.</div>}</section>}</>:<section className="panel"><div className="section-head"><h2>{sections.find(s=>s.id===section)?.label}</h2><div className="actions">{section==="attendance"&&<PunchControl api={API} onChanged={()=>refresh("attendance")}/>}{(section==="leaves"|| (canHR && ["employees","projects","bonuses","appraisals"].includes(section)))&&<button className="primary" onClick={()=>setForm(!form)}>{form?"Cancel":"+ Add new"}</button>}</div></div>
    {form&&formMap[section]&&<form className="form" onSubmit={submit} onInvalid={e=>{const field=e.target as HTMLInputElement;setError((field.closest("label")?.textContent||field.name||"Field")+": "+field.validationMessage)}}>{formMap[section].map(([key,label,type])=><label key={key}>{label}{type==="role"?<select name={key} required>{["employee","hr","accountant","admin"].map(r=><option key={r}>{r}</option>)}</select>:type==="leave"?<select name={key} required>{["Annual","Sick","Casual","Unpaid"].map(r=><option key={r}>{r}</option>)}</select>:type==="employee"?<select name={key} required><option value="">Select employee</option>{employees.map(e=><option key={e.id} value={e.id}>{e.name}</option>)}</select>:type==="rating"?<select name={key} required>{[1,2,3,4,5].map(r=><option key={r}>{r}</option>)}</select>:<input name={key} type={key==="phone"||key==="emergency_contact"?"tel":type||"text"} pattern={key==="phone"||key==="emergency_contact"?"[+]?[0-9 ()-]{7,20}":key==="period"?"[0-9]{4}-(0[1-9]|1[0-2])":undefined} maxLength={key==="phone"||key==="emergency_contact"?20:undefined} title={key==="period"?"Use YYYY-MM, for example 2026-11":key==="phone"?"Enter 7–15 digits, optionally with country code":undefined} required={["name","email","password","leave_type","start_date","end_date","employee_id","amount","period","rating"].includes(key)} min={type==="number"?"0.01":undefined} step={type==="number"?"0.01":undefined}/>}</label>)}{section==="employees"&&<label className="wide">Employee document (PDF/JPEG/PNG, max 5 MB)<input type="file" name="document" accept=".pdf,.png,.jpg,.jpeg"/></label>}<button className="primary wide" disabled={loading}>Save</button></form>}
    {section==="attendance"?<AttendanceByDay records={rows as {id:number;employee_id:number;punch_in:string;punch_out:string|null}[]}/>:<div className="table-wrap"><table><thead><tr>{headings[section].map(h=><th key={h}>{h}</th>)}</tr></thead><tbody>{rows.map(row=><tr key={row.id}>{headings[section].map(h=><td key={h}>{cell(row,h)}</td>)}</tr>)}</tbody></table>{rows.length===0&&<div className="empty">No records yet. Add your first record to get started.</div>}</div>}</section>}
  </main></div>;
}
