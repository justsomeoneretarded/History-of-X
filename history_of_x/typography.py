"""Bundled OFL Space Grotesk typography for the new animated visual system."""
from functools import lru_cache
from PIL import ImageFont
from .core import ROOT
@lru_cache(maxsize=96)
def font(size,bold=False):
 return ImageFont.truetype(str(ROOT/'assets'/'fonts'/('SpaceGrotesk-Bold.ttf' if bold else 'SpaceGrotesk-Regular.ttf')),max(1,int(size)))
