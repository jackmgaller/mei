# Akari for Visual Studio Code

Syntax highlighting for the Mei fantasy console's `.akr` files. Includes Akari
keywords, types, declarations, builtins, numbers, strings, comments and inline Mei
assembly (`asm` blocks and `asm fn`, including `{name}` references). Standard
TextMate scopes pick up your editor theme's colors. Also provides comment
toggling, bracket matching, quote pairing and indentation.

It also highlights `.mochi` files, the World Kit's game schemas written in Mochi
(docs/WORLDKIT.md): statements, type and field names, field types, `ref?`, enum
values, defaults, numbers and comments.

This is a declarative extension with no runtime code or dependencies. It does not
provide completion, diagnostics or a language server.

## Install

From this directory, with Node.js 22 or newer:

```sh
npm ci
npm test
npm run package
```

In VS Code, run **Extensions: Install from VSIX...** from the Command Palette and
select `akari-language-0.1.0.vsix` in this directory. Alternatively:

```sh
code --install-extension akari-language-0.1.0.vsix
```

Open any `.akr` file; its language mode should be **Akari**. If you previously
associated `.akr` files with another language, remove that `files.associations`
setting or select Akari from the language mode menu. Reload the VS Code window
if an already open file does not update.

`mei-local` is a local package identity, not a registered Marketplace publisher.
Packaging does not publish anything. This repo does not specify a license, so
the package is marked `UNLICENSED` and packaging skips the missing-license check.

## Develop

Open this directory itself in VS Code and press **F5** to launch an Extension
Development Host with the Mei repo open. Use **Developer: Inspect Editor Tokens
and Scopes** to inspect highlighting in an `.akr` file.

The grammar follows `src/lang/lex.c`, `src/lang/parse.c`, `src/lang/check.c`, and
`src/core/isa.c` in the repository. Keep keywords, builtins and assembly mnemonics
in sync with those sources when the language changes. Capitalized type names and
uppercase constant references are lexical conventions, not symbol resolution.

`npm test` runs the actual TextMate/Oniguruma tokenizer, checks scope boundaries
and tricky literals/assembly, and smoke-tests the repo's Akari source files and
Mochi game schemas. The Mochi grammar follows `tools/worldkit/mochi.py`.
Development dependencies and tests are excluded from the VSIX.

References: [VS Code syntax highlighting guide](https://code.visualstudio.com/api/language-extensions/syntax-highlight-guide)
and [extension packaging guide](https://code.visualstudio.com/api/working-with-extensions/publishing-extension).
