const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { before, test } = require('node:test');
const { Registry, parseRawGrammar, INITIAL } = require('vscode-textmate');
const onig = require('vscode-oniguruma');

let grammar;
before(async () => {
  const wasm = fs.readFileSync(require.resolve('vscode-oniguruma/release/onig.wasm'));
  await onig.loadWASM(wasm.buffer.slice(wasm.byteOffset, wasm.byteOffset + wasm.byteLength));
  const grammarPath = path.join(__dirname, '../syntaxes/mochi.tmLanguage.json');
  const registry = new Registry({
    onigLib: Promise.resolve({
      createOnigScanner: patterns => new onig.OnigScanner(patterns),
      createOnigString: text => new onig.OnigString(text),
    }),
    loadGrammar: async () => parseRawGrammar(fs.readFileSync(grammarPath, 'utf8'), grammarPath),
  });
  grammar = await registry.loadGrammar('source.mochi');
});

function tokenize(source) {
  let state = INITIAL;
  return source.split('\n').map(line => {
    const result = grammar.tokenizeLine(line, state);
    assert.equal(result.stoppedEarly, false);
    state = result.ruleStack;
    return result.tokens.map(token => ({
      text: line.slice(token.startIndex, token.endIndex), scopes: token.scopes,
    }));
  });
}

function has(tokens, text, scope) {
  assert.ok(tokens.some(t => t.text === text && t.scopes.includes(scope)),
    `${JSON.stringify(text)} should have ${scope}: ${JSON.stringify(tokens)}`);
}

test('statements, the probe and comments', () => {
  const lines = tokenize(`game garden // the test room
probe { radius = 0.3  floor_max_degrees = 40 }
worlds test_room, mall
saved type trigger {`);
  has(lines[0], 'game', 'keyword.other.mochi');
  has(lines[0], 'garden', 'entity.name.namespace.mochi');
  has(lines[0], '// the test room', 'comment.line.double-slash.mochi');
  has(lines[1], 'probe', 'keyword.other.mochi');
  has(lines[1], 'radius', 'variable.other.property.mochi');
  has(lines[1], '0.3', 'constant.numeric.mochi');
  has(lines[1], 'floor_max_degrees', 'variable.other.property.mochi');
  has(lines[2], 'worlds', 'keyword.other.mochi');
  has(lines[3], 'saved', 'storage.modifier.mochi');
  has(lines[3], 'type', 'storage.type.mochi');
  has(lines[3], 'trigger', 'entity.name.type.mochi');
});

test('fields: types, optional refs, enums and defaults', () => {
  const lines = tokenize(`  size:   vec3 = [0, -1.5, 2e-3]
  target: ref?
  window: any | day | night = any
  only:   | solo
  clash:  u8 | name = name
  on:     bool = true
  world:  world = city`);
  has(lines[0], 'size', 'variable.other.member.mochi');
  has(lines[0], 'vec3', 'support.type.mochi');
  has(lines[0], '-1.5', 'constant.numeric.mochi');
  has(lines[0], '2e-3', 'constant.numeric.mochi');
  has(lines[1], 'ref', 'support.type.mochi');
  has(lines[1], '?', 'keyword.operator.optional.mochi');
  has(lines[2], 'any', 'constant.other.enum.mochi');
  has(lines[2], 'night', 'constant.other.enum.mochi');
  has(lines[2], '|', 'keyword.operator.enum.mochi');
  has(lines[3], 'solo', 'constant.other.enum.mochi');
  // An enum value may be spelled like a type; the | decides.
  has(lines[4], 'u8', 'constant.other.enum.mochi');
  assert.ok(lines[4].every(t => !t.scopes.includes('support.type.mochi')));
  has(lines[5], 'true', 'constant.language.boolean.mochi');
  has(lines[6], 'world', 'variable.other.member.mochi');
  has(lines[6], 'world', 'support.type.mochi');
  has(lines[6], 'city', 'constant.other.value.mochi');
});

test('tokenizes the repository Mochi files', t => {
  const root = path.resolve(__dirname, '../../..');
  let files = 0;
  for (const relative of fs.readdirSync(path.join(root, 'examples'), { recursive: true })) {
    if (!relative.endsWith('.mochi')) continue;
    const lines = tokenize(fs.readFileSync(path.join(root, 'examples', relative), 'utf8'));
    assert.ok(lines.flat().some(token => token.scopes.includes('entity.name.type.mochi')));
    files++;
  }
  assert.ok(files > 0);
  t.diagnostic(`Tokenized ${files} Mochi files`);
});
