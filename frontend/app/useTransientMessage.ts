"use client";
import {useEffect,useState} from "react";

/** Transient confirmation copy, automatically cleared after a short accessible reading window.
 * State is scoped to each page; navigation unmounts it. Errors remain until explicitly resolved.
 */
export function useTransientMessage(durationMs=4500) {
  const [message,setMessage]=useState("");
  useEffect(()=>{
    if(!message)return;
    const timer=window.setTimeout(()=>setMessage(""),durationMs);
    return ()=>window.clearTimeout(timer);
  },[message,durationMs]);
  return [message,setMessage] as const;
}
