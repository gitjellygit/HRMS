"use client";
import {useEffect,useState} from "react";
import {Clock3} from "lucide-react";

type Punch={id:number;punch_in:string;punch_out:string|null};
export default function OverviewAttendance({api,refreshKey}:{api:string;refreshKey:number}){
 const [rows,setRows]=useState<Punch[]>([]);
 const [error,setError]=useState("");
 useEffect(()=>{
  let alive=true;
  fetch(api+"/attendance",{credentials:"include"}).then(async r=>{if(!r.ok)throw Error("Unable to load recent attendance.");return r.json()})
   .then((data:Punch[])=>{if(alive){setRows(data.slice(0,5));setError("")}})
   .catch(e=>{if(alive)setError((e as Error).message)});
  return()=>{alive=false};
 },[api,refreshKey]);
 return <section className="overview-recent-attendance">
  <div className="section-head"><h2><Clock3 size={17}/> Recent attendance</h2><span className="muted">Your last 5 punch sessions</span></div>
  {error?<p className="muted">{error}</p>:rows.length?<div className="table-wrap"><table><thead><tr><th>Date</th><th>Punch in</th><th>Punch out</th><th>Duration</th></tr></thead><tbody>{rows.map(r=><tr key={r.id}>
   <td>{new Date(r.punch_in).toLocaleDateString("en-IN",{day:"numeric",month:"short"})}</td>
   <td>{new Date(r.punch_in).toLocaleTimeString("en-IN",{hour:"2-digit",minute:"2-digit"})}</td>
   <td>{r.punch_out?new Date(r.punch_out).toLocaleTimeString("en-IN",{hour:"2-digit",minute:"2-digit"}):"Working"}</td>
   <td>{r.punch_out?((new Date(r.punch_out).getTime()-new Date(r.punch_in).getTime())/3600000).toFixed(2)+" h":"In progress"}</td>
  </tr>)}</tbody></table></div>:<p className="muted">No attendance records yet. Punch in to begin.</p>}
 </section>;
}
