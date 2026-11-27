// Preserve the historical Node command and resolve its owner in the selected installation.
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const suites = (process.env.UI_TEST_SUITE || '').split(path.delimiter).filter(Boolean);
const main = suites[0] || path.resolve(__dirname, '../../../ui-test');
const launcher = path.join(main, 'scripts/ui_test_suite.py');
const selected = JSON.parse(execFileSync(process.env.UI_TEST_PYTHON || 'python',
  [launcher, 'resolve', 'checkpoint-runtime'], { encoding: 'utf8' }));
require(path.join(selected.skill, 'scripts/checkpoint_runtime/playwright_runner.cjs'));
