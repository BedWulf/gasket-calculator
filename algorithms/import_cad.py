"""Безопасный импорт *одного* замкнутого контура прокладки из SVG/DXF.

Внешние размеры и координаты всегда приводятся к миллиметрам. Импорт служит
для подготовки сметы раскроя, НЕ для получения управляющих команд станка.
Неоднозначные единицы и несколько отдельных деталей требуют явного выбора.
Кривые дискретизируются с заданным допуском (по умолчанию 0,15 мм).
"""
from __future__ import annotations

import math
import re
from pathlib import Path
from xml.etree import ElementTree as ET

from shapely.affinity import affine_transform
from shapely.geometry import Polygon
from shapely.ops import polygonize, unary_union, snap

from algorithms.nesting import Part

MAX_FILE_SIZE = 3 * 1024 * 1024
MAX_POINTS = 30000
_NS = '{http://www.w3.org/2000/svg}'
_NUM = r'[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?'
_TOKENS = re.compile(rf'[a-zA-Z]|{_NUM}')
_LENGTH = re.compile(rf'^\s*({_NUM})\s*([a-zA-Z]*)\s*$')
_TRANSFORM = re.compile(r'([A-Za-z]+)\s*\(([^)]*)\)')
_UNIT_MM = {'mm':1., 'cm':10., 'm':1000., 'in':25.4, 'pt':25.4/72., 'pc':25.4/6., 'px':25.4/96.}
# DXF ACAD_INSUNITS; only linear units relevant to sheet-cutting
_DXF_UNITS = {1:25.4, 2:304.8, 4:1., 5:10., 6:1000., 7:1_000_000.,
              8:0.0000254, 9:0.0254, 10:914.4, 14:100., 15:10_000.}


def _read(path: str | Path) -> Path:
    p = Path(path)
    if not p.is_file() or p.stat().st_size > MAX_FILE_SIZE:
        raise ValueError('Файл отсутствует либо превышает предел 3 МБ')
    return p


def _mm(value: str, fallback_unit: str | None = None) -> float:
    m = _LENGTH.fullmatch(value)
    if m is None:
        raise ValueError(f'Неверная длина в SVG: {value!r}')
    number, unit = float(m[1]), m[2].lower()
    if not math.isfinite(number):
        raise ValueError('Недопустимый размер')
    if unit == '' and fallback_unit:
        unit = fallback_unit
    if unit not in _UNIT_MM:
        raise ValueError('SVG: размеры без единиц или неизвестные единицы; укажите мм явно')
    return number * _UNIT_MM[unit]


def _matrix_multiply(a, b):
    """Композиция a(b(x)); SVG [a c e; b d f]."""
    return (a[0]*b[0]+a[2]*b[1], a[1]*b[0]+a[3]*b[1],
            a[0]*b[2]+a[2]*b[3], a[1]*b[2]+a[3]*b[3],
            a[0]*b[4]+a[2]*b[5]+a[4], a[1]*b[4]+a[3]*b[5]+a[5])


IDENTITY = (1.,0.,0.,1.,0.,0.)


def _svg_transform(value: str):
    result = IDENTITY
    cleaned = _TRANSFORM.sub('', value).replace(',', '').strip()
    if cleaned:
        raise ValueError(f'SVG: неизвестное преобразование {value!r}')
    for name, params in _TRANSFORM.findall(value):
        nums = [float(x) for x in re.findall(_NUM, params)]
        if name == 'translate' and len(nums) in (1,2):
            op = (1,0,0,1,nums[0],nums[1] if len(nums)==2 else 0)
        elif name == 'scale' and len(nums) in (1,2):
            op = (nums[0],0,0,nums[1] if len(nums)==2 else nums[0],0,0)
        elif name == 'rotate' and len(nums) in (1,3):
            angle = math.radians(nums[0]); c,s = math.cos(angle),math.sin(angle)
            op = (c,s,-s,c,0,0)
            if len(nums)==3:
                x,y=nums[1:]
                op = _matrix_multiply((1,0,0,1,x,y),_matrix_multiply(op,(1,0,0,1,-x,-y)))
        elif name == 'matrix' and len(nums)==6:
            op = tuple(nums)
        else:
            raise ValueError(f'SVG: преобразование {name} не поддерживается')
        if not all(math.isfinite(x) for x in op):
            raise ValueError('SVG: некорректные координаты')
        result = _matrix_multiply(result,op)
    return result


def _shapely_affine(geom, m):
    return affine_transform(geom, [m[0],m[2],m[1],m[3],m[4],m[5]])


def _subdivide_curve(func, tol):
    result=[func(0)]
    def visit(a, b, pa, pb, depth):
        mid=(a+b)/2; pm=func(mid)
        err=math.hypot(pm[0]-(pa[0]+pb[0])/2,pm[1]-(pa[1]+pb[1])/2)
        if err <= tol or depth >= 12:
            result.append(pb)
            return
        visit(a,mid,pa,pm,depth+1)
        visit(mid,b,pm,pb,depth+1)
    visit(0,1,result[0],func(1),0)
    return result[1:]


def _svg_arc(p0, rx, ry, rotation, large, sweep, p1, tol):
    """SVG endpoint elliptical arc converted to center parameterization."""
    rx,ry=abs(rx),abs(ry)
    if rx<1e-10 or ry<1e-10 or p0==p1:
        return [p1]
    phi=math.radians(rotation); cp,sp=math.cos(phi),math.sin(phi)
    dx=(p0[0]-p1[0])/2; dy=(p0[1]-p1[1])/2
    xp=cp*dx+sp*dy; yp=-sp*dx+cp*dy
    scale_factor=math.sqrt((xp/rx)**2+(yp/ry)**2)
    if scale_factor>1: rx*=scale_factor;ry*=scale_factor
    rad=max(0, (rx*rx*ry*ry-rx*rx*yp*yp-ry*ry*xp*xp)/(rx*rx*yp*yp+ry*ry*xp*xp))
    sign=-1 if bool(large)==bool(sweep) else 1
    coef=sign*math.sqrt(rad)
    cxp=coef*rx*yp/ry; cyp=-coef*ry*xp/rx
    cx=cp*cxp-sp*cyp+(p0[0]+p1[0])/2
    cy=sp*cxp+cp*cyp+(p0[1]+p1[1])/2
    def vecang(u,v): return math.atan2(u[0]*v[1]-u[1]*v[0],u[0]*v[0]+u[1]*v[1])
    u=((xp-cxp)/rx,(yp-cyp)/ry);v=((-xp-cxp)/rx,(-yp-cyp)/ry)
    a0=vecang((1,0),u);delta=vecang(u,v)
    if not sweep and delta>0:delta-=2*math.pi
    if sweep and delta<0:delta+=2*math.pi
    def curve(t):
        theta=a0+delta*t
        return (cx+rx*cp*math.cos(theta)-ry*sp*math.sin(theta),
                cy+rx*sp*math.cos(theta)+ry*cp*math.sin(theta))
    return _subdivide_curve(curve,tol)


def _parse_path(data: str, tol: float) -> list[list[tuple[float,float]]]:
    """SVG path commands M L H V C S Q T A Z incl. relative variants."""
    tokens=_TOKENS.findall(data.replace(',', ' ')); i=0; cmd=None
    leftover=_TOKENS.sub('',data.replace(',',' '))
    if leftover.strip():
        raise ValueError('SVG: посторонние символы в описании пути')
    here=(0.,0.);start=None;ring=[];rings=[]
    last_cubic=None;last_quad=None;last_cmd=''
    argcounts={'M':2,'L':2,'H':1,'V':1,'C':6,'S':4,'Q':4,'T':2,'A':7,'Z':0}
    def xy(x,y,rel):return (here[0]+x,here[1]+y) if rel else (x,y)
    while i<len(tokens):
        if tokens[i].isalpha():
            cmd=tokens[i];i+=1
        if cmd is None or cmd.upper() not in argcounts:
            raise ValueError('SVG: неподдерживаемая команда path')
        op=cmd.upper(); rel=cmd.islower()
        if op=='Z':
            if start is None or len(ring)<3:
                raise ValueError('SVG: path должен быть замкнутым и иметь три вершины')
            if ring[-1]==start:ring.pop()
            rings.append(ring);ring=[];here=start;start=None;cmd=None
            last_cubic=last_quad=None;last_cmd='Z';continue
        n=argcounts[op]
        if i+n>len(tokens) or any(x.isalpha() for x in tokens[i:i+n]):
            raise ValueError('SVG: неполная команда path')
        a=list(map(float,tokens[i:i+n]));i+=n
        if not all(math.isfinite(x) for x in a):
            raise ValueError('SVG: недопустимые координаты')
        if op=='M':
            if ring:raise ValueError('SVG: незамкнутый под-контур path')
            here=xy(a[0],a[1],rel);start=here;ring=[here]
            cmd='l' if rel else 'L'
        elif start is None:
            raise ValueError('SVG: требуется начало контура M')
        elif op in ('L','H','V'):
            if op=='L':p=xy(a[0],a[1],rel)
            elif op=='H':p=(here[0]+a[0] if rel else a[0],here[1])
            else:p=(here[0],here[1]+a[0] if rel else a[0])
            ring.append(p);here=p
        elif op in ('C','S','Q','T'):
            if op=='C':
                c1=xy(a[0],a[1],rel);c2=xy(a[2],a[3],rel);p=xy(a[4],a[5],rel)
                last_cubic=c2
            elif op=='S':
                c1=(2*here[0]-last_cubic[0],2*here[1]-last_cubic[1]) if last_cmd in ('C','S') and last_cubic else here
                c2=xy(a[0],a[1],rel);p=xy(a[2],a[3],rel);last_cubic=c2
            else:
                if op=='Q':c=xy(a[0],a[1],rel);p=xy(a[2],a[3],rel)
                else:
                    c=(2*here[0]-last_quad[0],2*here[1]-last_quad[1]) if last_cmd in ('Q','T') and last_quad else here
                    p=xy(a[0],a[1],rel)
                last_quad=c
                c1=(here[0]+2*(c[0]-here[0])/3,here[1]+2*(c[1]-here[1])/3)
                c2=(p[0]+2*(c[0]-p[0])/3,p[1]+2*(c[1]-p[1])/3)
            origin=here
            def bez(t):
                s=1-t
                return (s**3*origin[0]+3*s*s*t*c1[0]+3*s*t*t*c2[0]+t**3*p[0],
                        s**3*origin[1]+3*s*s*t*c1[1]+3*s*t*t*c2[1]+t**3*p[1])
            ring.extend(_subdivide_curve(bez,tol));here=p
        elif op=='A':
            p=xy(a[5],a[6],rel)
            if a[3] not in (0,1) or a[4] not in (0,1):
                raise ValueError('SVG: флаги дуги должны быть 0 или 1')
            ring.extend(_svg_arc(here,a[0],a[1],a[2],int(a[3]),int(a[4]),p,tol));here=p
        if op not in ('C','S'):last_cubic=None
        if op not in ('Q','T'):last_quad=None
        last_cmd=op
        if len(ring)+sum(map(len,rings))>MAX_POINTS:
            raise ValueError('Слишком много вершин, упростите чертёж')
    if ring:
        raise ValueError('SVG: незамкнутый путь; соедините концы и закройте контур (Z)')
    if not rings:
        raise ValueError('SVG: не найдено замкнутых контуров')
    return rings


def _rings_to_part(rings, name: str) -> Part:
    """Интерпретируем вложенные замкнутые контуры по правилу чётности."""
    if not rings or sum(len(r) for r in rings)>MAX_POINTS:
        raise ValueError('Нет контуров или слишком много вершин')
    polys=[]
    for ring in rings:
        if len(ring)<3:raise ValueError('Контур должен содержать минимум 3 точки')
        p=Polygon(ring)
        if not p.is_valid or p.is_empty or p.area < 1e-6:
            raise ValueError('Контур незамкнут, вырожден или самопересекается')
        polys.append(p)
    # Один внешний контур; вложенные фигуры считаются отверстиями.
    # Независимые острова не объединяем в одну деталь во избежание ошибки.
    roots=[p for p in polys if not any(q!=p and q.contains(p) for q in polys)]
    if len(roots)!=1:
        raise ValueError('В файле несколько независимых внешних контуров. Импортируйте каждую прокладку отдельно')
    root=roots[0]
    if any(not root.covers(p) for p in polys):
        raise ValueError('В чертеже контуры пересекаются или расположены отдельно')
    geom=root
    for p in sorted((p for p in polys if not p.equals(root)),key=lambda p:-p.area):
        if any(q != p and p.intersects(q) and not (p.contains(q) or q.contains(p)) for q in polys):
            raise ValueError('Контуры пересекаются; поправьте чертёж')
        geom=geom.symmetric_difference(p)
    if geom.geom_type!='Polygon' or not geom.is_valid:
        raise ValueError('Сложный/раздельный контур: поддерживается одна деталь с отверстиями')
    outer=list(geom.exterior.coords)[:-1]
    holes=[list(h.coords)[:-1] for h in geom.interiors]
    xmin,ymin,_,_=geom.bounds
    result=Part(name,'polygon',points=[(round(x-xmin,5),round(y-ymin,5)) for x,y in outer],
                holes=[[(round(x-xmin,5),round(y-ymin,5)) for x,y in hole] for hole in holes])
    result.check()
    return result


def import_svg(path: str | Path, *, assume_unit: str | None = None, tolerance_mm: float = 0.15) -> Part:
    if tolerance_mm <= 0 or tolerance_mm>2:
        raise ValueError('Допуск аппроксимации должен быть между 0 и 2 мм')
    p=_read(path)
    # XML с DTD или сущностями от неизвестных отправителей отклоняем.
    contents=p.read_bytes()
    if b'<!DOCTYPE' in contents.upper() or b'<!ENTITY' in contents.upper():
        raise ValueError('SVG с DTD или пользовательскими сущностями не поддерживается')
    try:root=ET.fromstring(contents)
    except ET.ParseError as ex:raise ValueError('SVG: неверный XML') from ex
    if root.tag != _NS+'svg':raise ValueError('Требуется SVG-файл')
    viewbox=root.get('viewBox','')
    if viewbox:
        vb=[float(x) for x in re.findall(_NUM,viewbox)]
        if len(vb)!=4 or vb[2]<=0 or vb[3]<=0:
            raise ValueError('SVG: некорректный viewBox')
        x0,y0,vw,vh=vb
    else:
        x0=y0=0
        vw=vh=None
    width=root.get('width');height=root.get('height')
    if width and height:
        mm_w=_mm(width,assume_unit);mm_h=_mm(height,assume_unit)
    elif vw is not None and assume_unit:
        mm_w=vw*_UNIT_MM[assume_unit];mm_h=vh*_UNIT_MM[assume_unit]
    else:
        raise ValueError('В SVG не указаны ширина/высота в физических единицах (мм). Укажите единицы или подтвердите масштаб при импорте')
    if not 0<mm_w<1e7 or not 0<mm_h<1e7:
        raise ValueError('SVG: недопустимые габариты')
    if vw is None:vw=mm_w / (_UNIT_MM.get(assume_unit or 'px',25.4/96));vh=mm_h / (_UNIT_MM.get(assume_unit or 'px',25.4/96))
    # preserveAspectRatio: by default meet + centered; none uses independent scales.
    sx,sy=mm_w/vw,mm_h/vh
    par=root.get('preserveAspectRatio','xMidYMid meet')
    if par.strip()!='none':
        ss=min(sx,sy) if 'slice' not in par else max(sx,sy)
        align=par.split()[0] if par else 'xMidYMid'
        xshift=(mm_w-vw*ss)*({'Min':0,'Mid':0.5,'Max':1}.get(align[1:4],0.5))
        yshift=(mm_h-vh*ss)*({'Min':0,'Mid':0.5,'Max':1}.get(align[5:8],0.5))
        sx=sy=ss
    else:xshift=yshift=0
    outer_matrix=(sx,0,0,sy,xshift-x0*sx,yshift-y0*sy)
    rings=[]
    def push(points,m):
        g=_shapely_affine(Polygon(points),m)
        if not g.is_valid:raise ValueError('SVG: некорректный контур после преобразования')
        rings.append(list(g.exterior.coords)[:-1])
    def walk(node,m):
        tag=node.tag.removeprefix(_NS)
        if not node.tag.startswith(_NS):return
        if tag in ('defs','metadata','title','desc','style','clipPath','mask','symbol','pattern'):
            return
        if node.get('display')=='none' or node.get('visibility')=='hidden':return
        mat=_matrix_multiply(m,_svg_transform(node.get('transform','')))
        if tag in ('svg','g','a'):
            for c in node:walk(c,mat)
            return
        def attrs(*keys):return [float(node.attrib[k]) for k in keys]
        if tag=='path':
            for ring in _parse_path(node.get('d',''),tolerance_mm/max(sx,sy)):
                push(ring,mat)
        elif tag in ('polygon','polyline'):
            nums=[float(x) for x in re.findall(_NUM,node.get('points',''))]
            if len(nums)<6 or len(nums)%2:raise ValueError('SVG: полигон без вершин')
            if tag=='polyline' and (nums[0]!=nums[-2] or nums[1]!=nums[-1]):
                raise ValueError('SVG: открытая polyline; замкните контур')
            push(list(zip(nums[::2],nums[1::2])),mat)
        elif tag=='rect':
            x=float(node.get('x','0'));y=float(node.get('y','0'))
            w,h=attrs('width','height')
            rx=float(node.get('rx','0'));ry=float(node.get('ry',str(rx)))
            if w<=0 or h<=0 or rx<0 or ry<0:raise ValueError('SVG: неверный прямоугольник')
            rx=min(rx,w/2);ry=min(ry,h/2)
            if rx>0 and ry>0:
                coords=[]
                for cx,cy,begin in ((x+w-rx,y+ry,-90),(x+w-rx,y+h-ry,0),
                                     (x+rx,y+h-ry,90),(x+rx,y+ry,180)):
                    coords.extend((cx+rx*math.cos(math.radians(begin+90*k/24)),
                                   cy+ry*math.sin(math.radians(begin+90*k/24))) for k in range(25))
            else:coords=[(x,y),(x+w,y),(x+w,y+h),(x,y+h)]
            push(coords,mat)
        elif tag in ('circle','ellipse'):
            cx,cy=attrs('cx','cy');rx=attrs('r')[0] if tag=='circle' else attrs('rx')[0]
            ry=rx if tag=='circle' else attrs('ry')[0]
            if rx<=0 or ry<=0:raise ValueError('SVG: неверный круг/эллипс')
            n=min(1500,max(48,math.ceil(math.pi*max(rx,ry)/math.sqrt(2*max(rx,ry)*tolerance_mm/max(sx,sy)))))
            push([(cx+rx*math.cos(2*math.pi*i/n),cy+ry*math.sin(2*math.pi*i/n)) for i in range(n)],mat)
        elif tag in ('line','text','image','use','foreignObject'):
            raise ValueError(f'SVG: элемент {tag} не является замкнутой деталью; удалите подписи/размерные линии')
        else:raise ValueError(f'SVG: элемент {tag} пока не поддерживается')
    walk(root,outer_matrix)
    return _rings_to_part(rings,p.stem)


def import_dxf(path: str | Path, *, assume_mm: bool = False, tolerance_mm: float = 0.15) -> Part:
    """DXF: контуры LWPOLYLINE/POLYLINE/CIRCLE/ELLIPSE/SPLINE/LINE/ARC.

    LINE/ARC допускаются для составных замкнутых контуров. Высота Z не
    используется: это плоский листовой раскрой.
    """
    p=_read(path)
    try:import ezdxf
    except ImportError as ex:raise ValueError('Для DXF установите ezdxf из requirements.txt') from ex
    try:doc=ezdxf.readfile(p)
    except Exception as ex:raise ValueError('DXF: файл не удалось прочитать') from ex
    units=int(doc.header.get('$INSUNITS',0))
    if units==0 and assume_mm:factor=1.0
    elif units in _DXF_UNITS:factor=_DXF_UNITS[units]
    else:raise ValueError(f'DXF: неизвестные единицы ($INSUNITS={units}); укажите мм в чертеже или подтвердите импорт как мм')
    tol=tolerance_mm/factor
    segments=[]
    from ezdxf.path import make_path
    supported={'LWPOLYLINE','POLYLINE','LINE','ARC','CIRCLE','ELLIPSE','SPLINE'}
    for entity in doc.modelspace():
        kind=entity.dxftype()
        if kind not in supported:
            if kind in ('POINT','TEXT','MTEXT','DIMENSION','HATCH','INSERT','3DFACE','SOLID'):
                raise ValueError(f'DXF: {kind} не является плоским контуром; удалите оформление и блоки')
            continue
        try:
            pts=[(float(v.x)*factor,float(v.y)*factor) for v in make_path(entity).flattening(distance=tol,segments=8)]
        except Exception as ex:raise ValueError(f'DXF: нельзя преобразовать {kind} в контур') from ex
        if len(pts)<2:continue
        if len(pts)>MAX_POINTS:raise ValueError('DXF: слишком много вершин')
        segments.append(pts)
    if not segments:raise ValueError('DXF: замкнутые контуры не найдены')
    # Build polygon graph: paths may be multiple connected LINE/ARC entities.
    from shapely.geometry import LineString
    from shapely.ops import snap
    lines=[LineString(s) for s in segments]
    merged=unary_union(lines)
    # Иногда CAD выдаёт микроскопические разрывы после аппроксимации дуг.
    # Замыкаем лишь точки в пределах 0.01 мм, не меняя больших зазоров.
    merged=snap(merged,merged,0.01)
    polys=list(polygonize(merged))
    if not polys:raise ValueError('DXF: линии не образуют замкнутую фигуру (проверьте разрывы)')
    # polygonize produces both donut with holes and inner polygon; extract all
    # unique boundary rings once, then classify nesting by parity.
    rings=[];seen=set()
    for poly in polys:
        for r in [poly.exterior,*poly.interiors]:
            coords=list(r.coords)[:-1]
            signature=tuple(sorted((round(x,5),round(y,5)) for x,y in coords))
            if signature not in seen:
                seen.add(signature);rings.append(coords)
    return _rings_to_part(rings,p.stem)
