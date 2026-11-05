import {test,expect} from "@playwright/test";
import {login,navigate,users} from "./helpers";
import {API_URL,WEB_URL} from "../playwright.config";

const person=(key:string)=>users().find(u=>u.key===key)!;
const origin={Origin:WEB_URL};

test("employee creates a private goal and tracks progress",async({page})=>{
 await login(page,person("developer_a"));
 await navigate(page,"Performance & growth");
 await expect(page.getByRole("heading",{name:"Performance & growth"})).toBeVisible();
 const label="QA growth goal "+Date.now();
 await page.getByRole("tab",{name:"Goals & KRAs"}).click();
 await page.getByLabel("Goal title").fill(label);
 await page.getByRole("button",{name:"Add goal"}).click();
 await expect(page.getByText(label)).toBeVisible();
 const goals=await page.request.get(API_URL+"/performance/goals");
 expect(goals.status()).toBe(200);
 expect((await goals.json()).every((g:{employee_id:number})=>g.employee_id===person("developer_a").id)).toBeTruthy();
 const other=await page.request.get(API_URL+"/performance/goals?employee_id="+person("developer_b").id);
 expect(other.status()).toBe(403);
});

test("HR creates a cycle and employee completes a self-review",async({page})=>{
 await login(page,person("hr"));
 await navigate(page,"Performance & growth");
 await page.getByRole("tab",{name:"Appraisal cycles"}).click();
 const label="QA annual review "+Date.now();
 await page.getByLabel("Cycle name").fill(label);
 await page.getByRole("button",{name:"Create cycle"}).click();
 await expect(page.getByRole("status")).toContainText("Review cycle created");
 const cycles=await page.request.get(API_URL+"/performance/cycles");
 expect(cycles.status()).toBe(200);
 const cycle=(await cycles.json()).find((c:{name:string})=>c.name===label);
 expect(cycle).toBeTruthy();
 await page.locator(".sidebar nav").getByRole("button",{name:"Sign out"}).click();
 await login(page,person("developer_b"));
 await navigate(page,"Performance & growth");
 await page.getByRole("tab",{name:"Appraisal cycles"}).click();
 await page.getByLabel("Review cycle").selectOption(String(cycle.id));
 await page.getByLabel("Self assessment").fill("Delivered meaningful milestones on schedule and improved team collaboration.");
 await page.getByRole("button",{name:"Submit self-review"}).click();
 await expect(page.getByRole("status")).toContainText("Self-review submitted");
 const reviews=await page.request.get(API_URL+"/performance/reviews");
 expect(reviews.status()).toBe(200);
 expect((await reviews.json()).some((r:{cycle_id:number;status:string})=>r.cycle_id===cycle.id&&r.status==="self_submitted")).toBeTruthy();
});
