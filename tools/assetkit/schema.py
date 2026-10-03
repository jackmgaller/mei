"""The CLI's published JSON Schema and its dependency-free validation subset.

Keep the recipe contract and validation together: unknown properties are errors,
so a misspelled modeling instruction never silently disappears from an asset.
"""
import math
import re
from .geometry import AssetError


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


NUM = number(-32767,32767)
POS = dict(number(0,32767), exclusiveMinimum=0)
VEC = array(NUM,3,3)
POINT = array(NUM,2,2)
NAME = {'type':'string','pattern':r'^[a-z][a-z0-9_]{0,47}$'}
BOOL = {'type':'boolean'}
TRANSFORM = obj({'translate':VEC,'rotate':VEC,'scale':VEC,'pivot':VEC})
MATERIAL = obj({'color':{'type':'string','pattern':r'^#[0-9a-fA-F]{6}$'},
                'smooth':BOOL,'double_sided':BOOL}, ['color'])
VERIFICATION = obj({'required':BOOL,'yaw_steps':integer(4,120),
                    'pitches':array(number(-1.4,1.4),1,5),
                    'distances':array(number(.8,3),1,3),'far':number(1,1000),'geometry':choice('error','warn')})


def operation(name, props, required=(), common=None):
    return obj(dict(common or {}, op={'const':name}, **props), ['op', *required])


MODIFIERS = {'oneOf':[
    operation('mirror', {'axis':choice('x','y','z'),'offset':NUM,'keep_original':BOOL}, ['axis']),
    operation('array', {'count':integer(1,128),'step':VEC}, ['count','step']),
    operation('radial', {'count':integer(1,128),'axis':choice('x','y','z'),'degrees':NUM}, ['count']),
    operation('taper', {'top':POS,'bottom':POS}, ['top']),
    operation('twist', {'degrees':NUM}, ['degrees']),
    operation('subdivide', {'levels':integer(1,3)}, ['levels']),
]}
COMMON = {'id':NAME,'material':NAME,'transform':TRANSFORM,'modifiers':array(MODIFIERS,0,16)}
NODE = {'oneOf':[
    operation('box', {'size':array(POS,3,3)}, ['size'], COMMON),
    operation('sphere', {'radius':POS,'rings':integer(2,64),'segments':integer(3,128)}, ['radius'], COMMON),
    operation('cylinder', {'radius':POS,'height':POS,'segments':integer(3,128),'caps':BOOL}, ['radius','height'], COMMON),
    operation('cone', {'radius':POS,'height':POS,'segments':integer(3,128),'caps':BOOL}, ['radius','height'], COMMON),
    operation('lathe', {'profile':array(POINT,2,128),'segments':integer(3,128),'caps':BOOL}, ['profile'], COMMON),
    operation('extrude', {'points':array(POINT,3,256),'depth':POS}, ['points','depth'], COMMON),
    operation('loft', {'sections':array(obj({'y':NUM,'points':array(POINT,3,256)}, ['y','points']),2,128),'caps':BOOL}, ['sections'], COMMON),
    operation('mesh', {'vertices':array(VEC,3,8192),'faces':array(array(integer(0,8191),3,256),1,8192),
                       'face_materials':array(NAME,1,8192)}, ['vertices','faces'], COMMON),
    operation('group', {'children':array(ref('node'),1,128)}, ['children'], COMMON),
    operation('instance', {'ref':NAME}, ['ref'], COMMON),
]}
SCHEMA = {
    '$schema':'https://json-schema.org/draft/2020-12/schema',
    'title':'Mei agent asset recipe v1',
    'description':'Y-up, units in Mei world units. Degrees. Transforms: scale about pivot, rotate X/Y/Z, translate. Geometry uses outward right-handed normals; exporter converts to Mei winding.',
    **obj({
        'format':{'const':'mei-asset'},'version':{'const':1},'name':NAME,
        'materials':{'type':'object','propertyNames':NAME,'additionalProperties':MATERIAL,'maxProperties':128},
        'prototypes':{'type':'object','propertyNames':NAME,'additionalProperties':ref('node'),'maxProperties':128},
        'nodes':array(ref('node'),1,128),
        'lighting':obj({'direction':VEC,'ambient':number(0,1),'bake':BOOL}),
        'budget':obj({'vertices':integer(3,2048),'triangles':integer(1,4000)}),
        'verification':VERIFICATION,
    }, ['format','version','name','nodes']),
    '$defs':{'node':NODE},
}


def pointer(path, key):
    return path+'/'+str(key).replace('~','~0').replace('/','~1')


def validate(value, schema=SCHEMA, path='', depth=0):
    if depth > 64:
        raise AssetError(path, 'Recipe nesting exceeds 64 levels.')
    if '$ref' in schema:
        return validate(value, SCHEMA['$defs'][schema['$ref'].split('/')[-1]], path, depth+1)
    if 'oneOf' in schema:
        # Every union in this schema is discriminated by its op field.
        ops = {s['properties']['op']['const']:s for s in schema['oneOf']}
        if not isinstance(value,dict) or not isinstance(value.get('op'),str) or value['op'] not in ops:
            raise AssetError(path+'/op', 'Expected an operation: '+', '.join(ops))
        return validate(value, ops[value['op']], path, depth+1)
    if 'const' in schema and (type(value) is not type(schema['const']) or value != schema['const']):
        raise AssetError(path, f"Expected {schema['const']!r}.")
    if 'enum' in schema and value not in schema['enum']:
        raise AssetError(path, f"Expected one of {schema['enum']}.")
    kind = schema.get('type')
    valid = {'object':isinstance(value,dict),'array':isinstance(value,list),'string':isinstance(value,str),
             'number':type(value) in (int,float),'integer':type(value) is int,'boolean':type(value) is bool}
    if kind and not valid[kind]:
        raise AssetError(path, f'Expected {kind}.')
    if kind in ('number','integer'):
        if type(value) is float and not math.isfinite(value): raise AssetError(path, 'Number must be finite.')
        if 'minimum' in schema and value < schema['minimum']: raise AssetError(path, f"Minimum is {schema['minimum']}.")
        if 'maximum' in schema and value > schema['maximum']: raise AssetError(path, f"Maximum is {schema['maximum']}.")
        if 'exclusiveMinimum' in schema and value <= schema['exclusiveMinimum']: raise AssetError(path, 'Must be positive.')
    if kind == 'string' and 'pattern' in schema and not re.fullmatch(schema['pattern'],value):
        raise AssetError(path, f"Must match {schema['pattern']}.")
    if kind == 'array':
        if not schema['minItems'] <= len(value) <= schema['maxItems']:
            raise AssetError(path, f"Expected {schema['minItems']}–{schema['maxItems']} items.")
        for i,item in enumerate(value): validate(item,schema['items'],pointer(path,i),depth+1)
    if kind == 'object':
        if len(value) > schema.get('maxProperties',1024): raise AssetError(path,'Too many properties.')
        for key in schema.get('required',[]):
            if key not in value: raise AssetError(pointer(path,key),'Required property is missing.')
        for key,item in value.items():
            if 'propertyNames' in schema: validate(key,schema['propertyNames'],pointer(path,key),depth+1)
            child = schema.get('properties',{}).get(key,schema.get('additionalProperties',False))
            if child is False: raise AssetError(pointer(path,key),'Unknown property; check spelling or run the schema command.')
            validate(item,child,pointer(path,key),depth+1)
