// Execute the generated gallery's real review JavaScript with a minimal DOM.
// This tests the state/export contract, not browser layout or rendering.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const html = fs.readFileSync(process.argv[2] || 'docs/audit/live/index.html', 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const saved = new Map();
function article(evidence) {
  const select = {value: 'unreviewed', addEventListener(type, fn) { this[type] = fn; }};
  const textarea = {value: '', addEventListener(type, fn) { this[type] = fn; }};
  return {dataset: {case: 'menu', evidence}, select, textarea,
    querySelector(selector) { return selector === 'select' ? select : textarea; }};
}
function load(evidence) {
  const item = article(evidence), button = {};
  let download;
  const document = {
    querySelectorAll() { return [item]; },
    querySelector() { return button; },
    createElement() { return {click() {}}; }
  };
  vm.runInNewContext(script, {document, Blob, Date, JSON,
    localStorage: {getItem: key => saved.get(key), setItem: (key, value) => saved.set(key, value)},
    URL: {createObjectURL(blob) { download = blob; return 'blob:test'; }, revokeObjectURL() {}},
    setTimeout() {}
  }, {timeout: 1000});
  return {item, button, download: () => download};
}
const first = load('a'.repeat(64));
first.item.select.value = 'issue';
first.item.textarea.value = 'HUD split needs work';
first.item.select.change();
const reopened = load('a'.repeat(64));
assert.equal(reopened.item.select.value, 'issue');
assert.equal(reopened.item.textarea.value, 'HUD split needs work');
reopened.button.onclick();
const exported = JSON.parse(await reopened.download().text());
assert.equal(exported.schema, 'rcr-human-review-v1');
assert.equal(exported.reviews[0].evidence_sha256, 'a'.repeat(64));
assert.equal(exported.reviews[0].verdict, 'issue');
const changed = load('b'.repeat(64));
assert.equal(changed.item.select.value, 'unreviewed');
assert.equal(changed.item.textarea.value, '');
console.log('Review save/reload/export passed; changed evidence starts unreviewed.');
