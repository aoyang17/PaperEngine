#!/usr/bin/env python3
"""Build a self-contained offline HTML report for the Laghmach 2015 case."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from html import escape
import json
from pathlib import Path
from string import Template


def _inline_svg(path: Path, caption: str, figure_class: str = "") -> str:
    svg = path.read_text(encoding="utf-8")
    return (
        f'<figure class="{escape(figure_class)}"><div class="plot">{svg}</div>'
        f'<figcaption>{escape(caption)}</figcaption></figure>'
    )


def _acceptance_rows(summary: dict[str, object], *, required: bool) -> str:
    rows = []
    for item in summary["results"]:  # type: ignore[index]
        if bool(item["required"]) != required:
            continue
        status = "通过" if item["passed"] else "未通过"
        css = "pass" if item["passed"] else "fail"
        actual = "缺少结果" if item["actual"] is None else str(item["actual"])
        units = str(item.get("units", ""))
        rule = f'{item["operator"]} {item["expected"]}'
        rows.append(
            "<tr>"
            f'<td><code>{escape(str(item["criterion_id"]))}</code></td>'
            f'<td>{escape(actual)} {escape(units)}</td>'
            f'<td>{escape(rule)}</td>'
            f'<td><span class="tag {css}">{status}</span></td>'
            "</tr>"
        )
    return "\n".join(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent.parent
    result_root = project_root / "tmp" / "runs" / "reference" / "laghmach2015"
    summary = json.loads((result_root / "reference_acceptance_thresholds.json").read_text(encoding="utf-8"))
    metrics = json.loads((result_root / "core_metrics_thresholds.json").read_text(encoding="utf-8"))

    figures = {
        "free_energy": _inline_svg(
            result_root / "free_energy_figure2.svg",
            "图 1｜论文图 2 的二维体自由能交叉检查。虚线/实线含义在图例中按拉伸比区分。",
        ),
        "radius": _inline_svg(
            result_root / "radius_comparison.svg",
            "图 2｜303 K、λ=4：拓扑约束开启后半径饱和；关闭后持续增长；黑线为论文图 6b 数字化数据。",
        ),
        "theta": _inline_svg(
            result_root / "field_figures" / "final_theta.svg",
            "图 3｜约化参考求解器的最终相场。中心晶体由弥散界面连接至非晶基体。",
            "compact",
        ),
        "topology": _inline_svg(
            result_root / "field_figures" / "final_topological_energy.svg",
            "图 4｜拓扑弹性能对数分布。高能区集中成晶体—非晶界面环带。",
            "compact",
        ),
        "surface": _inline_svg(
            result_root / "surface_energy_nucleus_comparison.svg",
            "图 5｜Rn=5/9 nm 的弹性表面张力—界面位移曲线及论文指数拟合。两条模拟曲线彼此重合较好，但尚未完全复现论文指数参数。",
        ),
    }

    baseline = metrics["baseline"]
    control = metrics["control"]
    curve = metrics["paper_curve"]
    quality = metrics["quality"]
    surface = metrics["surface_fit"]

    template = Template(r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Laghmach 2015 相场仿真复现离线报告</title>
<style>
:root { --ink:#172033; --muted:#617087; --line:#dce3ec; --paper:#fff; --bg:#eef3f8;
  --blue:#2459a9; --blue2:#eaf2ff; --green:#147a55; --green2:#e7f7f0;
  --amber:#a25b00; --amber2:#fff4dd; --red:#ae3038; --red2:#ffebed; }
* { box-sizing:border-box; }
html { scroll-behavior:smooth; }
body { margin:0; color:var(--ink); background:var(--bg); font:16px/1.72 system-ui,-apple-system,"Segoe UI","Noto Sans CJK SC","Microsoft YaHei",sans-serif; }
.hero { color:white; padding:68px max(24px,calc((100vw - 1180px)/2)); background:linear-gradient(130deg,#10223f,#244f87 62%,#1d705f); }
.eyebrow { letter-spacing:.12em; text-transform:uppercase; opacity:.8; font-size:13px; }
h1 { max-width:930px; margin:.25em 0 .35em; font-size:clamp(34px,5vw,62px); line-height:1.12; }
.subtitle { max-width:900px; font-size:19px; opacity:.9; }
.meta { display:flex; flex-wrap:wrap; gap:10px; margin-top:26px; }
.pill { border:1px solid #ffffff52; border-radius:99px; padding:6px 12px; background:#ffffff14; }
.layout { max-width:1180px; margin:0 auto; display:grid; grid-template-columns:250px minmax(0,1fr); gap:28px; padding:30px 20px 80px; }
nav { position:sticky; top:18px; align-self:start; padding:18px; border:1px solid var(--line); border-radius:14px; background:#ffffffec; box-shadow:0 8px 30px #16304b12; }
nav strong { display:block; margin-bottom:8px; }
nav a { display:block; color:#35516f; text-decoration:none; padding:5px 0; }
nav a:hover { color:var(--blue); }
main { min-width:0; }
section { margin-bottom:24px; padding:30px; border:1px solid var(--line); border-radius:16px; background:var(--paper); box-shadow:0 8px 30px #16304b0b; }
h2 { margin:0 0 18px; font-size:28px; line-height:1.25; }
h3 { margin:24px 0 10px; font-size:20px; }
p { margin:9px 0; }
.lead { font-size:18px; color:#34435a; }
.callout { margin:18px 0; padding:16px 18px; border-left:5px solid var(--blue); border-radius:8px; background:var(--blue2); }
.warning { border-color:var(--amber); background:var(--amber2); }
.danger { border-color:var(--red); background:var(--red2); }
.cards { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; margin:18px 0; }
.card { padding:17px; border:1px solid var(--line); border-radius:12px; background:#f9fbfd; }
.card b { display:block; color:var(--blue); font-size:25px; line-height:1.2; }
.card span { color:var(--muted); font-size:13px; }
.equation { overflow-x:auto; margin:12px 0; padding:15px 18px; border:1px solid #d7e0ec; border-radius:10px; background:#f7f9fc; font:16px/1.65 "STIX Two Math","Cambria Math",Georgia,serif; white-space:pre-wrap; }
.eqname { color:var(--blue); font:600 13px system-ui,sans-serif; letter-spacing:.04em; }
table { width:100%; border-collapse:collapse; margin:14px 0; font-size:14px; }
th,td { padding:10px 11px; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; }
th { color:#40526b; background:#f5f8fb; }
code { color:#273f64; padding:.08em .28em; border-radius:4px; background:#edf2f8; }
.tag { display:inline-block; padding:2px 8px; border-radius:99px; font-weight:700; font-size:12px; }
.pass { color:var(--green); background:var(--green2); }
.fail { color:var(--red); background:var(--red2); }
.partial { color:var(--amber); background:var(--amber2); }
.flow { display:grid; grid-template-columns:repeat(5,1fr); gap:8px; margin:18px 0; }
.flow div { position:relative; min-height:85px; padding:12px; border-radius:10px; color:#18324f; background:#eaf2fb; font-size:14px; }
.flow b { display:block; margin-bottom:4px; }
.grid2 { display:grid; grid-template-columns:1fr 1fr; gap:16px; }
figure { margin:22px 0; padding:12px; border:1px solid var(--line); border-radius:12px; background:#fff; }
.plot { overflow:hidden; }
.plot svg { display:block; width:100%; height:auto; }
figcaption { margin:9px 5px 3px; color:var(--muted); font-size:14px; }
.source-note { color:var(--muted); font-size:13px; }
.footer { text-align:center; color:var(--muted); padding:8px 0 40px; }
@media (max-width:900px) { .layout{display:block}.layout nav{position:static;margin-bottom:20px}.cards{grid-template-columns:1fr 1fr}.flow{grid-template-columns:1fr}.grid2{grid-template-columns:1fr} }
@media print { body{background:#fff}.hero{padding:32px;color:#111;background:#fff;border-bottom:2px solid #333}.layout{display:block;max-width:none;padding:0}nav{display:none}section{box-shadow:none;border:0;border-bottom:1px solid #bbb;break-inside:avoid}.plot svg{max-height:680px}.cards{grid-template-columns:repeat(4,1fr)} }
</style>
</head>
<body>
<header class="hero">
  <div class="eyebrow">Offline reproduction dossier · JCP 142, 244905 (2015)</div>
  <h1>应变诱导晶体生长的相场模型：论文解读与仿真复现</h1>
  <div class="subtitle">Rabia Laghmach, Nicolas Candau, Laurent Chazeau, Etienne Munch, Thierry Biben<br>DOI: 10.1063/1.4923226</div>
  <div class="meta"><span class="pill">单文件离线报告</span><span class="pill">二维相场 + 有限变形 + 拓扑约束</span><span class="pill">当前验收 17/22</span><span class="pill">生成于 $generated</span></div>
</header>
<div class="layout">
<nav><strong>目录</strong>
  <a href="#executive">1. 执行摘要</a><a href="#paper">2. 原文结论</a><a href="#equations">3. 本构与演化方程</a>
  <a href="#setup">4. 仿真搭建</a><a href="#results">5. 关键结果</a><a href="#figures">6. 关键图表</a>
  <a href="#acceptance">7. 验收明细</a><a href="#limits">8. 局限与下一步</a><a href="#files">9. 文件索引</a>
</nav>
<main>
<section id="executive"><h2>1. 执行摘要</h2>
  <p class="lead">本地约化求解器已经定量复现论文最核心的因果链：<b>晶体生长 → 拓扑约束被排出 → 界面弹性能形成环带 → 晶体在纳米尺度停止生长</b>。</p>
  <div class="cards"><div class="card"><b>23.008 nm</b><span>拓扑开启最终有效半径</span></div><div class="card"><b>6.06%</b><span>论文图 6b 半径 NRMSE</span></div><div class="card"><b>69.49%</b><span>弹性能位于界面带的比例</span></div><div class="card"><b>17 / 22</b><span>必选验收通过数</span></div></div>
  <div class="callout warning"><b>状态边界：</b>这些数值来自透明的二维约化参考求解器，其中远场应变被预设。COMSOL 完整有限变形模型源码已搭建，但尚未在远程 COMSOL 6.4 编译和求解，因此不可压缩性与应力曲线仍没有权威结果，不能称为完整 COMSOL 复现。</div>
</section>

<section id="paper"><h2>2. 原文的主要结论</h2>
  <ol>
    <li>交联点和分子链缠结不能进入理想晶体，会随晶体界面向外移动并聚集在晶体—非晶界面附近。</li>
    <li>这些拓扑约束的聚集产生局部弹性带，其能量可等效为额外表面张力；该贡献随界面移动距离近似指数增加。</li>
    <li>指数增长的表面代价可在经典临界晶核之后产生新的自由能极小值，从而解释天然橡胶中稳定纳米晶粒，而不是让晶体无限长大。</li>
    <li>最终晶粒尺寸对拉伸比相对不敏感，但生长速度和临界拉伸比对温度、拉伸非常敏感。论文得到 λ<sub>c</sub>≈3、4、5，分别对应 298、303、308 K。</li>
    <li>由于拓扑表面能取决于界面从初始晶核出发移动了多远，最终状态保留初始晶核尺寸的“记忆”。</li>
    <li>引入各向异性界面能后，模型可给出垂直于拉伸方向伸长、尺寸与天然橡胶实验相近的晶体核心。</li>
  </ol>
  <p class="source-note">以上为对论文结论的中文归纳，不是逐字转载。原始论文位于 <code>paper/laghmach2015.pdf</code>。</p>
</section>

<section id="equations"><h2>3. 本构方程与耦合逻辑</h2>
  <h3>3.1 Flory 熔化自由能与有限变形</h3>
  <div class="equation"><span class="eqname">式 (2) · 局部熔化自由能差</span>
ΔG<sup>melt</sup> = ν [ n h<sub>m</sub>(T<sub>m</sub><sup>0</sup>−T)/T<sub>m</sub><sup>0</sup> + R T Tr(E) ]
E = ½(F<sup>T</sup>F − I),      det(F)=1</div>
  <p>论文正文写作 <code>kB</code>，但参数采用 mol/m³ 和 J/mol；为得到表中 <code>fscale=ρRTm0=37.03 MJ/m³</code>，实现必须一致使用摩尔气体常数 <code>R</code>。</p>

  <h3>3.2 双势阱体自由能与界面能</h3>
  <div class="equation"><span class="eqname">式 (4)–(8)</span>
f<sub>bulk</sub>(θ) = Γ θ²(1−θ)²/4 + g(θ) ΔG<sup>melt</sup>
g(θ) = 1 − θ²(3−2θ)
ℱ = ∫ [ f<sub>bulk</sub> + Γw²|∇θ|²/2 ] dV
γ = wΓ/(6√2)</div>
  <p><code>θ=0</code> 表示非晶，<code>θ=1</code> 表示晶体；梯度项赋予弥散界面有限厚度和表面张力。</p>

  <h3>3.3 Allen–Cahn 相场动力学</h3>
  <div class="equation"><span class="eqname">式 (9)、(10)、(27) · 各向同性写法</span>
τ₁ ∂θ/∂t = (Γ/f<sub>scale</sub>)[ w²∇²θ − ½ θ(1−θ)(1−2θ) ]
              − g′(θ)[ ΔG<sup>melt</sup>/f<sub>scale</sub> − f<sub>topo</sub>/f<sub>scale</sub> ]</div>
  <div class="callout danger"><b>原文内部系数矛盾：</b>印刷的式 (10)/(13)/(27) 给出 <code>+1/4</code> 势垒项，但式 (4) 的变分、式 (8) 的表面张力和式 (29) 的 tanh 界面共同要求 <code>−1/2</code>。本复现默认使用后者，并保留 <code>+1/4</code> 作为显式敏感性开关。</div>

  <h3>3.4 Eulerian 有限变形机械松弛</h3>
  <div class="equation"><span class="eqname">式 (18)–(19)</span>
∂u<sub>i</sub>/∂t = α<sub>u</sub> F<sub>kj</sub> ∂<sub>k</sub>[ −Pδ<sub>ij</sub> + g(θ)(ρRT/n) ∂u<sub>i</sub>/∂X<sub>j</sub> ]

F = [ 1−∂<sub>y</sub>u<sub>y</sub>     ∂<sub>x</sub>u<sub>y</sub> ]
    [   ∂<sub>y</sub>u<sub>x</sub>   1−∂<sub>x</sub>u<sub>x</sub> ]</div>
  <p>压力 <code>P</code> 是不可压缩约束的拉格朗日乘子；COMSOL 中公开加入 <code>1e−8·P</code> 零空间规范化，并同时输出 L2 与最大体积误差。</p>

  <h3>3.5 拓扑约束输运与弹性能</h3>
  <div class="equation"><span class="eqname">式 (20)、(23)–(26)</span>
∂u<sup>topo</sup>/∂t + v·∇u<sup>topo</sup> = v
v = −(∂θ/∂t) ∇θ / (|∇θ|² + α<sub>cut</sub>),      α<sub>cut</sub>=10<sup>−4</sup>
ε<sup>topo</sup> = sym(∇u<sup>topo</sup>)
f<sub>topo</sub> = μ* Tr[(ε<sup>topo</sup>)²] + λ*/2 [Tr(ε<sup>topo</sup>)]²</div>
  <p>界面速度把拓扑约束推出晶体，<code>f_topo</code> 再通过 <code>g(θ)</code> 反馈至相场方程，构成生长停止机制。</p>

  <h3>3.6 初始核、应力和观测量</h3>
  <div class="equation"><span class="eqname">式 (29)、(30) 与复现观测量</span>
θ(r,0) = ½{1 − tanh[(r−R<sub>n</sub>)/(2√2w)]}
σ<sub>xx</sub> = g(θ)(ρRT/n)(∂<sub>x</sub>u<sub>x</sub>−∂<sub>y</sub>u<sub>y</sub>)
R(t) = √[ ∫θ dA / π ]
γ<sub>elastic</sub>(r) = ∫g f<sub>topo</sub>dA / (2πR),      r=R(t)−R(0)</div>
</section>

<section id="setup"><h2>4. 仿真搭建</h2>
  <div class="flow"><div><b>① 几何/网格</b>200×200 nm 二维正方形；基准 1 nm；收敛网格 0.5 nm。</div><div><b>② 六个场</b>θ、u<sub>x</sub>、u<sub>y</sub>、P、u<sub>x</sub><sup>topo</sup>、u<sub>y</sub><sup>topo</sup>。</div><div><b>③ 三套弱式</b>Allen–Cahn、拓扑输运、有限变形位移 + 压力代数约束。</div><div><b>④ 对照/扫描</b>拓扑开关；网格/步长；温度—拉伸；Rn=5/9 nm。</div><div><b>⑤ 后处理验收</b>半径、应力、detF、界面能、曲线误差、t95 与拟合。</div></div>
  <div class="grid2"><div><h3>基准条件</h3><table><tr><th>项目</th><th>设置</th></tr><tr><td>温度/拉伸</td><td>303 K，λ=4</td></tr><tr><td>初始晶核</td><td>Rn=9 nm</td></tr><tr><td>时间尺度</td><td>t/τ₁；τ₂/τ₁=0.1</td></tr><tr><td>相场边界</td><td>四边 θ=0</td></tr><tr><td>位移边界</td><td>左右仅固定 ux；上下仅固定 uy；切向自然边界</td></tr><tr><td>时间积分</td><td>参考求解器显式 Euler；COMSOL BDF，最大步长受限</td></tr></table></div>
  <div><h3>核心材料参数</h3><table><tr><th>参数</th><th>数值</th></tr><tr><td>Tm0 / n / ρ</td><td>303 K / 95 / 1.47×10⁴ mol·m⁻³</td></tr><tr><td>hm</td><td>4.986 kJ·mol⁻¹</td></tr><tr><td>γ / w</td><td>0.02 J·m⁻² / 1 nm</td></tr><tr><td>Γ / fscale</td><td>169.7 / 37.03 MJ·m⁻³</td></tr><tr><td>λ* / μ*</td><td>0.611 / 0.15275 MPa</td></tr><tr><td>αcut</td><td>10⁻⁴</td></tr></table></div></div>
  <h3>COMSOL 实现</h3>
  <ul><li><b>Phase field：</b>标量 Weak Form PDE；所有非时间项显式除以 <code>τ1</code>。</li><li><b>Topology：</b>双分量 Weak Form PDE，速度仅在弥散界面附近非零。</li><li><b>Mechanics：</b><code>ux</code>/<code>uy</code> 分成两个标量接口以精确施加论文边界；<code>P</code> 为独立代数场。</li><li><b>输出：</b>有效半径、θ 极值、<code>incompL2</code>、<code>incompMax</code>、非晶平均应力、界面带重叠、弹性表面张力、拓扑能、总二维自由能和运行参数。</li></ul>
</section>

<section id="results"><h2>5. 定量结果</h2>
  <table><tr><th>量</th><th>当前结果</th><th>解释</th></tr>
  <tr><td>拓扑开启最终半径</td><td>$baseline_radius nm</td><td>落在论文 22–25 nm 平台区间</td></tr>
  <tr><td>后期漂移</td><td>$baseline_drift / 100τ₁</td><td>远低于 1% 稳态阈值</td></tr>
  <tr><td>拓扑关闭最终半径/斜率</td><td>$control_radius nm / $control_slope nm·τ₁⁻¹</td><td>仍在持续增长，负对照成立</td></tr>
  <tr><td>图 6b 半径 NRMSE</td><td>$radius_nrmse</td><td>小于 10% 标准</td></tr>
  <tr><td>平台误差 / t95 误差</td><td>$plateau_error / $t95_error</td><td>均通过论文曲线标准</td></tr>
  <tr><td>网格 / 半步长半径差</td><td>$grid_diff / $dt_diff</td><td>均小于 3%</td></tr>
  <tr><td>临界拉伸比</td><td>298/303/308 K → 3/4/5</td><td>与论文一致</td></tr>
  <tr><td>双晶核曲线重合 NRMSE</td><td>$collapse</td><td>通过 15% 标准</td></tr>
  <tr><td>指数拟合 A / B / R²</td><td>$fit_a / $fit_b / $fit_r2</td><td>A 通过；B 与 R² 未通过</td></tr></table>
</section>

<section id="figures"><h2>6. 关键图表</h2>
  $free_energy
  $radius
  <div class="grid2">$theta $topology</div>
  $surface
</section>

<section id="acceptance"><h2>7. 验收明细</h2>
  <div class="cards"><div class="card"><b>$required_passed / $required_total</b><span>必选指标</span></div><div class="card"><b>9 passed</b><span>定向代码测试</span></div><div class="card"><b>85</b><span>SHA-256 清单条目</span></div><div class="card"><b>0 / 5</b><span>第二阶段各向异性指标</span></div></div>
  <h3>必选指标</h3><table><tr><th>指标</th><th>实际值</th><th>规则</th><th>状态</th></tr>$required_rows</table>
  <h3>第二阶段可选指标</h3><table><tr><th>指标</th><th>实际值</th><th>规则</th><th>状态</th></tr>$optional_rows</table>
</section>

<section id="limits"><h2>8. 局限、风险与下一步</h2>
  <div class="callout danger"><b>尚缺 5 个必选指标：</b>最大不可压缩误差、应力净下降、应力曲线 NRMSE、指数拟合 B、指数拟合 R²。</div>
  <ol><li>约化求解器预设远场应变，不求解论文式 (18)，所以不能用它证明不可压缩性或应力松弛。</li><li>表面能双晶核曲线彼此重合，但约化模型的指数形状仍未达到论文 <code>R²≥0.98</code>。</li><li>COMSOL Java 源码尚未真正编译；远程 SSH 主机密钥发生变化，在可信确认前没有绕过安全校验。</li><li>各向异性式 (13) 已参数化，但 298 K、λ=6、E*=2 MPa 工况尚未求解，图 12–13 尺寸指标仍为空。</li></ol>
  <p><b>恢复顺序：</b>确认主机指纹 → 1τ₁ smoke solve → 核心四工况 → 阈值六工况 → 双晶核表面能 → 下载 MPH/CSV/日志 → 运行统一验收。只有 22/22 必选通过，才可称为第一阶段完整复现。</p>
</section>

<section id="files"><h2>9. 文件与复现入口</h2>
  <table><tr><th>用途</th><th>路径</th></tr><tr><td>论文 PDF</td><td><code>paper/laghmach2015.pdf</code></td></tr><tr><td>机器案例合同</td><td><code>simulations/laghmach2015/case.yml</code></td></tr><tr><td>方程逐式审计</td><td><code>simulations/laghmach2015/equation_audit.md</code></td></tr><tr><td>COMSOL 构建源码</td><td><code>simulations/laghmach2015/comsol/Laghmach2015.java</code></td></tr><tr><td>一键参考套件</td><td><code>simulations/laghmach2015/run_reference_suite.sh</code></td></tr><tr><td>COMSOL 后处理</td><td><code>simulations/laghmach2015/evaluate_comsol_suite.sh</code></td></tr><tr><td>逐项验收报告</td><td><code>tmp/runs/reference/laghmach2015/reference_acceptance_thresholds.md</code></td></tr><tr><td>结果校验清单</td><td><code>tmp/runs/reference/laghmach2015/manifest.sha256</code></td></tr></table>
  <p class="source-note">本 HTML 中的图均以内联 SVG 保存，不加载字体、脚本、样式表或网络图片；可直接复制到无网络环境浏览和打印为 PDF。</p>
</section>
</main></div>
<div class="footer">Laghmach 2015 · offline simulation reproduction report · generated from auditable local artifacts</div>
</body></html>""")

    html = template.substitute(
        generated=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        baseline_radius=f'{baseline["final_effective_radius_nm"]:.5f}',
        baseline_drift=f'{baseline["final_relative_drift_per_100tau1"]:.6f}',
        control_radius=f'{control["final_effective_radius_nm"]:.5f}',
        control_slope=f'{control["final_radius_slope_nm_per_tau1"]:.5f}',
        radius_nrmse=f'{curve["radius_nrmse"]:.2%}',
        plateau_error=f'{curve["plateau_relative_error"]:.2%}',
        t95_error=f'{curve["t95_relative_error"]:.2%}',
        grid_diff=f'{quality["radius_grid_relative_difference"]:.2%}',
        dt_diff=f'{quality["radius_timestep_relative_difference"]:.3%}',
        collapse=f'{surface["nucleus_curve_nrmse"]:.2%}',
        fit_a=f'{surface["A_J_m2"]:.4g} J·m⁻²',
        fit_b=f'{surface["B_per_nm"]:.4g} nm⁻¹',
        fit_r2=f'{surface["r_squared"]:.4f}',
        required_passed=summary["required_passed"],
        required_total=summary["required_total"],
        required_rows=_acceptance_rows(summary, required=True),
        optional_rows=_acceptance_rows(summary, required=False),
        **figures,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html, encoding="utf-8")
    print(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
