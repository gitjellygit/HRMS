"use client";
import {useEffect,useMemo,useState} from "react";
import {CalendarDays,ChevronDown,Clock3,RefreshCw,Users} from "lucide-react";
import AppSelect from "./AppSelect";
type Session={id:number;employee_id:number;employee_name:string;punch_in:string;punch_out:string|null};
type Result={items:Session[];has_more:boolean;next_offset:number};
type Range="last7"|"last30"|"last90"|"month"|"previous"|"year"|"lastyear"|"custom";
const localDate=(date:Date)=>[date.getFullYear(),String(date.getMonth()+1).padStart(2,"0"),String(date.getDate()).padStart(2,"0")].join("-");
function dates(which:Range){
 const now=new Date();
 const first=new Date(now.getFullYear(),now.getMonth(),1);
 if(which==="month")return [localDate(first),localDate(now)];
 if(which==="last7")return [localDate(new Date(now.getFullYear(),now.getMonth(),now.getDate()-6)),localDate(now)];
 if(which==="last90")return [localDate(new Date(now.getFullYear(),now.getMonth(),now.getDate()-89)),localDate(now)];
 if(which==="previous")return [localDate(new Date(now.getFullYear(),now.getMonth()-1,1)),localDate(new Date(now.getFullYear(),now.getMonth(),0))];
 if(which==="year")return [localDate(new Date(now.getFullYear(),0,1)),localDate(now)];
 if(which==="lastyear")return [localDate(new Date(now.getFullYear()-1,0,1)),localDate(new Date(now.getFullYear()-1,11,31))];
 return [localDate(new Date(now.getFullYear(),now.getMonth(),now.getDate()-29)),localDate(now)];
}
function attendanceParams(from:string,to:string,offset:number){
 const start=new Date(from+"T00:00:00");
 const nextDay=new Date(to+"T00:00:00");
 nextDay.setDate(nextDay.getDate()+1);
 return new URLSearchParams({
  start_date:from,end_date:to,limit:"150",offset:String(offset),
  start_utc_offset:String(start.getTimezoneOffset()),
  end_utc_offset:String(nextDay.getTimezoneOffset())
 });
}
const duration=(entry:Session)=>entry.punch_out?Math.max(0,(new Date(entry.punch_out).getTime()-new Date(entry.punch_in).getTime())/3600000):null;
const formatTime=(value:string)=>new Date(value).toLocaleTimeString([],{hour:"2-digit",minute:"2-digit"});
export default function TeamAttendanceDashboard({api,staff}:{api:string;staff:{id:number;name:string}[]}){
 const [range,setRange]=useState<Range>("last30");
 const [from,setFrom]=useState(dates("last30")[0]);
 const [to,setTo]=useState(dates("last30")[1]);
 const [person,setPerson]=useState("");
 const [rows,setRows]=useState<Session[]>([]);
 const [hasMore,setHasMore]=useState(false);
 const [offset,setOffset]=useState(0);
 const [loading,setLoading]=useState(false);
 const [error,setError]=useState("");
 const [refresh,setRefresh]=useState(0);
 const [opened,setOpened]=useState<Record<string,boolean>>({});
 function chooseRange(next:Range){setRange(next);if(next!=="custom"){const [a,b]=dates(next);setFrom(a);setTo(b)}}
 const valid=Boolean(from&&to&&from<=to&&(Date.parse(to)-Date.parse(from))/86400000<=366);
 useEffect(()=>{
  if(!valid){setRows([]);setError("Choose a valid date range of 366 days or fewer.");return}
  const abort=new AbortController();
  setLoading(true);setError("");setRows([]);setOffset(0);setHasMore(false);setOpened({});
  const params=attendanceParams(from,to,0);
  if(person)params.set("employee_id",person);
  fetch(api+"/attendance/team?"+params,{credentials:"include",signal:abort.signal})
   .then(async res=>{if(!res.ok){const body=await res.json().catch(()=>({}));throw Error(typeof body.detail==="string"?body.detail:"Could not load team attendance.")}return res.json() as Promise<Result>})
   .then(data=>{if(!abort.signal.aborted){setRows(data.items);setOffset(data.next_offset);setHasMore(data.has_more)}})
   .catch(err=>{if(!abort.signal.aborted)setError((err as Error).message)})
   .finally(()=>{if(!abort.signal.aborted)setLoading(false)});
  return ()=>abort.abort();
 },[api,from,to,person,refresh,valid]);
 async function loadMore(){
  setLoading(true);
  try{
   const params=attendanceParams(from,to,offset);
   if(person)params.set("employee_id",person);
   const res=await fetch(api+"/attendance/team?"+params,{credentials:"include"});
   if(!res.ok)throw Error("Could not load more attendance records.");
   const data=await res.json() as Result;
   setRows(prev=>[...prev,...data.items]);setOffset(data.next_offset);setHasMore(data.has_more);
  }catch(err){setError((err as Error).message)}finally{setLoading(false)}
 }
 const groups=useMemo(()=>{
  const result=new Map<string,Session[]>();
  for(const row of rows){
   const day=localDate(new Date(row.punch_in));
   const key=row.employee_id+"|"+day;
   result.set(key,[...(result.get(key)||[]),row]);
  }
  return Array.from(result.entries());
 },[rows]);
 const checkedIn=new Set(rows.filter(x=>!x.punch_out).map(x=>x.employee_id)).size;
 const completed=rows.filter(x=>x.punch_out);
 const hours=completed.reduce((sum,row)=>sum+(duration(row)||0),0);
 return <section className="jg-team-attendance" aria-label="Team attendance dashboard">
  <header className="jg-team-attendance-heading"><div><h3>Team attendance logs</h3><p>Review actual punch sessions and gross hours. No editing or late-arrival approvals are enabled.</p></div><button type="button" className="employee-cancel" onClick={()=>setRefresh(x=>x+1)} disabled={loading}><RefreshCw size={15}/> Refresh</button></header>
  <div className="jg-team-attendance-stats">
   <div><Users size={18}/><span>Employees in results</span><strong>{new Set(rows.map(x=>x.employee_id)).size}</strong></div>
   <div><Clock3 size={18}/><span>Open punch sessions</span><strong>{checkedIn}</strong></div>
   <div><CalendarDays size={18}/><span>Completed session hours</span><strong>{hours.toFixed(1)} h</strong></div>
  </div>
  <div className="jg-team-attendance-filters">
   <label>Employee<AppSelect aria-label="Filter by employee" value={person} onChange={e=>setPerson(e.target.value)}><option value="">All employees</option>{staff.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</AppSelect></label>
   <label>Date range<AppSelect aria-label="Attendance date range" value={range} onChange={e=>chooseRange(e.target.value as Range)}><option value="last7">Last 7 days</option><option value="last30">Last 30 days</option><option value="last90">Last 90 days</option><option value="month">This month</option><option value="previous">Previous month</option><option value="year">This year</option><option value="lastyear">Last year</option><option value="custom">Custom dates</option></AppSelect></label>
   {range==="custom"&&<><label>From<input type="date" value={from} onChange={e=>setFrom(e.target.value)}/></label><label>To<input type="date" value={to} onChange={e=>setTo(e.target.value)}/></label></>}
  </div>
  <p className="field-help">Dates and times use your browser's time zone, including daylight-saving changes. Gross hours use completed punch sessions; effective hours need reliable break/active-time records.</p>
  {error&&<div className="error" role="alert">{error}</div>}
  {loading&&rows.length===0?<div role="status" className="jg-team-attendance-empty">Loading attendance records…</div>:groups.length===0?<div className="jg-team-attendance-empty">No attendance sessions found for these filters.</div>:
   <div className="jg-team-attendance-log">{groups.map(([key,items])=>{
    const day=key.split("|")[1];
    const gross=items.reduce((sum,row)=>sum+(duration(row)||0),0);
    const active=items.some(row=>!row.punch_out);
    const expanded=opened[key]??false;
    return <div key={key} className="jg-team-attendance-day">
     <button type="button" className="jg-team-attendance-toggle" aria-expanded={expanded} onClick={()=>setOpened(prev=>({...prev,[key]:!expanded}))}><ChevronDown size={17} className={expanded?"is-open":""}/>
      <span className="jg-attendance-name">{items[0].employee_name}<small>{new Date(day+"T12:00:00").toLocaleDateString([],{weekday:"short",day:"numeric",month:"short",year:"numeric"})}</small></span>
      <span className="jg-attendance-hours">{gross.toFixed(2)} gross hours</span>
      <span className={"jg-attendance-status "+(active?"is-active":"")}>{active?"Checked in":"Completed"}</span>
     </button>
     {expanded&&<div className="jg-team-attendance-detail"><div className="jg-attendance-timeline" aria-hidden="true"><span style={{width:active?"45%":"80%"}}/></div>
      <div className="jg-attendance-session-scroll"><table><thead><tr><th>Arrival</th><th>Departure</th><th>Gross hours</th><th>Effective hours</th></tr></thead><tbody>{items.map(row=><tr key={row.id}><td>{formatTime(row.punch_in)}</td><td>{row.punch_out?formatTime(row.punch_out):"Working now"}</td><td>{duration(row)?.toFixed(2)??"In progress"}</td><td>Not tracked</td></tr>)}</tbody></table></div>
     </div>}
    </div>;
   })}</div>}
  {hasMore&&<button type="button" className="employee-cancel jg-team-attendance-more" disabled={loading} onClick={()=>void loadMore()}>{loading?"Loading…":"Load more attendance records"}</button>}
 </section>;
}
