"use client";
import React,{useState} from "react";
import {UploadCloud} from "lucide-react";

/** Styled file picker preserving an actual native input for validation,
 * browser file dialogs, drag/drop on the control and test setInputFiles.
 */
export default function UploadInput({onChange,className="",...props}:React.InputHTMLAttributes<HTMLInputElement>){
 const [fileName,setFileName]=useState("");
 return <span className={"jg-upload-picker "+className}>
  <input {...props} type="file" onChange={event=>{
   setFileName(Array.from(event.target.files||[]).map(file=>file.name).join(", "));
   onChange?.(event);
  }}/>
  <span className="jg-upload-action"><UploadCloud size={17} aria-hidden="true"/> Browse files</span>
  <span className="jg-upload-filename" title={fileName||"No file selected"}>{fileName||"No file selected"}</span>
 </span>;
}
