import {test,expect} from '@playwright/test';
import {login,navigate,users} from './helpers';

const hr=()=>users().find(u=>u.key==='hr')!;

test('shared form buttons stay below inputs in asset allocation',async({page})=>{
 await login(page,hr());await navigate(page,'People operations');
 await page.getByRole('tab',{name:'Assets & helpdesk'}).click();
 const form=page.locator('.asset-allocation-form');
 await expect(form).toBeVisible();
 const fields=await form.locator('select,input').all();
 const boxes=await Promise.all(fields.map(e=>e.boundingBox()));
 const button=await form.getByRole('button',{name:'Allocate asset'}).boundingBox();
 expect(button).not.toBeNull();
 expect(Math.min(...boxes.filter(Boolean).map(b=>b!.x))).toBeGreaterThanOrEqual(0);
 expect(button!.y).toBeGreaterThanOrEqual(Math.max(...boxes.filter(Boolean).map(b=>b!.y+b!.height))-1);
});

test('time requests explain official work and ask for timezone during punch correction',async({page})=>{
 await login(page,hr());await navigate(page,'Time & shifts');
 await page.getByRole('tab',{name:'Requests'}).click();
 await page.locator('[name=kind]').selectOption('on_duty');
 await expect(page.getByText('Use this when your manager sends you to a client site')).toBeVisible();
 await page.locator('[name=kind]').selectOption('regularization');
 const zone=page.locator('select[name=timezone]');
 await expect(zone).toBeVisible();
 await zone.selectOption('America/Chicago');
 await expect(zone).toHaveValue('America/Chicago');
 await expect(page.getByText('EST/EDT and CST/CDT change automatically')).toBeVisible();
});

test('shift timezone options and GPS guidance are visible to HR',async({page})=>{
 await login(page,hr());await navigate(page,'Time & shifts');
 await page.getByRole('tab',{name:'Shifts & roster'}).click();
 const timezone=page.locator('.time-form select[name=timezone]');
 await expect(timezone).toBeVisible();
 await timezone.selectOption('America/New_York');
 await expect(timezone).toHaveValue('America/New_York');
 await page.getByRole('tab',{name:'Rules & GPS'}).click();
 await expect(page.getByRole('button',{name:'What does this do?'})).toBeVisible();
 await page.getByRole('button',{name:'What does this do?'}).click();
 await expect(page.getByText('Employees must allow location access')).toBeVisible();
});

test('payroll runs use a stable responsive grid for review actions',async({page})=>{
 await page.setViewportSize({width:1100,height:850});
 await login(page,hr());await navigate(page,'Payroll & expenses');
 await page.getByRole('tab',{name:'Payroll runs'}).click();
 const row=page.locator('.payroll-run-row').first();
 if(await row.count()){
  const display=await row.evaluate(e=>getComputedStyle(e).display);
  expect(display).toBe('grid');
  const review=await row.getByRole('button',{name:'Review details'}).boundingBox();
  expect(review).not.toBeNull();
  expect(review!.height).toBeGreaterThanOrEqual(38);
 }
});
