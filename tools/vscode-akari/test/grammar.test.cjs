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
  const grammarPath = path.join(__dirname, '../syntaxes/akari.tmLanguage.json');
  const registry = new Registry({
    onigLib: Promise.resolve({
      createOnigScanner: patterns => new onig.OnigScanner(patterns),
      createOnigString: text => new onig.OnigString(text),
    }),
    loadGrammar: async () => parseRawGrammar(fs.readFileSync(grammarPath, 'utf8'), grammarPath),
  });
  grammar = await registry.loadGrammar('source.akari');
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

test('declarations, contextual keywords, types and builtins', () => {
  const lines = tokenize(`private struct Packet { flags: bits { enabled }, data: []const u8 }
weak fn screen.draw(v: vec3) -> fixed16 { return from_bits16(42) }
let f = fn(x: s32) => match x { 0 => true, else => false }
const limit = 10
let raw = bits(1.5)
private()`);
  has(lines[0], 'private', 'storage.modifier.akari');
  has(lines[0], 'Packet', 'entity.name.type.akari');
  has(lines[0], 'bits', 'storage.type.akari');
  has(lines[0], 'u8', 'support.type.akari');
  has(lines[1], 'weak', 'storage.modifier.akari');
  has(lines[1], 'draw', 'entity.name.function.akari');
  has(lines[1], 'fixed16', 'support.type.akari');
  has(lines[1], 'from_bits16', 'support.function.builtin.akari');
  has(lines[2], 'match', 'keyword.control.akari');
  has(lines[2], '=>', 'keyword.operator.akari');
  has(lines[2], 'false', 'constant.language.akari');
  has(lines[3], 'limit', 'variable.other.constant.akari');
  has(lines[4], 'bits', 'support.function.builtin.akari');
  has(lines[5], 'private', 'entity.name.function.akari');
});

test('numbers keep ranges distinct from fixed point literals', () => {
  const [tokens] = tokenize('0..10 0..=10 1_000 0xF_F 0B10_01 -0.25');
  for (const [text, suffix] of [['..', null], ['..=', null], ['1_000', 'integer'],
    ['0xF_F', 'hex'], ['0B10_01', 'binary'], ['0.25', 'fixed']]) {
    has(tokens, text, suffix ? `constant.numeric.${suffix}.akari` : 'keyword.operator.akari');
  }
});

test('strings, escapes, comments and recovery on the following line', () => {
  const lines = tokenize(String.raw`let s = "// asm { \n\x41\q"
let ch = '\''
/* fn hidden() {
still a comment */ fn visible() {}
let bad = "unterminated
fn recovered() {}`);
  has(lines[0], '\\n', 'constant.character.escape.akari');
  has(lines[0], '\\x41', 'constant.character.escape.akari');
  has(lines[0], '\\q', 'invalid.illegal.escape.akari');
  assert.ok(lines[0].every(t => !t.scopes.includes('meta.asm.akari')));
  has(lines[1], "\\'", 'constant.character.escape.akari');
  assert.ok(lines[2].every(t => t.scopes.includes('comment.block.akari')));
  has(lines[3], 'visible', 'entity.name.function.akari');
  has(lines[5], 'recovered', 'entity.name.function.akari');
});

test('assembly signatures, references and comments do not leak into Akari', () => {
  const lines = tokenize(`asm fn copy(
  dst: *u8, src: *u8
) {
.loop: LW R1, [{src}] ; } ignored
  sw r1, [{dst}] // } ignored
  addi {dst}, {dst}, 4
}
fn next() { let value = 1; return }
asm // comment before the body
{
  li r1, {value}
}
let after = true`);
  has(lines[0], 'copy', 'entity.name.function.akari');
  has(lines[1], 'u8', 'support.type.akari');
  has(lines[3], '.loop', 'entity.name.label.mei-asm');
  has(lines[3], 'LW', 'keyword.control.instruction.mei-asm');
  has(lines[3], 'R1', 'variable.language.register.mei-asm');
  has(lines[3], 'src', 'variable.other.akari');
  has(lines[4], 'sw', 'keyword.control.instruction.mei-asm');
  has(lines[5], 'addi', 'keyword.control.instruction.mei-asm');
  has(lines[10], 'li', 'keyword.control.instruction.mei-asm');
  for (const i of [7, 12]) {
    assert.ok(lines[i].every(t => !t.scopes.includes('meta.asm.akari')));
  }
  has(lines[7], 'return', 'keyword.control.akari');
  has(lines[12], 'true', 'constant.language.akari');
});

test('tokenizes the repository Akari corpus without timeouts', t => {
  const root = path.resolve(__dirname, '../../..');
  let files = 0;
  for (const directory of ['stdlib', 'system', 'carts', 'examples', 'tests/lang']) {
    for (const relative of fs.readdirSync(path.join(root, directory), { recursive: true })) {
      if (!relative.endsWith('.akr')) continue;
      tokenize(fs.readFileSync(path.join(root, directory, relative), 'utf8'));
      files++;
    }
  }
  assert.ok(files > 0);
  t.diagnostic(`Tokenized ${files} Akari source files`);
});
