"""Original 1086 body study. Dimensions in metres; +X forward, +Y door side."""
from math import cos, sin, pi, sqrt
from mathutils import Vector

SIDES = (-1, 1)
AXLES = (2.20, -2.20)
DOORS = ((3.05, 3.91), (-1.25, -.11))
ARCH = .49
WHEEL_Z = .39


def _prism(h, name, ring, delta, mat, bone="root", bevel=0):
    """Extrude a planar ring, correcting winding for either side of the bus."""
    loop = [Vector(v) for v in ring]
    step = Vector(delta)
    normal = Vector((0, 0, 0))
    for i, v in enumerate(loop):
        normal += v.cross(loop[(i + 1) % len(loop)])
    if normal.dot(step) < 0:
        loop.reverse()
    n = len(loop)
    faces = [tuple(reversed(range(n))), tuple(range(n, 2*n))]
    faces.extend((i, (i+1) % n, n+(i+1) % n, n+i) for i in range(n))
    return h.mesh(name, loop + [v + step for v in loop], faces, mat, bone=bone, bevel=bevel)


def _side_plate(h, name, side, shape, mat, y=1.124, depth=.025, bone="root", bevel=0):
    return _prism(h, name, [(x, side*y, z) for x, z in shape],
                  (0, side*depth, 0), mat, bone, bevel)


def _side_box(h, name, side, x0, x1, z0, z1, mat, y=1.135, depth=.018, bone="root", bevel=.003):
    return h.box(name, ((x0+x1)/2, side*y, (z0+z1)/2),
                 (x1-x0, depth, z1-z0), mat, bevel=bevel, bone=bone)


def _profile(z, stations):
    if z < stations[0][0]:
        return stations[0][1]
    for (a, value), (b, nxt) in zip(stations, stations[1:]):
        if z <= b:
            return value + (nxt-value)*(z-a)/(b-a)
    return stations[-1][1]


def _face_x(front, y, z):
    """Raked glass above a projecting nose, with quarter-round bodyside corners."""
    profile = ((.25, 4.27), (.42, 4.35), (.78, 4.38), (1.22, 4.34),
               (2.52, 4.19), (2.75, 4.16), (2.91, 4.00)) if front else (
               (.25, -4.52), (.49, -4.61), (1.1, -4.60), (2.71, -4.53), (2.91, -4.39))
    radius = .22
    radial = max(0., min(radius, abs(y) - (1.15-radius)))
    corner = radius - sqrt(max(0., radius*radius-radial*radial))
    return _profile(z, profile) + (-corner if front else corner)


def _point(front, y, z, gap=0):
    return (_face_x(front, y, z) + (gap if front else -gap), y, z)


def _face_panel(h, name, front, y0, y1, z0, z1, mat, gap=0, bone="root"):
    stations = [y0] + [k for k in (-1.145,-1.125,-1.09,-1.04,-.97,-.85,0,.85,.97,1.04,1.09,1.125,1.145) if y0<k<y1] + [y1]
    heights = [z0] + [k for k in (.42,.49,.78,1.10,1.22,2.52,2.71) if z0<k<z1] + [z1]
    verts = [_point(front,y,z,gap) for z in heights for y in stations]
    n = len(stations)
    faces = []
    for j in range(len(heights)-1):
        for i in range(n-1):
            a = j*n+i
            q = (a,a+1,a+1+n,a+n)
            faces.append(q if front else q[::-1])
    return h.mesh(name, verts, faces, mat, bone=bone)


def _arch_height(x):
    for axle in AXLES:
        offset = abs(x-axle)
        if offset <= ARCH + .000001:
            return WHEEL_Z + sqrt(max(0., ARCH**2-offset**2))
    return .25


def _body_side(h, s, tag):
    bays = [(-4.32,4.035)] if s==-1 else [(-4.32,-1.25),(-.11,3.05),(3.91,4.035)]
    for i,(lo,hi) in enumerate(bays):
        # Vertical shoulders at the ends of each arch, tangent to the raised eyebrows.
        low = [(lo,.25)]
        for axle in sorted(AXLES):
            if lo < axle < hi:
                low.append((axle-ARCH,.25))
                low.extend((axle+ARCH*cos(a*pi/32), WHEEL_Z+ARCH*sin(a*pi/32))
                           for a in range(32,-1,-1))
                low.append((axle+ARCH,.25))
        low.extend([(hi,.25),(hi,1.29),(lo,1.29)])
        _side_plate(h,tag+"_side_skin_"+str(i),s,low,"ExtSky")
        _side_box(h,tag+"_ivory_belt",s,lo,hi,1.10,1.204,"ExtPearl",1.153,.011)
        _side_box(h,tag+"_belt_piping",s,lo,hi,1.076,1.094,"ExtTeal",1.152,.01)
        _side_box(h,tag+"_glazing_sill",s,lo,hi,1.25,1.30,"ExtRubber",1.146,.012)
    for front in (False,True):
        xjoin = 4.035 if front else -4.32
        zs = [.25,.42,.49,.78,1.1,1.22,1.29,2.52,2.71,2.77]
        for z0,z1 in zip(zs,zs[1:]):
            shape = [(xjoin,z0),(_face_x(front,s*1.15,z0),z0),
                     (_face_x(front,s*1.15,z1),z1),(xjoin,z1)]
            mat = "ExtSky" if z0<1.29 else "ExtRubber"
            _side_plate(h,tag+"_corner_post",s,shape,mat,depth=.026)
    for axle in AXLES:
        outer = [(axle+(.536)*cos(i*pi/32), WHEEL_Z+.536*sin(i*pi/32)) for i in range(33)]
        inner = [(axle+ARCH*cos(i*pi/32), WHEEL_Z+ARCH*sin(i*pi/32)) for i in range(32,-1,-1)]
        _side_plate(h,tag+"_rolled_wheel_arch",s,outer+inner,"ExtWheelTrim",1.148,.015)
        # Inside the well a curved liner follows the tire envelope.
        verts,faces=[],[]
        for i in range(33):
            a=i*pi/32
            x,z=axle+ARCH*cos(a), WHEEL_Z+ARCH*sin(a)
            verts.extend(((x,s*.73,z),(x,s*1.13,z)))
        for i in range(32):
            k=2*i
            faces.append((k,k+1,k+3,k+2))
        h.mesh(tag+"_arched_well_liner",verts,faces,"ExtRubber")
        h.box(tag+"_mudflap",(axle-.47,s*.937,.34),(.035,.29,.28),"ExtRubber",bevel=.012)
    # Side access doors, flush stamped edges, locks and the rear engine intake.
    for x,z,w,height in [(-3.61,.70,.99,.56),(-1.48,.79,.32,.33),(.74,.73,1.00,.51)]:
        for zz in (z-height/2,z+height/2):
            _side_box(h,tag+"_hatch_seam",s,x-w/2,x+w/2,zz,zz+.009,"ExtSeam",1.151,.006,bevel=0)
        for xx in (x-w/2,x+w/2):
            _side_box(h,tag+"_hatch_seam",s,xx,xx+.009,z-height/2,z+height/2,"ExtSeam",1.151,.006,bevel=0)
        _side_box(h,tag+"_hatch_latch",s,x+.12,x+.23,z+.12,z+.15,"ExtMetal",1.16,.007)
    for i in range(8):
        z=.54+.042*i
        _side_box(h,tag+"_intake_louvre",s,-4.02,-3.28,z,z+.018,"ExtSlat",1.153,.008)
    for x in (-4.19,.10,3.97):
        _side_box(h,tag+"_repeater",s,x-.065,x+.065,.92,.956,
                  "SignalLeft" if s==1 else "SignalRight",1.158,.014)


def _windows(h,s,tag):
    # Distinct fixed panes, sash bars and mullions rather than a solid black strip.
    openings = [(-4.32,-3.39),(-3.39,-2.34),(-2.34,-1.25),
                (-.11,.93),(.93,1.98),(1.98,3.05)] if s==1 else [
                (-4.32,-3.34),(-3.34,-2.30),(-2.30,-1.25),(-1.25,-.18),
                (-.18,.89),(.89,1.93),(1.93,2.96),(2.96,4.035)]
    for j,(a,b) in enumerate(openings):
        _side_box(h,tag+"_safety_glass_"+str(j),s,a+.031,b-.031,1.29,2.68,
                  "ExtGlass",1.13,.009,bevel=.003)
        for xx in (a,b):
            _side_box(h,tag+"_black_window_post",s,xx-.025,xx+.025,1.265,2.69,"ExtRubber",1.138,.037)
            _side_box(h,tag+"_interior_pillar",s,xx-.020,xx+.020,1.27,2.755,"ExtInner",1.104,.04)
        sash = 2.245 if j%3 else 2.22
        _side_box(h,tag+"_transom",s,a+.02,b-.02,sash-.015,sash+.015,"ExtRubber",1.14,.025)
        _side_box(h,tag+"_transom_channel",s,a+.025,b-.025,sash+.012,sash+.019,"ExtMetal",1.15,.012)
        if j%2:
            xx=(a+b)/2
            _side_box(h,tag+"_sash_joint",s,xx-.009,xx+.009,sash,2.68,"ExtSlat",1.14,.017)
    _side_box(h,tag+"_header",s,-4.32,4.035,2.67,2.785,"ExtSky",1.13,.042)
    _side_box(h,tag+"_rain_gutter",s,-4.33,4.035,2.727,2.752,"ExtPearl",1.151,.018)


def _doors(h):
    for location,(a,b) in zip(("front","mid"),DOORS):
        m=(a+b)/2
        for leaf,lo,hi in (("A",m,b),("B",a,m)):
            bone="door_"+location+"_"+leaf
            x0,x1=lo+.011,hi-.011
            _side_box(h,bone+"_apron",1,x0,x1,.295,.94,"ExtSky",1.124,.036,bone)
            _side_box(h,bone+"_belt",1,x0,x1,1.10,1.204,"ExtPearl",1.141,.022,bone)
            _side_box(h,bone+"_crossmember",1,x0,x1,.94,1.00,"ExtRubber",1.125,.045,bone)
            _side_box(h,bone+"_glass",1,x0+.022,x1-.022,1.00,2.55,"ExtGlass",1.128,.011,bone)
            for x in (x0,x1):
                _side_box(h,bone+"_stile",1,x-.015,x+.015,.285,2.60,"ExtRubber",1.134,.041,bone)
            _side_box(h,bone+"_upper_rail",1,x0,x1,2.545,2.60,"ExtRubber",1.131,.04,bone)
            _side_box(h,bone+"_lower_rail",1,x0,x1,.284,.314,"ExtSlat",1.135,.044,bone)
            _side_box(h,bone+"_threshold_stripe",1,x0+.013,x1-.013,.35,.365,"ExtMark",1.145,.009,bone)
        _side_box(h,location+"_door_drive_cover",1,a,b,2.60,2.70,"ExtRubber",1.125,.05)
        _side_box(h,location+"_entry_tread",1,a,b,.332,.355,"ExtInner",1.042,.158)
        _side_box(h,location+"_tread_marker",1,a,b,.347,.365,"ExtMark",1.112,.023)


def _rounded_loop(x0,x1,y_half,z,r):
    corners=[(x1-r,y_half-r,0), (x0+r,y_half-r,90),
             (x0+r,-y_half+r,180), (x1-r,-y_half+r,270)]
    out=[]
    for x,y,degrees in corners:
        for i in range(7):
            angle=(degrees+90*i/6)*pi/180
            out.append((x+r*cos(angle),y+r*sin(angle),z))
    return out


def _roof_and_deck(h):
    # Stamped roof has a continuous curved perimeter and a shallow crown.
    rings = [_rounded_loop(-4.53,4.16,1.15,2.74,.22),
             _rounded_loop(-4.515,4.135,1.145,2.79,.22),
             _rounded_loop(-4.49,4.10,1.117,2.84,.22),
             _rounded_loop(-4.45,4.04,1.065,2.878,.21),
             _rounded_loop(-4.40,4.00,.98,2.89,.19)]
    n=len(rings[0])
    faces=[tuple(reversed(range(n)))]
    for j in range(len(rings)-1):
        for i in range(n):
            a=j*n+i; b=j*n+(i+1)%n
            faces.append((a,b,b+n,a+n))
    faces.append(tuple(range((len(rings)-1)*n,len(rings)*n)))
    h.mesh("Pressed_roof_shell",sum(rings,[]),faces,"ExtPearl")
    h.box("Roof_climate_base",(-.10,0,2.901),(2.95,1.54,.045),"ExtSeam",bevel=.021)
    h.box("Air_conditioner_fairing",(-.1,0,2.967),(2.85,1.49,.165),"ExtRoof",bevel=.074)
    for x in (-.9,.01,.91):
        h.cyl("Condenser_fan_grille",(x,0,3.038),(x,0,3.055),.295,"ExtSeam",sides=32)
        for j in range(-3,4):
            yy=.069*j
            dx=sqrt(.276**2-yy**2)
            h.box("Fan_guard_rib",(x,yy,3.055),(2*dx,.018,.011),"ExtRoof",bevel=.004)
        h.cyl("Fan_guard_hub",(x,0,3.054),(x,0,3.066),.058,"ExtRoof",sides=20)
    for s in SIDES:
        for j in range(12):
            h.box("Climate_intake",(-1.29+j*.215,s*.736,2.965),(.136,.014,.055),"ExtSlat",bevel=.008)
    h.box("Rear_roof_vent",(-3.46,0,2.919),(.73,.82,.062),"ExtRoof",bevel=.029)
    h.box("Driver_roof_hatch",(2.75,0,2.919),(.71,.73,.061),"ExtRoof",bevel=.029)
    # Deck notches leave the wheel sweep clear on both sides.
    h.box("Continuous_aisle",(-.135,0,.325),(8.60,1.38,.07),"ExtDeck",bevel=.012)
    for s in SIDES:
        for a,b in [(-4.42,-2.70),(-1.70,1.70),(2.70,4.15)]:
            h.box("Passenger_platform",((a+b)/2,s*.895,.325),(b-a,.41,.07),"ExtDeck",bevel=.009)
    for x in (-3.2,-.1,3.1):
        h.box("Underside_crossmember",(x,0,.253),(.086,1.85,.088),"ExtRubber",bevel=.009)


def _wheel(h,x,s,axle_name):
    tag="wheel_"+axle_name+("L" if s==1 else "R")
    hub_y=.94
    # Lathed cross-section retains rounded tire shoulders and a recessed steel rim.
    profile=[(-.108,.241),(-.121,.287),(-.124,.330),(-.112,.368),(-.089,.387),
             (-.067,.390),(-.063,.386),(-.058,.390),(-.029,.390),(-.024,.385),
             (-.020,.390),(.020,.390),(.024,.385),(.029,.390),(.058,.390),
             (.063,.386),(.067,.390),(.089,.387),(.112,.368),(.124,.330),(.121,.283),(.107,.241)]
    points,faces=[],[]
    segments=52
    for off,r in profile:
        for i in range(segments):
            a=i*2*pi/segments
            points.append((x+r*cos(a),s*(hub_y+off),WHEEL_Z+r*sin(a)))
    for j in range(len(profile)):
        k=(j+1)%len(profile)
        for i in range(segments):
            q=(j*segments+i,j*segments+(i+1)%segments,k*segments+(i+1)%segments,k*segments+i)
            faces.append(q if s==-1 else q[::-1])
    h.mesh(tag+"_tyre",points,faces,"ExtRubber",bone=tag)
    def disc(n,r,y0,y1,mat,segs=40):
        return h.cyl(tag+"_"+n,(x,s*(hub_y+y0),WHEEL_Z),(x,s*(hub_y+y1),WHEEL_Z),r,mat,bone=tag,sides=segs)
    disc("steel_barrel",.253,-.115,.106,"ExtMetal")
    disc("dish",.228,.105,.111,"ExtWheelSteel")
    disc("center",.154,.109,.122 if axle_name=="F" else .118,"ExtMetal")
    disc("axle_cap",.080,.12,.161 if axle_name=="R" else .15,"ExtWheelSteel",28)
    for i in range(8):
        a=2*pi*i/8+.1
        for r,rad,material,y0,y1 in ((.188,.027,"ExtSeam",.111,.115),(.111,.014,"ExtLug",.122,.139)):
            px=x+r*cos(a); pz=WHEEL_Z+r*sin(a)
            h.cyl(tag+"_rim_detail",(px,s*(hub_y+y0),pz),(px,s*(hub_y+y1),pz),rad,material,
                  bone=tag,sides=12 if r>.15 else 6)


# Hand-drawn diode patterns: 回送 (out of service), numerals and mode legends.
GLYPHS={
    "回":["11111111111","10000000001","10111111101","10100000101","10100000101","10100000101","10111111101","10000000001","11111111111"],
    "送":["10001000100","01000101000","00011111110","11000010000","01011111111","01000010000","01000101000","01001000100","10111111111"],
    "0":["01110","10001","10011","10101","11001","10001","01110"],
    "1":["00100","01100","00100","00100","00100","00100","01110"],
    "6":["00110","01000","10000","11110","10001","10001","01110"],
    "8":["01110","10001","10001","01110","10001","10001","01110"],
    "-":["000","000","000","111","000","000","000"],
}


def _dot_sign(h,name,text,project,pitch,mat):
    """All lit cells share one lightweight mesh; no font or texture dependency."""
    rows = [GLYPHS[c] for c in text]
    full=sum(len(r[0])+2 for r in rows)-2
    left=-full/2
    verts,faces=[],[]
    for pattern in rows:
        for j,row in enumerate(pattern):
            for i,pixel in enumerate(row):
                if pixel=="1":
                    u=(left+i+.5)*pitch; v=(len(pattern)/2-j-.5)*pitch
                    w=.36*pitch
                    start=len(verts)
                    verts.extend(project(u+dx,v+dz) for dx,dz in [(-w,-w),(w,-w),(w,w),(-w,w)])
                    faces.append((start,start+1,start+2,start+3))
        left+=len(pattern[0])+2
    h.mesh(name,verts,faces,mat)


def _front_rear(h,front):
    tag="Front" if front else "Rear"
    # Stretched curved corner windows surround the driver and the rear seats.
    glass_lo=1.235 if front else 1.455
    glass_hi=2.54 if front else 2.47
    _face_panel(h,tag+"_lower_painted_shell",front,-1.15,1.15,.275,glass_lo,"ExtSky")
    _face_panel(h,tag+"_bumper",front,-1.15,1.15,.275,.535,"ExtWheelTrim",.007)
    _face_panel(h,tag+"_bumper_cap",front,-1.15,1.15,.529,.552,"ExtSky",.014)
    _face_panel(h,tag+"_waist_line",front,-1.15,1.15,1.10,1.204,"ExtPearl",.009)
    _face_panel(h,tag+"_lower_glass_seal",front,-1.15,1.15,glass_lo-.043,glass_lo+.017,"ExtRubber",.014)
    for s in SIDES:
        y0,y1=sorted((s*1.15,s*1.071))
        _face_panel(h,tag+"_screen_pillar",front,y0,y1,glass_lo,2.71,"ExtRubber",.002)
    _face_panel(h,tag+"_screen",front,-1.079,1.079,glass_lo,glass_hi,"ExtGlass",.006)
    if front:
        _face_panel(h,"Screen_center_rubber",True,-.010,.010,glass_lo,glass_hi,"ExtRubber",.015)
    _face_panel(h,tag+"_upper_fascia",front,-1.15,1.15,glass_hi,2.748,"ExtSky")
    sign_width=.72 if front else .57
    _face_panel(h,tag+"_destination_frame",front,-sign_width,sign_width,glass_hi-.012,2.736,"ExtRubber",.016)
    _face_panel(h,tag+"_LED_aperture",front,-sign_width+.027,sign_width-.027,glass_hi+.009,2.710,"ExtDisplay",.020)
    zsign=(glass_hi+2.710)*.5
    def symbol(u,v):
        # At the front +Y reads to the viewer's right, reversed at the rear.
        return _point(front,u if front else -u,zsign+v,.025)
    _dot_sign(h,tag+"_LED_deadhead","回送",symbol,.0158 if front else .017,"ExtAmberLED")
    _face_panel(h,tag+"_number_plate_edge",front,-.233,.233,.535,.776,"ExtSlat",.027)
    _face_panel(h,tag+"_number_plate",front,-.223,.223,.545,.765,"ExtPlate",.029)
    def plate(u,v):
        return _point(front,u if front else -u,.643+v,.032)
    _dot_sign(h,tag+"_fleet_plate_1086","10-86",plate,.0127,"ExtIvory")
    for s in SIDES:
        sig="SignalLeft" if s==1 else "SignalRight"
        def lens(name,u0,u1,za,zb,mat,gap):
            y0,y1=sorted((s*u0,s*u1))
            _face_panel(h,name,front,y0,y1,za,zb,mat,gap)
        if front:
            lens("Headlamp_recess",.63,1.045,.675,.94,"ExtSlat",.017)
            lens("Headlamp_chrome",.653,1.022,.693,.912,"ExtMetal",.024)
            lens("Headlamp_main",.66,.867,.718,.891,"HeadlampLens",.029)
            lens("Headlamp_high",.88,.977,.717,.889,"HeadlampLens",.029)
            lens("Front_indicator",.986,1.019,.706,.895,sig,.031)
            lens("Foglamp_bezel",.78,.991,.354,.466,"ExtSeam",.024)
            lens("Foglamp_lens",.812,.952,.374,.447,"HeadlampLens",.030)
        else:
            lens("Tail_light_cluster",.884,1.066,.68,1.123,"ExtRubber",.022)
            lens("Tail_indicator",.901,1.048,.994,1.097,sig,.03)
            lens("Tail_stop_lamp",.901,1.048,.81,.981,"TailLens",.031)
            lens("Tail_reverse_lens",.901,1.048,.702,.794,"ExtIvory",.031)
    if front:
        _face_panel(h,"Fresh_air_recess",True,-.45,.45,.907,1.044,"ExtSeam",.01)
        for k in range(4):
            z=.921+.031*k
            _face_panel(h,"Nose_grille_horizontal",True,-.439,.439,z,z+.009,"ExtSlat",.013)
        for s,name in ((1,"L"),(-1,"R")):
            bone="wiper_"+name
            def pp(y,z): return _point(True,s*y,z,.030)
            h.cyl(bone+"_spindle",pp(.49,1.242),_point(True,s*.49,1.242,.053),.027,"ExtRubber",bone=bone,sides=16)
            h.tube(bone+"_arm",[pp(.49,1.242),pp(.55,1.283),pp(.78,1.568)],.013,"ExtSlat",bone=bone)
            h.tube(bone+"_blade",[pp(.46,1.434),pp(.74,1.54),pp(1.018,1.626)],.015,"ExtRubber",bone=bone)
    else:
        _face_panel(h,"Rear_powertrain_grille",False,-.56,.56,.85,1.29,"ExtSeam",.012)
        for j in range(9):
            z=.863+.047*j
            _face_panel(h,"Powertrain_access_louvre",False,-.543,.543,z,z+.018,"ExtSky",.018)
        h.cyl("Exhaust_end",(-4.50,-.68,.26),(-4.60,-.68,.24),.043,"ExtSlat",sides=16)


def _mirrors(h):
    for s in SIDES:
        tag="Left" if s==1 else "Right"
        pos=(4.06 if s==1 else 3.96,s*(1.39 if s==1 else 1.36),2.16)
        px,py,pz=pos
        arm=[(3.73,s*1.115,2.68),(3.83,s*1.22,2.73),(px,s*1.33,2.71),(px,py,2.52),(px,py,2.34)]
        h.tube(tag+"_mirror_gooseneck",arm,.024,"ExtSlat")
        h.box(tag+"_mirror_mount",(3.73,s*1.14,2.67),(.119,.042,.123),"ExtRubber",bevel=.025)
        h.box(tag+"_mirror_housing",pos,(.118,.213,.395),"ExtRubber",bevel=.043)
        h.box(tag+"_mirror_upper_glass",(px-.059,py,pz+.048),(.010,.177,.251),"ExtMirror",bevel=.004)
        h.box(tag+"_mirror_lower_glass",(px-.058,py,pz-.118),(.010,.171,.071),"ExtMirror",bevel=.004)
        if s==1:
            h.tube("Entry_convex_mirror_stem",[(px,py,2.51),(px+.1,py+.031,2.46)],.016,"ExtSlat")
            a=(px+.07,py+.031,2.432); b=(px+.14,py+.031,2.47)
            h.cyl("Auxiliary_mirror_shell",a,b,.102,"ExtRubber",sides=28)
            h.cyl("Auxiliary_mirror_lens",(a[0]-.005,a[1],a[2]-.003),a,.093,"ExtMirror",sides=28)


def _side_sign(h):
    # Route box faces passengers waiting on the pavement.
    _side_box(h,"Side_LED_case",1,-.08,.86,2.253,2.50,"ExtRubber",1.14,.032)
    _side_box(h,"Side_LED_blackface",1,-.065,.845,2.272,2.484,"ExtDisplay",1.158,.009)
    _dot_sign(h,"Side_LED_deadhead","回送",lambda u,v:(.39-u,1.165,2.377+v),.018,"ExtAmberLED")
    for s in SIDES:
        # Unit number in simple hand-drawn digits; no operator logo or photo texture.
        _dot_sign(h,"Vehicle_number_"+str(s),"1086",lambda u,v:(-2.99-s*u,s*1.159,.993+v),.007,"ExtIvory")
    _side_box(h,"Forward_door_quarterlight",1,3.927,4.036,1.29,2.68,"ExtGlass",1.13,.011)
    _side_box(h,"Quarterlight_gasket",1,3.914,3.932,1.27,2.68,"ExtRubber",1.14,.033)


def build(h):
    """Build individual rigidly skinned parts with metric production pivots."""
    mats=[
        ("ExtSky",(.155,.558,.787),.23,.30,1,0),
        ("ExtPearl",(.845,.880,.851),.13,.34,1,0),
        ("ExtTeal",(.026,.203,.319),.27,.34,1,0),
        ("ExtWheelTrim",(.089,.351,.531),.22,.32,1,0),
        ("ExtIvory",(.901,.890,.757),.08,.35,1,0),
        ("ExtSlat",(.068,.090,.103),.40,.40,1,0),
        ("ExtSeam",(.030,.048,.058),.16,.53,1,0),
        ("ExtRubber",(.020,.028,.033),.03,.69,1,0),
        ("ExtMetal",(.452,.497,.509),.75,.30,1,0),
        ("ExtWheelSteel",(.325,.378,.400),.81,.33,1,0),
        ("ExtLug",(.568,.599,.603),.79,.28,1,0),
        ("ExtRoof",(.649,.705,.724),.27,.42,1,0),
        ("ExtGlass",(.144,.323,.357),.08,.12,.17,0),
        ("ExtMirror",(.48,.61,.65),.89,.12,1,0),
        ("ExtDeck",(.126,.148,.155),0,.76,1,0),
        ("ExtInner",(.534,.577,.568),.16,.51,1,0),
        ("ExtMark",(.989,.492,.052),.02,.5,1,0),
        ("ExtDisplay",(.012,.021,.021),.02,.49,1,0),
        ("ExtAmberLED",(.96,.314,.019),.05,.36,1,1.8),
        ("ExtPlate",(.024,.206,.143),.13,.38,1,0),
        ("HeadlampLens",(.802,.878,.921),.42,.17,1,0),
        ("SignalLeft",(.931,.313,.019),.14,.24,1,0),
        ("SignalRight",(.931,.313,.019),.14,.24,1,0),
        ("TailLens",(.515,.032,.021),.14,.24,1,0),
    ]
    for name,color,metal,roughness,alpha,emit in mats:
        h.material(name,color,metallic=metal,roughness=roughness,alpha=alpha,emission=emit)
    _roof_and_deck(h)
    for s in SIDES:
        side="Curb" if s==1 else "Street"
        _body_side(h,s,side)
        _windows(h,s,side)
        for x,axle in zip(AXLES,("F","R")):
            _wheel(h,x,s,axle)
    _doors(h)
    _front_rear(h,True)
    _front_rear(h,False)
    _mirrors(h)
    _side_sign(h)
