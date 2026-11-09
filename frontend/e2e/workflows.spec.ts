import { test, expect, request } from '@playwright/test';
import { login, navigate, users } from './helpers';
import {TEST_PASSWORD} from './global-setup';
import { API_URL, WEB_URL } from '../playwright.config';

function persona(key:string){return users().find(u=>u.key===key)!}

test.describe('employee management & UI validation', () => {
  test.beforeEach(async ({page})=>{await login(page,persona('hr'));await navigate(page,'Employees');});
  test('seeded employees can be searched by name', async ({page}) => {
    await page.getByRole('textbox',{name:'Search employees'}).fill('Aarav Sales');
    await expect(page.locator('.employee-table')).toContainText('Aarav Sales');
  });
  test('bench-sales employees have the correct department in directory', async ({page}) => {
    await page.getByRole('textbox',{name:'Search employees'}).fill('Aarav Sales');
    await expect(page.locator('.employee-table')).toContainText('Bench Sales');
  });
  test('accountant has correct role in directory', async ({page}) => {
    await page.getByRole('textbox',{name:'Search employees'}).fill('Dev Accountant');
    await expect(page.locator('.employee-table')).toContainText('accountant');
  });
  test('Add employee form shows department dropdown', async ({page}) => {
    await page.getByRole('button',{name:'Add employee'}).click();
    await expect(page.locator('#emp-department')).toBeVisible();
    await expect(page.locator('#emp-department option').filter({hasText:'Engineering'}).first()).toHaveCount(1);
  });
  test('HR can create a department without leaving employee creation', async ({page}) => {
    await page.getByRole('button',{name:'Add employee'}).click();
    await page.getByRole('button',{name:'Add department'}).click();
    await page.locator('#new-dept-name').fill('E2E Business Operations ' + Date.now().toString().slice(-7));
    await page.locator('#new-dept-code').fill('BUS-' + Date.now().toString().slice(-7));
    await page.getByRole('button',{name:'Create department'}).click();
    await expect(page.locator('#emp-department')).toHaveValue(/\d+/);
  });
  test('no department triggers inline validation', async ({page}) => {
    await page.getByRole('button',{name:'Add employee'}).click();
    await page.getByRole('button',{name:'Save employee'}).click();
    await expect(page.locator('.employee-department-picker .field-error')).toContainText('Select a department');
  });
  test('invalid full name is called out specifically', async ({page}) => {
    await page.getByRole('button',{name:'Add employee'}).click();
    await page.locator('input[placeholder="e.g. Aarav Sharma"]').fill('Test');
    await page.getByRole('button',{name:'Save employee'}).click();
    await expect(page.locator('.employee-field .field-error').filter({hasText:'first and last'})).toBeVisible();
  });
  test('invalid email produces field-level feedback', async ({page}) => {
    await page.getByRole('button',{name:'Add employee'}).click();
    await page.locator('input[placeholder="aarav@jellygit.com"]').fill('invalid-address');
    await page.getByRole('button',{name:'Save employee'}).click();
    await expect(page.locator('.employee-field .field-error').filter({hasText:'valid work email'})).toBeVisible();
  });
  test('weak password produces a meaningful validation message', async ({page}) => {
    await page.getByRole('button',{name:'Add employee'}).click();
    await page.locator('input[placeholder="Create a strong password"]').fill('abc');
    await page.getByRole('button',{name:'Save employee'}).click();
    await expect(page.locator('.employee-field .field-error').filter({hasText:'12+ characters'})).toBeVisible();
  });
  test('HR can add an employee using an existing department', async ({page}) => {
    const unique=String(Date.now());
    await page.getByRole('button',{name:'Add employee'}).click();
    await page.locator('input[placeholder="e.g. Aarav Sharma"]').fill('Kiran Testemployee');
    await page.locator('input[placeholder="aarav@jellygit.com"]').fill('qa.ui.'+unique+'@example.org');
    await page.locator('input[placeholder="e.g. Software Engineer"]').fill('QA Associate');
    const departmentValue=await page.locator('#emp-department option').nth(1).getAttribute('value');
    await page.locator('#emp-department').selectOption(departmentValue!);
    await page.locator('#core-manager').selectOption(String(persona('manager').id));
    await page.locator('input[placeholder="Create a strong password"]').fill('DemoOnly!Pass1234');
    await page.getByRole('button',{name:'Save employee'}).click();
    await expect(page.getByRole('status')).toContainText('added successfully');
    await page.getByRole('textbox',{name:'Search employees'}).fill('Kiran Testemployee');
    await expect(page.locator('.employee-table')).toContainText('Kiran Testemployee');
  });
  test('cancel employee creation returns to directory', async ({page}) => {
    await page.getByRole('button',{name:'Add employee'}).click();
    await page.getByRole('button',{name:'Cancel',exact:true}).last().click();
    await expect(page.getByRole('heading',{name:'Employee directory'})).toBeVisible();
  });
});

test.describe('employee and finance workflows',()=>{
  test('bench sales employee can view self service profile', async ({page})=>{
    await login(page,persona('sales_a'));await navigate(page,'My profile');
    await expect(page.locator('.core-workspace')).toContainText('Aarav Sales');
  });
  test('developer can see leave request entry', async ({page})=>{
    await login(page,persona('developer_a'));await navigate(page,'Leave requests');
    await expect(page.getByRole('heading',{name:'Apply for leave'})).toBeVisible();
  });
  test('accountant can open bonuses but cannot add an employee', async ({page})=>{
    await login(page,persona('accountant'));await navigate(page,'Bonuses');
    await expect(page.getByRole('heading',{name:'Bonuses'}).first()).toBeVisible();
    await navigate(page,'Employees');
    await expect(page.getByRole('button',{name:'Add employee'})).toHaveCount(0);
  });
  test('HR can open the policies configuration', async ({page})=>{
    await login(page,persona('hr'));await navigate(page,'Policies');
    await expect(page.getByRole('heading',{name:'Company policies'})).toBeVisible();
  });
  test('HR can view employee leave balances', async ({page})=>{
    await login(page,persona('hr'));await navigate(page,'HR overview');
    await expect(page.locator('.employee-surface')).toContainText('FY');
  });
  test('manager can open approvals panel', async ({page})=>{
    await login(page,persona('manager'));await navigate(page,'Leave requests');
    await page.locator('.leave-tabs').getByRole('button',{name:'Approvals',exact:true}).click();
    await expect(page.getByRole('heading',{name:'Leave approvals'})).toBeVisible();
  });
  test('punch button reflects server state after check in/out', async ({page})=>{
    await login(page,persona('sales_c'));await navigate(page,'Attendance');
    const status=await page.request.get(API_URL+'/attendance/status');
    expect(status.ok()).toBeTruthy();
    const wasIn=(await status.json()).checked_in;
    const control=page.locator('.punch-control').first();
    await expect(control.getByRole('button',{name:wasIn?'Punch out':'Punch in'})).toBeVisible();
    await control.getByRole('button',{name:wasIn?'Punch out':'Punch in'}).click();
    await expect(control.getByRole('button',{name:wasIn?'Punch in':'Punch out'})).toBeVisible();
    // Return the test user to its initial attendance state.
    await control.getByRole('button',{name:wasIn?'Punch in':'Punch out'}).click();
  });
  test('desktop sidebar remains fixed when main content scrolls', async ({page})=>{
    await page.setViewportSize({width:1365,height:768});
    await login(page,persona('hr'));await navigate(page,'Employees');
    await page.getByRole('button',{name:'Add employee'}).click();
    await page.evaluate(()=>{const c=document.querySelector('main.content');if(c)c.scrollTop=500;});
    const sidebar=page.locator('.sidebar');
    const rect1=await sidebar.boundingBox();
    await page.evaluate(()=>{const c=document.querySelector('main.content');if(c)c.scrollTop=900;});
    const rect2=await sidebar.boundingBox();
    expect(rect1?.y).toBeCloseTo(rect2?.y||0,0);
  });
  test('unauthenticated API cannot view personnel information', async ({request})=>{
    const res=await request.get(API_URL+'/core/employees');
    expect(res.status()).toBe(401);
  });
  test('employee cannot configure company bonuses', async ({page})=>{
    await login(page,persona('developer_b'));
    const res=await page.request.put(API_URL+'/policies/project-bonus',{
      headers:{Origin:WEB_URL},data:{default_project_bonus_inr:15000},
    });
    expect(res.status()).toBe(403);
  });
});

test.describe('business-critical cross-role workflows',()=>{
  test('HR policy form saves company sourcing bonus through browser CORS', async ({page})=>{
    await login(page,persona('hr'));await navigate(page,'Policies');
    await page.getByPlaceholder('Explain why this policy change is needed').fill('HR bonus default needs approval for future placements.');
    await page.locator('#default-bonus').fill('10000');
    await page.getByRole('button',{name:'Save policy'}).click();
    await expect(page.getByText(/Bonus policy sent for admin approval/)).toBeVisible();
    const proposals=await (await page.request.get(API_URL+'/governance/requests')).json();
    const req=proposals.find((r:any)=>r.kind==='bonus_policy'&&r.status==='pending');
    expect(req).toBeTruthy();
    const admin=await request.newContext({extraHTTPHeaders:{Origin:WEB_URL}});
    try{
      expect((await admin.post(API_URL+'/auth/login',{data:{email:process.env.E2E_ADMIN_EMAIL,
        password:process.env.E2E_ADMIN_PASSWORD}})).status()).toBe(200);
      const ok=await admin.post(API_URL+'/governance/requests/'+req.id+'/review',{
        data:{approve:true,reason:'Reviewed HR sourcing bonus for new placements.'}});
      expect(ok.status()).toBe(200);
    }finally{await admin.dispose()}
    const response=await page.request.get(API_URL+'/policies/project-bonus');
    expect(response.ok()).toBeTruthy();
    expect((await response.json()).default_project_bonus_inr).toBe(10000);
  });

  test('HR creates sourced project and inherited bonus without typing amount', async ({page})=>{
    await login(page,persona('hr'));await navigate(page,'Projects');
    await page.getByRole('button',{name:'Add project'}).click();
    const unique='E2E QA Client Project '+Date.now();
    await page.locator('input[placeholder="e.g. Java Modernization"]').fill(unique);
    await page.locator('input[placeholder="e.g. Acme Corporation"]').fill('QA Client Company');
    await page.locator('#proj-sourced').selectOption(String(persona('sales_b').id));
    await expect(page.locator('.project-auto-bonus')).toContainText('₹10,000');
    await page.locator('input[type="date"]').fill(new Date().toISOString().slice(0,10));
    await page.locator('input[placeholder="e.g. 75.00"]').fill('75');
    await page.getByRole('button',{name:'Save project'}).click();
    await expect(page.getByRole('status')).toContainText('Project');
    await page.getByRole('textbox',{name:'Search projects'}).fill(unique);
    await expect(page.locator('.project-table')).toContainText(unique);
    await expect(page.locator('.project-table')).toContainText('₹10,000');
  });

  test('employee leave flows through reporting manager then HR', async ({page})=>{
    test.setTimeout(45000);
    const date=new Date();
    const weekday=date.getUTCDay();
    const offset=((8-weekday)%7)+7;
    date.setUTCDate(date.getUTCDate()+offset);
    const day=date.toISOString().slice(0,10);
    const reason='QA manager routing '+Date.now();
    await login(page,persona('hr'));
    const admin=await request.newContext({extraHTTPHeaders:{Origin:WEB_URL}});
    try{
      expect((await admin.post(API_URL+'/auth/login',{data:{email:process.env.E2E_ADMIN_EMAIL,
        password:process.env.E2E_ADMIN_PASSWORD}})).status()).toBe(200);
      const policy=await admin.put(API_URL+'/leave/policies',{
        data:{leave_type:'casual',annual_days:12,monthly_accrual:0,
              approval_chain:['manager','hr'],probation_allowed:true,active:true}});
      expect(policy.status()).toBe(200);
    }finally{await admin.dispose()}
    await page.locator('.sidebar nav').getByRole('button',{name:'Sign out'}).click();
    await login(page,persona('sales_a'));
    await navigate(page,'Leave requests');
    await page.locator('.leave-form select').first().selectOption('casual');
    await page.locator('.leave-form input[type="date"]').nth(0).fill(day);
    await page.locator('.leave-form input[type="date"]').nth(1).fill(day);
    await page.locator('.leave-form textarea').fill(reason);
    await page.getByRole('button',{name:'Submit request'}).click();
    await expect(page.getByRole('status')).toContainText('submitted for approval');
    await page.locator('.sidebar nav').getByRole('button',{name:'Sign out'}).click();

    // Verify the manager review with an isolated authenticated API session.
    // The submission stage above remains a full UI test; the manager and HR
    // stages independently verify role-scoped authorization and state changes.
    const managerReview=await request.newContext({extraHTTPHeaders:{Origin:WEB_URL}});
    try{
      const signedIn=await managerReview.post(API_URL+'/auth/login',{data:{
        email:persona('manager').email,password:TEST_PASSWORD}});
      expect(signedIn.status()).toBe(200);
      const approvals=await managerReview.get(API_URL+'/leave/requests?scope=approvals');
      expect(approvals.status()).toBe(200);
      const managerRow=(await approvals.json()).find((x:any)=>x.reason===reason);
      expect(managerRow).toBeTruthy();
      expect(managerRow.current_stage).toBe('manager');
      const reviewed=await managerReview.post(API_URL+'/leave/requests/'+managerRow.id+'/review',{
        data:{action:'approve',note:'Reporting manager approved employee request'}});
      expect(reviewed.status()).toBe(200);
      expect((await reviewed.json()).current_stage).toBe('hr');
    }finally{await managerReview.dispose()}

    // Isolated HR session avoids stale UI state when changing browser personas.
    const hrReview=await request.newContext({extraHTTPHeaders:{Origin:WEB_URL}});
    try{
      const signedIn=await hrReview.post(API_URL+'/auth/login',{data:{
        email:persona('hr').email,password:TEST_PASSWORD}});
      expect(signedIn.status()).toBe(200);
      const pending=await hrReview.get(API_URL+'/leave/requests?scope=approvals');
      expect(pending.status()).toBe(200);
      const row=(await pending.json()).find((x:any)=>x.reason===reason);
      expect(row?.current_stage).toBe('hr');
      const approved=await hrReview.post(API_URL+'/leave/requests/'+row.id+'/review',{
        data:{action:'approve',note:'HR validated the manager approval'}});
      expect(approved.status()).toBe(200);
      expect((await approved.json()).status).toBe('approved');
      const all=await hrReview.get(API_URL+'/leave/requests?scope=all');
      expect((await all.json()).find((x:any)=>x.id===row.id)?.status).toBe('approved');
    }finally{await hrReview.dispose()}
  });
});
