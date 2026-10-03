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
               'used_as':sorted(set(self.uses))}
        return out


def relative(path, base):
    try: return os.path.relpath(path,base)
    except ValueError: return str(path)


class Library:
    """The world's assets by name, compiled on first use."""

    def __init__(self, directory, base_path):
        self.directory = Path(directory)
        self.base_path = base_path
        self.assets = {}

    def get(self, name, path, file=None, use='placement'):
        if name in ('self','none'):
            raise WorldError(path,f'{name!r} is not an asset name here.',file)
        if name not in self.assets:
            source = self.directory/f'{name}.asset.json'
            if not source.is_file():
                raise WorldError(path,f'No asset recipe {source}. Create it with tools/mei_assets.py init, or fix the name.',file)
            try:
                recipe = jsonio.load(str(source),AssetError)
                mesh,materials,report = compile_recipe(recipe)
            except (AssetError,OSError,ValueError,RecursionError) as error:
                where = getattr(error,'path','/input')
                raise WorldError(path,f'Asset {name!r} does not build: {where}: {error}',file) from error
            if recipe['name'] != name:
                raise WorldError(path,f'{source} is named {recipe["name"]!r}; an asset file must be named after its recipe.',file)
            binary = native_bytes(mesh,materials,recipe.get('lighting',{}))
            manifest = material_manifest(mesh,materials,recipe)
            tags = [materials[f.material].get('tag') for f in mesh.faces]
            self.assets[name] = Asset(name,str(source),recipe,binary,manifest,report,tags,relative(source,self.base_path))
        asset = self.assets[name]
        asset.uses.append(use)
        return asset

    def verify(self, compiler, probe):
        """Runs the Asset Checker for every asset whose recipe requires it; any failure fails."""
        from assetkit.visibility import verify
        for name,asset in sorted(self.assets.items()):
            if not asset.policy_required: continue
            try:
                result = verify(asset.recipe,compiler=compiler,probe=probe)
            except (AssetError,OSError,ValueError) as error:
                raise WorldError('/assets',f'Asset {name!r}: the Asset Checker could not run: {error} '
                                 '(it needs NumPy and build/mei-asset-probe; pass --compiler/--probe).') from error
            asset.verification = {'ok':result['ok'],'views':len(result.get('views',[]))}
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
