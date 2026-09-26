const { chromium } = require('playwright');
const { spawn } = require('child_process');
const path = require('path');

async function main() {
  // Start a Python HTTP server on the dist folder
  const distPath = path.join(__dirname, '..', 'ui_posture', 'dist');
  const server = spawn('python', ['-m', 'http.server', '5199', '--directory', distPath], {
    stdio: 'ignore'
  });
  
  // Wait for server to start
  await new Promise(resolve => setTimeout(resolve, 2000));
  
  try {
    const browser = await chromium.launch({ headless: true });
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
    
    await page.goto('http://localhost:5199/', { waitUntil: 'networkidle', timeout: 15000 });
    await page.waitForTimeout(2000);
    
    // 1. Hero (viewport)
    await page.screenshot({ path: path.join(__dirname, '..', 'results', 'ui_comparison', 'v2_01_hero.png') });
    console.log('1. Hero viewport captured');
    
    // 2. Stats section
    await page.evaluate(() => window.scrollTo(0, 800));
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(__dirname, '..', 'results', 'ui_comparison', 'v2_02_stats.png') });
    console.log('2. Stats section captured');
    
    // 3. Technology section
    await page.evaluate(() => { document.querySelector('#technology')?.scrollIntoView(); });
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(__dirname, '..', 'results', 'ui_comparison', 'v2_03_tech.png') });
    console.log('3. Technology section captured');
    
    // 4. How It Works / Pipeline
    await page.evaluate(() => { document.querySelector('#how-it-works')?.scrollIntoView(); });
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(__dirname, '..', 'results', 'ui_comparison', 'v2_04_pipeline.png') });
    console.log('4. Pipeline section captured');
    
    // 5. Command Center
    await page.evaluate(() => { document.querySelector('#command-center')?.scrollIntoView(); });
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(__dirname, '..', 'results', 'ui_comparison', 'v2_05_command.png') });
    console.log('5. Command Center captured');
    
    // 6. CTA + Footer
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(__dirname, '..', 'results', 'ui_comparison', 'v2_06_footer.png') });
    console.log('6. CTA + Footer captured');
    
    // 7. Full page
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(__dirname, '..', 'results', 'ui_comparison', 'v2_07_full.png'), fullPage: true });
    console.log('7. Full page captured');
    
    await browser.close();
    console.log('\nAll 7 screenshots captured successfully!');
  } finally {
    server.kill();
  }
}

main().catch(console.error);
