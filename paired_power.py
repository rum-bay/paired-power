"""Pure-Python paired t-test power engine."""
from __future__ import annotations
import math
from typing import Callable

class NoSolutionError(Exception):
    """The requested numerical result cannot be bracketed in supported bounds."""

_SQRT2 = math.sqrt(2.0)
_LOG_SQRT2PI = 0.5 * math.log(2.0 * math.pi)

def _normal_cdf(x: float) -> float:
    return 0.5 * math.erfc(-x / _SQRT2)

def _log1pmx(x: float) -> float:
    if abs(x) < 1e-4:
        term = x*x
        total = -0.5*term
        for n in range(3, 15):
            term *= x
            total += (1.0 if n % 2 else -1.0) * term/n
        return total
    return math.log1p(x)-x

def _betacf(a: float, b: float, x: float) -> float:
    qab, qap, qam = a+b, a+1.0, a-1.0
    c = 1.0
    d = 1.0-qab*x/qap
    tiny=1e-300
    if abs(d)<tiny: d=tiny
    d=1.0/d
    h=d
    for m in range(1,301):
        m2=2*m
        aa=m*(b-m)*x/((qam+m2)*(a+m2))
        d=1.0+aa*d
        if abs(d)<tiny: d=tiny
        c=1.0+aa/c
        if abs(c)<tiny: c=tiny
        d=1.0/d
        h*=d*c
        aa=-(a+m)*(qab+m)*x/((a+m2)*(qap+m2))
        d=1.0+aa*d
        if abs(d)<tiny: d=tiny
        c=1.0+aa/c
        if abs(c)<tiny: c=tiny
        d=1.0/d
        change=d*c
        h*=change
        if abs(change-1.0)<=3e-14: return h
    return h

def _ibeta(x: float, a: float, b: float) -> float:
    if x<=0: return 0.0
    if x>=1: return 1.0
    logbt=math.lgamma(a+b)-math.lgamma(a)-math.lgamma(b)+a*math.log(x)+b*math.log1p(-x)
    bt=math.exp(logbt) if logbt>-745 else 0.0
    if x<(a+1)/(a+b+2):
        value=bt*_betacf(a,b,x)/a
    else:
        value=1-bt*_betacf(b,a,1-x)/b
    return min(1.0,max(0.0,value))

def central_t_cdf(t: float, df: int|float) -> float:
    nu=float(df)
    if not nu>0 or not math.isfinite(nu): raise ValueError("df must be finite and positive")
    if t==0: return 0.5
    if nu>1_000_000:
        phi=math.exp(-0.5*t*t)/math.sqrt(2*math.pi)
        return min(1.0,max(0.0,_normal_cdf(t)-(t**3+t)*phi/(4*nu)))
    area=0.5*_ibeta(t*t/(nu+t*t),0.5,nu/2)
    return 0.5+area if t>0 else 0.5-area

def _normal_quantile(p: float) -> float:
    if p<0.5: return -_normal_quantile(1-p)
    lo,hi=0.0,10.0
    for _ in range(90):
        m=(lo+hi)/2
        if _normal_cdf(m)<p: lo=m
        else: hi=m
    return (lo+hi)/2

def central_t_quantile(p: float, df: int|float) -> float:
    nu=float(df)
    if not nu>0 or not math.isfinite(nu): raise ValueError("df must be finite and positive")
    if not 0<p<1: raise ValueError("p must be between zero and one")
    if p==0.5: return 0.0
    if p<0.5: return -central_t_quantile(1-p,nu)
    if nu>1_000_000:
        z=_normal_quantile(p)
        return z+(z**3+z)/(4*nu)+(5*z**5+16*z**3+3*z)/(96*nu**2)+(3*z**7+19*z**5+17*z**3-15*z)/(384*nu**3)
    lo,hi=0.0,1.0
    while central_t_cdf(hi,nu)<p:
        hi*=2
        if hi>1e12: raise NoSolutionError("Central t quantile could not be bracketed")
    for _ in range(100):
        m=(lo+hi)/2
        if central_t_cdf(m,nu)<p: lo=m
        else: hi=m
    return (lo+hi)/2

def _simpson(f: Callable[[float],float], a: float, b: float, tol: float=2e-13, depth: int=16) -> float:
    if a>=b: return 0.0
    m=(a+b)/2
    fa,fm,fb=f(a),f(m),f(b)
    whole=(b-a)*(fa+4*fm+fb)/6
    def rec(a,b,fa,fm,fb,estimate,eps,left):
        m=(a+b)/2; lm=(a+m)/2; rm=(m+b)/2
        fl,fr=f(lm),f(rm)
        l=(m-a)*(fa+4*fl+fm)/6
        r=(b-m)*(fm+4*fr+fb)/6
        diff=l+r-estimate
        if left<=0 or abs(diff)<=15*eps: return l+r+diff/15
        return rec(a,m,fa,fl,fm,l,eps/2,left-1)+rec(m,b,fm,fr,fb,r,eps/2,left-1)
    return rec(a,b,fa,fm,fb,whole,tol,depth)

def noncentral_t_cdf(t: float, df: int|float, ncp: float) -> float:
    """Compute the noncentral-t CDF by integrating its chi-square mixture."""
    nu,delta=float(df),float(ncp)
    if not nu>0 or not math.isfinite(nu): raise ValueError("df must be finite and positive")
    if not math.isfinite(delta): raise ValueError("ncp must be finite")
    k=nu/2
    if k>=100:
        root=math.sqrt(k)
        lo=max(-13.0,-root+1e-12)
        inv=1/k
        c=-_LOG_SQRT2PI-inv/12+inv**3/360-inv**5/1260+inv**7/1680-inv**9/1188
        def f(z):
            r=z/root
            if r<=-1: return 0.0
            logdens=c+k*_log1pmx(r)-math.log1p(r)
            dens=math.exp(logdens) if logdens>-745 else 0.0
            return _normal_cdf(t*math.sqrt(1+r)-delta)*dens
        result=_simpson(f,lo,13.0,3e-13,18)
    else:
        lk=math.log(k)
        lo=lk-max(12.0,40/math.sqrt(k),80/k)
        hi=math.log(k+16*math.sqrt(k)+50)
        lg=math.lgamma(k)
        def f(y):
            x=math.exp(y)
            logdens=k*y-x-lg
            dens=math.exp(logdens) if logdens>-745 else 0.0
            scale=math.exp((y-lk)/2)
            return _normal_cdf(t*scale-delta)*dens
        parts=max(1,math.ceil((hi-lo)/0.75))
        step=(hi-lo)/parts
        result=math.fsum(_simpson(f,lo+i*step,hi if i+1==parts else lo+(i+1)*step,2e-13,14) for i in range(parts))
    return min(1.0,max(0.0,result))

def _critical(alpha: float, df: int, tails: int) -> float:
    return central_t_quantile(1-alpha if tails==1 else 1-alpha/2,df)

def _power(tails: int, crit: float, df: int, ncp: float) -> float:
    if tails==1: return min(1.0,max(0.0,1-noncentral_t_cdf(crit,df,ncp)))
    return min(1.0,max(0.0,noncentral_t_cdf(-crit,df,ncp)+1-noncentral_t_cdf(crit,df,ncp)))

def calculate(mode: str, v: dict[str,int|float]) -> dict[str,int|float]:
    """Calculate one mode from validated inputs."""
    tails=int(v["tails"])
    if mode=="a-priori":
        dz,alpha,target=float(v["dz"]),float(v["alpha"]),float(v["power"])
        def achieved(n):
            df=n-1; c=_critical(alpha,df,tails)
            return _power(tails,c,df,dz*math.sqrt(n))
        if achieved(2)>=target: n=2
        else:
            low,high=2,4
            while achieved(high)<target:
                low,high=high,high*2
                if high>2**63-1: raise NoSolutionError("Required sample size exceeds supported integer range")
            while low+1<high:
                mid=(low+high)//2
                if achieved(mid)>=target: high=mid
                else: low=mid
            n=high
        df=n-1; ncp=dz*math.sqrt(n); c=_critical(alpha,df,tails)
        return {"ncp":ncp,"critical_t":c,"df":df,"n_total":n,"actual_power":_power(tails,c,df,ncp)}
    n=int(v["n_total"]); df=n-1
    if mode=="post-hoc":
        ncp=float(v["dz"])*math.sqrt(n); c=_critical(float(v["alpha"]),df,tails)
        return {"ncp":ncp,"critical_t":c,"df":df,"power":_power(tails,c,df,ncp)}
    if mode=="compromise":
        ncp=float(v["dz"])*math.sqrt(n); ratio=float(v["beta_alpha_ratio"])
        lo,hi=1e-7,0.9999999
        def balance(a):
            c=_critical(a,df,tails)
            return 1-_power(tails,c,df,ncp)-ratio*a
        if balance(lo)<0 or balance(hi)>0: raise NoSolutionError("No compromise alpha is available")
        for _ in range(90):
            m=(lo+hi)/2
            if balance(m)>0: lo=m
            else: hi=m
        alpha=(lo+hi)/2; c=_critical(alpha,df,tails); power=_power(tails,c,df,ncp)
        return {"ncp":ncp,"critical_t":c,"df":df,"alpha":alpha,"beta":1-power,"power":power}
    if mode=="criterion":
        ncp=float(v["dz"])*math.sqrt(n); target=float(v["power"])
        if tails==1:
            wanted=1-target; lo,hi=-1.0,1.0
            while noncentral_t_cdf(lo,df,ncp)>wanted:
                lo*=2
                if lo < -1e12: raise NoSolutionError("Could not bracket criterion boundary")
            while noncentral_t_cdf(hi,df,ncp)<wanted:
                hi*=2
                if hi > 1e12: raise NoSolutionError("Could not bracket criterion boundary")
            for _ in range(90):
                m=(lo+hi)/2
                if noncentral_t_cdf(m,df,ncp)<wanted: lo=m
                else: hi=m
            c=(lo+hi)/2; alpha=1-central_t_cdf(c,df)
        else:
            lo,hi=0.0,1.0
            while _power(2,hi,df,ncp)>target:
                hi*=2
                if hi>1e12: raise NoSolutionError("Could not bracket criterion boundary")
            for _ in range(90):
                m=(lo+hi)/2
                if _power(2,m,df,ncp)>target: lo=m
                else: hi=m
            c=(lo+hi)/2; alpha=2*(1-central_t_cdf(c,df))
        return {"ncp":ncp,"critical_t":c,"df":df,"alpha":alpha}
    if mode=="sensitivity":
        alpha,target=float(v["alpha"]),float(v["power"]); c=_critical(alpha,df,tails)
        baseline=_power(tails,c,df,0.0)
        if target<baseline-1e-12: raise NoSolutionError("Requested power is below zero-effect power")
        lo,hi=0.0,20.0
        if target<=baseline: dz=0.0
        elif _power(tails,c,df,hi*math.sqrt(n))<target: raise NoSolutionError("Required effect size exceeds supported range")
        else:
            for _ in range(90):
                mid=(lo+hi)/2
                if _power(tails,c,df,mid*math.sqrt(n))<target: lo=mid
                else: hi=mid
            dz=(lo+hi)/2
        return {"ncp":dz*math.sqrt(n),"critical_t":c,"df":df,"dz":dz}
    raise ValueError(f"Unsupported mode: {mode}")


