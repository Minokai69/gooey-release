const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const policy = vm.createContext({});
vm.runInContext(fs.readFileSync(path.join(__dirname, '..', 'AnchorResolver.js'), 'utf8'), policy);

const buttons = [
  { token: 'left-on-B', output: 'DP-2', position: 12 },
  { token: 'right-on-A', output: 'DP-1', position: 900 },
  { token: 'left-on-A', output: 'DP-1', position: 12 },
];

assert.equal(policy.choose(buttons, 'left-on-B', 'DP-1').token, 'left-on-B', 'the clicked button wins over keyboard focus');
assert.equal(policy.choose(buttons, 'removed-button', 'DP-1'), null, 'a stale pointer identity must not target a different button');
assert.equal(policy.choose(buttons, '', 'DP-2').token, 'left-on-B', 'keyboard activation uses the focused output');
assert.equal(policy.choose(buttons, '', 'missing-output').token, 'left-on-A', 'fallback is output name then layout position');
assert.equal(policy.choose(buttons.slice().reverse(), '', 'missing-output').token, 'left-on-A', 'registration order does not affect fallback');
assert.equal(policy.choose([], '', 'DP-1'), null, 'there is no fabricated anchor when buttons are absent');
console.log('Gooey launcher anchor policy: 6 checks passed');
