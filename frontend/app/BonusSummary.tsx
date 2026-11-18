"use client";
import {useEffect,useState} from "react";
import {Award} from "lucide-react";
type Item={project:string;bonus_id:number;amount_inr:number;status:string;period:string};
export default function BonusSummary({api}:{api:string}){
 const [rows,setRows]=useState<Item[]>([]);
 const [manual,setManual]=useState<{id:number;amount:number;period:string;reason:string;status:string}[]>([]);
 useEffect(()=>{
  fetch(api+"/project-management/my-bonuses",{credentials:"include"})
   .then(r=>r.ok?r.json():[]).then(setRows).catch(()=>{});
 },[api]);
 if(!rows.length&&!manual.length)return null;
 return <section className="panel"><div className="section-head"><h2><Award size={18}/> My bonuses</h2></div><div className="table-wrap"><table><thead><tr><th>Project</th><th>Milestone month</th><th>Amount (INR)</th><th>Payment status</th></tr></thead><tbody>{rows.map(r=><tr key={r.bonus_id}><td>{r.project}</td><td>{r.period}</td><td>₹{r.amount_inr.toLocaleString("en-IN")}</td><td><span className={"pill "+r.status}>{r.status==="planned"?"Pending approval":r.status}</span></td></tr>)}</tbody></table></div>{manual.length>0&&<div className="table-wrap"><table><thead><tr><th>Period</th><th>Reason</th><th>Amount (INR)</th><th>Status</th></tr></thead><tbody>{manual.map(b=><tr key={b.id}><td>{b.period}</td><td>{b.reason}</td><td>₹{Number(b.amount).toLocaleString("en-IN")}</td><td><span className={"pill "+b.status}>{b.status}</span></td></tr>)}</tbody></table></div>}</section>;
}
