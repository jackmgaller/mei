"""The World Kit's published contracts: the world recipe, the cell file and the game schema, as
JSON Schema (the subset kitcore.schema validates), and their validators.

Unknown properties are errors, so a misspelled instruction never silently disappears. Properties
reserved for later work (terrain in a cell file, region audio) are errors that say so.
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

XZ = array(NUM,2,2)
AREA = dict(obj({
    'rect':dict(array(NUM,4,4),description='[x0, z0, x1, z1]: the rectangle between two corners.'),
    'circle':dict(array(NUM,3,3),description='[x, z, radius].'),
    'polygon':dict(array(XZ,3,256),description='[[x, z], ...]: a simple polygon (even-odd inside).'),
    'path':dict(NAME,description='A path of the world file: within width / 2 of its line, seen from above.'),
    'width':dict(POS,description='With path: the band\'s width (units).'),
}),description='Where an operation acts, seen from above (world x and z): exactly one of rect, circle, polygon or path. Omitted: the whole field.')
FALLOFF = dict(number(0,1024),description='Units outside the area over which the operation fades out (smoothstep). Default 0: a hard edge.')


def terrain_op(name, props, required=()):
    return obj(dict({'op':{'const':name},'area':AREA,'falloff':FALLOFF},**props),['op',*required])


TERRAIN_OP = {'oneOf':[
    terrain_op('set',{'height':dict(NUM,description='Flatten the area to this height.')},['height']),
    terrain_op('add',{'height':dict(NUM,description='Raise (or, negative, lower) the area by this much.')},['height']),
    terrain_op('carve',{'height':dict(NUM,description='Lower the area to at most this height (a pond, a cut); lower ground is left alone.')},['height']),
    terrain_op('fill',{'height':dict(NUM,description='Raise the area to at least this height; higher ground is left alone.')},['height']),
    terrain_op('ramp',{'from':dict(VEC,description='[x, y, z]: one end of the ramp\'s centre line and its height there.'),
                       'to':dict(VEC,description='[x, y, z]: the other end.'),
                       'width':dict(POS,description='Across the centre line (units).')},['from','to','width']),
    terrain_op('terrace',{'step':dict(POS,description='Height of each terrace (units).'),
                          'bank':dict(number(0.01,1),description='The fraction of each step\'s rise left as a slope between two flats. Default 0.25.'),
                          'base':dict(NUM,description='A height at which a flat begins. Default 0.')},['step']),
    terrain_op('smooth',{'passes':dict(integer(1,16),description='Passes of a 3 x 3 blur of the samples. Default 1.')}),
    terrain_op('bed',{'path':dict(NAME,description='A path of the world file.'),
                      'width':dict(POS,description='The bed\'s width across the path (units); the falloff blends beyond it.'),
                      'depth':dict(number(-64,64),description='How far below the path\'s line the bed lies. Default 0.')},['path','width']),
    terrain_op('paint',{'material':dict(NAME,description='A terrain material for the quads whose centres lie in the area.')},['material']),
    terrain_op('hole',{}),
]}
FIELD_LOD = obj({
    'distance':dict(POS,description='From this distance (units, viewer to a tile\'s centre) the coarse level is drawn.'),
    'tolerance':dict(POS,description='How far (units) the coarse level may stray from the samples. Default 0.25.'),
    'band':dict(number(0,1000),description='Hysteresis (units). Default 2.'),
}, ['distance'])
HEIGHTFIELD = obj({
    'spacing':dict(choice(0.5,1,2,4,8),description='Units between samples.'),
    'min':dict(XZ,description='[x, z]: the field\'s low corner, a multiple of spacing.'),
    'max':dict(XZ,description='[x, z]: the high corner, a multiple of spacing.'),
    'height':dict(NUM,description='The starting height of every sample. Default 0.'),
    'heights':dict(PATH,description='A text file of starting heights instead: one line per row of samples from z = min to max, each x = min to max, numbers separated by spaces; # starts a comment.'),
    'material':dict(NAME,description='The terrain material of every quad not painted.'),
    'steep':dict(obj({'degrees':number(1,89),'material':NAME},['degrees','material']),
                 description='Unpainted quads steeper than degrees take this material (a bank, a cliff).'),
    'operations':dict(array(TERRAIN_OP,0,1024),description='Applied in order to the samples (paint and hole to the quads).'),
    'tile':dict(choice(4,8,16,32,64,128),description='Units per side of a tile: one mesh and one placement. At most a cell and 32 quads. Default: a cell, or 16 quads if that is less.'),
    'tolerance':dict(number(0,1),description='How far (units) level 0 may stray from the samples where flat or evenly sloping quads are merged. Default 0.001.'),
    'shading':dict(choice('smooth','flat'),description='smooth (default): each sample shaded by the field\'s normal there, so shading runs on across seams; flat: each face by its own.'),
    'ground':dict(BOOL,description='Drawn in the ground pass (WORLDKIT.md, "Ground"). Default true.'),
    'collision':dict(BOOL,description='The field\'s faces are collision triangles. Default true.'),
    'lod':dict(FIELD_LOD,description='A coarser level of every tile, for distance.'),
}, ['spacing','min','max','material'])
TERRAIN_MATERIAL = obj({
    'color':COLOR,
    'class':dict(choice('surface','emissive'),description='As an Asset Kit material\'s. Default surface.'),
    'tag':dict(NAME,description='A surface tag, mapped to the collision surface byte by collision.surfaces.'),
    'share':dict(BOOL,description='As an Asset Kit material\'s: false gives the material a palette entry of its own. Default true.'),
}, ['color'])
SWEEP = obj({
    'profile':dict(array(array(NUM,2,2),2,64),description='[[x, y], ...]: the cross-section, x to the right of the path\'s direction, y up from its line. Each edge faces to its left (an edge drawn from left to right faces up).'),
    'material':dict(NAME,description='The terrain material of every edge of the profile.'),
    'materials':dict(array(NAME,1,63),description='One terrain material per edge of the profile, instead of material.'),
    'stairs':dict(obj({'rise':dict(POS,description='The highest a step may be (units).')},['rise']),
                  description='Steps instead of a slope: each segment of the path climbs in equal steps no higher than rise.'),
    'caps':dict(BOOL,description='Close the ends of an open path with the profile\'s outline, fanned from its first point. Default false.'),
    'ground':dict(BOOL,description='Drawn in the ground pass. Default: true unless the path is raised.'),
    'collision':dict(BOOL,description='The sweep\'s faces are collision triangles. Default true.'),
}, ['profile'])
TERRAIN = obj({
    'materials':{'type':'object','propertyNames':NAME,'additionalProperties':TERRAIN_MATERIAL,'maxProperties':128,
                 'description':'Terrain materials, drawn through palette entries of the cell\'s region as palette-backed asset materials are ("NAME" or "terrain.NAME" in a variant\'s colors).'},
    'lighting':dict(obj({'direction':VEC,'ambient':number(0,1),'mode':choice('directional','vertical')}),
                    description='The baked shading of fields and sweeps, as an Asset Kit recipe\'s lighting. Default vertical.'),
    'fields':{'type':'object','propertyNames':NAME,'additionalProperties':HEIGHTFIELD,'maxProperties':64,
              'description':'Ground heightfields in world coordinates, cut per cell by the kit. Fields may not overlap or touch.'},
}, ['materials'])

PATH_SPEC = obj({
    'points':dict(array(VEC,2,4095),description='World coordinates, in order; consecutive points differ. A closed path joins the last back to the first (do not repeat it).'),
    'raised':dict(BOOL,description='Raised: not lying on the ground (a rail, a wire, a jib). Carried to the pack for the game; a raised path\'s sweep is not ground. Default false.'),
    'closed':dict(BOOL,description='A loop: the last point joins the first. Default false.'),
    'tag':dict(NAME,description='A surface tag, mapped to the pack\'s surface byte by collision.surfaces as material tags are.'),
    'sweep':dict(SWEEP,description='A profile swept along the path: geometry and collision the kit makes and cuts per cell (WORLDKIT.md, "Terrain"), in the world\'s terrain materials.'),
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
CELL_TERRAIN = 'Terrain in a cell '+RESERVED+' Put terrain in the world file: it is cut per cell by the kit.'
CELL = dict(obj(CELL_PROPS,['id','at','region']),**{'x-unknown':{'terrain':CELL_TERRAIN}})
CELL_FILE = dict(obj({'format':{'const':'mei-world-cell'},'version':{'const':1},**CELL_PROPS},
                     ['format','version','id','at','region']),**{'x-unknown':{'terrain':CELL_TERRAIN}})

SLOTS = {'type':'string','pattern':r'^[0-9]{1,2}(-[0-9]{1,2})?(,[0-9]{1,2}(-[0-9]{1,2})?)*$',
         'description':'Texture slots in order of preference: a range "13-6" (in that order) or a list "14,12,10-11". '
                       'Slot 15 holds the fonts. Default "13-0".'}
TEXTURES = obj({
    'slots':SLOTS,
    'budget':dict(integer(0,15*32768),description='Bytes of texture VRAM the region may use (tiles on the 8-texel grid); '
                                                  'default: its slots (32,768 bytes a slot). Over it, the build fails naming the assets.'),
})
COLOR_MAP = {'type':'object','propertyNames':COLOR,'additionalProperties':COLOR,'maxProperties':255}
SILHOUETTE = obj({
    'image':dict(PATH,description='A PNG panorama 256, 512 or 1024 pixels wide and up to 128 tall; pixels with alpha below one half are sky. At most 15 colours (more are quantised).'),
    'pattern':dict(choice('skyline','mountains'),description='A generated silhouette: "skyline" (blocks in colors[0], lit windows in colors[1], nearer blocks in colors[2..]) or "mountains" (one range per colour, far to near).'),
    'width':dict(choice(256,512,1024),description='Patterns: pixels around the panorama.'),
    'height':dict(integer(1,128),description='Patterns: pixels tall.'),
    'colors':dict(array(COLOR,1,15),description='Patterns: the colours (see pattern).'),
    'seed':integer(0,65535),
    'horizon':dict(integer(0,127),description='Rows of the silhouette below the horizon (default 0: it stands on the horizon).'),
    'repeat':dict(integer(1,8),description='Times the panorama goes around the circle (default: the count that turns it closest to the camera\'s rate).'),
})
BACKDROP = obj({
    'elevations':dict(array(number(-89,89),1,64),description='Degrees above the horizon of the sky gradient\'s stops, increasing.'),
    'sky':{'type':'object','propertyNames':NAME,'additionalProperties':array(COLOR,1,64),'maxProperties':64,
           'description':'Per palette variant of the region: one colour per elevation. A variant not given takes the first one\'s colours times its surface multiply.'},
    'silhouette':dict(SILHOUETTE,description='A distant skyline or mountains on tile plane BG1, scrolled with the camera\'s yaw and pitch.'),
}, ['elevations','sky'])

TINT = obj({'multiply':dict(COLOR,description='Each colour channel is multiplied by this colour / 255.')})
VARIANT = obj({
    'surface':dict(TINT,description='Applied to every surface entry of the region.'),
    'emissive':dict(TINT,description='Applied to every emissive entry of the region.'),
    'colors':{'type':'object','propertyNames':{'type':'string','pattern':r'^[a-z][a-z0-9_]{0,47}(\.[a-z][a-z0-9_]{0,47})?$'},
              'additionalProperties':COLOR,'maxProperties':4080,
              'description':'Exact colours after the tints: "MATERIAL" (that material of every asset in the region) or "ASSET.MATERIAL".'},
    'texels':{'type':'object','propertyNames':{'type':'string','pattern':r'^[a-z][a-z0-9_]{0,47}(\.[a-z][a-z0-9_]{0,47})?$'},
              'additionalProperties':COLOR_MAP,'maxProperties':4096,
              'description':'Exact colours of 4-bit textures after the tints: "MATERIAL" or "ASSET.MATERIAL" -> {texture colour: colour in this variant}.'},
    'backdrop':dict(COLOR_MAP,description='Exact colours of the backdrop silhouette after the surface tint: {its colour: colour in this variant}.'),
})
REGION = dict(obj({
    'palettes':dict(obj({'first':integer(0,254),'count':integer(1,255)},['first']),
                    description='4-bit palettes the region\'s entries use: from first, count of them (default: as many as needed). Regions never overlap.'),
    'variants':{'type':'object','propertyNames':NAME,'additionalProperties':VARIANT,'maxProperties':64,
                'description':'Named palette variants, in order; the kit does not know what they mean. Default: one, "default".'},
    'textures':dict(TEXTURES,description='The region\'s texture set: its slots and VRAM budget (default: the world\'s textures).'),
    'backdrop':dict(BACKDROP,description='A sky gradient and a horizon silhouette drawn by the plane chip behind the world (WORLDKIT.md, "Backdrops").'),
}),**{'x-unknown':{'audio':'Region audio '+RESERVED}})

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
    'palette':obj({'swatch_slot':integer(0,14),'swatch_row':integer(0,255),'first':integer(0,254),
                   'first8':dict(integer(1,14),description='The first 8-bit palette 8-bit textures take (regions take them downward; default 14).')}),
    'textures':dict(TEXTURES,description='Every region\'s texture slots and VRAM budget, unless the region gives its own.'),
    'regions':{'type':'object','propertyNames':NAME,'additionalProperties':REGION,'maxProperties':255},
    'layers':{'type':'object','propertyNames':NAME,'additionalProperties':obj({'group':NAME,'on':BOOL}),'maxProperties':255},
    'cells':array(CELL,1,4096),
    'cell_dir':dict(PATH,description='Directory of cell files (*.cell.json), one per cell; instead of cells.'),
    'lod':dict(obj({
        'scale':dict(number(0.05,20),description='Multiplies every asset\'s switch and cull distances (not the band). Default 1.'),
        'assets':{'type':'object','propertyNames':NAME,'maxProperties':4096,
                  'additionalProperties':obj({'distances':dict(array(POS,1,7),description='One switch distance per level after level 0, as the asset\'s recipe has levels.'),
                                              'cull':dict({'anyOf':[POS,{'type':'null'}]},description='Not drawn from this distance on; null: never culled.'),
                                              'band':number(0,1000),
                                              'off':dict(BOOL,description='Draw level 0 always.')}),
                  'description':'Per asset, replaces its recipe\'s lod distances, cull or band (before scale).'},
     }),description='Levels of detail: the switch distances the pack stores for assets whose recipe has lod (WORLDKIT.md, "Levels of detail").'),
    'runtime':dict(obj({'near_far':dict(number(1,2048),description='The near pass\'s far depth (units) the pack asks the reader for; default 1.5 cells. The World Checker measures with it.'),
                        'depth':dict(BOOL,description='The game draws the world with the depth buffer (render_depth(true), docs/RENDERING.md). The World Checker and the Asset Checker judge it so. Not stored in the pack. Default false.'),
                        'perspective':dict(BOOL,description='The game draws it with perspective-correct texturing (render_perspective(true)). The checkers draw it so. Not stored in the pack. Default false.')}),
                   description='Runtime settings stored in the pack.'),
    'paths':{'type':'object','propertyNames':NAME,'additionalProperties':PATH_SPEC,'maxProperties':4096,
             'description':'Named polylines in world coordinates, in order (the pack\'s path numbers): rails, wires, routes. The kit attaches no meaning to them; entities refer to them by name.'},
    'verification':obj({'mode':choice('report','enforce'),
                        'thresholds':{'type':'object','propertyNames':NAME,'additionalProperties':{},
                                      'description':'Per-world World Checker settings (defaults from the kit).'}}),
    'terrain':dict(TERRAIN,description='Ground heightfields and their materials (WORLDKIT.md, "Terrain"); profiles swept along paths are in paths.'),
}, ['format','version','name','game','assets','grid','regions']))


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
