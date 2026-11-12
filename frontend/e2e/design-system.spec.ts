import {test,expect} from '@playwright/test';
import {login,navigate,users} from './helpers';

const hr=()=>users().find(u=>u.key==='hr')!;

test('timesheet cards form an aligned 2-by-2 grid and required asterisks stay inline',async({page})=>{
 await page.setViewportSize({width:1440,height:900});
 await login(page,hr());
 await navigate(page,'Time & shifts');
 await page.getByRole('tab',{name:'Timesheets'}).click();
 const card=async(cls:string)=>page.locator('.timesheet-workspace-grid '+cls).boundingBox();
 const entry=await card('.timesheet-log-card');
 const mine=await card('.timesheet-entries-card');
 const review=await card('.timesheet-review-card');
 const assign=await card('.timesheet-assignments-card');
 for(const box of [entry,mine,review,assign])expect(box).not.toBeNull();
 expect(Math.abs(entry!.y-mine!.y)).toBeLessThan(3);
 expect(Math.abs(review!.y-assign!.y)).toBeLessThan(3);
 expect(Math.abs(entry!.x-review!.x)).toBeLessThan(3);
 expect(Math.abs(mine!.x-assign!.x)).toBeLessThan(3);
 for(const name of ['task','hours']){
  const label=page.locator('.timesheet-log-card').locator('label').filter({has:page.locator('[name='+name+']')});
  const marker=label.locator('.required');
  const title=label.locator('.field-label-line');
  const labelBox=await title.boundingBox(),markBox=await marker.boundingBox();
  expect(labelBox).not.toBeNull();
  expect(markBox).not.toBeNull();
  expect(markBox!.y).toBeGreaterThanOrEqual(labelBox!.y-2);
  expect(markBox!.y+markBox!.height).toBeLessThanOrEqual(labelBox!.y+labelBox!.height+3);
 }
});

test('timesheet cards stack cleanly on a narrow mobile screen',async({page})=>{
 await page.setViewportSize({width:390,height:844});
 await login(page,hr());
 await navigate(page,'Time & shifts');
 await page.getByRole('tab',{name:'Timesheets'}).click();
 const cards=page.locator('.timesheet-workspace-grid > .employee-surface');
 const boxes=await cards.evaluateAll(nodes=>nodes.map(x=>({x:x.getBoundingClientRect().x,y:x.getBoundingClientRect().y})));
 expect(boxes.length).toBe(4);
 for(let i=1;i<boxes.length;i++){
  expect(Math.abs(boxes[i].x-boxes[0].x)).toBeLessThan(3);
  expect(boxes[i].y).toBeGreaterThan(boxes[i-1].y);
 }
});

test('primary and secondary actions use one consistent theme throughout all HRMS sections and tabs',async({page})=>{
 test.setTimeout(180000);
 await page.setViewportSize({width:1440,height:900});
 await login(page,hr());
 for(const pageName of ['Overview','Notifications','Employees','Attendance','Time & shifts','Payroll & expenses',
  'Finance & invoicing','Admin approvals','People operations','Leave requests','Projects','Bonuses','Appraisals',
  'Performance & growth','HR overview','Policies','Organization','Org chart','My profile',
  'Profile requests','Bulk data & expiries']){
  const nav=page.locator('.sidebar nav').getByRole('button',{name:pageName,exact:true});
  if(!(await nav.isVisible()))continue;
  await navigate(page,pageName);
  const assertTheme=async(label:string)=>{
  const colors=await page.locator('main.content').evaluate(root=>{
   const isVisible=(el:HTMLElement)=>el.getClientRects().length>0;
   const buttons=Array.from(root.querySelectorAll<HTMLElement>('button.primary,button.secondary,button.employee-primary,button.employee-cancel'));
   return buttons.filter(isVisible).map(b=>({name:b.textContent?.trim().slice(0,60),type:b.classList.contains('employee-primary')||b.classList.contains('primary')?'primary':'secondary',
     color:getComputedStyle(b).backgroundColor}));
  });
  const primary=[...new Set(colors.filter(c=>c.type==='primary').map(c=>c.color))];
  const secondary=[...new Set(colors.filter(c=>c.type==='secondary').map(c=>c.color))];
  expect(primary.length,'Inconsistent primary buttons on '+label+': '+JSON.stringify(colors)).toBeLessThanOrEqual(1);
  expect(secondary.length,'Inconsistent secondary buttons on '+label+': '+JSON.stringify(colors)).toBeLessThanOrEqual(1);
  };
  await assertTheme(pageName);
  // Check visible subtabs as well as every sidebar page. Only tabs are clicked: no writes.
  const tabs=await page.getByRole('tab').allTextContents();
  for(const title of tabs.map(x=>x.trim()).filter(Boolean).slice(0,12)){
   const tab=page.getByRole('tab',{name:title,exact:true}).first();
   if(await tab.isVisible()){
    await tab.click();
    await assertTheme(pageName+' / '+title);
   }
  }
 }
});

test('payroll draft creation follows the list of existing runs',async({page})=>{
 await login(page,hr());
 await navigate(page,'Payroll & expenses');
 await page.getByRole('tab',{name:'Payroll runs'}).click();
 await expect(page.getByRole('heading',{name:'Existing payroll runs'})).toBeVisible();
 const cta=page.getByRole('button',{name:'Calculate payroll draft'});
 await expect(cta).toBeVisible();
 const list=await page.locator('.payroll-runs-list').boundingBox();
 const create=await page.locator('.payroll-create-draft').boundingBox();
 expect(list).not.toBeNull();
 expect(create).not.toBeNull();
 expect(create!.y).toBeGreaterThanOrEqual(list!.y+list!.height);
});
