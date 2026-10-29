"""Geometry-only subject continuity. No identity recognition or speaker inference."""
import math


def iou(a, b):
    x=max(a[0],b[0]); y=max(a[1],b[1])
    intersection=max(0,min(a[0]+a[2],b[0]+b[2])-x)*max(0,min(a[1]+a[3],b[1]+b[3])-y)
    return intersection/max(1e-9,a[2]*a[3]+b[2]*b[3]-intersection)


def deduplicate(boxes):
    kept=[]
    for box in sorted(boxes,key=lambda b:b[2]*b[3],reverse=True):
        if all(iou(box,other)<.35 for other in kept):kept.append(box)
    return kept


class SubjectTracker:
    def __init__(self, fallback=.5):
        self.fallback=max(0,min(1,fallback))
        self.focus=self.fallback
        self.box=None
        self.seen=None
        self.time=None

    def update(self, boxes, time, cut=False):
        boxes=deduplicate([b for b in boxes if all(math.isfinite(v) for v in b) and b[2]>0 and b[3]>0])
        dt=max(.001,time-self.time) if self.time is not None else .25
        self.time=time
        if cut:self.box=None;self.seen=None
        chosen=None
        if self.box is not None:
            old=self.box;cx=old[0]+old[2]/2;cy=old[1]+old[3]/2
            nearby=[]
            for b in boxes:
                distance=math.hypot(b[0]+b[2]/2-cx,b[1]+b[3]/2-cy)
                ratio=b[2]*b[3]/(old[2]*old[3])
                if .35<ratio<2.8 and (iou(old,b)>.08 or distance<.16):
                    nearby.append((iou(old,b)-distance,b))
            if nearby:chosen=max(nearby,key=lambda pair:pair[0])[1]
        # Hold a missing subject briefly instead of jumping to another person.
        if chosen is None and (self.box is None or time-self.seen>=1.5):
            if boxes:
                chosen=max(boxes,key=lambda b:b[2]*b[3]/(1+2*abs(b[0]+b[2]/2-self.focus)))
        if chosen is not None:
            target=max(0,min(1,chosen[0]+chosen[2]/2))
            if self.seen is None or cut:
                self.focus=target
            elif abs(target-self.focus)>.008:
                delta=(target-self.focus)*(1-math.exp(-dt/.22))
                self.focus+=max(-.8*dt,min(.8*dt,delta))
            self.box=chosen;self.seen=time
        elif self.seen is not None and time-self.seen>3:
            self.focus+=(self.fallback-self.focus)*(1-math.exp(-dt/1.5))
            self.box=None
        elif cut:
            self.focus=self.fallback
        return round(max(0,min(1,self.focus)),5)


def simplify(points, tolerance=.004, limit=256):
    """Bound FFmpeg expression complexity while retaining significant motion."""
    if len(points)<=2:return points
    def reduce(epsilon):
        keep={0,len(points)-1};stack=[(0,len(points)-1)]
        while stack:
            a,b=stack.pop();ta,xa=points[a];tb,xb=points[b]
            if b-a<2:continue
            error,index=max((abs(x-(xa+(xb-xa)*(t-ta)/max(1e-9,tb-ta))),i) for i,(t,x) in enumerate(points[a+1:b],a+1))
            if error>epsilon:keep.add(index);stack.extend([(a,index),(index,b)])
        return [points[i] for i in sorted(keep)]
    result=reduce(tolerance)
    while len(result)>limit:
        tolerance*=1.5;result=reduce(tolerance)
    return result
