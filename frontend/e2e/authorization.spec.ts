import { test, expect } from '@playwright/test';
import { users, login } from './helpers';
import { API_URL } from '../playwright.config';

const allRoles=['sales_a','developer_a','hr','accountant','manager'] as const;
const restricted=[
  { method:'GET', path:'/leave/hr-overview', label:'HR data overview' },
  { method:'GET', path:'/leave/reports?year=2026', label:'HR leave reports' },
  { method:'GET', path:'/policies/project-bonus', label:'company bonus policy' },
  { method:'GET', path:'/core/document-alerts', label:'confidential document expiry' },
  { method:'GET', path:'/project-management/next-number', label:'project number generation' },
  { method:'GET', path:'/core/changes', label:'profile change queue' },
] as const;
for (const key of allRoles) {
  for (const endpoint of restricted) {
    test(key + ': server authorization / ' + endpoint.label, async ({ page }) => {
      const persona=users().find(u=>u.key===key)!;
      await login(page,persona);
      const response=await page.request.get(API_URL+endpoint.path);
      if (key==='hr') expect(response.status()).toBe(200);
      else if (endpoint.path==='/core/changes') expect(response.status()).toBe(200); // own requests only
      else expect(response.status()).toBe(403);
    });
  }
}
test('employee cannot create organization departments via API', async ({ page }) => {
  await login(page,users().find(u=>u.key==='sales_a')!);
  const response=await page.request.post(API_URL+'/core/units',{
    headers:{Origin:process.env.E2E_WEB_URL||'http://127.0.0.1:3100'},
    data:{kind:'department',name:'Unauthorized Department',code:'BAD'},
  });
  expect(response.status()).toBe(403);
});
test('accountant cannot create another employee via API', async ({ page }) => {
  await login(page,users().find(u=>u.key==='accountant')!);
  const response=await page.request.post(API_URL+'/core/employees',{
    headers:{Origin:process.env.E2E_WEB_URL||'http://127.0.0.1:3100'},
    data:{account:{name:'Unauthorized Person',email:'unauth@example.test',password:'ExampleOnly!123',department:'Finance',designation:'Accountant'},master:{}},
  });
  expect(response.status()).toBe(403);
});
test('employee cannot see another employee core profile', async ({ page }) => {
  const person=users().find(u=>u.key==='sales_a')!;
  const other=users().find(u=>u.key==='developer_a')!;
  await login(page,person);
  const response=await page.request.get(API_URL+'/core/employees/'+other.id);
  expect(response.status()).toBe(403);
});
test('accountant cannot view employee sensitive master record', async ({ page }) => {
  const person=users().find(u=>u.key==='accountant')!;
  await login(page,person);
  const response=await page.request.get(API_URL+'/core/employees/'+users().find(u=>u.key==='developer_a')!.id);
  expect(response.status()).toBe(403);
});
test('HR can list test employees in employee directory', async ({ page }) => {
  await login(page,users().find(u=>u.key==='hr')!);
  const response=await page.request.get(API_URL+'/core/employees');
  expect(response.status()).toBe(200);
  const names=(await response.json()).map((p:{name:string})=>p.name);
  for(const person of users())expect(names).toContain(person.name);
});

test('legacy HR leave dashboard returns actionable retirement status', async ({ page }) => {
  await login(page,users().find(u=>u.key==='hr')!);
  const response=await page.request.get(API_URL+'/core/hr-overview');
  expect(response.status()).toBe(410);
  const body=await response.json();
  expect(JSON.stringify(body)).toContain('/leave/hr-overview');
});
