"""Data-only watch thumbnails; no administrative polygons are published."""
import datetime,json,re
from pathlib import Path
from PIL import Image
from build_homepage_summary import COUNTRIES,atomic
def candidates(root,pattern):
    return [(code,path,json.loads(path.read_text())) for code,config in COUNTRIES.items() for path in (root/"data"/config[1]).glob(pattern)]
def svg(title,labels,values,unit):
    colors=["#8C510A","#D9A441","#5AB4AC","#01665E"]
    maximum=max((v for v in values if v is not None),default=1) or 1
    bars=[]
    for i,(label,value) in enumerate(zip(labels,values)):
        x=56+i*128;h=0 if value is None else value/maximum*185
        bars.append(f'<rect x="{x}" y="{260-h:.1f}" width="76" height="{h:.1f}" fill="{colors[i%4]}"/><text x="{x+38}" y="{244-h:.1f}" text-anchor="middle">{("N/A" if value is None else f"{value:.1f}")}{unit}</text><text x="{x+38}" y="292" text-anchor="middle">{label}</text>')
    import html
    return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 340" width="600" height="340"><rect width="600" height="340" fill="#F3EEE4"/><g fill="#14110D" font-family="monospace" font-size="16"><text x="32" y="36">'+html.escape(title)+'</text>'+"".join(bars)+'</g></svg>'
def build_outputs(root,pending=None):
    def save(path,content):
        if pending is None:atomic(path,content)
        else:pending.append((path,content))
    assets=root/"frontend/static/data/homepage-output";output={}
    crop=max(candidates(root,"ndvi_*.json"),key=lambda item:(item[2].get("year",0),item[2].get("doy",0),item[0]))
    code,path,obj=crop;stats=obj["stress_score"]
    date=datetime.date(obj["year"],1,1)+datetime.timedelta(days=obj["doy"]-1)
    save(assets/"crop.svg",svg("MODIS vegetation health",["Severe","Moderate","Fair","Healthy"],[stats.get(k) for k in ("severe_stress","moderate_stress","fair","healthy")],"%"))
    output["crop"]={"country":code,"date":date.isoformat(),"image":"/static/data/homepage-output/crop.svg","label":COUNTRIES[code][0]+": vegetation condition","source":"MODIS MOD13Q1","note":"Share of classified pixels; not a crop-yield forecast.","href":f"/{code}/crop/"}
    heat=max(candidates(root,"heat_*.json"),key=lambda item:(item[2].get("date",""),item[0],item[2].get("city_id","")))
    code,path,obj=heat;stats=obj["stats"]
    save(assets/"heat.svg",svg(obj["city_name"]+" · land surface",["Minimum","Mean","Maximum"],[stats.get(k) for k in ("min_lst_c","mean_lst_c","max_lst_c")],"°C"))
    output["heat"]={"country":code,"date":obj["date"],"image":"/static/data/homepage-output/heat.svg","label":obj["city_name"]+": surface temperature","source":obj["source"],"note":"Land-surface temperature is not air temperature.","href":f"/{code}/heat/"}
    mine=[]
    for code,config in COUNTRIES.items():
        folder=root/"data"/config[1];path=folder/("galamsey_sites.json" if code=="ghana" else code+"_mining_sites.json")
        if not path.exists():continue
        for site in json.loads(path.read_text()):
            dates=re.findall(r"\d{4}-\d{2}-\d{2}",site.get("period",""))
            name=site.get("ndvi_png")
            if len(dates)==2 and name:
                recent=folder/name;before=folder/name.replace("_recent_","_baseline_")
                if recent.is_file() and before.is_file():mine.append((dates[-1],code,site,dates,before,recent))
    if not mine:raise ValueError("No existing Sentinel-2 before/after pair is available")
    _,code,site,dates,before,recent=max(mine,key=lambda v:(v[0],v[1],v[2]["id"]))
    for label,path in (("before",before),("after",recent)):
        with Image.open(path) as image:
            image.thumbnail((760,440));buf=__import__("io").BytesIO();image.save(buf,"WEBP",quality=85)
            save(assets/f"mine-{label}.webp",buf.getvalue())
    output["mine"]={"country":code,"site":site["name"],"dates":dates,"before":"/static/data/homepage-output/mine-before.webp","after":"/static/data/homepage-output/mine-after.webp","source":"Sentinel-2 NDVI","note":"The same site box; vegetation-index frames, not natural-colour photographs.","href":f"/{code}/mine/"}
    return output
