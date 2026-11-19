import {test,expect,Locator} from '@playwright/test';
import {login,navigate,users} from './helpers';

/** Explicit WCAG 2.1 AA 4.5:1 text contrast against its rendered surface.
 * Checking colors differ is not sufficient: pale text on pale backgrounds
 * looked acceptable to the previous smoke tests but was unreadable in the UI.
 */
async function checkContrast(locator:Locator,surface:".payroll-validation"|".payroll-net-preview",label:string){
 const sample=await locator.evaluate((el,bgSelector)=>{
  const bg=el.closest(bgSelector);
  if(!bg)throw Error('Missing background surface for contrast assertion');
  return {
   foreground:getComputedStyle(el).color,
   background:getComputedStyle(bg).backgroundColor
  };
 },surface);
 const rgb=(value:string)=>{
  const numbers=value.match(/[0-9]+(?:\.[0-9]+)?/g)?.map(Number)||[];
  if(numbers.length<3)throw Error('Not an RGB color: '+value);
  return numbers.slice(0,3);
 };
 const luminosity=(value:string)=>{
  const [r,g,b]=rgb(value).map(n=>{
   const c=n/255;
   return c<=0.04045?c/12.92:Math.pow((c+0.055)/1.055,2.4);
  });
  return 0.2126*r+0.7152*g+0.0722*b;
 };
 const front=luminosity(sample.foreground),back=luminosity(sample.background);
 const ratio=(Math.max(front,back)+0.05)/(Math.min(front,back)+0.05);
 expect(ratio,`${label}: foreground ${sample.foreground} against ${sample.background}`).toBeGreaterThanOrEqual(4.5);
}

for(const theme of ['light','dark'] as const){
 test(`Payroll salary validation and gross preview meet AA contrast in ${theme} mode`,async({page})=>{
  const hr=users().find(p=>p.key==='hr')!;
  await login(page,hr);
  await page.evaluate(mode=>{document.documentElement.dataset.theme=mode},theme);
  await navigate(page,'Payroll & expenses');
  await expect(page.getByRole('heading',{name:'Configure employee payroll'})).toBeVisible();
  const preview=page.locator('.payroll-net-preview');
  await expect(preview).toBeVisible();
  await checkContrast(preview.locator('span'),'.payroll-net-preview','Proposed gross monthly salary label');
  await checkContrast(preview.locator('strong'),'.payroll-net-preview','Proposed gross monthly salary total');
  await checkContrast(preview.locator('small'),'.payroll-net-preview','Gross monthly salary explanation');

  await page.getByRole('button',{name:'Submit salary approval request'}).click();
  const warning=page.locator('.payroll-validation');
  await expect(warning).toBeVisible();
  await expect(warning.getByText('Fix these fields before submitting:')).toBeVisible();
  await checkContrast(warning.locator('strong'),'.payroll-validation','Validation heading');
  await checkContrast(warning.locator('li').first(),'.payroll-validation','Validation error list item');
  await page.getByRole('tab',{name:'Statutory deductions'}).click();
  await page.getByRole('button',{name:'Submit statutory approval request'}).click();
  await expect(warning).toBeVisible();
  await checkContrast(warning.locator('strong'),'.payroll-validation','Statutory validation heading');
  await page.getByRole('tab',{name:'Additional earnings'}).click();
  await page.getByRole('button',{name:'Submit component approval request'}).click();
  await expect(warning).toBeVisible();
  await checkContrast(warning.locator('strong'),'.payroll-validation','Earnings validation heading');
 });
}
