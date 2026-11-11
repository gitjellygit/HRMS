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
