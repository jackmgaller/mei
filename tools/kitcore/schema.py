"""Schema building blocks and a dependency-free validator for the JSON Schema subset the kits
publish.

The subset: type, const, enum, minimum, maximum, exclusiveMinimum, pattern, minItems/maxItems
(required on arrays), properties, required, additionalProperties (False or a schema),
propertyNames, maxProperties, $ref into the root's $defs, and oneOf discriminated by a property
that is a const in every branch (an Asset Kit node's `op`). Unknown properties are errors, so a
misspelled instruction never silently disappears.
"""
import math
import re

from .errors import KitError, pointer


def number(minimum=None, maximum=None):
    s = {'type':'number'}
    if minimum is not None: s['minimum'] = minimum
    if maximum is not None: s['maximum'] = maximum
    return s


def integer(lo, hi): return dict(number(lo, hi), type='integer')
def array(items, lo=1, hi=256): return {'type':'array','items':items,'minItems':lo,'maxItems':hi}
def obj(properties, required=()):
    return {'type':'object','properties':properties,'required':list(required),'additionalProperties':False}
def choice(*values): return {'enum':list(values)}
def ref(name): return {'$ref':'#/$defs/'+name}


NAME = {'type':'string','pattern':r'^[a-z][a-z0-9_]{0,47}$'}
BOOL = {'type':'boolean'}
COLOR = {'type':'string','pattern':r'^#[0-9a-fA-F]{6}$'}


def discriminator(branches):
    """The property every branch of a oneOf fixes with a const."""
    keys = None
    for s in branches:
        consts = {k for k,v in s.get('properties',{}).items() if 'const' in v}
        keys = consts if keys is None else keys & consts
    if not keys: raise ValueError('oneOf branches share no const property')
    return sorted(keys)[0]


def validator(root, error=KitError):
    """A validate(value, schema=root, path='', depth=0) function for one root schema, raising
    error(path, message) at the first problem."""
    defs = root.get('$defs',{})

    def validate(value, schema=root, path='', depth=0):
        if depth > 64:
            raise error(path, 'Recipe nesting exceeds 64 levels.')
        if '$ref' in schema:
            return validate(value, defs[schema['$ref'].split('/')[-1]], path, depth+1)
        if 'oneOf' in schema:
            key = discriminator(schema['oneOf'])
            ops = {s['properties'][key]['const']:s for s in schema['oneOf']}
            if not isinstance(value,dict) or not isinstance(value.get(key),str) or value[key] not in ops:
                what = 'an operation' if key == 'op' else f'{key!r} to be one of'
                raise error(path+'/'+key, f'Expected {what}: '+', '.join(ops))
            return validate(value, ops[value[key]], path, depth+1)
        if 'const' in schema and (type(value) is not type(schema['const']) or value != schema['const']):
            raise error(path, f"Expected {schema['const']!r}.")
        if 'enum' in schema and value not in schema['enum']:
            raise error(path, f"Expected one of {schema['enum']}.")
        kind = schema.get('type')
        valid = {'object':isinstance(value,dict),'array':isinstance(value,list),'string':isinstance(value,str),
                 'number':type(value) in (int,float),'integer':type(value) is int,'boolean':type(value) is bool}
        if kind and not valid[kind]:
            raise error(path, f'Expected {kind}.')
        if kind in ('number','integer'):
            if type(value) is float and not math.isfinite(value): raise error(path, 'Number must be finite.')
            if 'minimum' in schema and value < schema['minimum']: raise error(path, f"Minimum is {schema['minimum']}.")
            if 'maximum' in schema and value > schema['maximum']: raise error(path, f"Maximum is {schema['maximum']}.")
            if 'exclusiveMinimum' in schema and value <= schema['exclusiveMinimum']: raise error(path, 'Must be positive.')
        if kind == 'string' and 'pattern' in schema and not re.fullmatch(schema['pattern'],value):
            raise error(path, f"Must match {schema['pattern']}.")
        if kind == 'array':
            if not schema['minItems'] <= len(value) <= schema['maxItems']:
                raise error(path, f"Expected {schema['minItems']}–{schema['maxItems']} items.")
            for i,item in enumerate(value): validate(item,schema['items'],pointer(path,i),depth+1)
        if kind == 'object':
            if len(value) > schema.get('maxProperties',1024): raise error(path,'Too many properties.')
            for key in schema.get('required',[]):
                if key not in value: raise error(pointer(path,key),'Required property is missing.')
            for key,item in value.items():
                if 'propertyNames' in schema: validate(key,schema['propertyNames'],pointer(path,key),depth+1)
                child = schema.get('properties',{}).get(key,schema.get('additionalProperties',False))
                if child is False:
                    message = schema.get('x-unknown',{}).get(key,'Unknown property; check spelling or run the schema command.')
                    raise error(pointer(path,key),message)
                validate(item,child,pointer(path,key),depth+1)

    return validate
