import test from 'node:test';
import assert from 'node:assert/strict';
import {splitBeats, beatSeconds, shortPlan, shortSrt, wrapCaption} from '../nexo7/web/media-studio.js';

test('splitBeats splits sentences and caps at 8 beats', () => {
  assert.deepEqual(splitBeats('Hello world. This is a second sentence!'), ['Hello world.', 'This is a second sentence!']);
  assert.deepEqual(splitBeats('One\nTwo\nThree'), ['One', 'Two', 'Three']);
  assert.throws(() => splitBeats('   '), /paragraph/);
  assert.throws(() => splitBeats(Array(9).fill('Short line.').join(' ')), /8/);
  const long = 'word '.repeat(60).trim() + '.';
  const parts = splitBeats(long);
  assert.ok(parts.length >= 2);
  assert.ok(parts.every(p => p.length <= 140));
});

test('beatSeconds clamps narration time to 3..12 seconds', () => {
  assert.equal(beatSeconds('Hi there.'), 3);
  assert.equal(beatSeconds('a '.repeat(60).trim()), 12);
  const mid = beatSeconds('This is a normal ten word sentence for timing here.');
  assert.ok(mid > 3 && mid < 12);
  assert.throws(() => beatSeconds(''), /1 to 140/);
});

test('shortPlan validates beats and lays out timings', () => {
  const plan = shortPlan([
    {text: 'Hello world.', scene: 'landscape', palette: 'sunrise'},
    {text: 'A second beat with more words in it.', scene: 'space', palette: 'night'},
  ]);
  assert.equal(plan.items.length, 2);
  assert.equal(plan.items[0].start, 0);
  assert.ok(plan.items[1].start >= plan.items[0].end - 0.001);
  assert.ok(plan.total > 0 && plan.total <= 60);
  assert.throws(() => shortPlan([]), /at least one/);
  assert.throws(() => shortPlan([{text: 'x'.repeat(141), scene: 'landscape', palette: 'sunrise'}]), /140/);
  assert.throws(() => shortPlan([{text: 'Hi.', scene: 'nope', palette: 'sunrise'}]), /scene/);
  assert.throws(() => shortPlan([{text: 'Hi.', scene: 'landscape', palette: 'nope'}]), /palette/);
  const over = Array(8).fill({text: 'a '.repeat(35).trim(), scene: 'landscape', palette: 'sunrise'});
  assert.throws(() => shortPlan(over), /60/);
});

test('shortSrt formats timestamps and numbering', () => {
  const srt = shortSrt([
    {text: 'Hi.', start: 0, end: 3.5},
    {text: 'Bye.', start: 3.5, end: 61.25},
  ]);
  assert.match(srt, /^1\n00:00:00,000 --> 00:00:03,500\nHi\.\n/m);
  assert.match(srt, /^2\n00:00:03,500 --> 00:01:01,250\nBye\.\n/m);
});

test('wrapCaption wraps to width and truncates with ellipsis', () => {
  const ctx = {measureText: s => ({width: s.length * 10})};
  assert.deepEqual(wrapCaption(ctx, 'aaa bbb ccc ddd', 35), ['aaa', 'bbb', 'ccc', 'ddd']);
  assert.deepEqual(wrapCaption(ctx, 'aaa bbb', 200), ['aaa bbb']);
  const long = wrapCaption(ctx, 'word '.repeat(30).trim(), 50, 2);
  assert.equal(long.length, 2);
  assert.ok(long[1].endsWith('…'));
  assert.deepEqual(wrapCaption(ctx, '', 100), []);
});
