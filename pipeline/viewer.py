# -*- coding: utf-8 -*-
"""单文件交互看图台（3D 走廊 + 2D 页签）——通用参数化版。"""
import base64
import io
import json
import math
import os
from pathlib import Path

from PIL import Image

from .common import ensure_dirs, image_to_data_uri, log, load_json, save_json
from .geo import RouteIndex, load_geometry


def _jpeg_data(png, max_w=5200, q=84):
    if not png or not os.path.exists(png):
        return None
    im = Image.open(png).convert("RGB")
    if im.size[0] > max_w:
        k = max_w / im.size[0]
        im = im.resize((int(im.size[0] * k), int(im.size[1] * k)), Image.LANCZOS)
    b = io.BytesIO()
    im.save(b, "JPEG", quality=q, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()


def build_viewer(cfg, out_html=None):
    ensure_dirs(cfg)
    g = load_geometry(cfg)
    v = cfg.get("viewer", {})
    # 参考中心：优先底图元数据，否则几何中心
    meta = None
    if cfg.get("_base_meta") and os.path.exists(cfg["_base_meta"]):
        meta = load_json(cfg["_base_meta"])
    route = g["route"]
    if meta:
        lat0 = (meta["lat_min"] + meta["lat_max"]) / 2
        lon0 = (meta["lon_min"] + meta["lon_max"]) / 2
        gw = meta["width_px"] * meta["m_per_px"]
        gh = meta["height_px"] * meta["m_per_px"]
    else:
        lat0 = (min(p["lat"] for p in route) + max(p["lat"] for p in route)) / 2
        lon0 = (min(p["lon"] for p in route) + max(p["lon"] for p in route)) / 2
        las = [p["lat"] for p in route]
        lons = [p["lon"] for p in route]
        gw = (max(lons) - min(lons)) * 101000 * math.cos(math.radians(lat0)) + 2000
        gh = (max(las) - min(las)) * 111320 + 2000
    mlon = 111320.0 * math.cos(math.radians(lat0))

    def en(lat, lon):
        return (lon - lon0) * mlon, (lat - lat0) * 111320.0

    pts = []
    for p in route:
        x, z = en(p["lat"], p["lon"])
        pts.append([round(x, 1), round(z, 1), round(p["station_m"], 1)])
    feats = []
    for f in g.get("features", []):
        x, z = en(f["geo"]["lat"], f["geo"]["lon"])
        feats.append([f["name"], f["station_m"], round(x, 1), round(z, 1)])
    bridges = []
    for b in g.get("bridges", []):
        ri = RouteIndex(route)
        a, c = ri.interp(b["center"] - b["len_m"] / 2), ri.interp(b["center"] + b["len_m"] / 2)
        x0, z0 = en(a["lat"], a["lon"])
        x1, z1 = en(c["lat"], c["lon"])
        bridges.append([b["center"], b["len_m"], b.get("width_m", 24.5),
                        round(x0, 1), round(z0, 1), round(x1, 1), round(z1, 1),
                        b.get("spans", ""), b["name"]])
    xs = [p[0] for p in pts]
    zs = [p[1] for p in pts]
    cx, cz = (min(xs) + max(xs)) / 2, (min(zs) + max(zs)) / 2
    span = max(max(xs) - min(xs), max(zs) - min(zs), 600.0)
    d0 = 1.25 * span
    pan = [round(cx - d0 * 0.72, 1), round(d0 * 0.58, 1), round(cz - d0 * 0.52, 1)]
    if bridges:
        bx = (bridges[0][3] + bridges[0][5]) / 2
        bz = (bridges[0][4] + bridges[0][6]) / 2
        close = [round(bx - 300, 1), 220, round(bz - 400, 1), round(bx, 1), round(bz, 1)]
    else:
        close = [pan[0], pan[1], pan[2], round(cx, 1), round(cz, 1)]

    sat = _jpeg_data(cfg.get("_base"))
    map2d = None
    if v.get("2d_embed", True):
        mp = cfg.get("_map2d")
        if mp and os.path.exists(mp):
            map2d = image_to_data_uri(mp, 2300, 80)
    title = v.get("title", cfg["project"].get("title_viewer", "工程 3D 看图台"))
    note = v.get("note", "")
    three = Path(__file__).resolve().parents[1] / "templates" / "three.min.js"
    three_js = (three.read_text(encoding="utf-8", errors="replace")
                if three.exists()
                else "console.warn('缺少 templates/three.min.js');")
    html = _template().replace("@@TITLE@@", title).replace("@@NOTE@@", note)
    html = html.replace("@@THREE@@", three_js)
    html = html.replace("@@ROUTE@@", "[" + ",".join("[%.1f,%.1f,%.1f]" % tuple(p) for p in pts) + "]")
    html = html.replace("@@FEAT@@", "[" + ",".join('["%s",%.1f,%.1f,%.1f]' % tuple(f) for f in feats) + "]")
    html = html.replace("@@BRIDGES@@", "[" + ",".join(
        "[%.1f,%.1f,%.1f,%.1f,%.1f,%.1f,%.1f,'%s','%s']" % tuple(b) for b in bridges) + "]")
    html = html.replace("@@GW@@", "%.1f" % gw).replace("@@GH@@", "%.1f" % gh)
    html = html.replace("@@SAT@@", sat or "''")
    html = html.replace("@@MAP2D@@", map2d or "")
    html = html.replace("@@CTX@@", "%.1f" % cx).replace("@@CTZ@@", "%.1f" % cz)
    html = html.replace("@@PPOS@@", ",".join("%.1f" % x for x in pan))
    html = html.replace("@@BPOS@@", ",".join("%.1f" % x for x in close[:3]))
    html = html.replace("@@BTX@@", "%.1f" % close[3]).replace("@@BTZ@@", "%.1f" % close[4])
    html = html.replace("@@RD@@", "%.1f" % d0)
    out = Path(out_html or (Path(cfg["_work"]) / "输出" / "看图台.html"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    cfg["_viewer"] = str(out)
    log("看图台已保存 %s (%.1f MB)" % (out, out.stat().st_size / 1e6))
    return out


def _template():
    return r"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>@@TITLE@@</title>
<style>
html,body{margin:0;height:100%;overflow:hidden;background:#0d1a26;font-family:"Microsoft YaHei","PingFang SC",sans-serif}
canvas{display:block;touch-action:none}
#tabs{position:fixed;top:12px;left:50%;transform:translateX(-50%);z-index:30;display:flex;gap:6px;background:rgba(14,30,45,.8);padding:6px;border-radius:12px}
#tabs button{border:0;border-radius:8px;padding:9px 16px;color:#eaf1f6;background:rgba(255,255,255,.15);font:14px sans-serif;cursor:pointer}
#tabs button.on{background:#2f7fd0}
#ui{position:fixed;left:50%;bottom:12px;transform:translateX(-50%);z-index:30;display:flex;gap:6px;background:rgba(14,30,45,.8);padding:7px 10px;border-radius:12px}
#ui button{border:0;border-radius:7px;padding:7px 11px;color:#eaf1f6;background:rgba(255,255,255,.16);font:13px sans-serif;cursor:pointer}
#cap{position:fixed;left:12px;top:12px;color:#fff;font:14px/1.6 sans-serif;background:rgba(12,26,40,.72);padding:9px 14px;border-radius:10px;z-index:25;max-width:600px;pointer-events:none}
#hint{position:fixed;right:12px;top:12px;color:#d7e3ec;font:12px sans-serif;background:rgba(12,26,40,.65);padding:7px 11px;border-radius:8px;z-index:25;pointer-events:none}
#map2d{position:fixed;inset:0;z-index:5;display:none;background:#0d1a26;overflow:hidden;cursor:grab}
#map2d.drag{cursor:grabbing}
#mapstage{position:absolute;left:0;top:0;transform-origin:0 0}
#mapstage img{display:block;pointer-events:none}
#mapzoom{position:fixed;right:16px;bottom:58px;z-index:35;background:rgba(14,30,45,.9);color:#fff;font:13px sans-serif;padding:5px 11px;border-radius:8px;display:none}
#map2d .tip{position:fixed;left:50%;bottom:58px;transform:translateX(-50%);z-index:35;background:rgba(14,30,45,.85);color:#d7e3ec;font:13px sans-serif;padding:5px 11px;border-radius:8px;pointer-events:none}
</style></head><body>
<div id="tabs"><button id="tb3d" class="on">3D 全景看图</button><button id="tb2d">2D 走向图</button></div>
<div id="hint">左键旋转 · 右键平移 · 滚轮缩放 · 双击复位</div>
<div id="cap"><b>@@TITLE@@</b><br>@@NOTE@@</div>
<div id="map2d"><div class="tip">左键拖动平移 · 滚轮缩放 · 双击复位</div><div id="mapzoom">100%</div><div id="mapstage"><img id="img2d" alt="2D"></div></div>
<div id="ui"></div>
<script>@@THREE@@</script>
<script>
var ROUTE=@@ROUTE@@,FEATURES=@@FEAT@@,BRIDGES=@@BRIDGES@@;
var GEO={w:@@GW@@,h:@@GH@@};
var SAT=@@SAT@@;
var scene=new THREE.Scene();
(function(){var c=document.createElement('canvas');c.width=8;c.height=256;var g=c.getContext('2d');
 var gr=g.createLinearGradient(0,0,0,256);gr.addColorStop(0,'#6fa8dc');gr.addColorStop(.5,'#c5dcef');gr.addColorStop(1,'#dbe7ed');
 g.fillStyle=gr;g.fillRect(0,0,8,256);scene.background=new THREE.CanvasTexture(c);})();
var camera=new THREE.PerspectiveCamera(44,innerWidth/innerHeight,1,20000);
var renderer=new THREE.WebGLRenderer({antialias:true});
renderer.setSize(innerWidth,innerHeight);renderer.setPixelRatio(Math.min(devicePixelRatio||1,2));
renderer.outputEncoding=THREE.sRGBEncoding;renderer.toneMapping=THREE.ACESFilmicToneMapping;
document.body.appendChild(renderer.domElement);
scene.add(new THREE.HemisphereLight(0xdce8ff,0x9aa87c,.9));
var sun=new THREE.DirectionalLight(0xfff0d8,1.4);sun.position.set(800,1200,400);scene.add(sun);
function M(w,h,d,color,o){o=o||{};var m=new THREE.Mesh(new THREE.BoxGeometry(w,h,d),new THREE.MeshStandardMaterial({color:color,roughness:o.roughness||.85}));return m;}
function bar(x0,z0,x1,z1,w,h,y,color,o){var dx=x1-x0,dz=z1-z0,ln=Math.sqrt(dx*dx+dz*dz);if(ln<.2)return;
 var m=M(w,h,ln,color,o);m.position.set((x0+x1)/2,y,(z0+z1)/2);m.rotation.y=Math.atan2(dx,dz);scene.add(m);}
if(SAT){var t=new THREE.TextureLoader().load(SAT,function(){if(NONINTER)renderOnce();});
 t.encoding=THREE.sRGBEncoding;t.flipY=false;t.anisotropy=8;
 var sp=new THREE.Mesh(new THREE.PlaneGeometry(GEO.w,GEO.h),new THREE.MeshStandardMaterial({map:t,roughness:1}));
 sp.rotation.x=-Math.PI/2;sp.position.y=.05;scene.add(sp);}
var satReady=true,NONINTER=false;
var RW=20;
for(var i=0;i<ROUTE.length-1;i++){var a=ROUTE[i],b=ROUTE[i+1];
 var dx=b[0]-a[0],dz=b[1]-a[1],ln=Math.sqrt(dx*dx+dz*dz);if(ln<1)continue;
 bar(a[0],a[1],b[0],b[1],RW,.24,.14,'#23262a',{roughness:.95});
 var nx=-dz/ln,nz=dx/ln;
 bar(a[0]+nx*RW/2,a[1]+nz*RW/2,b[0]+nx*RW/2,b[1]+nz*RW/2,.2,.3,.2,'#dfe5ea');
 bar(a[0]-nx*RW/2,a[1]-nz*RW/2,b[0]-nx*RW/2,b[1]-nz*RW/2,.2,.3,.2,'#dfe5ea');
 if(i%2===0)bar(a[0],a[1],b[0],b[1],.22,.12,.3,'#e7c94f');}
BRIDGES.forEach(function(b){var x0=b[3],z0=b[4],x1=b[5],z1=b[6],L=Math.hypot(x1-x0,z1-z0);
 bar(x0,z0,x1,z1,b[2]+.5,2.2,7.0,'#6a7076');
 bar(x0,z0,x1,z1,b[2]-1.4,.2,7.5,'#191b1e');
 var n=Math.max(1,Math.round(L/20));
 for(var k=1;k<n;k++){var fx=x0+(x1-x0)*k/n,fz=z0+(z1-z0)*k/n;
  var p=M(2,6.2,2,'#a9a49b');p.position.set(fx,3.1,fz);p.rotation.y=Math.atan2(x1-x0,z1-z0);scene.add(p);}
 var sp=label(String(b[8]).slice(0,12),(x0+x1)/2,(z0+z1)/2,12);sp.position.y=9;scene.add(sp);});
var markers=new THREE.Group();
FEATURES.forEach(function(f){
 var sp=label(f[0].slice(0,18),(f[2]),(f[3]),14);sp.position.y=8;markers.add(sp);});
scene.add(markers);
function label(txt,x,z,sc){var c=document.createElement('canvas');c.width=900;c.height=160;var g=c.getContext('2d');
 g.fillStyle='rgba(13,28,44,.88)';g.fillRect(0,0,900,160);g.fillStyle='#fff';g.font='bold 60px sans-serif';
 g.textAlign='center';g.textBaseline='middle';g.fillText(txt,450,80);
 var tx=new THREE.CanvasTexture(c);tx.encoding=THREE.sRGBEncoding;
 var sp=new THREE.Sprite(new THREE.SpriteMaterial({map:tx,transparent:true,depthTest:false}));
 sp.scale.set(sc,sc*.18,1);sp.position.set(x,0,z);return sp;}
scene.traverse(function(o){if(!o.material)return;var ms=[].concat(o.material);for(var i=0;i<ms.length;i++){var m=ms[i];if(m&&m.color&&m.color.convertSRGBToLinear)m.color.convertSRGBToLinear();}});
var CT=@@CTX@@,CZ=@@CTZ@@;
var PRESETS={panorama:{pos:[@@PPOS@@],fov:52,tgt:[@@CTX@@,0,@@CTZ@@]},
 bridge:{pos:[@@BPOS@@],fov:46,tgt:[@@BTX@@,6,@@BTZ@@]}};
var view=new URLSearchParams(location.search).get('v')||'interactive';
var map2d=document.getElementById('map2d'),mapStage=document.getElementById('mapstage'),mapZoomLbl=document.getElementById('mapzoom');
var mapOpen=false,mapInit=false,radius=@@RD@@,theta=Math.PI/2,phi=.62,autoRotate=false;
function updateCam(){camera.position.set(tgt.x+radius*Math.sin(phi)*Math.cos(theta),tgt.y+radius*Math.cos(phi),tgt.z+radius*Math.sin(phi)*Math.sin(theta));camera.lookAt(tgt);}
var tgt=new THREE.Vector3(CT,0,CZ);
function applyCam(p){tgt.set(p.tgt[0],p.tgt[1],p.tgt[2]);var dx=p.pos[0]-tgt.x,dy=p.pos[1]-tgt.y,dz=p.pos[2]-tgt.z;
 radius=Math.sqrt(dx*dx+dy*dy+dz*dz);phi=Math.max(.12,Math.min(1.5,Math.acos(dy/radius)));theta=Math.atan2(dz,dx);
 camera.fov=p.fov;camera.updateProjectionMatrix();updateCam();}
function renderOnce(){renderer.render(scene,camera);}
if(view==='interactive'){
 var down=false,mode='orbit',lx=0,ly=0;
 addEventListener('pointerdown',function(e){if(e.target&&e.target.closest&&e.target.closest('button'))return;if(mapOpen)return;
  down=true;lx=e.clientX;ly=e.clientY;mode=e.button===2?'pan':'orbit';autoRotate=false;});
 addEventListener('pointermove',function(e){if(!down||mapOpen)return;var dx=e.clientX-lx,dy=e.clientY-ly;
  if(mode==='pan'){var vx=Math.sin(theta),vz=Math.cos(theta);tgt.x-=vx*dx*radius*.0011;tgt.z-=vz*dx*radius*.0011;tgt.x-=Math.cos(theta)*dy*radius*.0011;tgt.z+=Math.sin(theta)*dy*radius*.0011;}
  else{theta-=dx*.006;phi=Math.max(.15,Math.min(1.5,phi-dy*.005));}
  lx=e.clientX;ly=e.clientY;});
 addEventListener('pointerup',function(){down=false;});addEventListener('contextmenu',function(e){e.preventDefault();});
 addEventListener('wheel',function(e){if(mapOpen)return;e.preventDefault();radius=Math.max(150,Math.min(20000,radius*(e.deltaY>0?1.08:.92)));},{passive:false});
 addEventListener('dblclick',function(){if(!mapOpen)applyCam(PRESETS.panorama);});
 var ui=document.getElementById('ui');
 function btn(t,f){var b=document.createElement('button');b.textContent=t;b.onclick=f;ui.appendChild(b);}
 btn('自动旋转',function(){autoRotate=!autoRotate;});btn('全景',function(){applyCam(PRESETS.panorama);autoRotate=false;});
 btn('近景',function(){applyCam(PRESETS.bridge);autoRotate=false;});btn('桩号',function(){markers.visible=!markers.visible;});
 updateCam();(function loop(){if(autoRotate&&!down)theta+=.0016;updateCam();renderer.render(scene,camera);requestAnimationFrame(loop);})();
 var tb3d=document.getElementById('tb3d'),tb2d=document.getElementById('tb2d'),cap=document.getElementById('cap'),uiBar=document.getElementById('ui');
 document.getElementById('img2d').src='data:image/jpeg;base64,@@MAP2D@@';
 var ms={scale:1,tx:0,ty:0};
 function fitMap(){var cw=map2d.clientWidth,ch=map2d.clientHeight,img=document.getElementById('img2d');
  var iw=img.naturalWidth||2400,ih=img.naturalHeight||1600,sc=Math.min(1,Math.min(cw/iw,ch/ih)*.98);
  ms.scale=sc;ms.tx=(cw-iw*sc)/2;ms.ty=(ch-ih*sc)/2;applyMap();}
 function applyMap(){mapStage.style.transform='translate('+ms.tx+'px,'+ms.ty+'px) scale('+ms.scale+')';mapZoomLbl.textContent=Math.round(ms.scale*100)+'%';}
 function setup2D(){if(mapInit)return;mapInit=true;var img=document.getElementById('img2d');img.addEventListener('load',fitMap);if(img.complete)fitMap();
  var dn=false,a=0,b=0;map2d.addEventListener('pointerdown',function(e){dn=true;a=e.clientX;b=e.clientY;map2d.classList.add('drag');});
  map2d.addEventListener('pointermove',function(e){if(!dn)return;ms.tx+=e.clientX-a;ms.ty+=e.clientY-b;a=e.clientX;b=e.clientY;applyMap();});
  map2d.addEventListener('pointerup',function(){dn=false;map2d.classList.remove('drag');});
  map2d.addEventListener('wheel',function(e){e.preventDefault();var k=e.deltaY>0?1/1.16:1.16;var cw=map2d.clientWidth,ch=map2d.clientHeight;
   var px=(cw/2-ms.tx)/ms.scale,py=(ch/2-ms.ty)/ms.scale;ms.scale=Math.max(.2,Math.min(14,ms.scale*k));
   ms.tx=cw/2-px*ms.scale;ms.ty=ch/2-py*ms.scale;applyMap();},{passive:false});
  map2d.addEventListener('dblclick',function(e){e.preventDefault();fitMap();});}
 tb3d.onclick=function(){mapOpen=false;tb3d.className='on';tb2d.className='';map2d.style.display='none';mapZoomLbl.style.display='none';uiBar.style.display='flex';cap.style.display='block';};
 tb2d.onclick=function(){tb2d.className='on';tb3d.className='';mapOpen=true;map2d.style.display='block';mapZoomLbl.style.display='block';uiBar.style.display='none';cap.style.display='none';setup2D();fitMap();};
}else{NONINTER=true;applyCam(PRESETS[view]||PRESETS.panorama);document.getElementById('hint').style.display='none';
 document.getElementById('tabs').style.display='none';document.getElementById('ui').style.display='none';
 setTimeout(renderOnce,400);setTimeout(renderOnce,1800);}
</script></body></html>"""
