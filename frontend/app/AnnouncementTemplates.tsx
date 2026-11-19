"use client";
import {Download,ImagePlus} from "lucide-react";

export type AnnouncementPreset={
 key:string;name:string;headline:string;message:string;accent:string;art:string;
};
export const ANNOUNCEMENT_PRESETS:AnnouncementPreset[]=[
 {key:"welcome",name:"New joiner",headline:"Welcome to the team!",
  message:"Please join us in welcoming our newest teammate. We are excited to work together!",
  accent:"#5448b7",art:"Welcome"},
 {key:"holiday",name:"Holiday notice",headline:"Upcoming company holiday",
  message:"Please review the upcoming holiday and plan your project handovers accordingly.",
  accent:"#16786b",art:"Holiday"},
 {key:"christmas",name:"Christmas",headline:"Merry Christmas!",
  message:"Wishing everyone a wonderful Christmas and a peaceful holiday season.",
  accent:"#b3404a",art:"Christmas"},
 {key:"thanksgiving",name:"Thanksgiving",headline:"Happy Thanksgiving!",
  message:"Thank you for your hard work and collaboration. Wishing you and your families a joyful Thanksgiving.",
  accent:"#a26327",art:"Thanks"},
 {key:"birthday",name:"Birthday",headline:"Happy birthday!",
  message:"Join us in wishing our teammate a wonderful birthday and a successful year ahead.",
  accent:"#9652a5",art:"Celebrate"},
 {key:"general",name:"Company update",headline:"Company announcement",
  message:"We have an important company update to share. Please read the details below.",
  accent:"#255b98",art:"News"}
];
function xmlEscape(value:string){return value.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;")}
function downloadableSvg(p:AnnouncementPreset):string{
 const title=xmlEscape(p.headline);const type=xmlEscape(p.art);
 return `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
 <rect width="1200" height="630" rx="34" fill="#f7f8fd"/>
 <rect x="32" y="32" width="1136" height="566" rx="30" fill="${p.accent}"/>
 <circle cx="966" cy="320" r="175" fill="#ffffff" fill-opacity=".09"/>
 <circle cx="1026" cy="260" r="111" fill="#ffffff" fill-opacity=".12"/>
 <circle cx="1026" cy="260" r="70" fill="#ffffff" fill-opacity=".15"/>
 <text x="103" y="143" font-size="30" fill="#ffffff" font-family="Arial, sans-serif" font-weight="700" letter-spacing="3">JELLYGIT • TEAM NEWS</text>
 <text x="103" y="315" font-size="60" fill="#ffffff" font-family="Arial, sans-serif" font-weight="750">${title}</text>
 <text x="103" y="405" font-size="27" fill="#ffffff" font-family="Arial, sans-serif" opacity=".9">Edit this text in your design tool</text>
 <text x="103" y="539" font-size="25" fill="#ffffff" font-family="Arial, sans-serif" opacity=".85">${type.toUpperCase()} • ANNOUNCEMENT</text>
 </svg>`;
}
export default function AnnouncementTemplates({selected,onPick}:{selected:string;onPick:(p:AnnouncementPreset)=>void}){
 function download(p:AnnouncementPreset){
  const blob=new Blob([downloadableSvg(p)],{type:"image/svg+xml;charset=utf-8"});
  const url=URL.createObjectURL(blob);const anchor=document.createElement("a");
  anchor.href=url;anchor.download="jellygit-"+p.key+"-editable.svg";anchor.click();
  URL.revokeObjectURL(url);
 }
 return <section className="jg-announcement-presets" aria-label="Announcement template gallery">
  <div><h4>Choose an announcement design</h4><p>Select a preset to fill the announcement text, or write your own. You can download an editable SVG design, customize it, export to PNG/JPEG, and upload the final image below.</p></div>
  <div className="jg-preset-grid">{ANNOUNCEMENT_PRESETS.map(p=><button key={p.key} type="button" className="jg-preset-card" aria-pressed={selected===p.key} onClick={()=>onPick(p)}>
   <span className="jg-preset-swatch" style={{background:p.accent,height:8,borderRadius:4}}/>
   <strong>{p.name}</strong><small>{p.headline}</small>
  </button>)}</div>
  <div className="jg-preset-actions">{ANNOUNCEMENT_PRESETS.filter(p=>p.key===selected).map(p=><button key={p.key} type="button" className="employee-cancel" onClick={()=>download(p)}><Download size={15}/> Download editable {p.name} design</button>)}<small><ImagePlus size={14} aria-hidden="true"/> You can also skip presets and upload your own image.</small></div>
 </section>;
}
