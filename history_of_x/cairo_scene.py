"""Subpixel affine compositing through Cairo/pixman on the Actions CPU.

The same raster artwork and world matrices drive both backends. Source surfaces
are decoded once; Cairo resamples and composites them in compiled code.
"""
from __future__ import annotations
import io
import numpy as np
from PIL import Image
from .scene_film import WIDTH,HEIGHT,interpolate,transform_matrix,layer_states

class CairoCompositor:
 def __init__(self,program,size,raster,raster_scale):
  import cairocffi as cairo
  self.cairo=cairo;self.program=program;self.size=size
  self.viewport=np.diag([size[0]/WIDTH,size[1]/HEIGHT,1.])
  self.art={}
  for ident,(image,offset) in raster.items():
   if image.getbbox() is None:continue
   data=io.BytesIO();image.save(data,format="PNG")
   surface=cairo.ImageSurface.create_from_png(io.BytesIO(data.getvalue()))
   source=np.array([[1/raster_scale,0,offset[0]],
                    [0,1/raster_scale,offset[1]],[0.,0.,1.]])
   self.art[ident]=(surface,source,image.width,image.height)
 def frame(self,time):
  cairo=self.cairo;program=self.program
  surface=cairo.ImageSurface(cairo.FORMAT_ARGB32,*self.size)
  context=cairo.Context(surface)
  color=program["background"].lstrip("#")
  context.set_source_rgb(*(int(color[i:i+2],16)/255 for i in (0,2,4)));context.paint()
  camera=interpolate(program["camera"]["keyframes"],time)
  camera_matrix=transform_matrix(camera,(WIDTH/2,HEIGHT/2))
  global_matrix=self.viewport@camera_matrix
  states=layer_states(program,time)
  for layer in program["layers"]:
   ident=layer["id"];art=self.art.get(ident)
   if art is None:continue
   local,opacity,reveal=states[ident];opacity*=camera["opacity"]
   if opacity<=0 or reveal<=0:continue
   source,pixels,width,height=art
   forward=global_matrix@local@pixels
   if abs(forward[0,0]*forward[1,1]-forward[0,1]*forward[1,0])<=1e-12:continue
   context.save()
   context.set_matrix(cairo.Matrix(forward[0,0],forward[1,0],forward[0,1],
                                   forward[1,1],forward[0,2],forward[1,2]))
   if reveal<1:
    context.rectangle(0,0,max(1,round(width*reveal)),height);context.clip()
   context.set_source_surface(source,0,0)
   context.get_source().set_filter(cairo.FILTER_BEST)
   context.paint_with_alpha(min(1,max(0,opacity)));context.restore()
  surface.flush()
  # The opaque canvas means its final premultiplied alpha is255 everywhere.
  return Image.frombuffer("RGBA",self.size,surface.get_data(),"raw",
                          "BGRA",surface.get_stride(),1).convert("RGB")
