"""Packs the palette entries of the assets drawn in a region into that region's palettes.

Each asset's material manifest lists its palette entries (class, colour, materials, and
`separate` for an entry its recipe forced to stay apart). Within a region, entries of the same
class and colour from any asset share one region entry, as the Asset Kit shares them within one
asset; separate entries stay separate. Surface entries come first, then emissive ones, as indices
1-15 of consecutive 4-bit palettes (index 0 is never drawn). Regions get disjoint palettes, so
every region's colours can be loaded at once and a far cell's stand-in is coloured correctly
whichever region the player is in. Each asset's faces are then moved to the region's entries
with assetkit.compiler.relocate(), so a mesh drawn in two regions is stored twice.

Variants are named full sets of the region's colours: the defaults, tinted per class, then exact
colours per material. The kit treats variant names as opaque.
"""
from assetkit.compiler import relocate, rgb15
from assetkit.texout import rgb_hex
from kitcore.errors import pointer
from .haze import mix as haze_mix
from .schema import WorldError

CLASSES = ('surface','emissive')


def hex_rgb(color):
    return tuple(int(color[k:k+2],16) for k in (1,3,5))


def multiply(color, tint):
    if not tint: return color.lower()
    return '#'+''.join(f'{round(c*t/255):02x}' for c,t in zip(hex_rgb(color),hex_rgb(tint)))


class RegionPalette:
    """One region's entries: key -> {colour, class, color, owners [(asset, material)]}."""

    def __init__(self, name, spec, path):
        self.name, self.spec, self.path = name, spec, path
        self.entries = []
        self.by_key = {}
        self.first = None      # first 4-bit palette
        self.count = 0         # palettes
        # textures and the backdrop (worldkit/textures.py, backdrop.py), after the entries' palettes
        self.tex4 = {}         # 4-bit palette -> (class, [15-bit colours, index 1 first])
        self.tex8 = {}         # 8-bit palette -> (class, [15-bit colours, index 1 first])
        self.texels = {}       # (asset, material) -> (bits, palette, {15-bit colour: index})
        self.backdrop = None   # (4-bit palette, [15-bit colours])
        self.sky = None        # backdrop.Backdrop
        self.run_rows = []     # per 8-bit palette: [colours per variant] (variants())
        self.sky_rows = []     # per variant: [0xBBGGRR] per sky stop (variants())
        self.haze = None       # {'colours': {variant: hex}, 'amount', 'emissive'}: hazes the far colours (haze.py)
        self.haze_palettes = set()   # 4-bit texture palettes hazed the same way (the stand-ins' card copies)

    @property
    def extra(self):
        """Whether the region has textures or a backdrop (its colours are more than its entries)."""
        return bool(self.tex4 or self.tex8 or self.backdrop or self.sky)

    def add_asset(self, asset):
        for entry in asset.manifest.get('entries',[]):
            owners = [(asset.name,m) for m in entry['materials']]
            key = ((entry['class'],entry['color'],asset.name,tuple(entry['materials'])) if entry.get('separate')
                   else (entry['class'],entry['color']))
            if key not in self.by_key:
                self.by_key[key] = {'class':entry['class'],'color':entry['color'],'owners':[],
                                    'separate':bool(entry.get('separate'))}
                if entry.get('haze'): self.by_key[key]['haze'] = True
            for owner in owners:
                if owner not in self.by_key[key]['owners']: self.by_key[key]['owners'].append(owner)

    def entry_palettes(self):
        """4-bit palettes the entries need."""
        n = len(self.by_key)
        return max(1,(n+14)//15) if n else 0

    def assign(self, first, extra=0):
        """Gives the entries colours from 4-bit palette `first` (or the recipe's), leaving `extra`
        palettes after them (textures, the backdrop). Returns the palette after the region's last."""
        spec = self.spec.get('palettes',{})
        self.first = spec.get('first',first)
        keys = [k for kind in CLASSES for k in self.by_key if k[0] == kind]
        needed = (max(1,(len(keys)+14)//15) if keys else 0)+extra
        self.count = spec.get('count',needed)
        if needed > self.count:
            raise WorldError(self.path+'/palettes/count',f'Region {self.name!r} needs {needed} 4-bit palettes for '
                             f'{len(keys)} entries; it declares {self.count}.')
        if self.count and self.first <= 255 < self.first+self.count:
            raise WorldError(self.path+'/palettes',f'Region {self.name!r}: palettes {self.first}-{self.first+self.count-1} '
                             'run into palette 255, which holds the fonts.')
        if self.count and self.first+self.count > 512:
            raise WorldError(self.path+'/palettes',f'Region {self.name!r}: palettes {self.first}-{self.first+self.count-1} '
                             'run past palette 511, the last (VRAM at 2 MB: 4-bit palettes 0-511).')
        for i,key in enumerate(keys):
            e = self.by_key[key]
            e['colour'] = (self.first+i//15)*16+1+i%15
            self.entries.append(e)
        return self.first+self.count

    @property
    def first_colour(self): return self.first*16

    @property
    def colours(self): return self.count*16

    def mapping(self, asset):
        """Old colour index -> region colour index for one asset's palette entries."""
        out = {}
        for entry in asset.manifest.get('entries',[]):
            key = ((entry['class'],entry['color'],asset.name,tuple(entry['materials'])) if entry.get('separate')
                   else (entry['class'],entry['color']))
            out[entry['colour']] = self.by_key[key]['colour']
        return out

    def relocated(self, asset, slot, row):
        if not asset.manifest.get('entries'): return asset.binary
        return relocate(asset.binary,self.mapping(asset),slot,row)

    def relocated_levels(self, asset, slot, row):
        """The asset's levels of detail 1.., moved like level 0 (they share its palette entries)."""
        if not asset.manifest.get('entries'): return list(asset.levels)
        return [relocate(b,self.mapping(asset),slot,row) for b in asset.levels]

    def variants(self, warnings):
        """[(name, [15-bit colour] * colours)] for the pack, and their colours for the report."""
        specs = self.spec.get('variants') or {'default':{}}
        out, shown = [], {}
        for vname,v in specs.items():
            vpath = pointer(pointer(self.path,'variants'),vname)
            colors = {id(e):multiply(e['color'],v.get(e['class'],{}).get('multiply')) for e in self.entries}
            setters = {}
            for selector,color in v.get('colors',{}).items():
                asset,_,material = selector.rpartition('.')
                hits = [e for e in self.entries if any(m == material and (not asset or a == asset) for a,m in e['owners'])]
                if not hits:
                    raise WorldError(pointer(pointer(vpath,'colors'),selector),
                                     f'No palette-backed material {selector!r} is drawn in region {self.name!r}. '
                                     'Use MATERIAL or ASSET.MATERIAL of an asset placed in the region.')
                for e in hits:
                    if id(e) in setters and colors[id(e)] != color.lower():
                        raise WorldError(pointer(pointer(vpath,'colors'),selector),
                                         f'{selector!r} and {setters[id(e)]!r} give one shared palette entry two colours. '
                                         'Give them one colour, or set share: false on the material in its asset recipe.')
                    setters[id(e)] = selector
                    colors[id(e)] = color.lower()
                    others = [f'{a}.{m}' for a,m in e['owners'] if not (m == material and (not asset or a == asset))]
                    if others:
                        warnings.append({'code':'shared_entry_recoloured','region':self.name,'variant':vname,
                                         'message':f'{selector!r} shares its palette entry with {", ".join(others)}, which change colour too. '
                                                   'Set share: false on the material in its asset recipe to keep them apart.'})
            if self.haze:
                # far colours (stand-ins only): moved toward this variant's haze colour
                target, amount, emissive = self.haze['colours'][vname], self.haze['amount'], self.haze['emissive']
                for e in self.entries:
                    if e.get('haze'):
                        colors[id(e)] = haze_mix(colors[id(e)], target, amount*(emissive if e['class'] == 'emissive' else 1))
            row = [0]*self.colours
            for e in self.entries: row[e['colour']-self.first_colour] = rgb15(colors[id(e)])
            if self.extra: self.extra_colours(vname,v,vpath,row,warnings)
            out.append((vname,row))
            shown[vname] = {str(e['colour']):colors[id(e)] for e in self.entries}
        return out, shown

    def extra_colours(self, vname, v, vpath, row, warnings):
        """Textures, 8-bit runs and the backdrop in variant v: each colour times its class's
        multiply, then the exact colours of `texels` (per textured material) and `backdrop`."""
        tint = lambda cls: v.get(cls,{}).get('multiply')
        fixed = {}
        for selector,mapping in v.get('texels',{}).items():
            asset,_,material = selector.rpartition('.')
            hits = [(k,t) for k,t in self.texels.items() if k[1] == material and (not asset or k[0] == asset)]
            sp = pointer(pointer(vpath,'texels'),selector)
            if not hits:
                raise WorldError(sp,f'No textured material {selector!r} is drawn in region {self.name!r}. '
                                    'Use MATERIAL or ASSET.MATERIAL of a textured asset placed in the region.')
            for (a,m),(bits,pal,index) in hits:
                by_c = {c:i for c,i in index.items()}
                for src,dst in mapping.items():
                    if rgb15(src) not in by_c:
                        raise WorldError(pointer(sp,src),f'{a}.{m}\'s texture has no colour {src} (its colours: '
                                                         f'{", ".join(sorted(rgb_hex(c) for c in by_c))}; colours are compared at 15 bits).')
                    if bits == 8:
                        raise WorldError(pointer(sp,src),f'{a}.{m} is an 8-bit texture: a variant tints its whole palette '
                                                         'by its class\'s multiply; exact colours are for 4-bit textures.')
                    fixed[pal*16+by_c[rgb15(src)]] = (dst.lower(),f'{a}.{m}')
        for pal,(cls,cols) in self.tex4.items():
            for i,c in enumerate(cols,1):
                colour = pal*16+i
                hexc = fixed[colour][0] if colour in fixed else multiply(rgb_hex(c),tint(cls))
                if pal in self.haze_palettes:
                    hexc = haze_mix(hexc,self.haze['colours'][vname],
                                    self.haze['amount']*(self.haze['emissive'] if cls == 'emissive' else 1))
                row[colour-self.first_colour] = rgb15(hexc)
        shared = {}
        for (a,m),(bits,pal,index) in self.texels.items():
            for c,i in index.items():
                if bits == 4: shared.setdefault(pal*16+i,[]).append(f'{a}.{m}')
        for colour,(_,who) in fixed.items():
            others = [x for x in shared.get(colour,[]) if x != who]
            if others:
                warnings.append({'code':'shared_texel_recoloured','region':self.name,'variant':vname,
                                 'message':f'{who} shares texture palette entry {colour} with {", ".join(sorted(set(others)))}, '
                                           'which change colour too.'})
        if self.backdrop:
            pal,cols = self.backdrop
            exact = {rgb15(k):c.lower() for k,c in v.get('backdrop',{}).items()}
            known = set(cols)
            for k in exact:
                if k not in known:
                    raise WorldError(pointer(vpath,'backdrop'),f'The backdrop silhouette has no colour {rgb_hex(k)} '
                                     f'(its colours: {", ".join(sorted(rgb_hex(c) for c in known))}; compared at 15 bits).')
            for i,c in enumerate(cols,1):
                row[pal*16+i-self.first_colour] = rgb15(exact.get(c) or multiply(rgb_hex(c),tint('surface')))
        elif v.get('backdrop'):
            raise WorldError(pointer(vpath,'backdrop'),f'Region {self.name!r} has no backdrop silhouette to recolour.')
        for q,(pal,(cls,cols)) in enumerate(sorted(self.tex8.items())):
            if len(self.run_rows) <= q: self.run_rows.append([])
            self.run_rows[q].append([0]+[rgb15(multiply(rgb_hex(c),tint(cls))) for c in cols])
        if self.sky:
            given = self.sky.sky
            if vname in given:
                cols = given[vname]
            else:
                first = next(iter(given.values()))
                cols = [multiply(c,tint('surface')) for c in first]
            self.sky_rows.append([int(c[1:3],16) | int(c[3:5],16) << 8 | int(c[5:7],16) << 16 for c in cols])

    def describe(self):
        classes = {}
        for kind in CLASSES:
            cols = [e['colour'] for e in self.entries if e['class'] == kind]
            if cols: classes[kind] = {'first_colour':cols[0],'colours':cols[-1]-cols[0]+1,'entries':len(cols)}
        return {'palettes':list(range(self.first,self.first+self.count)),'first_colour':self.first_colour,
                'colours':self.colours,'entries':[{'colour':e['colour'],'class':e['class'],'color':e['color'],
                                                   'materials':[f'{a}.{m}' for a,m in e['owners']],
                                                   **({'separate':True} if e['separate'] else {})} for e in self.entries],
                'classes':classes}
