// Smoke test: load media-studio.js in jsdom, switch to Shorts mode, exercise the beats UI.
const {JSDOM, VirtualConsole} = require('jsdom');
const fs = require('fs');
const path = require('path');
const assert = require('assert');

const errors = [];
const virtualConsole = new VirtualConsole();
virtualConsole.on('jsdomError', e => errors.push(e.message || String(e)));

(async () => {
  const html = '<!doctype html><html><body><div id="desktop-media-studio"></div></body></html>';
  const dom = new JSDOM(html, {runScripts: 'outside-only', pretendToBeVisual: true, virtualConsole, url: 'http://localhost/'});
  const {window} = dom;
  window.URL.createObjectURL = () => 'blob:nexo-test';
  window.URL.revokeObjectURL = () => {};
  // jsdom has no canvas 2d; stub the contexts the module touches at setup.
  const ctxStub = () => new Proxy({}, {get: (t, k) => (k === 'measureText' ? () => ({width: 10}) : (k === 'canvas' ? {} : (...a) => ctxStub()))});
  window.HTMLCanvasElement.prototype.getContext = () => ctxStub();
  const src = fs.readFileSync(path.join(__dirname, '..', 'nexo7', 'web', 'media-studio.js'), 'utf8');
  await window.eval(`(async () => { ${src.replace(/^import .*$/gm, '').replace(/export /g, '')} })()`);
  const d = window.document;
  assert(d.getElementById('shorts-box'), 'shorts box exists');
  assert.equal(d.querySelectorAll('.shorts-beat').length, 3, '3 example beats rendered');
  const mode = d.getElementById('media-mode');
  mode.value = 'shorts';
  mode.dispatchEvent(new window.Event('change', {bubbles: true}));
  mode.onchange();
  assert(!d.getElementById('shorts-box').hidden, 'shorts box visible in shorts mode');
  assert(!d.getElementById('media-shorts').hidden, 'Record short video button visible');
  assert(!d.getElementById('media-shorts-srt').hidden, 'SRT button visible');
  assert(d.getElementById('media-video').hidden, 'old clip button hidden in shorts mode');
  assert(d.getElementById('shorts-info').textContent.includes('seconds'), 'timing info shown: ' + d.getElementById('shorts-info').textContent);
  // SRT export should produce a download link without errors.
  d.getElementById('media-shorts-srt').click();
  assert(d.querySelector('#media-output a[download$="-short.srt"]'), 'srt download link created');
  // Paragraph splitter.
  d.querySelector('#shorts-box textarea[aria-label="Paragraph to split into beats"]').value = 'First line here. Second line here!';
  [...d.querySelectorAll('#shorts-box button')].find(b => b.textContent.includes('Split paragraph')).click();
  assert.equal(d.querySelectorAll('.shorts-beat').length, 2, 'paragraph split into 2 beats');
  // Validation message for overlong input.
  const ta = d.querySelector('.shorts-beat textarea');
  ta.value = 'x'.repeat(141);
  ta.dispatchEvent(new window.Event('input', {bubbles: true}));
  assert(d.getElementById('shorts-info').textContent.includes('140'), 'overlong beat rejected: ' + d.getElementById('shorts-info').textContent);
  assert.deepEqual(errors, []);
  console.log('media-studio shorts smoke test passed');
  window.close();
})().catch(e => {console.error(e); process.exitCode = 1;});
