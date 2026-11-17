import {test,expect} from '@playwright/test';
import {login,navigate,users} from './helpers';
import {API_URL} from '../playwright.config';

const actor=(key:string)=>users().find(u=>u.key===key)!;

test('HR can inspect employee punches in New York time without modifying attendance',async({page})=>{
 await login(page,actor('hr'));
 await navigate(page,'Time & shifts');
 const audit=page.locator('.time-attendance-audit');
 await expect(audit.getByRole('heading',{name:'HR attendance audit'})).toBeVisible();
 await audit.getByLabel('Employee').selectOption(String(actor('developer_a').id));
 await audit.getByLabel('Work date').fill('2026-11-17');
 await audit.getByLabel('Time zone').selectOption('America/New_York');
 await audit.getByRole('button',{name:'View punch record'}).click();
 await expect(audit.locator('.time-audit-results')).toContainText(actor('developer_a').name);
 await expect(audit.locator('.time-audit-results')).toContainText('America/New_York');
 await expect(audit.locator('.time-audit-results')).toContainText('Inferred breaks');
});

test('HR can configure separate April-Nov and December-March accrual rates',async({page})=>{
 await login(page,actor('hr'));
 await navigate(page,'Leave requests');
 await page.getByRole('button',{name:'Policies & balances'}).click();
 await expect(page.getByText('Monthly accrual Dec–Mar (days)')).toBeVisible();
 await page.getByLabel('Monthly accrual (days)',{exact:true}).fill('1.5');
 await page.getByLabel('Monthly accrual Dec–Mar (days)').fill('2.5');
 await expect(page.getByText(/22-day example/)).toBeVisible();
});

test('HR can upload one manual payslip; other employee cannot download it',async({page})=>{
 await login(page,actor('hr'));
 await navigate(page,'Payroll & expenses');
 await page.getByRole('tab',{name:'My payslips'}).click();
 const form=page.locator('.payroll-manual-upload');
 await expect(form).toBeVisible();
 await form.locator('select').first().selectOption(String(actor('developer_a').id));
 await form.getByLabel('Pay period').fill('2026-11');
 const pdf=Buffer.from('%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n%%EOF');
 await form.getByLabel('Payslip PDF (max 5 MB)').setInputFiles({
  name:'QA-november.pdf',mimeType:'application/pdf',buffer:pdf});
 await form.getByLabel('Mandatory reason').fill('QA payroll manual payslip confidential access test');
 await form.getByRole('button',{name:'Publish manual payslip'}).click();
 await expect(page.getByText('Imported 1 payslip(s)')).toBeVisible();
 const all=await page.request.get(API_URL+'/payroll/manual-payslips');
 expect(all.ok()).toBeTruthy();
 const slip=(await all.json()).find((row:{employee_id:number;original_name:string})=>
  row.employee_id===actor('developer_a').id&&row.original_name==='QA-november.pdf');
 expect(slip).toBeTruthy();
 await page.locator('.sidebar nav').getByRole('button',{name:'Sign out'}).click();
 await login(page,actor('developer_b'));
 expect((await page.request.get(API_URL+'/payroll/manual-payslips/'+slip.id+'.pdf')).status()).toBe(403);
});
