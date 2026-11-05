import {test,expect,request} from '@playwright/test';
import {API_URL,WEB_URL} from '../playwright.config';
import {login,navigate,users} from './helpers';

const qa=(key:string)=>users().find(u=>u.key===key)!;

test('generate employee ID advances sequence and remains editable',async({page})=>{
  await login(page,qa('hr'));await navigate(page,'Employees');
  await page.getByRole('button',{name:'Add employee'}).click();
  const field=page.getByRole('textbox',{name:'Employee ID (editable)'});
  await expect(field).toHaveValue(/^JG-\d{3,}$/);
  const before=Number((await field.inputValue()).slice(3));
  await page.getByRole('button',{name:/Generate ID/}).click();
  await expect.poll(async()=>Number((await field.inputValue()).slice(3))).toBe(before+1);
  await field.fill('JG-0098');
  await expect(field).toHaveValue('JG-0098');
});

test('project number can be generated twice or entered manually',async({page})=>{
  await login(page,qa('hr'));await navigate(page,'Projects');
  await page.getByRole('button',{name:'Add project'}).click();
  const field=page.getByRole('textbox',{name:'Project number (editable)'});
  await expect(field).toHaveValue(/^JG-P-\d{4,}$/);
  const before=Number((await field.inputValue()).slice(5));
  await page.getByRole('button',{name:'Generate',exact:true}).click();
  await expect.poll(async()=>Number((await field.inputValue()).slice(5))).toBe(before+1);
  await field.fill('JG-P-0098');
  await expect(field).toHaveValue('JG-P-0098');
});

test('HR can add company policy and view it in the register',async({page})=>{
  await login(page,qa('hr'));await navigate(page,'Policies');
  await page.getByRole('button',{name:'Add policy'}).click();
  const title='QA policy '+Date.now();
  await page.locator('.policy-record-form input').first().fill(title);
  await page.locator('.policy-record-form textarea').fill('Quality assurance policy for controlled test data, never applied to real employee records.');
  await page.getByPlaceholder('Explain why this policy change is needed').fill('HR onboarding policy requires independent admin approval.');
  await page.getByRole('button',{name:'Create policy'}).click();
  await expect(page.getByText(/Policy submitted for admin approval/)).toBeVisible();
  const proposals=await (await page.request.get(API_URL+'/governance/requests')).json();
  const proposal=proposals.find((r:any)=>r.payload?.title===title);
  expect(proposal?.status).toBe('pending');
  const admin=await request.newContext({extraHTTPHeaders:{Origin:WEB_URL}});
  try{
    expect((await admin.post(API_URL+'/auth/login',{data:{email:process.env.E2E_ADMIN_EMAIL,
      password:process.env.E2E_ADMIN_PASSWORD}})).status()).toBe(200);
    expect((await admin.post(API_URL+'/governance/requests/'+proposal.id+'/review',{data:{
      approve:true,reason:'Approved for controlled QA onboarding policy.'}})).status()).toBe(200);
  }finally{await admin.dispose()}
  await page.reload();
  await navigate(page,'Policies');
  await expect(page.locator('.policy-record-list')).toContainText(title);
});

test('employee master record shows mobile and probation dates',async({page})=>{
  await login(page,qa('hr'));await navigate(page,'Employees');
  await page.getByRole('textbox',{name:'Search employees'}).fill(qa('developer_a').name);
  await page.getByRole('button',{name:qa('developer_a').name,exact:true}).click();
  await expect(page.locator('.core-contact-grid')).toContainText('Indian mobile');
  await expect(page.locator('.core-contact-grid')).toContainText('90-day probation ends');
  await expect(page.locator('.core-contact-grid')).toContainText('Date of joining');
});

test('attendance groups sessions by day and expands/collapses',async({page})=>{
  await login(page,qa('sales_b'));await navigate(page,'Attendance');
  const group=page.locator('.attendance-day').first();
  // Produce a completed session in this isolated test account when none exists.
  const open=await page.request.get((process.env.E2E_API_URL||'http://127.0.0.1:8100')+'/attendance/status');
  const wasIn=(await open.json()).checked_in;
  if(!wasIn){
    await page.locator('.punch-control').getByRole('button',{name:'Punch in'}).click();
  }
  await page.locator('.punch-control').getByRole('button',{name:'Punch out'}).click();
  await expect(group).toBeVisible();
  const summary=group.getByRole('button').first();
  await expect(summary).toHaveAttribute('aria-expanded','true');
  await summary.click();
  await expect(summary).toHaveAttribute('aria-expanded','false');
  await summary.click();
  await expect(group.locator('table')).toBeVisible();
});

test('employee cannot issue HR password resets',async({page})=>{
  await login(page,qa('sales_a'));
  const response=await page.request.post((process.env.E2E_API_URL||'http://127.0.0.1:8100')+
    '/core/employees/'+qa('developer_a').id+'/reset-password',{
    headers:{Origin:process.env.E2E_WEB_URL||'http://127.0.0.1:3100'},
    data:{reason:'Requesting reset without HR permissions'},
  });
  expect(response.status()).toBe(403);
});
