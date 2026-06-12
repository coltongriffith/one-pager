// Serverless PDF printer: receives { html } and returns PDF bytes.
// Uses @sparticuz/chromium, a Chromium build packaged for serverless runtimes.

const chromium = require('@sparticuz/chromium');
const puppeteer = require('puppeteer-core');

const MAX_HTML_BYTES = 6 * 1024 * 1024;

module.exports = async (req, res) => {
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

  let browser;
  try {
    browser = await puppeteer.launch({
      args: chromium.args,
      executablePath: await chromium.executablePath(),
      headless: 'shell',
    });
    const page = await browser.newPage();
    await page.setContent(html, { waitUntil: 'load', timeout: 30000 });
    await page.evaluate(() => document.fonts.ready);
    const pdf = await page.pdf({
      preferCSSPageSize: true,
      printBackground: true,
      pageRanges: '1',
    });
    res.setHeader('Content-Type', 'application/pdf');
    res.setHeader('Content-Disposition', 'inline; filename="onepager.pdf"');
    res.status(200).send(Buffer.from(pdf));
  } catch (err) {
    res.status(500).json({ error: `PDF rendering failed: ${err.message}` });
  } finally {
    if (browser) await browser.close();
  }
};
