// Node port of capture_web.py's step DSL for the Higgsfield sandbox (live egress, no Python Playwright).
// Writes gh/frames/f_%05d.png plus gh/actions.json in the same schema, so stage.py / beats.py take it as a
// `capture` layer. Edit the STEPS block, run `node capture_sandbox.mjs`, tar the output and PUT it to a
// presigned R2 URL inside the same sandbox call (the sandbox is wiped between calls).
// Proven 2026-09-17 on github.com/G-Core/FastEdge-templates (215 frames, click + scroll + hover).
import pkg from '/usr/local/lib/node_modules/playwright/index.js';
import fs from 'fs';
const { chromium } = pkg;
const OUT = process.env.OUT || 'gh';
const css = [1440, 820], dpr = 2, fps = 25;
const NUKE = `(()=>{const k=['[id*="cookie" i]','[class*="cookie" i]','[id*="consent" i]','[class*="consent" i]'];for(const s of k){document.querySelectorAll(s).forEach(e=>{const r=e.getBoundingClientRect(); if(r.height<780) e.remove()})}})()`;
const STILL = `*,*::before,*::after{transition:none!important;animation:none!important;scroll-behavior:auto!important;caret-color:transparent!important}`;
const ease = p => { p = Math.max(0, Math.min(1, p)); return p < 0.5 ? 2 * p * p : 1 - Math.pow(-2 * p + 2, 2) / 2 };
let n = 0, cursor = [], events = [], cur = null, page;
const t = () => n / fps, fr = s => Math.max(1, Math.round(s * fps));
fs.mkdirSync(`${OUT}/frames`, { recursive: true });
async function snap() { await page.screenshot({ path: `${OUT}/frames/f_${String(n).padStart(5, '0')}.png`, type: 'png', animations: 'disabled', caret: 'hide' }); cursor.push(cur ? [cur[0], cur[1]] : null); n++; }
async function settle() { try { await page.evaluate(NUKE); await page.addStyleTag({ content: STILL }); } catch (e) { } }
async function point(tg) { if (Array.isArray(tg)) return tg; for (const sel of (Array.isArray(tg.any) ? tg.any : [tg])) { const loc = page.locator(sel).locator('visible=true').first(); try { await loc.scrollIntoViewIfNeeded({ timeout: 4000 }); const b = await loc.boundingBox(); if (b) return [b.x + b.width / 2, b.y + b.height / 2]; } catch (e) { } } throw new Error('not found ' + JSON.stringify(tg)); }
async function move(pt, dur) { const [x1, y1] = pt; if (!cur) cur = [Math.min(css[0] - 40, x1 + 260), Math.min(css[1] - 30, y1 + 180)]; const [x0, y0] = cur; const N = fr(dur); for (let i = 1; i <= N; i++) { const p = ease(i / N); cur = [x0 + (x1 - x0) * p, y0 + (y1 - y0) * p]; await page.mouse.move(cur[0], cur[1]); await snap(); } }
async function hold(s) { for (let i = 0; i < fr(s); i++) await snap(); }
async function goto(url, wait = 1.2) { await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 45000 }); try { await page.waitForLoadState('networkidle', { timeout: 8000 }); } catch (e) { } await settle(); await page.waitForTimeout(wait * 1000); await settle(); }
async function click(tg, wait = 1.2) { const pt = await point(tg); if (!cur || Math.hypot(cur[0] - pt[0], cur[1] - pt[1]) > 2) await move(pt, 0.7); await page.mouse.down(); await snap(); await page.mouse.up(); events.push({ t: t(), kind: 'click', x: cur[0], y: cur[1], end: t() + wait }); await page.waitForTimeout(150); try { await page.waitForLoadState('networkidle', { timeout: 6000 }); } catch (e) { } await settle(); await hold(wait); }
async function hover(tg, wait = 1.2) { await move(await point(tg), 0.6); events.push({ t: t(), kind: 'hover', x: cur[0], y: cur[1], end: t() + wait }); await hold(wait); }
async function scroll(dy, dur = 1.4, wait = 0.3) { const N = fr(dur), t0 = t(); let done = 0; for (let i = 1; i <= N; i++) { const tg = dy * ease(i / N); await page.mouse.wheel(0, tg - done); done = tg; await snap(); } events.push({ t: t0, kind: 'scroll', x: cur ? cur[0] : css[0] / 2, y: cur ? cur[1] : css[1] / 2, end: t() }); await hold(wait); }

const b = await chromium.launch({ args: ['--no-sandbox', '--hide-scrollbars'] });
const ctx = await b.newContext({ viewport: { width: css[0], height: css[1] }, deviceScaleFactor: dpr, reducedMotion: 'reduce', userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36' });
page = await ctx.newPage();

// ---- STEPS (edit per shot) ----------------------------------------------------------------
await goto('https://github.com/G-Core/FastEdge-templates');
await hold(1.0);
await click({ any: ['a[title="html2md"]', 'a:has-text("html2md")'] }, 1.4);
await scroll(520, 1.4, 0.3);
await hover({ any: ['article a:has-text("Deploy")', 'article img[alt*="Deploy" i]'] }, 1.5);
await hold(1.5);
// -------------------------------------------------------------------------------------------

await ctx.close(); await b.close();
fs.writeFileSync(`${OUT}/actions.json`, JSON.stringify({ css, dpr, fps, frames: n, cursor, events }));
console.log('frames', n, 'events', JSON.stringify(events));
