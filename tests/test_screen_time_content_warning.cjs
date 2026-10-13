const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert');

const source = fs.readFileSync(path.join(__dirname, '..', 'resources', 'screen_time', 'extension', 'content.js'), 'utf8');

async function run(sequence) {
  const texts = [];
  let reply = {};
  const element = tag => {
    const node = { tag, children: [], style: {}, isConnected: true, attachShadow: () => ({ append() {}, replaceChildren() {} }), append() {}, remove() {} };
    let text;
    Object.defineProperty(node, 'textContent', { get: () => text, set: value => { text = value; texts.push(String(value)); } });
    return node;
  };
  let interval;
  const timers = [];
  const context = {
    globalThis: null,
    crypto: { randomUUID: () => '00000000-0000-0000-0000-000000000000' },
    URLSearchParams,
    URL,
    JSON,
    Set,
    Math,
    console,
    setInterval: callback => { interval = callback; return 1; },
    clearInterval() {},
    setTimeout: callback => { timers.push(callback); return 1; },
    window: { addEventListener() {} },
    document: {
      hidden: false,
      documentElement: { append() {} },
      createElement: element,
      querySelectorAll: () => [],
      addEventListener() {},
    },
  };
  context.globalThis = context;
  context.chrome = { runtime: { id: 'test', getURL: value => value, sendMessage: async () => reply } };
  vm.createContext(context);
  vm.runInContext(source, context);
  await new Promise(resolve => setImmediate(resolve)); // let the load-time tick finish
  const warnings = [];
  for (const next of sequence) {
    reply = { group: 'g', enabled: true, mode: 'limit', blocked: false, paused: false, needs_intent: false, ...next };
    const before = texts.length;
    await interval();
    await new Promise(resolve => setImmediate(resolve));
    warnings.push(texts.slice(before).filter(text => /额度|禁用时段/.test(text)));
  }
  return warnings;
}

(async () => {
  let result = await run([{ remaining_seconds: 600 }, { remaining_seconds: 299 }, { remaining_seconds: 250 }, { remaining_seconds: 59 }, { remaining_seconds: 40 }]);
  assert.deepStrictEqual(result[0], [], 'no warning above five minutes');
  assert.ok(result[1][0] && result[1][0].includes('5 分钟'), 'warns once near five minutes: ' + result[1]);
  assert.deepStrictEqual(result[2], [], 'five-minute warning is not repeated');
  assert.ok(result[3][0] && result[3][0].includes('不足 1 分钟'), 'warns under one minute');
  assert.deepStrictEqual(result[4], [], 'one-minute warning is not repeated');

  result = await run([{ remaining_seconds: 40 }, { remaining_seconds: 40 }]);
  assert.strictEqual(result[0].length, 1, 'jumping straight under a minute warns once');
  assert.strictEqual(result[1].length, 0);

  result = await run([{ remaining_seconds: 1000, curfew_starts_in: 240 }, { remaining_seconds: 1000, curfew_starts_in: 230 }]);
  assert.ok(result[0][0] && result[0][0].includes('4 分钟后进入禁用时段'), 'curfew countdown: ' + result[0]);
  assert.strictEqual(result[1].length, 0, 'curfew warning is not repeated');

  result = await run([{ remaining_seconds: 100, blocked: true }, { remaining_seconds: 100, paused: true }, { remaining_seconds: 100, mode: 'block' }, { remaining_seconds: 100, enabled: false }]);
  assert.ok(result.every(list => !list.some(text => /还剩|不足|后进入/.test(text))), 'no warnings when blocked, paused, disabled or block-mode');

  console.log('content warning checks passed');
})().catch(error => { console.error(error); process.exit(1); });
