import {test,expect} from '@playwright/test';
import {login,navigate,users} from './helpers';
import {API_URL,WEB_URL} from '../playwright.config';
const person=(key:string)=>users().find(u=>u.key===key)!;
const origin={Origin:WEB_URL};

test('employee overview loads without an insufficient-permissions banner',async({page})=>{
 await login(page,person('developer_a'));
 await expect(page.locator('main.content')).toBeVisible();
 await expect(page.locator('main.content > .error')).toHaveCount(0);
 await expect(page.locator('details.overview-attendance-collapse > summary')).toContainText('Recent attendance');
 await expect(page.getByRole('button',{name:'Profile requests'})).toHaveCount(0);
});

test('sourcing employee sees only their projects, not other employee rates',async({page})=>{
 await login(page,person('hr'));
 const unique=String(Date.now());
 const create=async(name:string,employee_id:number)=>{
  const r=await page.request.post(API_URL+'/project-management/projects',{headers:origin,data:{
   name:name+' '+unique,client:'QA Client',engagement_type:'c2c',rate:100,
   sourced_by_id:employee_id,start_date:'2026-11-04'}});
  expect(r.status()).toBe(201);
  return (await r.json()).id as number;
 };
 const mine=await create('Owned QA Project',person('developer_a').id);
 const other=await create('Private Other Project',person('developer_b').id);
 await page.locator('.sidebar nav').getByRole('button',{name:'Sign out'}).click();
 await login(page,person('developer_a'));
 await navigate(page,'Projects');
 await expect(page.locator('.project-page')).toContainText('Owned QA Project '+unique);
 await expect(page.locator('.project-page')).not.toContainText('Private Other Project '+unique);
 expect((await page.request.get(API_URL+'/project-management/projects/'+other)).status()).toBe(404);
 expect((await page.request.get(API_URL+'/project-management/projects/'+mine)).status()).toBe(200);
});

test('employees see only their own appraisals',async({page})=>{
 await login(page,person('hr'));
 const period='QA-'+Date.now();
 const create=async(id:number)=>{
  const r=await page.request.post(API_URL+'/appraisals',{headers:origin,data:{
   employee_id:id,period,rating:4,feedback:'E2E review '+id}});
  expect(r.status()).toBe(201);
 };
 await create(person('developer_a').id);
 await create(person('developer_b').id);
 await page.locator('.sidebar nav').getByRole('button',{name:'Sign out'}).click();
 await login(page,person('developer_a'));
 await navigate(page,'Appraisals');
 const list=await page.request.get(API_URL+'/appraisals');
 expect(list.status()).toBe(200);
 expect((await list.json()).every((p:{employee_id:number})=>p.employee_id===person('developer_a').id)).toBeTruthy();
});

test('employee can change appearance and upload a private profile picture',async({page})=>{
 await login(page,person('sales_c'));
 const trigger=page.getByRole('button',{name:'Profile and appearance'});
 await trigger.click();
 await page.getByRole('button',{name:'Switch to dark mode'}).click();
 await expect(page.locator('html')).toHaveAttribute('data-theme','dark');
 await trigger.click();
 await page.getByRole('button',{name:'Switch to light mode'}).click();
 await expect(page.locator('html')).toHaveAttribute('data-theme','light');
 const png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9zMfSC8AAAAASUVORK5CYII=','base64');
 await trigger.click();
 await page.locator('.hrms-photo-change input[type="file"]').setInputFiles({
  name:'qa-avatar.png',mimeType:'image/png',buffer:png});
 await expect(page.locator('.hrms-profile-trigger img')).toBeVisible();
 await expect.poll(async()=>(await page.request.get(API_URL+'/me/photo')).status()).toBe(200);
});

test('HR reset reports missing SMTP and new employee must change initial password',async({page})=>{
 await login(page,person('hr'));
 const manager=person('manager').id, unique=Date.now();
 const email='qa.reset.'+unique+'@example.org';
 const c=await page.request.post(API_URL+'/core/employees',{headers:origin,data:{
  account:{name:'Forced Password Tester',email,password:'InitialSecret!1234',role:'employee',
   designation:'QA Associate',department:'Engineering'},
  master:{manager_id:manager}}});
 expect(c.status()).toBe(201);
 const id=(await c.json()).id;
 const reset=await page.request.post(API_URL+'/core/employees/'+id+'/reset-password',{
  headers:origin,data:{reason:'QA verification of first-login password change'}});
 // CI does not configure outgoing SMTP, so the request must fail safely:
 // HR cannot obtain a plaintext replacement password.
 expect(reset.status()).toBe(503);
 const resetBody=await reset.json();
 expect(JSON.stringify(resetBody)).not.toContain('temporary_password');
 await page.locator('.sidebar nav').getByRole('button',{name:'Sign out'}).click();
 await page.goto('/');
 await page.locator('input[name="email"]').fill(email);
 await page.locator('input[name="password"]').fill('InitialSecret!1234');
 await page.getByRole('button',{name:'Sign in to HRMS'}).click();
 await expect(page.getByRole('heading',{name:'Change your temporary password'})).toBeVisible();
 await expect(page.locator('.sidebar')).toHaveCount(0);
 await page.getByLabel('Initial password',{exact:true}).fill('InitialSecret!1234');
 await page.getByLabel('New password',{exact:true}).fill('NewUserChoice!7890');
 await page.getByLabel('Confirm new password').fill('NewUserChoice!7890');
 await page.getByRole('button',{name:'Change password and sign out'}).click();
 await expect(page.getByRole('status')).toContainText('Password successfully changed');
 await page.locator('input[name="email"]').fill(email);
 await page.locator('input[name="password"]').fill('NewUserChoice!7890');
 await page.getByRole('button',{name:'Sign in to HRMS'}).click();
 await expect(page.locator('.sidebar')).toBeVisible();
});
