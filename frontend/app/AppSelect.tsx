"use client";
import React,{Children,isValidElement,useEffect,useId,useMemo,useRef,useState} from "react";
import {Check,ChevronDown,Search} from "lucide-react";

type Choice={value:string;label:string;disabled:boolean};
type SelectProps=Omit<React.SelectHTMLAttributes<HTMLSelectElement>,"children"> & {
 children:React.ReactNode;
};
function flatten(children:React.ReactNode):Choice[]{
 const result:Choice[]=[];
 Children.forEach(children,child=>{
  if(!isValidElement(child))return;
  if(child.type==="option"){
   const p=child.props as React.OptionHTMLAttributes<HTMLOptionElement>;
   const label=typeof p.children==="string"||typeof p.children==="number"?String(p.children):String(p.label||p.value||"");
   result.push({value:String(p.value??label),label,disabled:!!p.disabled});
  }else if(child.type==="optgroup"){
   result.push(...flatten((child.props as {children?:React.ReactNode}).children));
  }
 });
 return result;
}
/** Accessible app-owned menu. Native select remains in the form for required validation,
 * keyboard-independent automation and existing Playwright selectOption contracts.
 */
export default function AppSelect({children,value,defaultValue,onChange,onBlur,onFocus,multiple,size,disabled,required,className="",style,...rest}:SelectProps){
 const choices=useMemo(()=>flatten(children),[children]);
 const native=useRef<HTMLSelectElement>(null);
 const shell=useRef<HTMLDivElement>(null);
 const uid=useId();
 const [opened,setOpened]=useState(false);
 const [term,setTerm]=useState("");
 const [local,setLocal]=useState(String(defaultValue??choices.find(c=>!c.disabled)?.value??""));
 const chosen=String(value??local);
 const selected=choices.find(c=>c.value===chosen);
 const active=choices.filter(c=>!c.disabled);
 const visible=active.filter(c=>c.label.toLowerCase().includes(term.trim().toLowerCase()));
 useEffect(()=>{
  if(!opened)return;
  const outside=(event:MouseEvent|TouchEvent)=>{if(!shell.current?.contains(event.target as Node))setOpened(false)};
  const escape=(event:KeyboardEvent)=>{if(event.key==="Escape")setOpened(false)};
  document.addEventListener("mousedown",outside);
  document.addEventListener("touchstart",outside);
  document.addEventListener("keydown",escape);
  return ()=>{document.removeEventListener("mousedown",outside);document.removeEventListener("touchstart",outside);document.removeEventListener("keydown",escape)};
 },[opened]);
 function pick(next:string){
  if(disabled)return;
  if(native.current)native.current.value=next;
  if(value===undefined)setLocal(next);
  // The original select callback contract is preserved for existing pages.
  if(onChange)onChange({target:native.current,currentTarget:native.current} as React.ChangeEvent<HTMLSelectElement>);
  setOpened(false);setTerm("");
 }
 // Native multiple-select semantics need a dedicated multi-picker. Preserve existing
 // multiple controls unchanged until they are converted with explicit checkbox controls.
 if(multiple)return <select {...rest} className={className} style={style} value={value} defaultValue={defaultValue} onChange={onChange} onBlur={onBlur} onFocus={onFocus} multiple size={size} disabled={disabled} required={required}>{children}</select>;
 return <div className={"jg-select "+(opened?"jg-select-open ":"")+(disabled?"jg-select-disabled ":"")+className} ref={shell} style={style}>
  <select {...rest} ref={native} value={value} defaultValue={value===undefined?defaultValue:undefined} onChange={e=>{if(value===undefined)setLocal(e.target.value);onChange?.(e)}} onBlur={onBlur} onFocus={onFocus} required={required} disabled={disabled} tabIndex={-1} className="jg-native-select" aria-label={rest["aria-label"]} data-native-select="true">{children}</select>
  <button type="button" className="jg-select-trigger" disabled={disabled} aria-haspopup="listbox" aria-expanded={opened} aria-controls={uid} onClick={()=>setOpened(v=>!v)}>
   <span className={!chosen?"jg-select-placeholder":""}>{selected?.label||choices[0]?.label||"Choose an option"}</span><ChevronDown size={16} aria-hidden="true"/>
  </button>
  {opened&&<div className="jg-select-popover" id={uid} role="listbox" aria-label={rest["aria-label"]||"Choose an option"}>
   {active.length>7&&<div className="jg-select-search"><Search size={15}/><input type="search" autoFocus aria-label="Search options" placeholder="Search…" value={term} onChange={e=>setTerm(e.target.value)}/></div>}
   <div className="jg-select-options">{visible.length?visible.map(c=><button key={c.value} type="button" role="option" aria-selected={c.value===chosen} className={"jg-select-option "+(c.value===chosen?"is-selected":"")} onClick={()=>pick(c.value)}><span>{c.label}</span>{c.value===chosen&&<Check size={15}/>}</button>):<p className="jg-select-empty">No matching options</p>}</div>
  </div>}
 </div>;
}
