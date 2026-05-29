// Playwright test — valida todas as páginas do Jarvis (exceto agentes/hermes desligados)
import { chromium } from 'playwright';

const BASE = 'https://10.140.0.220';
const EMAIL = process.env.JARVIS_EMAIL || '';
const PASS  = process.env.JARVIS_PASS  || '';

const PAGES = [
  { path: '/',                       name: 'Home' },
  { path: '/moneypenny',             name: 'Moneypenny' },
  { path: '/perfil',                 name: 'Perfil' },
  { path: '/freshservice',           name: 'Freshservice' },
  { path: '/desempenho',             name: 'Desempenho' },
  { path: '/admin/acesso',           name: 'Gerenciamento de Acesso' },
  { path: '/admin/logs',             name: 'Logs' },
  { path: '/admin/monitoramento',    name: 'Monitoramento' },
  { path: '/admin/gastos',           name: 'Gastos' },
  { path: '/admin/fiscal',           name: 'Fiscal' },
  { path: '/admin/governanca',       name: 'Governança' },
  { path: '/admin/payfly',           name: 'PayFly' },
  { path: '/admin/proposals',        name: 'Proposals' },
  { path: '/admin/cto-inbox',        name: 'CTO Inbox' },
  { path: '/admin/orquestrador',     name: 'Orquestrador' },
  // Desligados — skip:
  // { path: '/admin/agentes',       name: 'Agentes' },
  // { path: '/admin/hermes',        name: 'Hermes' },
];

async function run() {
  const browser = await chromium.launch({
    executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    headless: true,
    args: ['--ignore-certificate-errors', '--no-sandbox']
  });

  const ctx = await browser.newContext({ ignoreHTTPSErrors: true });
  const page = await ctx.newPage();

  const errors   = [];
  const warnings = [];
  const passed   = [];

  // Captura erros de console
  page.on('console', msg => {
    if (msg.type() === 'error') errors.push({ page: page.url(), msg: msg.text() });
  });
  page.on('pageerror', err => errors.push({ page: page.url(), msg: err.message }));

  // ── Login ──────────────────────────────────────────────────────────
  console.log('🔐 Fazendo login...');
  await page.goto(`${BASE}/login`, { waitUntil: 'networkidle', timeout: 15000 });
  await page.fill('input[type="email"]', EMAIL);
  await page.fill('input[type="password"]', PASS);

  const [loginResp] = await Promise.all([
    page.waitForResponse(r => r.url().includes('/api/auth/login'), { timeout: 10000 }),
    page.click('button[type="submit"]')
  ]);

  const loginStatus = loginResp.status();
  if (loginStatus !== 200) {
    console.error(`❌ Login falhou — HTTP ${loginStatus}`);
    await browser.close();
    process.exit(1);
  }
  console.log(`✅ Login OK (${loginStatus})\n`);

  // ── Testa cada página ──────────────────────────────────────────────
  for (const p of PAGES) {
    const url = `${BASE}${p.path}`;
    const pageErrors = [];

    page.removeAllListeners('console');
    page.removeAllListeners('pageerror');
    page.on('console', msg => { if (msg.type() === 'error') pageErrors.push(msg.text()); });
    page.on('pageerror', err => pageErrors.push(err.message));

    const failed5xx = [];
    page.on('response', resp => {
      if (resp.status() >= 500) failed5xx.push(`${resp.status()} ${resp.url()}`);
    });

    try {
      const resp = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 15000 });
      await page.waitForTimeout(2000); // aguarda requests async

      const finalUrl = page.url();
      const httpStatus = resp?.status();
      const redirectedToLogin = finalUrl.includes('/login');

      if (redirectedToLogin) {
        warnings.push(`WARN  [${p.name}] Redirecionou para login (sessão expirou?)`);
        console.log(`⚠️  ${p.name} → redirecionou para login`);
      } else if (failed5xx.length > 0) {
        errors.push({ page: p.name, msg: failed5xx.join(', ') });
        console.log(`❌  ${p.name} → 5xx: ${failed5xx.join(', ')}`);
      } else if (pageErrors.length > 0) {
        // Filtra erros conhecidos/inofensivos
        const real = pageErrors.filter(e =>
          !e.includes('favicon') &&
          !e.includes('net::ERR_ABORTED') &&
          !e.includes('evolution-api') &&
          !e.includes('hermes')
        );
        if (real.length > 0) {
          warnings.push(`WARN  [${p.name}] Console errors: ${real.slice(0,2).join(' | ')}`);
          console.log(`⚠️  ${p.name} → console error: ${real[0]?.substring(0, 100)}`);
        } else {
          passed.push(p.name);
          console.log(`✅  ${p.name}`);
        }
      } else {
        passed.push(p.name);
        console.log(`✅  ${p.name}`);
      }
    } catch (e) {
      errors.push({ page: p.name, msg: e.message });
      console.log(`❌  ${p.name} → ${e.message.substring(0, 80)}`);
    }
  }

  await browser.close();

  // ── Relatório ──────────────────────────────────────────────────────
  console.log('\n══════════════════════════════════════════');
  console.log(`RESULTADO: ${passed.length} OK | ${warnings.length} WARN | ${errors.length} FAIL`);
  if (warnings.length) { console.log('\nAVISOS:'); warnings.forEach(w => console.log(' ' + w)); }
  if (errors.length)   { console.log('\nERROS:');  errors.forEach(e => console.log(` FAIL [${e.page}] ${e.msg?.substring(0,120)}`)); }
  console.log('══════════════════════════════════════════');
}

run().catch(e => { console.error('FATAL:', e.message); process.exit(1); });
