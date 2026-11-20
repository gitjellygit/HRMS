import {test,expect} from "@playwright/test";
import {login,navigate,users} from "./helpers";
import {API_URL,WEB_URL} from "../playwright.config";

const role=(name:string)=>users().find(p=>p.key===name)!;

test("HR deactivates and reactivates a project from Projects with an audited reason",async({page})=>{
 await login(page,role("hr"));
 const name="QA Lifecycle "+Date.now();
 const response=await page.request.post(API_URL+"/project-management/projects",{
  headers:{Origin:WEB_URL},data:{name,client:"QA Billing Client",
   engagement_type:"c2c",rate:78,currency:"USD",rate_unit:"hour",
   sourced_by_id:role("sales_a").id,start_date:"2026-10-01"}});
 expect(response.status()).toBe(201);
 const project=await response.json();
 await navigate(page,"Projects");
 const entry=page.locator(".project-table tbody tr").filter({hasText:name});
 await expect(entry).toBeVisible();
 await entry.getByRole("button",{name:"Deactivate"}).click();
 const dialog=page.getByRole("dialog",{name:"Deactivate "+name});
 await expect(dialog).toBeVisible();
 await expect(dialog.getByRole("button",{name:"Confirm deactivation"})).toBeDisabled();
 await dialog.getByRole("textbox",{name:/Reason for status change/}).fill("Client contract completed successfully");
 await dialog.getByRole("button",{name:"Confirm deactivation"}).click();
 await expect(page.getByRole("status")).toContainText("deactivated successfully");
 await expect(entry.getByText("inactive",{exact:true})).toBeVisible();
 const after=await page.request.get(API_URL+"/finance/projects");
 expect((await after.json()).find((p:any)=>p.id===project.id).status).toBe("inactive");
 await entry.getByRole("button",{name:"Reactivate"}).click();
 const again=page.getByRole("dialog",{name:"Reactivate "+name});
 await again.getByRole("textbox",{name:/Reason for status change/}).fill("New client assignment officially approved");
 await again.getByRole("button",{name:"Confirm reactivation"}).click();
 await expect(page.getByRole("status")).toContainText("reactivated successfully");
 await expect(entry.getByRole("button",{name:"Deactivate"})).toBeVisible();
});
