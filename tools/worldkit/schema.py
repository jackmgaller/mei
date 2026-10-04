"""The World Kit's published contracts: the world recipe, the cell file and the game schema, as
JSON Schema (the subset kitcore.schema validates), and their validators.

Unknown properties are errors, so a misspelled instruction never silently disappears. Properties
reserved for later work (terrain, region textures, audio and backdrops) are errors that say so.
"""
from kitcore.errors import KitError
from kitcore.schema import number, integer, array, obj, choice, NAME, BOOL, COLOR, validator


class WorldError(KitError):
    """A world error: a JSON Pointer path into `file` (the world recipe when None), and for a Mochi
    game schema the line and column."""
    def __init__(self, path, message, file=None):
        super().__init__(path, message)
        self.file = file
        self.line = self.column = None


NUM = number(-32767,32767)
VEC = array(NUM,3,3)
POS = dict(number(0,32767), exclusiveMinimum=0)
PATH = {'type':'string','minLength':1,'description':'A file path, relative to the world recipe.'}
ASSET = dict(NAME,description='An Asset Kit recipe: ASSETS/NAME.asset.json.')
YAW = dict(number(-360,360),description='Degrees about +Y, turning +Z toward +X as mesh_at() does.')
AKARI_KEYWORDS = {'fn','var','let','const','struct','enum','if','else','while','for','in','match','break',
                  'continue','return','import','asm','reg','embed','as','true','false','null','cart',
                  'assert','assert_eq','private','sizeof','len'}

PLACEMENT = obj({
    'id':dict(NAME,description='Stable within the cell; reports and witnesses name it.'),
    'asset':ASSET,
    'position':dict(VEC,description='World coordinates of the asset origin; must lie in the cell.'),
    'yaw':YAW,
    'layer':dict(NAME,description='A layer of the world: drawn (and collided with) only while it is on.'),
    'collision':{'type':'string','pattern':r'^[a-z][a-z0-9_]{0,47}$',
                 'description':'"self" (the asset\'s own mesh), "none", or a companion collision asset recipe.'},
    'merge':dict(BOOL,description='Merge this static prop with the cell\'s other merged props into one mesh per layer (trades ROM for the ~500-cycle cost per drawn placement). Default false.'),
    'ground':dict(BOOL,description='Ground: drawn before everything else near the camera, so nothing standing on it is drawn behind it. Only for surfaces nothing can be seen through or behind: open floors with nothing below them (WORLDKIT.md, "Ground"). Default false.'),
}, ['id','asset','position','collision'])

ENTITY = obj({
    'id':dict(NAME,description='Stable across the world; saved bits and entity_ref parameters follow it.'),
    'type':dict(NAME,description='A type of the game schema.'),
    'position':VEC,
    'yaw':YAW,
    'layer':NAME,
    'asset':dict(ASSET,description='A mesh the game may draw for it.'),
    'collision':dict(ASSET,description='A collision asset in the entity\'s own frame (a moving object).'),
    'params':{'type':'object','propertyNames':NAME,'additionalProperties':{},'maxProperties':64,
              'description':'Checked against the game schema\'s parameters for the type.'},
    'was':dict(NAME,description='The ID this entity had before a rename: it keeps that ID\'s saved bit.'),
}, ['id','type','position'])

PATH_SPEC = obj({
    'points':dict(array(VEC,2,4095),description='World coordinates, in order; consecutive points differ. A closed path joins the last back to the first (do not repeat it).'),
    'raised':dict(BOOL,description='Raised: not lying on the ground (a rail, a wire, a jib). Carried to the pack for the game and for swept geometry later. Default false.'),
    'closed':dict(BOOL,description='A loop: the last point joins the first. Default false.'),
    'tag':dict(NAME,description='A surface tag, mapped to the pack\'s surface byte by collision.surfaces as material tags are.'),
}, ['points'])

RESERVED = 'is reserved for a later version of the World Kit and not supported yet.'
CELL_PROPS = {
    'id':NAME,
    'at':dict(array(integer(-2048,2047),2,2),description='Grid coordinate (i, j): the cell covers x in [i S, (i+1) S) and z in [j S, (j+1) S).'),
    'region':NAME,
    'standin':dict(ASSET,description='A low-detail asset in cell-local coordinates (around the cell centre), drawn when the cell is far.'),
    'placements':array(PLACEMENT,0,4096),
    'entities':array(ENTITY,0,4096),
}
CELL = dict(obj(CELL_PROPS,['id','at','region']),**{'x-unknown':{'terrain':'Terrain '+RESERVED}})
CELL_FILE = dict(obj({'format':{'const':'mei-world-cell'},'version':{'const':1},**CELL_PROPS},
                     ['format','version','id','at','region']),**{'x-unknown':{'terrain':'Terrain '+RESERVED}})

TINT = obj({'multiply':dict(COLOR,description='Each colour channel is multiplied by this colour / 255.')})
VARIANT = obj({
    'surface':dict(TINT,description='Applied to every surface entry of the region.'),
    'emissive':dict(TINT,description='Applied to every emissive entry of the region.'),
    'colors':{'type':'object','propertyNames':{'type':'string','pattern':r'^[a-z][a-z0-9_]{0,47}(\.[a-z][a-z0-9_]{0,47})?$'},
              'additionalProperties':COLOR,'maxProperties':4080,
              'description':'Exact colours after the tints: "MATERIAL" (that material of every asset in the region) or "ASSET.MATERIAL".'},
})
REGION = dict(obj({
    'palettes':dict(obj({'first':integer(0,254),'count':integer(1,255)},['first']),
                    description='4-bit palettes the region\'s entries use: from first, count of them (default: as many as needed). Regions never overlap.'),
    'variants':{'type':'object','propertyNames':NAME,'additionalProperties':VARIANT,'maxProperties':64,
                'description':'Named palette variants, in order; the kit does not know what they mean. Default: one, "default".'},
}),**{'x-unknown':{k:f'Region {k} '+RESERVED for k in ('textures','audio','backdrop')}})

WORLD = dict(obj({
    'format':{'const':'mei-world'},'version':{'const':1},'name':NAME,
    'game':dict(PATH,description='The game schema: Mochi (a .mochi file; see $defs/game x-mochi) or JSON (format mei-world-game).'),
    'assets':dict(PATH,description='Directory of Asset Kit recipes.'),
    'grid':obj({'cell_size':dict(choice(16,32,64,128),description='Units; one unit is a metre by convention.')},['cell_size']),
    'overhang':dict(number(0,64),description='How far placements may reach past their cell (units, default 8, at most half a cell).'),
    'collision':obj({
        'pad':dict(number(0,64),description='How far walls are copied past a cell; at least the probe radius (default).'),
        'surfaces':obj({'default':integer(0,255),
                        'tags':{'type':'object','propertyNames':NAME,'additionalProperties':integer(0,255),'maxProperties':256}}),
    }),
    'palette':obj({'swatch_slot':integer(0,14),'swatch_row':integer(0,255),'first':integer(0,254)}),
    'regions':{'type':'object','propertyNames':NAME,'additionalProperties':REGION,'maxProperties':255},
    'layers':{'type':'object','propertyNames':NAME,'additionalProperties':obj({'group':NAME,'on':BOOL}),'maxProperties':255},
    'cells':array(CELL,1,4096),
    'cell_dir':dict(PATH,description='Directory of cell files (*.cell.json), one per cell; instead of cells.'),
    'paths':{'type':'object','propertyNames':NAME,'additionalProperties':PATH_SPEC,'maxProperties':4096,
             'description':'Named polylines in world coordinates, in order (the pack\'s path numbers): rails, wires, routes. The kit attaches no meaning to them; entities refer to them by name.'},
    'verification':obj({'mode':choice('report','enforce'),
                        'thresholds':{'type':'object','propertyNames':NAME,'additionalProperties':{},
                                      'description':'Per-world World Checker settings (defaults from the kit).'}}),
}, ['format','version','name','game','assets','grid','regions']),**{'x-unknown':{'terrain':'Terrain '+RESERVED}})


def field(kind, default, **extra):
    props = {'type':{'const':kind},'default':default,**extra}
    return obj(props,['type'])


FIELD = {'oneOf':[
    field('bool',BOOL),
    field('u8',integer(0,255)),
    field('s16',integer(-32768,32767)),
    field('s32',integer(-2**31,2**31-1)),
    field('fixed',number(-32768,32767)),
    field('vec3',array(number(-32768,32767),3,3)),
    field('enum',NAME,values=array(NAME,1,255)),
    field('name',NAME),
    field('entity_ref',NAME,required=BOOL),
    field('world_ref',NAME),
]}
GAME = obj({
    'format':{'const':'mei-world-game'},'version':{'const':1},'name':NAME,
    'probe':obj({'radius':POS,'height':POS,'step':number(0,64),
                 'floor_max_degrees':number(1,89),'ceiling_max_degrees':number(1,89)},['radius','floor_max_degrees']),
    'types':{'type':'object','propertyNames':NAME,'maxProperties':1024,
             'additionalProperties':obj({'saved':BOOL,'params':{'type':'object','propertyNames':NAME,
                                                                'additionalProperties':FIELD,'maxProperties':64}})},
    'worlds':array(NAME,1,1024),
}, ['format','version','name','probe','types'])

SCHEMA = {
    '$schema':'https://json-schema.org/draft/2020-12/schema',
    'title':'Mei World Kit recipe v1',
    'description':'Y up, world units (a metre by convention), degrees. A world recipe places Asset Kit assets into a square grid of cells and attaches game data checked against the game schema. Cells are inline (cells) or one file each (cell_dir).',
    **WORLD,
    '$defs':{'cell_file':CELL_FILE,'game':GAME},
}

validate_world = validator(WORLD, WorldError)
validate_cell_file = validator(CELL_FILE, WorldError)
validate_game = validator(GAME, WorldError)


def param_schema(spec, worlds):
    """The JSON Schema of one game parameter's value."""
    kind = spec['type']
    return {'bool':BOOL,'u8':integer(0,255),'s16':integer(-32768,32767),'s32':integer(-2**31,2**31-1),
            'fixed':number(-32768,32767),'vec3':array(number(-32768,32767),3,3),
            'enum':choice(*spec.get('values',[])),'name':NAME,'entity_ref':NAME,
            'world_ref':choice(*worlds) if worlds else NAME}[kind]


def entity_schema(game):
    """ENTITY with the game's types folded in: one branch per type, its params checked."""
    branches = []
    for name,t in game['types'].items():
        params = t.get('params',{})
        required = [k for k,p in params.items() if 'default' not in p and p['type'] != 'entity_ref' or p.get('required')]
        props = dict(ENTITY['properties'],type={'const':name},
                     params=obj({k:param_schema(p,game.get('worlds',[])) for k,p in params.items()},required))
        branches.append(obj(props,['id','type','position']+(['params'] if required else [])))
    return {'oneOf':branches}


def published(game=None):
    """The schema the `schema` command prints, with Mochi described under $defs/game and a game's
    entity types folded in if given."""
    from .mochi import CONTRACT
    base = dict(SCHEMA,**{'$defs':dict(SCHEMA['$defs'],game=dict(GAME,**{'x-mochi':CONTRACT}))})
    if game is None: return base
    entity = entity_schema(game)
    def swap(cell):
        props = dict(cell['properties'],entities=array(entity,0,4096))
        return dict(cell,properties=props)
    world = dict(base,properties=dict(SCHEMA['properties'],cells=array(swap(CELL),1,4096)))
    world['$defs'] = dict(base['$defs'],cell_file=swap(CELL_FILE))
    return world
