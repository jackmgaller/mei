"""The CLI's published JSON Schema and its dependency-free validation subset.

Keep the recipe contract and validation together: unknown properties are errors,
so a misspelled modeling instruction never silently disappears from an asset.
"""
from kitcore.schema import (number, integer, array, obj, choice, ref, NAME, BOOL,  # noqa: F401
                            validator)
from .geometry import AssetError


NUM = number(-32767,32767)
POS = dict(number(0,32767), exclusiveMinimum=0)
VEC = array(NUM,3,3)
POINT = array(NUM,2,2)
TRANSFORM = obj({'translate':VEC,'rotate':VEC,'scale':VEC,'pivot':VEC})
MATERIAL = obj({'color':{'type':'string','pattern':r'^#[0-9a-fA-F]{6}$'},
                'smooth':BOOL,'double_sided':BOOL,
                'palette':dict(BOOL,description='Draw through a 4-bit palette entry (a textured swatch face tinted by the baked shade), so rewriting the palette recolours it. Default false; true for emissive.'),
                'class':dict(choice('surface','emissive'),description='emissive: own palette entries, never shaded, reported separately. Default surface.'),
                'tag':dict(NAME,description='Opaque surface tag carried to the material manifest; not interpreted by the kit.'),
                'share':dict(BOOL,description='Palette-backed materials only. Default true: share a palette entry with every material of the same class and colour. false: an entry of its own, so it can be recoloured separately.')}, ['color'])
PALETTE_LAYOUT = dict(obj({'slot':integer(0,14),'row':integer(0,255),'first':integer(0,254)}),
                      description='Where palette-backed materials live: swatch texels u 0-15 of row `row` in texture slot `slot` (default 14, 0); entries from 4-bit palette `first` (default 0).')
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
BOX_SIDES = ('top','bottom','left','right','back','front')
COMMON = {'id':NAME,'material':NAME,'transform':TRANSFORM,'modifiers':array(MODIFIERS,0,16)}
NODE = {'oneOf':[
    operation('box', {'size':array(POS,3,3),
                      'open':dict(array(choice(*BOX_SIDES),1,5),description='Faces to leave out: top (+Y), bottom (-Y), left (-X), right (+X), back (-Z), front (+Z). For a ground tile ["bottom"], for a building standing on the ground ["bottom"].')},
              ['size'], COMMON),
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
        'lighting':obj({'direction':VEC,'ambient':number(0,1),'bake':BOOL,
                        'mode':dict(choice('directional','vertical'),description='vertical: shade by the face normal\'s Y only (tops light, walls mid, undersides dark), unchanged by any yaw. Default directional.')}),
        'palette_layout':PALETTE_LAYOUT,
        'budget':obj({'vertices':integer(3,2048),'triangles':integer(1,4000)}),
        'verification':VERIFICATION,
    }, ['format','version','name','nodes']),
    '$defs':{'node':NODE},
}


# validate(value, schema=SCHEMA, path='', depth=0) raises AssetError at the first problem.
validate = validator(SCHEMA, AssetError)
