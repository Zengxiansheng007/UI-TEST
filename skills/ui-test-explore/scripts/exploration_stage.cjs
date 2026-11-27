/** Existing fixtures resolve the explorer inside the selected installation. */
const path = require('node:path');
const {execFileSync} = require('node:child_process');

function runExplorationStage(options) {
  const root = process.env.UI_TEST_SUITE?.split(path.delimiter)[0] || path.resolve(__dirname, '../../ui-test');
  const result = execFileSync(options.python || 'python',
    [path.join(root,'scripts/ui_test_suite.py'),'resolve','explore'],{encoding:'utf8',windowsHide:true});
  return require(path.join(JSON.parse(result).skill,'scripts/exploration_stage.cjs')).runExplorationStage(options);
}

module.exports = {runExplorationStage};
