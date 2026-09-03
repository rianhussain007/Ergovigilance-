const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const BACKEND_URL = 'http://localhost:8000';
const FRONTEND_URL = 'http://localhost:3000';
const OUTPUT_DIR = path.join(__dirname, '..', 'ui_posture', 'public', 'images');

async function main() {
  // Ensure output directory exists
  if (!fs.existsSync(OUTPUT_DIR)) {
    fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  }

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  try {
    // 1. Login to get JWT token
    console.log('1. Logging in...');
    const loginResponse = await page.request.post(`${BACKEND_URL}/api/auth/login`, {
      data: { username: 'admin@demo.com', password: 'Demo1234!' }
    });
    const loginData = await loginResponse.json();
    const token = loginData.access_token;
    console.log('   Token received');

    // 2. Set token in localStorage
    await page.goto(FRONTEND_URL);
    await page.evaluate((t) => {
      localStorage.setItem('ergovigilance_token', t);
      localStorage.setItem('ergovigilance_onboarded', 'true');
    }, token);

    // 3. Capture Dashboard
    console.log('2. Capturing Dashboard...');
    await page.goto(`${FRONTEND_URL}/dashboard`, { waitUntil: 'networkidle', timeout: 15000 });
    await page.waitForTimeout(3000);
    await page.screenshot({
      path: path.join(OUTPUT_DIR, 'dashboard-admin-full.png'),
      fullPage: false
    });
    console.log('   Dashboard captured');

    // 4. Capture Live Monitoring
    console.log('3. Capturing Live Monitoring...');
    await page.goto(`${FRONTEND_URL}/monitoring`, { waitUntil: 'networkidle', timeout: 15000 });
    await page.waitForTimeout(3000);
    await page.screenshot({
      path: path.join(OUTPUT_DIR, 'live_camera.png'),
      fullPage: false
    });
    console.log('   Live Monitoring captured');

    // 5. Capture Reports
    console.log('4. Capturing Reports...');
    await page.goto(`${FRONTEND_URL}/reports`, { waitUntil: 'networkidle', timeout: 15000 });
    await page.waitForTimeout(3000);
    await page.screenshot({
      path: path.join(OUTPUT_DIR, 'dashboard-operator.png'),
      fullPage: false
    });
    console.log('   Reports captured');

    // 6. Capture Landing Page
    console.log('5. Capturing Landing Page...');
    await page.goto(FRONTEND_URL, { waitUntil: 'networkidle', timeout: 15000 });
    await page.waitForTimeout(2000);
    await page.screenshot({
      path: path.join(OUTPUT_DIR, 'landing-hero.png'),
      fullPage: false
    });
    console.log('   Landing Page captured');

    console.log('\n✅ All 4 real screenshots captured successfully!');
    console.log(`   Output: ${OUTPUT_DIR}`);

  } finally {
    await browser.close();
  }
}

main().catch(err => {
  console.error('Failed:', err.message);
  process.exit(1);
});
