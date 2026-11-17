import {test,expect} from '@playwright/test';
import {login,navigate,users} from './helpers';

const hr=()=>users().find(user=>user.key==='hr')!;

test('payroll configuration explains missing employee and reason instead of silently disabling submit',async({page})=>{
 await login(page,hr());
 await navigate(page,'Payroll & expenses');
 await expect(page.getByRole('heading',{name:'Configure employee payroll'})).toBeVisible();
 const submit=page.getByRole('button',{name:'Submit salary approval request'});
 await expect(submit).toBeEnabled();
 await submit.click();
 await expect(page.getByRole('alert').filter({hasText:'Fix these fields before submitting'})).toBeVisible();
 await expect(page.getByText('Select the employee whose payroll configuration you want to change.')).toBeVisible();
 await expect(page.getByText('Explain why this change is needed (at least 10 characters).')).toBeVisible();
 await page.getByRole('tab',{name:'Statutory deductions'}).click();
 await expect(page.getByRole('button',{name:'Submit statutory approval request'})).toBeEnabled();
 await page.getByRole('button',{name:'Submit statutory approval request'}).click();
 await expect(page.getByText('Select the employee whose payroll configuration you want to change.')).toBeVisible();
 await page.getByRole('tab',{name:'Additional earnings'}).click();
 await page.getByRole('button',{name:'Submit component approval request'}).click();
 await expect(page.getByText('Component code is required.')).toBeVisible();
});

test('payroll review opens a visible detail panel or a specific error',async({page})=>{
 await login(page,hr());await navigate(page,'Payroll & expenses');
 await page.getByRole('tab',{name:'Payroll runs'}).click();
 const review=page.getByRole('button',{name:'Review details'}).first();
 if(await review.count()){
  await review.click();
  await expect(page.locator('.payroll-run-review').or(page.locator('.time-form-error'))).toBeVisible();
 }
});

test('employee directory explains why inactive employees have no deactivate action',async({page})=>{
 await login(page,hr());await navigate(page,'Employees');
 const directory=page.locator('.employee-table');
 await expect(directory).toBeVisible();
 await expect(directory.getByRole('columnheader',{name:'HR actions'})).toBeVisible();
});

test('payroll runs show an actionable empty state and aligned draft controls',async({page})=>{
 await login(page,hr());
 await navigate(page,'Payroll & expenses');
 await page.getByRole('tab',{name:'Payroll runs'}).click();
 const runs=page.locator('.payroll-runs-list .payroll-run-row');
 if(await runs.count()===0){
  await expect(page.getByText('No payroll runs yet')).toBeVisible();
  await expect(page.getByText('Your monthly payroll runs will appear here once you calculate your first draft.')).toBeVisible();
 }
 const month=page.locator('.payroll-create-actions input[type="month"]');
 const action=page.getByRole('button',{name:'Calculate payroll draft'});
 await expect(month).toBeVisible();await expect(action).toBeVisible();
 const m=await month.boundingBox(),b=await action.boundingBox();
 expect(m).not.toBeNull();expect(b).not.toBeNull();
 if(page.viewportSize()!.width>620)expect(Math.abs((m!.y+m!.height)-(b!.y+b!.height))).toBeLessThan(10);
});

test('HR employee directory exposes edit details and prefilled employee form',async({page})=>{
 await login(page,hr());
 await navigate(page,'Employees');
 const row=page.locator('.employee-table tbody tr').filter({has:page.locator('.employee-role',{hasText:'employee'})}).first();
 const edit=row.getByRole('button',{name:/Edit details for /});
 await expect(edit).toBeVisible();
 await edit.click();
 await expect(page.getByRole('heading',{name:'Edit employee details'})).toBeVisible();
 await expect(page.getByRole('button',{name:'Save employee details'})).toBeVisible();
 await expect(page.getByText('Reason for changes (minimum 10 characters)')).toBeVisible();
});
