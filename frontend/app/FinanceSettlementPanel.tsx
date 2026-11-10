"use client";
import {useEffect,useState} from "react";
import {explainError} from "./formErrors";

type Invoice=Record<string,any>;
type Ageing=Record<string,any>;
const today=()=>new Date().toISOString().slice(0,10);
const money=(value:unknown,currency="USD")=>{
 try{return new Intl.NumberFormat("en-US",{style:"currency",currency}).format(Number(value||0))}
 catch{return String(value||0)+" "+currency}
};

export default function FinanceSettlementPanel({api,invoices,refresh}:{api:string;invoices:Invoice[];refresh:()=>Promise<void>}){
 const [invoiceId,setInvoiceId]=useState("");
 const [detail,setDetail]=useState<Invoice|null>(null);
 const [ageing,setAgeing]=useState<Ageing|null>(null);
 const [amount,setAmount]=useState("");
 const [paymentRef,setPaymentRef]=useState("");
 const [receivedOn,setReceivedOn]=useState(today());
 const [creditSubtotal,setCreditSubtotal]=useState("");
 const [creditRef,setCreditRef]=useState("");
 const [creditReason,setCreditReason]=useState("");
 const [error,setError]=useState("");
 const [success,setSuccess]=useState("");
 const [busy,setBusy]=useState(false);
 const selected=invoices.find(x=>String(x.id)===invoiceId);
 async function call(url:string,method="GET",body?:unknown){
  const response=await fetch(api+"/finance"+url,{method,credentials:"include",
   headers:{"Content-Type":"application/json"},body:body===undefined?undefined:JSON.stringify(body)});
  const data=await response.json().catch(()=>({}));
  if(!response.ok)throw Error(explainError(data,response.status));
  return data;
 }
 async function reload(invoice=invoiceId){
  const a=await call("/receivables/ageing");
  setAgeing(a);
  if(invoice)setDetail(await call("/invoices/"+invoice+"/settlement"));
  else setDetail(null);
 }
 useEffect(()=>{void reload().catch(e=>setError((e as Error).message))},[api,invoiceId]);
 async function submit(path:string,payload:unknown,message:string){
  setBusy(true);setError("");setSuccess("");
  try{
   await call(path,"POST",payload);
   await refresh();await reload();
   setSuccess(message);
  }catch(e){setError((e as Error).message)}finally{setBusy(false)}
 }
 const balance=detail?.balance;
 const canRecord=selected?.stored_status==="sent"&&Number(balance?.outstanding)>0;
 return <div className="ops-area">
  <section className="employee-surface">
   <h2>Receivables and invoice settlement</h2>
   <p className="field-help">Record received payments and adjustments against an invoice. Entries are audited and cannot exceed the outstanding balance. Credit adjustments are internal records, not statutory GST credit notes.</p>
   {error&&<p role="alert" className="time-form-error">{error}</p>}
   {success&&<p role="status">{success}</p>}
   <label className="ops-label">Invoice<select value={invoiceId} onChange={e=>{setInvoiceId(e.target.value);setError("");setSuccess("")}}>
     <option value="">Select an invoice</option>
     {invoices.filter(x=>x.stored_status!=="draft"&&x.stored_status!=="void").map(x=>
       <option key={x.id} value={x.id}>#{x.id} · {x.recipient_name} · {x.status} · {money(x.total,x.currency)}</option>)}
    </select></label>
   {selected&&balance&&<div className="ops-breakdown">
    <h3>Invoice #{selected.id} · {selected.currency}</h3>
    <p>Invoice total: <strong>{money(balance.total,selected.currency)}</strong></p>
    <p>Received: {money(balance.paid,selected.currency)} · Credits: {money(balance.credited,selected.currency)}</p>
    <p>Remaining due: <strong>{money(balance.outstanding,selected.currency)}</strong></p>
    {Number(balance.outstanding)===0&&<p>Invoice balance settled; no additional payments or credits may be recorded.</p>}
   </div>}
   {canRecord&&<>
    <form className="ops-form" onSubmit={e=>{e.preventDefault();void submit("/invoices/"+invoiceId+"/payments",{
     amount,received_on:receivedOn,reference:paymentRef.trim()},"Payment recorded and invoice balance updated.")}}>
     <h3>Record payment</h3>
     <label>Received amount ({selected.currency})<input required type="number" min="0.01" max={balance.outstanding} step="0.01"
      value={amount} onChange={e=>setAmount(e.target.value)}/></label>
     <label>Received on<input required type="date" max={today()} value={receivedOn} onChange={e=>setReceivedOn(e.target.value)}/></label>
     <label>Bank/payment reference<input required minLength={3} maxLength={120} value={paymentRef}
      onChange={e=>setPaymentRef(e.target.value)} placeholder="Bank UTR or receipt reference"/></label>
     <button className="employee-primary" disabled={busy}>Record payment</button>
    </form>
    <form className="ops-form" onSubmit={e=>{e.preventDefault();void submit("/invoices/"+invoiceId+"/credit-notes",{
     subtotal:creditSubtotal,reason:creditReason.trim(),reference:creditRef.trim()},
     "Credit adjustment recorded against invoice. This is not a GST credit-note document.")}}>
     <h3>Internal credit adjustment</h3>
     <label>Amount before tax ({selected.currency})<input required type="number" min="0.01" step="0.01"
      value={creditSubtotal} onChange={e=>setCreditSubtotal(e.target.value)}/></label>
     <label>Reference<input required minLength={3} maxLength={120} value={creditRef}
      onChange={e=>setCreditRef(e.target.value)}/></label>
     <label>Correction reason (10+ characters)<textarea required minLength={10} maxLength={1000}
      value={creditReason} onChange={e=>setCreditReason(e.target.value)}/></label>
     <button className="employee-primary" disabled={busy}>Record credit adjustment</button>
    </form>
   </>}
   {detail&&<div className="ops-table">
    <h3>Settlement history</h3>
    {detail.payments?.map((x:Invoice)=><p key={"p"+x.id}>Payment #{x.id} · {x.received_on} · {money(x.amount,selected?.currency)} · {x.reference}</p>)}
    {detail.credit_notes?.map((x:Invoice)=><p key={"c"+x.id}>Credit #{x.id} · {x.issued_on} · {money(x.total,selected?.currency)} · {x.reference} · {x.reason}</p>)}
    {!detail.payments?.length&&!detail.credit_notes?.length&&<p>No settlements recorded.</p>}
   </div>}
  </section>
  <section className="employee-surface">
   <h3>Receivables ageing</h3>
   <p className="field-help">Outstanding balances are grouped separately by currency. These are amounts due, not tax returns or bank reconciliation.</p>
   {ageing?.currency_totals?.map((x:Invoice)=><p key={x.currency}>
    <strong>{x.currency}: {money(x.total,x.currency)}</strong> · Current {money(x.current,x.currency)}
     · 1–30 days {money(x["1_30"],x.currency)} · 31–60 days {money(x["31_60"],x.currency)}
     · 61–90 days {money(x["61_90"],x.currency)} · Over 90 days {money(x["90_plus"],x.currency)}
   </p>)}
   <div className="table-wrap"><table><thead><tr><th>Invoice</th><th>Recipient</th><th>Due</th><th>Days overdue</th><th>Outstanding</th></tr></thead>
    <tbody>{ageing?.invoices?.map((x:Invoice)=><tr key={x.invoice_id}>
     <td>#{x.invoice_id}</td><td>{x.recipient_name}</td><td>{x.due_date}</td>
     <td>{x.days_overdue}</td><td>{money(x.outstanding,x.currency)}</td>
    </tr>)}</tbody></table></div>
   {!ageing?.invoices?.length&&<p>No outstanding sent invoices.</p>}
  </section>
 </div>;
}
