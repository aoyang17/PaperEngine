from pathlib import Path
import math

root = Path('tmp/runs/comsol/laghmach2015/segsmoke/segsmoke')
src = root / 'segsmoke_radius_and_quality.csv'
rows = []
for line in src.read_text().splitlines():
    if not line or line.startswith('%'):
        continue
    vals = [float(x) for x in line.split(',')]
    rows.append(vals)
t = [r[0] for r in rows]
radius = [r[1] for r in rows]
detf = [r[3] for r in rows]
theta_max = [r[4] for r in rows]
theta_min = [r[5] for r in rows]

out = root / 'figures'
out.mkdir(exist_ok=True)
def draw(name, title, arrays, log=False):
    vals=[v for a in arrays for v in a]; lo=max(min(vals),1e-20) if log else min(vals); hi=max(vals)
    def x(i): return 70+620*i/max(1,len(t)-1)
    def y(v):
        a=math.log10(v) if log else v; l=math.log10(lo) if log else lo; h=math.log10(hi) if log else hi
        return 365-320*(a-l)/max(1e-30,h-l)
    s=f'<svg xmlns="http://www.w3.org/2000/svg" width="720" height="420"><rect width="100%" height="100%" fill="white"/><text x="360" y="25" text-anchor="middle" font-size="18">{title}</text><line x1="70" y1="365" x2="690" y2="365" stroke="black"/><line x1="70" y1="45" x2="70" y2="365" stroke="black"/>'
    for k,a in enumerate(arrays): s+=f'<polyline points="{" ".join(f"{x(i):.1f},{y(v):.1f}" for i,v in enumerate(a))}" fill="none" stroke="{("#1464a0", "#b33b3b")[k]}" stroke-width="3"/>'
    (out/name).write_text(s+'</svg>')
draw('radius_vs_time.svg','Radius vs time',[radius])
draw('phase_bounds.svg','Phase-field bounds',[theta_min,theta_max])
draw('detF_residual.svg','Incompressibility residual',[detf],True)
print('generated 3 SVG figures in', out)
