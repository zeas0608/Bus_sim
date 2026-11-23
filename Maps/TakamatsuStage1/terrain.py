"""Sample GSI DEM tiles, and optionally an original PLATEAU building CityGML tile."""
import math
import xml.etree.ElementTree as ET

from shapely.geometry import Polygon, box

from survey import BBOX, ORIGIN, project


def pixels(lon,lat):
    size = 256 * 2**14
    return (lon+180)/360*size, (1-math.asinh(math.tan(math.radians(lat)))/math.pi)/2*size


def tile_ids():
    west,south,east,north = BBOX
    x0,y0 = pixels(west,north)
    x1,y1 = pixels(east,south)
    return [(x,y) for x in range(int(x0)//256,int(x1)//256+1) for y in range(int(y0)//256,int(y1)//256+1)]


class Elevation:
    def __init__(self, tiles):
        self.tiles = tiles
        self.x0,self.y0 = pixels(*ORIGIN)
        de,_ = project(ORIGIN[0]+.001, ORIGIN[1])
        _,dn = project(ORIGIN[0], ORIGIN[1]+.001)
        self.dx = (pixels(ORIGIN[0]+.001, ORIGIN[1])[0]-self.x0)/de
        self.dy = (pixels(ORIGIN[0], ORIGIN[1]+.001)[1]-self.y0)/dn
        self.variable = bool(tiles)
        self.reference = self.sample(0,0) if tiles else 0

    def sample(self,e,n):
        # Values describe pixel centres, bilinear interpolation across tile edges.
        x,y = self.x0+self.dx*e-.5,self.y0+self.dy*n-.5
        i,j = math.floor(x),math.floor(y)
        h = 0.
        for ix,fx in ((i,1-(x-i)),(i+1,x-i)):
            for iy,fy in ((j,1-(y-j)),(j+1,y-j)):
                tile = self.tiles.get((ix//256,iy//256))
                if tile is None or tile[iy%256][ix%256] == "e":
                    raise ValueError("GSI DEM has no sample inside the extent")
                h += float(tile[iy%256][ix%256])*fx*fy
        return h

    def __call__(self,e,n):
        return self.sample(e,n)-self.reference if self.variable else 0.


def plateau_buildings(path):
    # Japan PLATEAU uses lat,lon,height (JGD2011 + vertical datum, EPSG:6697).
    root = ET.parse(path).getroot()
    ns = {"b":"http://www.opengis.net/citygml/building/2.0","g":"http://www.opengis.net/gml"}
    envelope = root.find(".//g:Envelope",ns)
    if envelope is None or envelope.get("srsName","").split("/")[-1].split(":")[-1] != "6697":
        raise ValueError("PLATEAU input requires CityGML 2.0 EPSG:6697")
    extent = box(*project(*BBOX[:2]),*project(*BBOX[2:]))
    result=[]
    for b in root.findall(".//b:Building",ns):
        height = b.find("b:measuredHeight",ns)
        if height is None or height.get("uom","m") != "m" or not height.text:
            continue
        h = float(height.text)
        if not 0 < h < 400:
            continue
        candidates = b.findall(".//b:lod0FootPrint//g:Polygon",ns) or b.findall(".//b:GroundSurface//g:Polygon",ns)
        if not candidates:
            # In LOD1 solids the lowest horizontal polygon is the ground ring.
            candidates = b.findall(".//b:lod1Solid//g:Polygon",ns)
        surfaces = []
        for p in candidates:
            def ring(e):
                if e is None or not e.text or e.get("srsDimension","3") != "3":
                    return [],[]
                a = list(map(float,e.text.split()))
                return [project(lon,lat) for lat,lon in zip(a[::3],a[1::3])], a[2::3]
            pts,z = ring(p.find("g:exterior//g:posList",ns))
            if len(pts)<4 or len(z)!=len(pts):
                continue
            holes = [ring(e)[0] for e in p.findall("g:interior//g:posList",ns)]
            poly = Polygon(pts,[r for r in holes if len(r)>=4])
            if poly.is_valid and poly.area>1 and poly.intersects(extent):
                surfaces.append((sum(z)/len(z),poly))
        if surfaces:
            low = min(item[0] for item in surfaces)
            for z,p in surfaces:
                if z-low < 1:
                    result.append((p,h,"PLATEAU/"+b.get("{"+ns["g"]+"}id","unknown"),"CityGML measuredHeight, LOD footprint"))
    return result
