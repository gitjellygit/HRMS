import {test,expect} from "@playwright/test";
import {login,navigate,users} from "./helpers";
import {API_URL,WEB_URL} from "../playwright.config";
const role=(key:string)=>users().find(x=>x.key===key)!;
const origin={Origin:WEB_URL};
const today=()=>new Date().toISOString().slice(0,10);
const daysAgo=(n:number)=>new Date(Date.now()-86400000*n).toISOString().slice(0,10);

async function project(page:any,rateUnit="hour"){
 const unique=Date.now().toString();
 const r=await page.request.post(API_URL+"/project-management/projects",{headers:origin,data:{
  name:"QA Finance Project "+unique,client:"Bensys Client",
  candidate_name:"QA Contractor",vendor_name:"QA Vendor",prime_vendor_name:"QA Prime",
  engagement_type:"c2c",rate:110,currency:"USD",rate_unit:rateUnit,
  sourced_by_id:role("sales_a").id,start_date:daysAgo(6)}});
 expect(r.status()).toBe(201);
 return (await r.json()).id as number;
}

test("accountant can see sourced placements, configure recipient and prepare invoice",async({page})=>{
 await login(page,role("hr"));
 const id=await project(page);
 await page.locator(".sidebar nav").getByRole("button",{name:"Sign out"}).click();
 await login(page,role("accountant"));
 await navigate(page,"Finance & invoicing");
 await expect(page.getByRole("heading",{name:"Projects available for finance"})).toBeVisible();
 const row=(await page.request.get(API_URL+"/finance/projects")).json();
 expect((await row).some((p:{id:number})=>p.id===id)).toBeTruthy();
 const denied=await page.request.put(API_URL+"/finance/projects/"+id+"/lifecycle",{headers:origin,
  data:{active:false,reason:"Attempt by accountant denied by role gate"}});
 expect(denied.status()).toBe(403);
 const contacts=await page.request.put(API_URL+"/finance/projects/"+id+"/billing",{headers:origin,
  data:{recipient_type:"vendor",recipient_name:"QA Finance Vendor",
   recipient_email:"qa.billing@example.org",recipient_phone:"555-0100",
   billing_address:"QA example address",billing_day:15,payment_terms_days:14}});
 expect(contacts.status()).toBe(200);
 await page.getByRole("tab",{name:"Invoice ledger"}).click();
 await page.getByLabel("Project").selectOption(String(id));
 await page.getByLabel("Project start date").fill(daysAgo(3));
 await page.getByLabel("Project end date").fill(today());
 await page.getByLabel("Billable units (verified hours, days or milestones)").fill("10");
 await page.getByRole("button",{name:"Create invoice draft"}).click();
 await expect(page.getByRole("status")).toContainText("Invoice draft created");
 const invoices=await (await page.request.get(API_URL+"/finance/invoices?project_id="+id)).json();
 expect(invoices.length).toBe(1);
 expect(invoices[0].recipient_type).toBe("vendor");
});

test("employee cannot access finance, but can complete a welcome orientation",async({page})=>{
 await login(page,role("hr"));
 const status=await page.request.post(API_URL+"/people/onboarding/orientation/"+role("developer_a").id,{headers:origin});
 expect(status.status()).toBe(200);
 expect((await status.json()).total_steps).toBe(7);
 const again=await page.request.post(API_URL+"/people/onboarding/orientation/"+role("developer_a").id,{headers:origin});
 expect((await again.json()).created).toBe(0);
 await page.locator(".sidebar nav").getByRole("button",{name:"Sign out"}).click();
 await login(page,role("developer_a"));
 await expect(page.locator(".sidebar nav").getByRole("button",{name:"Finance & invoicing"})).toHaveCount(0);
 expect((await page.request.get(API_URL+"/finance/projects")).status()).toBe(403);
 await navigate(page,"People operations");
 await page.getByRole("tab",{name:"Onboarding"}).click();
 await expect(page.getByText("Meet your HR buddy")).toBeVisible();
 await expect(page.getByLabel("Onboarding progress")).toBeVisible();
});
