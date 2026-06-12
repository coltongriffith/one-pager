// Serverless PDF printer: POST { html } returns PDF bytes.
// GET runs a self-test and reports diagnostics as JSON.
// Uses @sparticuz/chromium, a Chromium build packaged for serverless runtimes.
//
// Dependencies are required inside the handler so that a broken install
// produces a readable JSON error instead of a function-invocation crash.

const MAX_HTML_BYTES = 6 * 1024 * 1024;

function loadDeps() {
  // the package is ESM-first: under require() its API lives on .default
  const chromiumModule = require('@sparticuz/chromium');
  const chromium = chromiumModule.default || chromiumModule;
  const puppeteerModule = require('puppeteer-core');
  const puppeteer = puppeteerModule.default || puppeteerModule;
  return { chromium, puppeteer };
}

async function launchBrowser({ chromium, puppeteer }) {
  chromium.setGraphicsMode = false;
  return puppeteer.launch({
    args: chromium.args,
    executablePath: await chromium.executablePath(),
    headless: 'shell',
  });
}

async function printHtml(deps, html) {
  const browser = await launchBrowser(deps);
  try {
    const page = await browser.newPage();
    await page.setContent(html, { waitUntil: 'load', timeout: 30000 });
    await page.evaluate(() => document.fonts.ready);
    return await page.pdf({
      preferCSSPageSize: true,
      printBackground: true,
      pageRanges: '1',
    });
  } finally {
    await browser.close();
  }
}

const errText = (err) => (err.stack || String(err)).split('\n').slice(0, 5).join(' | ');

module.exports = async (req, res) => {
  let deps;
  try {
    deps = loadDeps();
  } catch (err) {
    res.status(500).json({ error: `printer dependencies failed to load: ${errText(err)}` });
    return;
  }

  if (req.method === 'GET') {
    // self-test: visit /api/pdf in a browser to diagnose the printer
    const report = {
      node: process.version,
      memoryMb: process.env.AWS_LAMBDA_FUNCTION_MEMORY_SIZE || null,
    };
    try {
      report.executablePath = await deps.chromium.executablePath();
      const pdf = await printHtml(deps, '<html><body><h1>self-test</h1></body></html>');
      report.ok = true;
      report.pdfBytes = pdf.length;
      res.status(200).json(report);
    } catch (err) {
      report.ok = false;
      report.error = errText(err);
      res.status(500).json(report);
    }
    return;
  }

  if (req.method !== 'POST') {
    res.status(405).json({ error: 'POST a JSON body: { "html": "..." }' });
    return;
  }
  const html = req.body && req.body.html;
  if (typeof html !== 'string' || !html.trim()) {
    res.status(400).json({ error: 'Missing "html" in request body' });
    return;
  }
  if (Buffer.byteLength(html, 'utf8') > MAX_HTML_BYTES) {
    res.status(413).json({ error: 'HTML payload too large' });
    return;
  }

  try {
    const pdf = await printHtml(deps, html);
    res.setHeader('Content-Type', 'application/pdf');
    res.setHeader('Content-Disposition', 'inline; filename="onepager.pdf"');
    res.status(200).send(Buffer.from(pdf));
  } catch (err) {
    res.status(500).json({ error: `PDF rendering failed: ${errText(err)}` });
  }
};
