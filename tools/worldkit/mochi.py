"""Mochi: a small language for the World Kit's game schema (docs/WORLDKIT.md, "Built: the game
schema"). A thin front end: parse() turns Mochi text into exactly the dict the JSON form (format
mei-world-game) loads as, so the kit's own validation runs on it unchanged; format() turns such
a dict back into canonical Mochi. Types only: no expressions, includes or macros.

    game, at = parse(text)       # WorldError with .line and .column at the first syntax error
    locate(error, at)            # gives a later validation error (a JSON Pointer) its line
    text = format(game)
"""
import difflib
import json
import re

from kitcore.errors import pointer
from .schema import WorldError

KINDS = {'bool':'bool','u8':'u8','s16':'s16','s32':'s32','fixed':'fixed','vec3':'vec3','name':'name',
         'world':'world_ref','ref':'entity_ref'}
SPELLING = {v:k for k,v in KINDS.items()}
PROBE = ('radius','height','step','floor_max_degrees','ceiling_max_degrees','bridge')
STATEMENTS = ('type','saved','probe','worlds')
NAME = re.compile(r'[a-z][a-z0-9_]{0,47}')
NUMBER = re.compile(r'-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?')
TOKEN = re.compile(r'(?P<space>[ \t\r\n]+)|(?P<comment>//[^\n]*)|(?P<word>[A-Za-z_][A-Za-z0-9_]*)'
                   r'|(?P<number>-?[0-9.](?:[eE][+-]|[0-9A-Za-z_.])*)|(?P<punct>[{}:=|,\[\]?])|(?P<other>.)')
TYPE_LIST = 'bool, u8, s16, s32, fixed, vec3, name, world, ref, ref? or an enum (a | b)'
HINTS = {
    'entity_ref':'An entity reference is written ref (required) or ref? (may be none).',
    'world_ref':'A world reference is written world.',
    'enum':'Write an enum as its values: a | b | c (a one-value enum is | a).',
    'string':'Names are written name.', 'int':'Integers are u8, s16 or s32.', 'float':'Use fixed.',
}

GRAMMAR = [
    "file   := 'game' NAME stmt*                          game first; then any order, types in order",
    "stmt   := probe | worlds | type",
    "probe  := 'probe' '{' (PROBEKEY '=' NUMBER)* '}'      radius, floor_max_degrees required; height, step, ceiling_max_degrees, bridge optional",
    "worlds := 'worlds' NAME (',' NAME)*",
    "type   := ['saved'] 'type' NAME ['{' field* '}']",
    "field  := NAME ':' kind ['=' value]",
    "kind   := bool | u8 | s16 | s32 | fixed | vec3 | name | world | ref | ref? | enum",
    "enum   := ['|'] NAME ('|' NAME)*                     two or more values, or a leading | for one",
    "value  := true | false | NUMBER | NAME | '[' NUMBER ',' NUMBER ',' NUMBER ']'",
    "NAME   := [a-z][a-z0-9_]{0,47}    NUMBER := a JSON number (1, -2, 0.25, 1e-3)    // comment to end of line",
]
RULES = [
    'Line breaks and spaces are free; // starts a comment. There are no reserved words.',
    'A colon gives a field its type; = gives a value (a probe value or a field default).',
    'A field is required unless it has a default. ref is a required entity ID (JSON: entity_ref, required true); '
    'ref? may be none (entity_ref). A ref never has a default; ? is only for ref.',
    'world is a world of the worlds list (JSON: world_ref). An enum is its values separated by |; '
    'with one value it starts with |, so mode: | only.',
    'Defaults: true or false, a number, [x, y, z] for vec3, a bare name for name, world and enum values.',
    'saved type gives every entity of the type a saved bit. Types are numbered in the order written.',
    'game NAME stands for "format": "mei-world-game", "version": 1, "name": NAME. Files ending .mochi are Mochi; '
    'any other game schema is JSON, which is still accepted.',
]
EXAMPLE = '''\
// The game schema of a small city game.
game city

probe {
  radius            = 0.3
  height            = 1.6
  step              = 0.32
  floor_max_degrees = 40
}

worlds city, mall

saved type coin

saved type challenge_switch {
  course:      ref
  time_window: any | day | night = any
  reward:      u8 = 1
}

type camera_zone {
  size:     vec3 = [8, 4, 8]
  mode:     follow | fixed | rail
  priority: s16 = 0
}

type door {
  world:  world
  spawn:  name = entrance
  locked: bool = false
  key:    ref?
}
'''
CONTRACT = {'description':'Mochi: the game schema as a small typed language, translated into exactly this JSON. '
                          'Errors give file, line and column.',
            'grammar':GRAMMAR,'rules':RULES,'example':EXAMPLE}


class Token:
    def __init__(self, kind, text, line, column):
        self.kind, self.text, self.line, self.column = kind, text, line, column

    def describe(self):
        if self.text == '"': return '\'"\' (Mochi has no strings: write names bare)'
        if self.text == '#': return '\'#\' (comments start with //)'
        return 'the end of the file' if self.kind == 'eof' else repr(self.text)


def tokens(text):
    line, start = 1, 0
    for m in TOKEN.finditer(text):
        kind, value = m.lastgroup, m.group()
        if kind not in ('space','comment'): yield Token(kind,value,line,m.start()-start+1)
        if '\n' in value:
            line += value.count('\n')
            start = m.start()+value.rindex('\n')+1
    yield Token('eof','',line,len(text)-start+1)


def suggest(word, options):
    close = difflib.get_close_matches(word,options,1)
    return f' Did you mean {close[0]}?' if close else ''


class Parser:
    def __init__(self, text):
        self.toks, self.i, self.at = list(tokens(text)), 0, {}

    def peek(self, k=0): return self.toks[min(self.i+k,len(self.toks)-1)]

    def next(self):
        t = self.peek()
        self.i += 1
        return t

    def error(self, tok, message, path='/input'):
        error = WorldError(path,message)
        error.line, error.column = tok.line, tok.column
        return error

    def mark(self, path, tok): self.at.setdefault(path,(tok.line,tok.column))

    def expect(self, text, message, path):
        t = self.next()
        if t.text != text or t.kind != 'punct': raise self.error(t,f'{message}, found {t.describe()}.',path)
        return t

    def name(self, what, path):
        t = self.next()
        if t.kind != 'word': raise self.error(t,f'Expected {what}, found {t.describe()}.',path)
        if not NAME.fullmatch(t.text):
            fix = re.sub(r'[^a-z0-9_]','_',t.text.lower()).lstrip('_0123456789')[:48]
            raise self.error(t,f'{t.text!r} is not a valid name: names are a lowercase letter, then lowercase letters, '
                             f'digits or _, at most 48 characters' + (f'. Try {fix}.' if fix and fix != t.text else '.'),path)
        self.mark(path,t)
        return t.text

    def number(self, path):
        t = self.next()
        if t.kind != 'number': raise self.error(t,f'Expected a number, found {t.describe()}.',path)
        if not NUMBER.fullmatch(t.text):
            raise self.error(t,f'{t.text!r} is not a number. Write numbers as in JSON: 1, -2, 0.25, 1e-3.',path)
        self.mark(path,t)
        return json.loads(t.text)

    def parse(self):
        t = self.peek()
        if t.text != 'game':
            raise self.error(t,f'A Mochi file starts with game NAME (the game\'s name), found {t.describe()}.')
        self.mark('',self.next())
        game = {'format':'mei-world-game','version':1,'name':self.name('the game\'s name after game','/name')}
        probe = worlds = None
        types = {}
        while self.peek().kind != 'eof':
            t = self.peek()
            if t.text == 'probe' and t.kind == 'word':
                if probe is not None: raise self.error(t,f'The probe is already given at line {self.at["/probe"][0]}.','/probe')
                probe = self.probe()
            elif t.text == 'worlds' and t.kind == 'word':
                if worlds is not None: raise self.error(t,f'worlds is already given at line {self.at["/worlds"][0]}; list every world there.','/worlds')
                worlds = self.worlds()
            elif t.text in ('saved','type') and t.kind == 'word':
                self.type(types)
            elif t.text == 'game':
                raise self.error(t,'A file describes one game: game appears only once, first.')
            else:
                hint = suggest(t.text,STATEMENTS) if t.kind == 'word' else ''
                raise self.error(t,f'Expected type, saved type, probe or worlds, found {t.describe()}.{hint}')
        if probe is None:
            raise self.error(self.peek(),'The game has no probe. Add one: probe { radius = 0.3  floor_max_degrees = 40 }.','/probe')
        game['probe'] = probe
        game['types'] = types
        if worlds is not None: game['worlds'] = worlds
        return game

    def probe(self):
        kw = self.next()
        self.mark('/probe',kw)
        self.expect('{','Expected { after probe','/probe')
        probe = {}
        while self.peek().text != '}':
            t = self.peek()
            if t.kind == 'eof': raise self.error(t,f'Expected }} to close the probe opened at line {kw.line}.','/probe')
            key = self.name('a probe property or }','/probe')
            if key not in PROBE:
                raise self.error(t,f'Unknown probe property {key!r}. Probe properties: {", ".join(PROBE)}.'
                                 + suggest(key,PROBE),'/probe/'+key)
            if key in probe: raise self.error(t,f'probe {key} is already given at line {self.at["/probe/"+key][0]}.','/probe/'+key)
            self.expect('=',f'Expected = after {key} (write {key} = 0.3)','/probe/'+key)
            probe[key] = self.number('/probe/'+key)
        self.next()
        return probe

    def worlds(self):
        self.mark('/worlds',self.next())
        worlds = []
        while True:
            t = self.peek()
            world = self.name('a world name','/worlds/%d' % len(worlds))
            if world in worlds: raise self.error(t,f'World {world!r} is listed twice.','/worlds/%d' % len(worlds))
            worlds.append(world)
            after = self.peek()
            if after.text != ',':
                if after.kind == 'word' and after.text not in STATEMENTS:
                    raise self.error(after,f'Separate worlds with commas: worlds {", ".join(worlds+[after.text])}.','/worlds')
                return worlds
            self.next()

    def type(self, types):
        saved = self.peek() if self.peek().text == 'saved' else None
        if saved:
            self.next()
            if self.peek().text != 'type': raise self.error(self.peek(),f'Expected type after saved, found {self.peek().describe()}.')
        self.next()
        t = self.peek()
        tname = self.name('a type name','/types')
        path = pointer('/types',tname)
        if tname in types: raise self.error(t,f'Type {tname!r} is already declared at line {self.at[path][0]}.',path)
        self.mark(path,t)
        spec = types[tname] = {}
        if saved:
            spec['saved'] = True
            self.mark(path+'/saved',saved)
        if self.peek().text != '{': return
        opened = self.next()
        params = {}
        while self.peek().text != '}':
            f = self.peek()
            if f.kind == 'eof': raise self.error(f,f'Expected }} to close type {tname!r} (opened at line {opened.line}).',path)
            if f.text == ',': raise self.error(f,'Fields need no separator: put each on its own line.',path)
            self.field(params,path+'/params')
        self.next()
        if params: spec['params'] = params

    def field(self, params, base):
        t = self.peek()
        fname = self.name('a field name or }',base)
        path = pointer(base,fname)
        if fname in params: raise self.error(t,f'Field {fname!r} is already declared at line {self.at[path][0]}.',path)
        self.mark(path,t)
        self.expect(':',f'Expected : after field {fname!r} (write {fname}: u8)',path)
        k = self.peek()
        if k.text == '|' or (k.kind == 'word' and self.peek(1).text == '|'):
            if k.text == '|': self.next()
            self.mark(path+'/type',k)
            values = []
            while True:
                v = self.peek()
                value = self.name('an enum value',f'{path}/values/{len(values)}')
                if value in values: raise self.error(v,f'Enum value {value!r} is listed twice.',f'{path}/values/{len(values)}')
                if not values: self.mark(path+'/values',v)
                values.append(value)
                if self.peek().text != '|': break
                self.next()
            spec = {'type':'enum','values':values}
        elif k.kind == 'word':
            self.next()
            if k.text not in KINDS:
                hint = HINTS.get(k.text) or (f'Field types: {TYPE_LIST}; a one-value enum is | {k.text}.'
                                             + suggest(k.text,list(KINDS)))
                raise self.error(k,f'Unknown field type {k.text!r}. {hint}',path+'/type')
            self.mark(path+'/type',k)
            spec = {'type':KINDS[k.text]}
            if self.peek().text == '?':
                q = self.next()
                if k.text != 'ref':
                    raise self.error(q,f'Only a ref can be optional (ref?). A {k.text} field is required unless it has a '
                                     f'default: {fname}: {k.text} = ...',path)
            elif k.text == 'ref':
                spec['required'] = True
                self.mark(path+'/required',k)
        else:
            raise self.error(k,f'Expected a field type after {fname}:, found {k.describe()}. Field types: {TYPE_LIST}.',path+'/type')
        if self.peek().text == '=':
            eq = self.next()
            if spec['type'] == 'entity_ref':
                raise self.error(eq,'A ref has no default. Write ref? for a reference that may be none.',path+'/default')
            spec['default'] = self.value(spec['type'],path+'/default')
        params[fname] = spec

    def value(self, kind, path):
        t = self.peek()
        if kind == 'bool':
            if t.text not in ('true','false'): raise self.error(t,f'A bool default is true or false, found {t.describe()}.',path)
            self.mark(path,self.next())
            return t.text == 'true'
        if kind == 'vec3':
            self.expect('[','Expected a vec3 default like [0, 1, 0]',path)
            self.mark(path,t)
            items = [self.number(path+'/0')]
            while self.peek().text == ',':
                self.next()
                items.append(self.number(f'{path}/{len(items)}'))
            self.expect(']','Expected , or ] in the vec3 default',path)
            if len(items) != 3: raise self.error(t,f'A vec3 default has three numbers, [x, y, z]; found {len(items)}.',path)
            return items
        if kind in ('enum','name','world_ref'): return self.name('a name',path)
        return self.number(path)


def parse(text):
    """The game schema dict of Mochi text, and a map from JSON Pointer to (line, column)."""
    p = Parser(text)
    return p.parse(), p.at


def locate(error, at):
    """Gives a validation error the line and column of the nearest construct its path names."""
    path = error.path
    while path and path not in at: path = path.rsplit('/',1)[0]
    error.line, error.column = at.get(path,(1,1))
    key = error.path.rsplit('/',1)[-1]
    message = {'Required property is missing.':f'The probe needs {key}: add {key} = ... to it.',
               'A world_ref needs the game schema\'s worlds list.':'A world field needs the game\'s worlds: add worlds NAME, ...'
               }.get(str(error))
    if message: error.args = (message,)
    return error


def literal(value):
    if isinstance(value,bool): return 'true' if value else 'false'
    if isinstance(value,list): return '['+', '.join(map(literal,value))+']'
    return value if isinstance(value,str) else json.dumps(value)


def kind(p):
    t = p['type']
    if t == 'enum': text = ('| ' if len(p['values']) == 1 else '')+' | '.join(p['values'])
    elif t == 'entity_ref': text = 'ref' if p.get('required') else 'ref?'
    else: text = SPELLING[t]
    return text+(' = '+literal(p['default']) if 'default' in p else '')


def format(game):
    """Canonical Mochi for a valid game schema dict. saved: false, empty params and required: false
    mean the same as leaving them out, and are left out."""
    probe = [k for k in PROBE if k in game['probe']]
    width = max(map(len,probe))
    out = [f'game {game["name"]}','','probe {']+[f'  {k.ljust(width)} = {literal(game["probe"][k])}' for k in probe]+['}','']
    if game.get('worlds'): out += ['worlds '+', '.join(game['worlds']),'']
    for tname,t in game['types'].items():
        head = ('saved ' if t.get('saved') else '')+'type '+tname
        params = t.get('params') or {}
        if not params:
            out += [head,'']
            continue
        width = max(len(k) for k in params)+1
        out += [head+' {']+[f'  {(k+":").ljust(width)} {kind(p)}' for k,p in params.items()]+['}','']
    return '\n'.join(out).rstrip('\n')+'\n'
