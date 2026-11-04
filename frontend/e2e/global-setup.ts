import { request, type APIRequestContext, type FullConfig } from '@playwright/test';
import { mkdirSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { WEB_URL, API_URL } from '../playwright.config';

export const TEST_PASSWORD = 'DemoOnly!Pass1234';
export const E2E_DIR = resolve(__dirname, '.auth');
export const USERS_FILE = resolve(E2E_DIR, 'users.json');

type Persona = { key: string; name: string; department: string; code: string; role: string; designation: string; email: string; id: number; };
const SEEDS = [
  ['sales_a', 'Aarav Sales', 'Bench Sales', 'BSA', 'employee', 'Bench Sales Executive'],
  ['sales_b', 'Ishita Sales', 'Bench Sales', 'BSA', 'employee', 'Bench Sales Executive'],
  ['sales_c', 'Kabir Sales', 'Bench Sales', 'BSA', 'employee', 'Bench Sales Executive'],
  ['developer_a', 'Nisha Developer', 'Engineering', 'ENG', 'employee', 'Software Developer'],
  ['developer_b', 'Rohan Developer', 'Engineering', 'ENG', 'employee', 'Software Developer'],
  ['hr', 'Meera Humanresources', 'Human Resources', 'HR', 'hr', 'HR Specialist'],
  ['accountant', 'Dev Accountant', 'Finance', 'FIN', 'accountant', 'Accountant'],
  ['manager', 'Neha Manager', 'Bench Sales', 'BSA', 'manager', 'Bench Sales Manager'],
] as const;

async function required(context: APIRequestContext, url: string, options: Parameters<APIRequestContext['post']>[1]) {
  const response = await context.post(API_URL + url, options);
  if (!response.ok()) throw Error('E2E seed failed: POST ' + url + ' -> ' + response.status() + ' ' + (await response.text()).slice(0, 500));
  return response.json();
}

export default async function setup(_config: FullConfig) {
  // Never seed any shared dev/prod database. Explicit opt-in plus loopback origins
  // are necessary even if someone copies the command by accident.
  if (process.env.E2E_ALLOW_SEED !== 'isolated') throw Error('E2E_ALLOW_SEED=isolated is required for fixture creation.');
  for (const url of [WEB_URL, API_URL]) {
    const target = new URL(url);
    if (!['localhost', '127.0.0.1'].includes(target.hostname)) throw Error('E2E can only target loopback URLs.');
  }
  if (!process.env.E2E_ADMIN_EMAIL || !process.env.E2E_ADMIN_PASSWORD) throw Error('Supply E2E_ADMIN_EMAIL and E2E_ADMIN_PASSWORD in the test environment.');

  mkdirSync(E2E_DIR, { recursive: true });
  const admin = await request.newContext({ extraHTTPHeaders: { Origin: WEB_URL } });
  const login = await admin.post(API_URL + '/auth/login', {
    data: { email: process.env.E2E_ADMIN_EMAIL, password: process.env.E2E_ADMIN_PASSWORD, remember: false },
  });
  if (!login.ok()) throw Error('Cannot sign into isolated HRMS as seeded administrator: ' + login.status());
  const departments: Record<string, number> = {};
  const token = String(Date.now()).slice(-8);
  for (const [, , department, code] of SEEDS) {
    if (departments[department]) continue;
    const unit = await required(admin, '/core/units', {
      data: { kind: 'department', name: department + ' QA ' + token, code: code + '-' + token },
    });
    departments[department] = unit.id;
  }
  const users: Persona[] = [];
  for (const [key, name, department, code, role, designation] of SEEDS) {
    const email = 'qa.' + key + '.' + token + '@example.org';
    const result = await required(admin, '/core/employees', {
      data: {
        account: {
          name, email, role, designation, department, joining_date: '2026-04-01',
          password: TEST_PASSWORD, employee_code: '', employment_type: 'Full time',
        },
        master: { department_id: departments[department] },
      },
    });
    users.push({ key, name, department: department + ' QA ' + token, code, role, designation, email, id: result.id });
  }
  // Route Bench Sales approvals to their actual reporting manager.
  const manager = users.find(person => person.key === 'manager')!;
  for (const sales of users.filter(person => person.key.startsWith('sales_'))) {
    const update = await admin.put(API_URL + '/core/employees/' + sales.id, {
      data: { manager_id: manager.id, department_id: departments['Bench Sales'] },
    });
    if (!update.ok()) throw Error('Could not assign sales reporting manager: ' + (await update.text()).slice(0, 350));
  }
  await admin.dispose();
  writeFileSync(USERS_FILE, JSON.stringify({ users, token }, null, 2), { mode: 0o600 });

  // Verify the seeded accounts really authenticate before UI tests begin.
  for (const persona of users) {
    const check = await request.newContext();
    const response = await check.post(API_URL + '/auth/login', {
      data: { email: persona.email, password: TEST_PASSWORD },
    });
    if (!response.ok()) throw Error('Seeded account failed login: ' + persona.key);
    await check.dispose();
  }
  process.stdout.write('Prepared ' + users.length + ' isolated E2E accounts; no real employee credentials used.\n');
}
