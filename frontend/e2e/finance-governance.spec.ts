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
 await expect(page.getByRole("heading",{name:"Project billing"})).toBeVisible();
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
 await page.locator(".finance-workspace form select").first().selectOption(String(id));
 await page.getByLabel("Billing period starts").fill(daysAgo(3));
 await page.getByLabel("Billing period ends").fill(today());
 await page.getByLabel("Verified billable quantity").fill("10");
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


test("accountant can save a weekly invoice rate in a single action and expand the selected project row",async({page})=>{
 await login(page,role("hr"));
 const pid=await project(page);
 const profile=await (await page.request.get(API_URL+"/finance/projects")).json();
 const row=profile.find((x:any)=>x.id===pid);
 expect(row).toBeTruthy();
 await page.locator(".sidebar nav").getByRole("button",{name:"Sign out"}).click();
 await login(page,role("accountant"));
 await navigate(page,"Finance & invoicing");
 await page.getByRole("button",{name:new RegExp(row.project_number)}).click();
 const expanded=page.locator(".finance-expanded-row");
 await expect(expanded.getByText("Billing settings")).toBeVisible();
 await expect(page.locator(".finance-selected-row + .finance-expanded-row")).toHaveCount(1);
 await expanded.getByRole("textbox",{name:"Billing recipient name"}).fill("QA Billing Client");
 await expanded.getByRole("textbox",{name:"Billing email"}).fill("candidate.billing@example.org");
 await expanded.getByRole("combobox",{name:"Bill every"}).selectOption("weekly");
 await expanded.getByRole("spinbutton",{name:/Billing weekday/}).fill("5");
 await expanded.getByRole("spinbutton",{name:"Invoice rate (USD)"}).fill("20");
 await expanded.getByRole("button",{name:"Save billing settings"}).click();
 await expect(page.getByRole("status")).toContainText("saved");
 const pricing=await (await page.request.get(API_URL+"/finance/projects")).json();
 const selected=pricing.find((x:any)=>x.id===pid);
 expect(selected.charges.find((x:any)=>x.recipient_type==="client").pricing_value).toBe(20);
 expect(selected.billing.billing_frequency).toBe("weekly");
 await expanded.getByRole("button",{name:"Collapse"}).click();
 await expect(expanded).toHaveCount(0);
 await page.getByRole("tab",{name:"Invoice schedule"}).click();
 await page.getByRole("combobox",{name:"Projects"}).selectOption(String(pid));
 await expect(page.getByText("candidate.billing@example.org")).toBeVisible();
});
