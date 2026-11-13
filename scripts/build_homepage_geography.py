"""Prepare public-domain country geometry; optional GADM stays outside the frontend."""
import argparse,json,math
from pathlib import Path
from build_homepage_summary import COUNTRIES,atomic,identity
ROOT=Path(__file__).resolve().parents[1]
def simplify(points,tolerance):
    if len(points)<5:return points
    def distance(point,a,b):
        dx,dy=b[0]-a[0],b[1]-a[1]
        t=max(0,min(1,((point[0]-a[0])*dx+(point[1]-a[1])*dy)/(dx*dx+dy*dy))) if dx or dy else 0
        return math.hypot(point[0]-a[0]-t*dx,point[1]-a[1]-t*dy)
    def rdp(coords):
        if len(coords)<=2:return coords
        distances=[distance(p,coords[0],coords[-1]) for p in coords[1:-1]]
        maximum=max(distances,default=0)
        if maximum<=tolerance:return [coords[0],coords[-1]]
        split=distances.index(maximum)+1
        return rdp(coords[:split+1])[:-1]+rdp(coords[split:])
    reduced=rdp(points)
    return reduced if len(reduced)>=4 else points
def topology(collections,tolerance=.025):
    arcs=[];objects={}
    def ring(points,outer):
        coords=[[round(x,5),round(y,5)] for x,y,*_ in simplify(points,tolerance)]
        signed=sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(coords,coords[1:]))
        if (signed>0)==outer:coords.reverse()  # D3 small-polygon winding.
        index=len(arcs);arcs.append(coords);return [index]
    for name,features in collections.items():
        geometries=[]
        for feature in features:
            shape=feature["geometry"]
            polygons=[shape["coordinates"]] if shape["type"]=="Polygon" else shape["coordinates"]
            converted=[[ring(points,i==0) for i,points in enumerate(polygon)] for polygon in polygons]
            geometries.append({"type":shape["type"],"id":feature.get("id"),"properties":feature["properties"],
                               "arcs":converted[0] if shape["type"]=="Polygon" else converted})
        objects[name]={"type":"GeometryCollection","geometries":geometries}
    return {"type":"Topology","objects":objects,"arcs":arcs}
def features(topology,name):
    def ring(indexes):
        result=[]
        for index in indexes:
            arc=topology["arcs"][index if index>=0 else ~index]
            points=arc if index>=0 else list(reversed(arc))
            result.extend(points if not result else points[1:])
        return result
    result=[]
    for geometry in topology["objects"][name]["geometries"]:
        arcs=geometry["arcs"]
        coordinates=[ring(a) for a in arcs] if geometry["type"]=="Polygon" else [[ring(a) for a in polygon] for polygon in arcs]
        result.append({"type":"Feature","id":geometry.get("id"),"properties":geometry["properties"],"geometry":{"type":geometry["type"],"coordinates":coordinates}})
    return result
def public_geometry(root):
    data=root/"frontend/static/data"
    africa=json.loads((data/"natural-earth-africa.geojson").read_text())["features"]
    for feature in africa:feature["properties"]={"name":feature["properties"].get("ADMIN",feature["properties"].get("NAME","Africa"))}
    covered=json.loads((data/"natural-earth-covered.geojson").read_text())["features"]
    output=topology({"africa":africa,"countries":covered},.018)
    atomic(data/"homepage_countries.topojson",json.dumps(output,separators=(",",":"),ensure_ascii=False))
    return output
def local_regions(root,crosswalk=None,output=None):
    output=output or root/".ia-local-geometry/homepage_regions.topojson"
    if output.resolve().is_relative_to((root/"frontend").resolve()):raise ValueError("GADM output cannot be written beneath the publicly served frontend (TD-3)")
    regions=[]
    for country,config in COUNTRIES.items():
        collection=json.loads((root/"data"/config[1]/config[4]).read_text())
        for feature in collection["features"]:
            key=feature["properties"]["name"];region_id,_=identity(country,config[2],key,crosswalk or {})
            feature["id"]=region_id;feature["properties"]={"id":region_id,"country":country,"key":key,"name":key}
            regions.append(feature)
    value=topology({"regions":regions},.01)
    value["notice"]="LOCAL DEVELOPMENT ONLY: GADM geometry is not licensed for publication; see TD-3."
    atomic(output,json.dumps(value,separators=(",",":"),ensure_ascii=False))
    return value
if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--root",type=Path,default=ROOT);parser.add_argument("--local-regions",choices=["gadm"]);parser.add_argument("--crosswalk",type=Path);args=parser.parse_args()
    public_geometry(args.root)
    if args.local_regions:local_regions(args.root,json.loads(args.crosswalk.read_text()) if args.crosswalk else None)
    print("Public geography: Natural Earth only"+("; GADM development geometry kept outside frontend" if args.local_regions else ""))
