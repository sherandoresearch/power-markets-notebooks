"""Existing Volume I section 5.1 scenario, extracted without new assumptions."""
from pathlib import Path
import numpy as np
from scipy.optimize import linprog
import yaml

ROOT=Path(__file__).resolve().parents[2]


def operators():
    model=yaml.safe_load((ROOT/'data/processed/triangle/manifest.yaml').read_text())
    a=np.zeros((3,3)); weights=[]
    for k,(i,j,x) in enumerate(model['reactances']):
        a[k,i-1]=1; a[k,j-1]=-1; weights.append(1/x)
    w=np.diag(weights); lap=a.T@w@a
    return a,w,w@a@np.linalg.pinv(lap)


def flow(injection):
    injection=np.asarray(injection,float)
    if injection.shape!=(3,) or not np.isfinite(injection).all() or abs(injection.sum())>1e-9:
        raise ValueError('Three finite balanced injections required')
    return operators()[2]@injection


def dispatch(demand=None):
    # Existing base case: demand at bus 3 = 300 MW, offers $10 and $30,
    # only line 1-3 limited, to 150 MW; see vol-i/chapters/05-s5.html.
    d=np.array([0.,0.,300.]) if demand is None else np.asarray(demand,float)
    if d.shape!=(3,) or not np.isfinite(d).all() or (d<0).any(): raise ValueError('Invalid demand')
    psi=operators()[2]; h=psi[1]; g=np.eye(3)[:,:2]
    pm=h@g
    result=linprog([10.,30.],A_ub=[pm,-pm],b_ub=[150+h@d,150-h@d],
        A_eq=[[1.,1.]],b_eq=[d.sum()],bounds=[(0,None),(0,None)],method='highs')
    if not result.success: raise RuntimeError(result.message)
    dual=-result.ineqlin.marginals
    signed=dual[0]-dual[1]
    price=result.eqlin.marginals[0]-h*signed
    return {'generation_mw':result.x,'flow_mw':flow(g@result.x-d),
            'lmp_usd_mwh':price,'directional_duals':dual,'signed_dual':signed,
            'cost_usd_hour':result.fun,'demand_mw':d}
