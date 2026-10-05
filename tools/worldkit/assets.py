"""Builds the Asset Kit recipes a world references, through the Asset Kit's public entry points.

The dependency is one way: the Asset Kit never learns that worlds exist. Every build compiles
each referenced recipe from source and records its hash, so a world build never trusts a stale
mesh; `build` also runs each asset's own verification policy (the Asset Checker) and requires
it to pass.
"""
from dataclasses import dataclass, field
import hashlib
import os
from pathlib import Path

from assetkit.compiler import compile_recipe, native_bytes, material_manifest
from assetkit.geometry import AssetError
from kitcore import jsonio
from .pack import mesh_triangles
from .schema import WorldError


@dataclass
class Asset:
    name: str
    file: str
    recipe: dict
    binary: bytes
    manifest: dict
    report: dict
    face_tags: list                      # the material tag (or None) of each exported face
    shown: str = ''                      # the recipe path as reports show it (relative to the world)
    verification: dict = None            # the Asset Checker's result, when it ran
    uses: list = field(default_factory=list)
    levels: list = field(default_factory=list)   # native meshes of levels of detail 1.. (recipe lod)
    mesh: object = None                  # textured assets: the compiled mesh, placed per region
    materials: dict = None

    @property
    def textured(self): return self.mesh is not None

    @property
    def triangles(self): return self.report['triangles']

    @property
    def vertical(self):
        light = self.recipe.get('lighting',{})
        return light.get('mode','directional') == 'vertical' or light.get('bake',True) is False

    @property
    def policy_required(self):
        policy = self.recipe.get('verification')
        return policy is not None and policy.get('required',True)

    def summary(self):
        out = {'recipe':self.shown or self.file,'recipe_sha256':self.report['recipe_sha256'],
               'mesh_sha256':hashlib.sha256(self.binary).hexdigest(),
               'vertices':self.report['vertices'],'triangles':self.report['triangles'],
               'mesh_bytes':self.report['mesh_bytes'],
               'palette_entries':len(self.manifest.get('entries',[])),
               'verification':('passed' if self.verification and self.verification['ok'] else
                               'required' if self.policy_required else 'none'),
               **({'verified_with':self.verification['drawn_with']}
                  if self.verification and 'drawn_with' in self.verification else {}),
               'used_as':sorted(set(self.uses))}
        if 'lod' in self.report: out['lod'] = self.report['lod']
        return out


def relative(path, base):
    try: return os.path.relpath(path,base)
    except ValueError: return str(path)


class Library:
    """The world's assets by name, compiled on first use."""

    def __init__(self, directory, base_path, more=()):
        self.directory = Path(directory)
        self.directories = [self.directory]+[Path(d) for d in more]
        self.base_path = base_path
        self.assets = {}

    def source_of(self, name, path, file=None):
        """NAME.asset.json in the asset directories (the world's assets, then asset_dirs); a
        name in two of them is an error."""
        found = [d/f'{name}.asset.json' for d in self.directories if (d/f'{name}.asset.json').is_file()]
        if len(found) > 1:
            raise WorldError(path,f'Asset {name!r} is in more than one asset directory: '
                                  +', '.join(relative(f,self.base_path) for f in found)+'.',file)
        return found[0] if found else self.directory/f'{name}.asset.json'

    @staticmethod
    def policy_recipe(asset, runtime):
        """The recipe the Asset Checker runs: the asset's own, its policy given the world's
        depth and perspective where it does not set them itself."""
        extra = {k:True for k in ('depth','perspective') if (runtime or {}).get(k)
                 and k not in asset.recipe['verification']}
        return {**asset.recipe,'verification':{**asset.recipe['verification'],**extra}} if extra else asset.recipe

    def get(self, name, path, file=None, use='placement'):
        if name in ('self','none'):
            raise WorldError(path,f'{name!r} is not an asset name here.',file)
        if name not in self.assets:
            source = self.source_of(name,path,file)
            if not source.is_file():
                raise WorldError(path,f'No asset recipe {source}. Create it with tools/mei_assets.py init, or fix the name.',file)
            try:
                recipe = jsonio.load(str(source),AssetError)
                mesh,materials,report = compile_recipe(recipe,source.parent)
            except (AssetError,OSError,ValueError,RecursionError) as error:
                where = getattr(error,'path','/input')
                raise WorldError(path,f'Asset {name!r} does not build: {where}: {error}',file) from error
            if recipe['name'] != name:
                raise WorldError(path,f'{source} is named {recipe["name"]!r}; an asset file must be named after its recipe.',file)
            binary = native_bytes(mesh,materials,recipe.get('lighting',{}))
            manifest = material_manifest(mesh,materials,recipe)
            tags = [materials[f.material].get('tag') for f in mesh.faces]
            self.assets[name] = Asset(name,str(source),recipe,binary,manifest,report,tags,relative(source,self.base_path))
            self.assets[name].levels = [native_bytes(m,materials,recipe.get('lighting',{})) for m,_ in mesh.levels or []]
            if mesh.textures:
                # Placed per region later (worldkit/textures.py); binary is the asset's own
                # placement, whose geometry, collision and bounds are the same.
                self.assets[name].mesh,self.assets[name].materials = mesh,materials
        asset = self.assets[name]
        asset.uses.append(use)
        return asset

    def verify(self, compiler, probe, cache=None, runtime=None):
        """Runs the Asset Checker for every asset whose recipe requires it; any failure fails.
        The checks run in parallel, and with a cache directory unchanged assets are not checked
        again (worldkit/cache.py); the verdicts are the ones a serial run gives. runtime: the
        world's runtime.depth and runtime.perspective, which become each policy's depth and
        perspective where the recipe does not set them (the world draws its assets so)."""
        from .cache import AssetVerdicts
        required = {name:self.policy_recipe(asset,runtime) for name,asset in self.assets.items() if asset.policy_required}
        folders = {name:Path(self.assets[name].file).parent for name in required}
        outcomes = AssetVerdicts(cache,compiler,probe).run(required,folders)
        for name,asset in sorted(self.assets.items()):
            if not asset.policy_required: continue
            result,error = outcomes[name]
            if error:
                raise WorldError('/assets',f'Asset {name!r}: the Asset Checker could not run: {error} '
                                 '(it needs NumPy and build/mei-asset-probe; pass --compiler/--probe).') from error
            asset.verification = {'ok':result['ok'],'views':result['views']}
            drawn = {k:v for k,v in required[name]['verification'].items() if k in ('depth','perspective') and v}
            if drawn: asset.verification['drawn_with'] = drawn
            if not result['ok']:
                raise WorldError('/assets',f'Asset {name!r} fails its own verification policy. Run '
                                 f'tools/mei_assets.py verify {asset.file} and repair it.')


def collision_triangles(asset, surface_of):
    """The asset's faces as collision triangles in its own frame: [(a, b, c, surface byte)] with
    exact Fraction corners. Asset Kit meshes are triangles, so face k is triangle k."""
    tris = mesh_triangles(asset.binary)
    if len(tris) != len(asset.face_tags):
        raise WorldError('/assets',f'Asset {asset.name!r}: unexpected quad faces.')
    return [(a,b,c,surface_of(tag)) for (a,b,c),tag in zip(tris,asset.face_tags)]
