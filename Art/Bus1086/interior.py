"""Original, estimated right-hand-drive cabin in metres. Positive X points forward."""
import math

import bpy
from mathutils import Vector


EYE = (3.20, -.65, 1.86)
STEERING = (3.62, -.66, 1.31)
SPEED = (3.872, -.515, 1.527)
RPM = (3.872, -.805, 1.527)
SELECTOR = (3.70, -.245, 1.30)
SWITCHES = (
    ('switch_front', (3.82, -.15, 1.385), 'F', 'CabAmber'),
    ('switch_mid', (3.82, -.04, 1.385), 'M', 'CabAmber'),
    ('switch_park', (3.61, -.13, 1.30), 'P', 'CabRed'),
    ('switch_lights', (3.91, -.15, 1.42), 'L', 'CabGreen'),
    ('switch_left', (3.71, -.035, 1.33), '<', 'CabGreen'),
    ('switch_right', (3.71, -.12, 1.33), '>', 'CabGreen'),
)
UV_RIGHT = Vector((0, -1, 0))


def materials(h):
    palette = {
        'CabGraphite': ((.034, .044, .053), .06, .42),
        'CabBlack': ((.011, .016, .021), .03, .48),
        'CabWheelGrip': ((.031, .039, .042), .01, .60),
        'CabShell': ((.24, .30, .32), .10, .40),
        'CabFloor': ((.12, .15, .16), .02, .73),
        'CabStone': ((.54, .56, .50), .02, .49),
        'CabLight': ((.77, .78, .70), .01, .41),
        'CabSilver': ((.45, .51, .53), .68, .30),
        'CabWhite': ((.85, .88, .82), .03, .36),
        'CabOcean': ((.034, .125, .26), .02, .78),
        'CabBlue': ((.085, .25, .42), .01, .77),
        'CabWeave': ((.11, .38, .51), .01, .67),
        'CabOrange': ((.94, .36, .055), .03, .43),
        'CabYellow': ((.90, .67, .12), .02, .49),
        'CabRed': ((.68, .052, .025), .03, .42),
        'CabGreen': ((.045, .54, .28), .04, .39),
        'CabAmber': ((.95, .44, .055), .02, .37),
        'CabScreen': ((.028, .086, .083), .12, .29),
    }
    for name, (color, metal, rough) in palette.items():
        h.material(name, color, metallic=metal, roughness=rough)


def panel(h, name, origin, u, v, width, height, thickness, radius, material, bone='root'):
    """Rounded face in the (u,v) plane, front surface at origin."""
    origin, u, v = Vector(origin), Vector(u), Vector(v)
    n = u.cross(v).normalized()
    radius = min(radius, width * .49, height * .49)
    contour = []
    for i, (sx, sy) in enumerate(((1, 1), (-1, 1), (-1, -1), (1, -1))):
        cx, cy = sx * (width / 2 - radius), sy * (height / 2 - radius)
        for k in range(4):
            a = (i + k / 3) * math.pi / 2
            contour.append(origin + (cx + radius * math.cos(a)) * u + (cy + radius * math.sin(a)) * v)
    num = len(contour)
    verts = contour + [point - thickness * n for point in contour]
    faces = [tuple(range(num)), tuple(reversed(range(num, 2 * num)))]
    faces.extend((j, num+j, num+(j+1)%num, (j+1)%num) for j in range(num))
    return h.mesh(name, verts, faces, material, bone=bone)


def inscription(h, name, text, center, u, v, height, mat, bone='root'):
    # Bake Blender's built-in vector font to real faces; no image/font asset dependency in FBX.
    font = bpy.data.curves.new('Cabin lettering', 'FONT')
    font.body = text
    font.align_x = 'CENTER'
    font.align_y = 'CENTER'
    font.size = height
    font.resolution_u = 3
    obj = bpy.data.objects.new('Cabin glyph outlines', font)
    bpy.context.scene.collection.objects.link(obj)
    mesh = bpy.data.meshes.new_from_object(obj.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    verts = [Vector(center) + Vector(u)*vtx.co.x + Vector(v)*vtx.co.y for vtx in mesh.vertices]
    faces = [tuple(p.vertices) for p in mesh.polygons]
    bpy.data.objects.remove(obj, do_unlink=True)
    bpy.data.meshes.remove(mesh)
    bpy.data.curves.remove(font)
    if verts:
        return h.mesh(name, verts, faces, mat, bone=bone)


def ring(h, name, center, u, v, radius, section, material, bone='root', steps=48):
    o, u, v = Vector(center), Vector(u), Vector(v)
    normal = u.cross(v).normalized()
    verts, faces = [], []
    for i in range(steps):
        a = 2 * math.pi * i / steps
        radial = math.cos(a)*u + math.sin(a)*v
        for j in range(8):
            b = 2 * math.pi * j / 8
            verts.append(o + radial*(radius+section*math.cos(b)) + normal*(section*math.sin(b)))
            k = i*8+j
            j2 = i*8+(j+1)%8
            faces.append((k, (k+8)%(8*steps), (j2+8)%(8*steps), j2))
    return h.mesh(name, verts, faces, material, bone=bone)


def dial(h, name, position, maximum, unit, bone, warning_from):
    n = Vector((-.94, 0, .342)).normalized()
    u, v, o = UV_RIGHT, n.cross(UV_RIGHT), Vector(position)
    r = .103
    h.cyl(name+'Bowl', o-.025*n, o-.005*n, r+.008, 'CabSilver', sides=48)
    h.cyl(name+'Face', o-.006*n, o-.002*n, r, 'CabBlack', sides=48)
    # Place all narrow gauge marks in two meshes for clear FBX silhouettes at close range.
    for warning in (False, True):
        verts, faces = [], []
        for j in range(31):
            if (j>=warning_from) != warning:
                continue
            a = math.radians(225-270*j/30)
            d = math.cos(a)*u + math.sin(a)*v
            t = -math.sin(a)*u + math.cos(a)*v
            long = j%5 == 0
            k = len(verts)
            near, far = (.077 if long else .085), .095
            width = .0022 if long else .00095
            verts += [o+d*length+t*offset for length,offset in ((near,-width),(far,-width),(far,width),(near,width))]
            faces.append(tuple(range(k,k+4)))
        if faces:
            h.mesh(name+('Redline' if warning else 'Scale'), verts, faces, 'CabRed' if warning else 'CabWhite')
    for j in range(7):
        a = math.radians(225-45*j)
        inscription(h, name+'Digit%02d'%j, format(maximum*j/6, 'g'), o+.064*(math.cos(a)*u+math.sin(a)*v),
                    u,v,.022, 'CabWhite')
    inscription(h, name+'Units', unit, o-.026*v, u,v,.018,'CabWhite')
    a = math.radians(225)
    d = math.cos(a)*u + math.sin(a)*v
    t = -math.sin(a)*u + math.cos(a)*v
    tip=o+.089*d+.002*n
    h.mesh(name+'Needle', [o-.013*d-.004*t+.002*n,tip,o-.013*d+.004*t+.002*n],
           [(0,1,2)],'CabAmber',bone=bone)
    h.cyl(name+'Pin',o,o+.005*n,.009,'CabShell',bone=bone,sides=16)


def cockpit(h):
    box, cyl = h.box, h.cyl
    # Stepped driver platform, ribbed heel mat and workstation.
    box('DriverPedestalPlatform',(3.4125,-.662,.499),(1.365,.89,.274),'CabFloor',.043)
    box('DriverMat',(3.45,-.66,.646),(.99,.74,.024),'CabBlack',.015)
    for j in range(6):
        box('HeelMatRib%02d'%j,(3.58+j*.056,-.68,.662),(.008,.51,.008),'CabShell',.002)
    box('FrontApronInner',(4.16,0,.89),(.27,2.18,.81),'CabStone',.07)
    box('CockpitMoulding',(3.99,-.64,1.243),(.44,.96,.31),'CabGraphite',.066)
    n = Vector((-.94,0,.342)).normalized()
    v = n.cross(UV_RIGHT)
    panel(h,'InstrumentBinnacle',(3.893,-.66,1.514),UV_RIGHT,v,.641,.272,.13,.058,'CabBlack')
    for center,maximum,unit,bone,threshold,title in (
        (SPEED,120,'km/h','needle_speed',31,'RoadSpeed'),
        (RPM,3,'x1000 rpm','needle_rpm',25,'EngineSpeed')):
        dial(h,title,center,maximum,unit,bone,threshold)
    for j, mat in enumerate(('CabGreen','CabAmber','CabRed')):
        panel(h,'PilotLamp%02d'%j,Vector((3.867,-.66,1.56)) - j*.023*v, UV_RIGHT,v,.034,.010,.002,.003,mat)
    # Inset face vents and defroster slots across the dashboard top.
    for j,y in enumerate((-.993,-.322)):
        p=Vector((3.786,y,1.317))
        panel(h,'VentRim%d'%j,p,UV_RIGHT,v,.105,.056,.015,.013,'CabSilver')
        panel(h,'VentOpening%d'%j,p+.002*n,UV_RIGHT,v,.093,.046,.004,.009,'CabBlack')
        for k in range(3):
            panel(h,'VentLouvre%d_%d'%(j,k),p+n*.005+v*(k-1)*.012,UV_RIGHT,v,.080,.005,.004,.002,'CabShell')
    for j in range(6):
        box('DefrostOutlet%d'%j,(4.112,-.99+.14*j,1.399),(.036,.100,.004),'CabBlack',.001)
    p=Vector((3.876,-.656,1.457))
    panel(h,'ClusterLCD',p,UV_RIGHT,v,.083,.033,.005,.004,'CabScreen')
    inscription(h,'ClusterLCDLegend','ODO km',p+n*.001,UV_RIGHT,v,.017,'CabWhite')
    # Bulged steering hub with three tapered spokes in the sloping wheel plane.
    spin = Vector((-.54,0,.842)).normalized()
    rise = spin.cross(UV_RIGHT)
    o = Vector(STEERING)
    cyl('SteeringColumn',o-.34*spin,o-.035*spin,.049,'CabBlack')
    ring(h,'SteeringGrip',o,UV_RIGHT,rise,.233,.020,'CabWheelGrip','steering',64)
    for j,angle in enumerate((12,168,270)):
        a=math.radians(angle)
        d=math.cos(a)*UV_RIGHT+math.sin(a)*rise
        t=-math.sin(a)*UV_RIGHT+math.cos(a)*rise
        p=[o+.034*d-.044*t, o+.225*d-.016*t, o+.225*d+.016*t, o+.034*d+.044*t]
        verts=p+[q-.017*spin for q in p]
        h.mesh('SteeringSpoke%02d'%j,verts,[(0,1,2,3),(7,6,5,4),(0,4,5,1),(1,5,6,2),(2,6,7,3),(3,7,4,0)],'CabWheelGrip',bone='steering',bevel=.003)
    panel(h,'SteeringHornPad',o+.011*spin,UV_RIGHT,rise,.189,.119,.032,.043,'CabGraphite','steering')
    h.tube('IndicatorStalk',[o-.075*spin+.06*UV_RIGHT,o-.072*spin+.20*UV_RIGHT,o-.055*spin+.24*UV_RIGHT],.011,'CabBlack')
    for name, x, y, size in [('Brake',3.79,-.675,(.066,.116,.022)),('Throttle',3.80,-.86,(.124,.054,.022))]:
        foot=(x,y,.754)
        h.bone('pedal_'+name.lower(),foot)
        cyl(name+'PedalArm',(x+.095,y,.68),foot,.012,'CabSilver',bone='pedal_'+name.lower())
        box(name+'PedalRubber',foot,size,'CabBlack',bevel=.009,bone='pedal_'+name.lower(),rot=(0,-.36,0))
        for j in range(3):
            box(name+'PedalRib%02d'%j,(x+(j-1)*.019,y,.767+.007*(j-1)),(.005,size[1]*.8,.004),'CabShell',.001,bone='pedal_'+name.lower(),rot=(0,-.36,0))
    # Control console follows the same shallow rising plane as the physical switches.
    panel_n=Vector((-.35,0,.937)).normalized()
    panel_up=panel_n.cross(UV_RIGHT)
    panel(h,'SwitchConsole',(3.76,-.152,1.338),UV_RIGHT,panel_up,.367,.483,.14,.029,'CabGraphite')
    for bone, center, label, material in SWITCHES:
        h.bone(bone,center)
        p=Vector(center)
        panel(h,bone+'Surround',p-.006*panel_n,UV_RIGHT,panel_up,.068,.065,.013,.009,'CabBlack')
        panel(h,bone+'Rocker',p,UV_RIGHT,panel_up,.049,.045,.009,.006,material,bone)
        inscription(h,bone+'Legend',label,p+.0015*panel_n, UV_RIGHT,panel_up,.030,'CabBlack',bone)
    p=Vector(SELECTOR)
    panel(h,'SelectorGate',p,UV_RIGHT,panel_up,.105,.138,.015,.015,'CabBlack')
    for j,label in enumerate('RND'):
        inscription(h,'AT_'+label,label, p+(-.041+j*.041)*panel_up+.033*UV_RIGHT+.002*panel_n,
                    UV_RIGHT,panel_up,.020,'CabWhite')
    cyl('SelectorStem',p,p+.065*panel_n,.011,'CabSilver',bone='selector')
    panel(h,'SelectorKnob',p+.075*panel_n,UV_RIGHT,panel_up,.045,.052,.022,.017,'CabWheelGrip','selector')
    # Raised driver chair with a visible pneumatic pedestal, rake and two armrests.
    box('DriverSeatRail',(3.07,-.66,.70),(.51,.48,.10),'CabBlack',.025)
    for j in range(4):
        box('DriverAirBellows%d'%j,(3.07,-.66,.762+j*.027),(.36,.32,.025),'CabGraphite',.009)
    box('DriverCushion',(3.09,-.66,.939),(.49,.50,.16),'CabOcean',.059)
    box('DriverBackrest',(2.871,-.66,1.235),(.16,.52,.61),'CabOcean',.072,rot=(0,-.11,0))
    box('DriverBackInsert',(2.938,-.66,1.232),(.066,.372,.48),'CabBlue',.03,rot=(0,-.11,0))
    box('DriverHeadrest',(2.832,-.66,1.575),(.15,.313,.135),'CabGraphite',.05)
    for j,offset in enumerate((-.281,.281)):
        cyl('ArmrestBracket%d'%j,(2.92,-.66+offset,1.02),(2.92,-.66+offset,1.20),.014,'CabSilver')
        box('DriverArmrest%d'%j,(3.015,-.66+offset,1.207),(.232,.053,.048),'CabBlack',.016)
    # Farebox: passenger slot, return tray and independent IC reader.
    box('FareboxBase',(3.23,.105,.595),(.39,.30,.43),'CabShell',.04)
    box('FareboxCabinet',(3.24,.105,.925),(.44,.36,.55),'CabStone',.048)
    box('FareboxBlueCap',(3.25,.105,1.197),(.445,.364,.070),'CabBlue',.02)
    box('CoinHopperFrame',(3.225,.154,1.245),(.207,.156,.034),'CabSilver',.011)
    box('CoinHopper',(3.225,.154,1.261),(.169,.121,.010),'CabBlack',.004)
    box('NoteSlotLip',(3.017,.094,1.078),(.022,.160,.046),'CabGraphite',.007)
    box('FareReturnTray',(3.008,.094,.877),(.108,.205,.063),'CabGraphite',.016)
    reader_n=Vector((-.28,.63,.725)).normalized()
    reader_u=Vector((.91,.4,0)).normalized()
    reader_v=reader_n.cross(reader_u).normalized()
    q=Vector((3.33,.205,1.307))
    panel(h,'CardReaderHousing',q,reader_u,reader_v,.146,.174,.056,.019,'CabBlack')
    panel(h,'CardReaderGlass',q+.002*reader_n,reader_u,reader_v,.119,.126,.004,.010,'CabScreen')
    inscription(h,'ReaderLegend','IC',q+.006*reader_n,reader_u,reader_v,.057,'CabWhite')


def passenger_seat(h, tag, station, lateral, floor, yaw=0):
    """Bent shell, contoured seat pad, contrasting fabric inlay and tubular handle."""
    c, s = math.cos(yaw), math.sin(yaw)

    def p(x, y, z):
        return Vector((station+x*c-y*s, lateral+x*s+y*c, floor+z))

    def loft(suffix, rings, mat, bevel):
        verts=[p(*pt) for ring_pts in rings for pt in ring_pts]
        n=len(rings[0])
        faces=[tuple(reversed(range(n)))]
        for j in range(len(rings)-1):
            for i in range(n):
                k=j*n+i
                faces.append((k,j*n+(i+1)%n,(j+1)*n+(i+1)%n,k+n))
        faces.append(tuple(range(len(verts)-n,len(verts))))
        return h.mesh(tag+suffix,verts,faces,mat,bevel=bevel)

    def back(suffix, levels, mat):
        rings=[]
        for z,x,w,d in levels:
            rings.append([(x-d,-w+.024,z),(x-d+.012,-w,z),(x+d-.010,-w,z),(x+d,-w+.024,z),
                          (x+d,w-.024,z),(x+d-.010,w,z),(x-d+.012,w,z),(x-d,w-.024,z)])
        loft(suffix,rings,mat,.010)

    def pad(suffix, layers, mat):
        rings=[]
        for z, xrear, xf, w in layers:
            rings.append([(xrear,-w+.038,z),(xrear+.042,-w,z),(xf-.048,-w,z),(xf,-w+.035,z),
                          (xf,w-.035,z),(xf-.048,w,z),(xrear+.042,w,z),(xrear,w-.038,z)])
        loft(suffix,rings,mat,.008)

    pad('SeatShell',[(.359,-.197,.185,.187),(.404,-.213,.201,.206)],'CabShell')
    pad('Cushion',[(.396,-.192,.192,.194),(.458,-.182,.190,.201),(.472,-.172,.158,.183)],'CabOcean')
    back('BackShell',[(.392,-.190,.196,.032),(.665,-.213,.205,.037),(.935,-.248,.176,.033),(.962,-.253,.132,.023)],'CabShell')
    back('BackPad',[(.437,-.157,.170,.025),(.636,-.165,.182,.039),(.854,-.206,.159,.040),(.907,-.213,.137,.030)],'CabOcean')

    # V-shaped woven flashes on the upholstered face; color accents survive FBX without textures.
    verts, faces=[],[]
    for k in range(5):
        z=.555+.052*k
        x=-.119-.170*(z-.555)
        for direction in (-1,1):
            j=len(verts)
            verts.extend([p(x-.005, direction*.013,z),p(x-.013,direction*.138,z+.045),
                          p(x-.015,direction*.138,z+.057),p(x-.006,direction*.013,z+.012)])
            faces.append((j,j+1,j+2,j+3) if direction>0 else (j+3,j+2,j+1,j))
    h.mesh(tag+'Weave',verts,faces,'CabWeave')
    h.tube(tag+'TopHandle',[p(-.255,-.110,.941),p(-.259,-.118,1.003),p(-.263,-.093,1.028),
                             p(-.263,.093,1.028),p(-.259,.118,1.003),p(-.255,.110,.941)],.014,'CabOrange')
    h.cyl(tag+'Leg',p(-.020,0,.04),p(-.020,0,.37),.043,'CabSilver',sides=12)
    h.box(tag+'Foot',p(-.020,0,.022),(.21,.11,.04),'CabBlack',.009,rot=(0,0,yaw))


def passenger_deck(h):
    box, cyl, tube = h.box, h.cyl, h.tube
    # Make the rear deck climb in two risers. Keep the centre-door vestibule level.
    for tag, x0,x1,zt in [('Lower',-1.67,-1.32,.512),('Rear',-4.435,-1.67,.672)]:
        # The rear deck stops at the inboard wheel wells for the length of the axle.
        spans = [(x0,x1,2.17)] if tag=='Lower' else [(x0,-2.73,2.17),(-2.73,x1,1.50)]
        for k,(xa,xb,width) in enumerate(spans):
            box('RearFloor'+tag+str(k),((xa+xb)/2,0,(.362+zt)/2),(xb-xa,width,zt-.362),'CabFloor',.012)
        box('StepNosing'+tag,(x1-.017,0,zt+.005),(.035,2.13,.012),'CabYellow',.003)
    for axle,label in [(2.20,'Front'),(-2.20,'Rear')]:
        for sign,side in [(-1,'Right'),(1,'Left')]:
            # D-shaped wheel housing on the inside wall, with sufficient tyre clearance.
            center_y=sign*.926
            pts=[(axle-.520,.356),(axle+.520,.356),(axle+.520,.425)]
            pts += [(axle+.520*math.cos(i*math.pi/18),.425+.51*math.sin(i*math.pi/18))
                    for i in range(1,19)]
            verts=[(x,center_y+offset,z) for offset in (-.170,.170) for x,z in pts]
            n=len(pts)
            # A closed outboard end would place a solid disc in front of the tyre.
            faces=[tuple(range(n))] if sign>0 else [tuple(reversed(range(n,n*2)))]
            faces += [(j,n+j,n+(j+1)%n,(j+1)%n) for j in range(1,n)]
            h.mesh(label+side+'ArchCover',verts,faces,'CabShell',bevel=.008)
    for tag, station, w in [('Front',3.48,.86),('Middle',-.68,1.14)]:
        box(tag+'Threshold',(station,1.022,.366),(w-.04,.178,.018),'CabSilver',.006)
        box(tag+'ThresholdEdge',(station,.938,.38),(w-.035,.027,.012),'CabYellow',.004)
        for j in range(3):
            box(tag+'ThresholdGroove%d'%j,(station,.979+.032*j,.378),(w-.057,.008,.006),'CabBlack',.002)
    # Raised rear engine bench and rectangular aisle for boarding.
    box('RearBenchPlinth',(-4.14,0,.84),(.59,2.10,.335),'CabShell',.038)
    for j,y in enumerate((-.82,-.407,0,.407,.82)):
        passenger_seat(h,'Bench%02d'%j,-4.12,y,.925)
    for i,station in enumerate((-3.33,-2.585)):
        for j,y in enumerate((-.864,-.432,.432,.864)):
            passenger_seat(h,'Rear%02d%02d'%(i,j),station,y,.672)
    # Wheel housings keep the aisle clear, with staggered low-floor seating forward.
    for i,station in enumerate((-1.0,-.29,.43,1.15)):
        passenger_seat(h,'LowRight%02d'%i,station,-.831,.364)
    for i,station in enumerate((.26,1.02)):
        passenger_seat(h,'LowLeft%02d'%i,station,.837,.364)
    box('DriverScreenBase',(2.734,-.697,1.005),(.070,.774,.65),'CabStone',.024)
    tube('DriverScreenRail',[(2.734,-1.06,1.319),(2.734,-1.06,1.70),(2.734,-1.03,1.727),
                              (2.734,-.35,1.727),(2.734,-.314,1.692),(2.734,-.314,1.319)],.018,'CabSilver')

    # Stanchions form one unobstructed central lane; split rails at the two doorways.
    for j,(station,lateral,bottom) in enumerate(((2.79,.67,.36),(1.60,-.38,.36),
                  (.96,.44,.36),(-1.30,.56,.36),(-.098,.64,.36),(-1.13,-.43,.36),
                  (-2.94,.315,.67),(-2.94,-.315,.67))):
        a=(station,lateral,bottom+.018)
        b=(station,lateral,2.642)
        cyl('Upright%02d'%j,a,b,.018,'CabOrange',sides=14)
        cyl('UprightBoot%02d'%j,a,(station,lateral,bottom+.085),.031,'CabGraphite',sides=16)
        cyl('RailCollar%02d'%j,(station,lateral,2.48),(station,lateral,2.52),.024,'CabSilver',sides=14)
    for sign,tag in [(1,'Left'),(-1,'Right')]:
        tube(tag+'OverheadRail',[(-3.87,sign*.36,2.67),(-3.84,sign*.36,2.57),
                                 (-3.78,sign*.36,2.53),(2.68,sign*.36,2.53),
                                 (2.74,sign*.36,2.57),(2.77,sign*.36,2.67)],.023,'CabSilver')
        for j in range(9):
            x=-3.50+j*.713
            if sign==-1 and x>1.7:
                continue
            # Strap descends to a moulded rounded triangular handhold.
            cyl(tag+'StrapBar%d'%j,(x-.026,sign*.36,2.545),(x+.026,sign*.36,2.545),.026,'CabBlack',sides=12)
            box(tag+'Strap%d'%j,(x,sign*.36,2.428),(.034,.011,.19),'CabGraphite',.004)
            pts=[(x-.023,sign*.36,2.334),(x-.079,sign*.36,2.220),(x-.068,sign*.36,2.201),
                 (x+.068,sign*.36,2.201),(x+.079,sign*.36,2.220),(x+.023,sign*.36,2.334),
                 (x-.023,sign*.36,2.334)]
            tube(tag+'HangingGrip%d'%j,pts,.012,'CabLight')
    for j,x in enumerate((-3.33,-1.87,-.41,1.05,2.51)):
        for sign,tag in [(-1,'Right'),(1,'Left')]:
            box(tag+'CeilingLightCase%d'%j,(x,sign*.545,2.748),(1.05,.106,.034),'CabSilver',.012)
            box(tag+'CeilingDiffuser%d'%j,(x,sign*.545,2.731),(1.003,.084,.015),'CabWhite',.005)
    # Stainless grab rings guard the stair edge beside the middle door.
    tube('MiddleVestibuleRail',[(-1.32,.95,.55),(-1.32,.95,1.38),(-1.32,.91,1.43),
                                 (-1.32,.56,1.43)],.022,'CabOrange')
    tube('FrontVestibuleRail',[(3.991,.96,.43),(3.991,.96,1.13),(3.96,.95,1.19),
                                (3.76,.87,1.30)],.021,'CabOrange')


def build(h):
    materials(h)
    passenger_deck(h)
    cockpit(h)
