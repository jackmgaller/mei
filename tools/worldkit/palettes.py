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
from kitcore.errors import pointer
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

    def add_asset(self, asset):
        for entry in asset.manifest.get('entries',[]):
            owners = [(asset.name,m) for m in entry['materials']]
            key = ((entry['class'],entry['color'],asset.name,tuple(entry['materials'])) if entry.get('separate')
                   else (entry['class'],entry['color']))
            if key not in self.by_key:
                self.by_key[key] = {'class':entry['class'],'color':entry['color'],'owners':[],
                                    'separate':bool(entry.get('separate'))}
            for owner in owners:
                if owner not in self.by_key[key]['owners']: self.by_key[key]['owners'].append(owner)

    def assign(self, first):
        """Gives the entries colours from 4-bit palette `first` (or the recipe's). Returns the
        palette after the region's last."""
        spec = self.spec.get('palettes',{})
        self.first = spec.get('first',first)
        keys = [k for kind in CLASSES for k in self.by_key if k[0] == kind]
        needed = max(1,(len(keys)+14)//15) if keys else 0
        self.count = spec.get('count',needed)
        if needed > self.count:
            raise WorldError(self.path+'/palettes/count',f'Region {self.name!r} needs {needed} 4-bit palettes for '
                             f'{len(keys)} entries; it declares {self.count}.')
        if self.count and self.first+self.count > 255:
            raise WorldError(self.path+'/palettes',f'Region {self.name!r}: palettes {self.first}-{self.first+self.count-1} '
                             'run into palette 255, which holds the fonts.')
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
            row = [0]*self.colours
            for e in self.entries: row[e['colour']-self.first_colour] = rgb15(colors[id(e)])
            out.append((vname,row))
            shown[vname] = {str(e['colour']):colors[id(e)] for e in self.entries}
        return out, shown

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
