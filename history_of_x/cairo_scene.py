"""Subpixel affine compositing through Cairo/pixman on the Actions CPU.

The same raster artwork and world matrices drive both backends. Source surfaces
are decoded once; Cairo resamples and composites them in compiled code.
"""
from __future__ import annotations
import io
import math
import numpy as np
from PIL import Image
from .scene_film import WIDTH,HEIGHT,interpolate,transform_matrix,layer_states

class CairoCompositor:
 def __init__(self,program,size,raster=None,raster_scale=1,recording=False):
  import cairocffi as cairo
  self.cairo=cairo;self.program=program;self.size=size
  self.viewport=np.diag([size[0]/WIDTH,size[1]/HEIGHT,1.])
  self.art={}
  if recording:
   self.art=self._recorded_art(program,cairo)
   return
  for ident,(image,offset) in raster.items():
   if image.getbbox() is None:continue
   data=io.BytesIO();image.save(data,format="PNG")
   surface=cairo.ImageSurface.create_from_png(io.BytesIO(data.getvalue()))
   source=np.array([[1/raster_scale,0,offset[0]],
                    [0,1/raster_scale,offset[1]],[0.,0.,1.]])
   self.art[ident]=(surface,source,image.width,image.height,0,0)
 def _recorded_art(self,program,cairo):
  import copy
  import xml.etree.ElementTree as ET
  from cairosvg.parser import Tree
  from cairosvg.surface import PNGSurface
  from .scene_film import _svg_tree,_name
  class RecordedSVG(PNGSurface):
   def _create_surface(self,width,height):
    return cairo.RecordingSurface(cairo.CONTENT_COLOR_ALPHA,None),width,height
  root,_=_svg_tree(program["svg"])
  definitions=[child for child in root if _name(child.tag)=="defs"]
  groups={child.get("id"):child for child in root if _name(child.tag)=="g"}
  result={}
  for layer in program["layers"]:
   group=groups[layer["id"]]
   if not len(group):continue
   art=ET.Element(root.tag,dict(root.attrib))
   art.set("overflow","visible")
   for definition in definitions:art.append(copy.deepcopy(definition))
   art.append(copy.deepcopy(group))
   source_bytes=ET.tostring(art)
   tree=Tree(bytestring=source_bytes,unsafe=False)
   drawing=RecordedSVG(tree,None,96,output_width=WIDTH,output_height=HEIGHT)
   x,y,w,h=drawing.cairo.ink_extents()
   if w<=0 or h<=0:continue
   if any(_name(element.tag) in ("text","tspan") for element in group.iter()):
    # Keep the verified font rendering for short labels/documents. Only these
    # small layers need supersampled pixels; characters/scenery remain vector.
    import cairosvg
    scale=max(2.,max(f.get("scale",1) for f in program["camera"]["keyframes"]))
    left,top=math.floor(x)-2,math.floor(y)-2
    width,height=math.ceil(x+w)+2-left,math.ceil(y+h)+2-top
    if width*height*scale*scale>40_000_000:raise ValueError("Text layer exceeds the raster budget")
    # Crop around the actual ink even if it begins outside the camera. The
    # nested SVG retains the original1920x1080 percentage-coordinate context.
    crop=ET.Element(root.tag,{"viewBox":f"{left} {top} {width} {height}","width":str(width),"height":str(height)})
    art.set("x","0");art.set("y","0");art.set("width",str(WIDTH));art.set("height",str(HEIGHT));crop.append(art)
    png=cairosvg.svg2png(bytestring=ET.tostring(crop),output_width=round(width*scale),output_height=round(height*scale),unsafe=False)
    image=Image.open(io.BytesIO(png)).convert("RGBA");data=io.BytesIO();image.save(data,format="PNG")
    pixels=cairo.ImageSurface.create_from_png(io.BytesIO(data.getvalue()))
    matrix=np.array([[1/scale,0,left],[0,1/scale,top],[0.,0.,1.]])
    result[layer["id"]]=(pixels,matrix,image.width,image.height,0,0)
    continue
   # Retain the recording; replay shapes at the current fractional transform.
   result[layer["id"]]=(drawing.cairo,np.eye(3),w,h,x,y)
  return result
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
   source,pixels,width,height,clip_x,clip_y=art
   forward=global_matrix@local@pixels
   if abs(forward[0,0]*forward[1,1]-forward[0,1]*forward[1,0])<=1e-12:continue
   context.save()
   context.set_matrix(cairo.Matrix(forward[0,0],forward[1,0],forward[0,1],
                                   forward[1,1],forward[0,2],forward[1,2]))
   if reveal<1:
    context.rectangle(clip_x,clip_y,max(1,round(width*reveal)),height);context.clip()
   context.set_source_surface(source,0,0)
   context.get_source().set_filter(cairo.FILTER_BEST)
   context.paint_with_alpha(min(1,max(0,opacity)));context.restore()
  surface.flush()
  # The opaque canvas means its final premultiplied alpha is255 everywhere.
  return Image.frombuffer("RGBA",self.size,surface.get_data(),"raw",
                          "BGRA",surface.get_stride(),1).convert("RGB")
