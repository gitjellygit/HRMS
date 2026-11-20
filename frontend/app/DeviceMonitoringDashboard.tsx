"use client";
import {useCallback,useEffect,useMemo,useState} from "react";
import {Activity,RefreshCw,Monitor,Clock3,Search,ShieldCheck} from "lucide-react";

type Device={
 id:number;employee_id:number|null;employee_name:string;device_label:string;
 status:string;last_seen:string|null;active_seconds:number;idle_seconds:number;
 apps:Record<string,number>;exit_reason:string;revoked:boolean
};
const minutes=(value:number)=>Math.round((Number(value)||0)/60);
const elapsed=(value:string|null)=>value?new Date(value).toLocaleString():"Never";
export default function DeviceMonitoringDashboard({api}:{api:string}){
 const [devices,setDevices]=useState<Device[]>([]);
 const [search,setSearch]=useState("");
 const [selected,setSelected]=useState<number|null>(null);
 const [updated,setUpdated]=useState<Date|null>(null);
 const [loading,setLoading]=useState(false);
 const [error,setError]=useState("");
 const refresh=useCallback(async (signal?:AbortSignal)=>{
  if(document.visibilityState==="hidden")return;
  setLoading(true);
  try{
   const response=await fetch(api+"/activity-agent/devices",{credentials:"include",cache:"no-store",signal});
   if(!response.ok)throw Error("Couldn't refresh monitoring. Check HR/Admin access and try again.");
   const data:Device[]=await response.json();
   if(signal?.aborted)return;
   setDevices(data);setUpdated(new Date());setError("");
  }catch(e){if(!signal?.aborted)setError((e as Error).message)}
  finally{if(!signal?.aborted)setLoading(false)}
 },[api]);
 useEffect(()=>{
  const controller=new AbortController();
  void refresh(controller.signal);
  const id=window.setInterval(()=>{if(document.visibilityState==="visible")void refresh(controller.signal)},15000);
  const onVisible=()=>{if(document.visibilityState==="visible")void refresh(controller.signal)};
  document.addEventListener("visibilitychange",onVisible);
  return()=>{controller.abort();window.clearInterval(id);document.removeEventListener("visibilitychange",onVisible)};
 },[refresh]);
 const assigned=useMemo(()=>devices.filter(d=>d.employee_id!==null&&!d.revoked),[devices]);
 const filtered=useMemo(()=>assigned.filter(d=>(d.employee_name+" "+d.device_label).toLowerCase().includes(search.toLowerCase())),[assigned,search]);
 const detail=assigned.find(d=>d.id===selected);
 const online=assigned.filter(d=>d.status==="monitoring").length;
 return <section className="employee-surface jg-monitoring" aria-label="Employee activity monitoring">
  <div className="jg-monitoring-heading">
   <div><h2><Activity size={20}/> Live device monitoring</h2><p>Activity summaries from authorized company laptops. Refreshes every 15 seconds; a device is offline if HRMS has not accepted a heartbeat for over 100 seconds. Internet access alone does not imply active monitoring. Not a live screen view.</p></div>
   <button type="button" className="employee-cancel" onClick={()=>void refresh()} disabled={loading}><RefreshCw size={15} aria-hidden="true"/> {loading?"Refreshing…":"Refresh"}</button>
  </div>
  <div className="jg-monitoring-summary">
   <div><span>Assigned devices</span><strong>{assigned.length}</strong></div>
   <div><span>Reporting now</span><strong>{online}</strong></div>
   <div><span>No recent heartbeat</span><strong>{assigned.length-online}</strong></div>
   <div><span>Last refreshed</span><strong className="jg-monitoring-timestamp">{updated?updated.toLocaleTimeString():"Not yet"}</strong></div>
  </div>
  {error&&<p className="time-form-error" role="alert">{error}</p>}
  <div className="jg-monitoring-tools">
   <label><Search size={16}/><input type="search" placeholder="Find employee or laptop" value={search} onChange={e=>setSearch(e.target.value)} aria-label="Find employee or laptop"/></label>
   <span>{filtered.length} shown · select a card for details</span>
  </div>
  <div className="jg-monitoring-grid">
   {filtered.map(d=><button type="button" key={d.id} onClick={()=>setSelected(d.id===selected?null:d.id)} aria-pressed={selected===d.id} className={"jg-monitoring-card "+(selected===d.id?"is-selected":"")}>
    <div className="jg-monitoring-card-heading"><div className="jg-monitoring-avatar"><Monitor size={18}/></div><span className={"jg-monitoring-state "+(d.status==="monitoring"?"online":"offline")}>{d.status==="monitoring"?"Reporting":d.status==="stopped"?"Stopped":"No heartbeat"}</span></div>
    <strong>{d.employee_name}</strong><small>{d.device_label}</small>
    <div className="jg-monitoring-times"><div><span>Active</span><b>{minutes(d.active_seconds)}m</b></div><div><span>Idle</span><b>{minutes(d.idle_seconds)}m</b></div></div>
    <span className="jg-monitoring-seen">Top reported app: {Object.entries(d.apps||{}).sort((a,b)=>b[1]-a[1])[0]?.[0]||"Not reported"}</span>
    <span className="jg-monitoring-seen"><Clock3 size={13}/> Last update: {elapsed(d.last_seen)}</span>
   </button>)}
  </div>
  {!filtered.length&&<p className="jg-device-empty">{assigned.length?"No employees match your search.":"No assigned laptops yet. Assign a pending laptop under Analytics → Employee device monitoring."}</p>}
  {detail&&<section className="jg-monitoring-detail" aria-label={"Activity details for "+detail.employee_name}>
   <div className="jg-monitoring-detail-head"><div><h3>{detail.employee_name} · {detail.device_label}</h3><p>Most recently reported cumulative activity totals. Values may reset when the companion restarts.</p></div><button type="button" className="employee-cancel" onClick={()=>setSelected(null)}>Close details</button></div>
   <div className="jg-monitoring-apps">
    {Object.entries(detail.apps||{}).sort((a,b)=>b[1]-a[1]).slice(0,10).map(([name,seconds])=><div key={name}><span>{name}</span><strong>{minutes(seconds)} min</strong></div>)}
    {!Object.keys(detail.apps||{}).length&&<p>No application usage reported yet. Check the device is reporting and its last heartbeat is recent.</p>}
   </div>
   {detail.exit_reason&&<p>Exit reason: {detail.exit_reason}</p>}
   <p className="jg-monitoring-disclosure"><ShieldCheck size={15}/> The companion sends aggregate foreground-application and active/idle summaries, not screenshots, keystrokes, URLs, or live screen contents.</p>
  </section>}
 </section>;

}
