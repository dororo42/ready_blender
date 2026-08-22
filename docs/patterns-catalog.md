# Ready 生态 93 个 Pattern 目录(按可用性排序)

> 生成:2026-08-18 ｜ 数据源:Ready 0.6 官方 Patterns 目录 ｜ 解析:本项目 fileio.vtk_xml(93/93)

**可用性分级说明**(对本插件的"导入 Pattern 为初始条件"功能而言):

| 级 | 含义 | 数量 |
|---|---|---|
| ① 导入即用 | Gray-Scott 标准参数型(2D,五参数齐全) | 7 |
| ② 参数参考 | 公式型/特殊变体(2D) | 56 |
| ③ 仅文献参考 | 内核型(2D,本项目无内核引擎) | 11 |
| ④ 不支持导入 | 3D 体素 / .vtu 网格型 | 19 |

> 注:全部 93 个 pattern 中,仅 grayscott_1D 带真实初始场(1D,不在导入范围);2D pattern 均为生成器型(初始场为空,导入时自动改用基底+中央种子)。


## ① 导入即用 —— Gray-Scott 标准参数型(2D,五参数齐全)(7 个)

| Pattern | 规则 | 化学量 | 参数 | 文献描述/说明 |
|---|---|---|---|---|
| CPU-only/grayscott_1D.vti *(1D)* | Gray-Scott | 2 | timestep=1.0, D_a=0.082, D_b=0.041, k=0.06, F=0.035 | ★**真实初始场** Self-replicating spots in one dimension. This example uses an inbuilt implementation (currently only Gray-Scott is available) and so the formula ca... |
| CPU-only/grayscott_2D.vti | Gray-Scott | 2 | timestep=1.0, D_a=0.082, D_b=0.041, k=0.064, F=0.035 | (生成器型,场为空) Self-replicating spots in two dimensions. This example uses an inbuilt implementation (currently only Gray-Scott is available) and so the formula c... |
| Gray-Scott/self-replicating_spots.vti | Gray-Scott | 2 | timestep=1.0, D_a=0.082, D_b=0.041, k=0.064, F=0.035 | (生成器型,场为空) Self-replicating spots. |
| Gray-Scott/U-Skate/Munafo_glider.vti | Gray-Scott | 2 | timestep=1.0, D_a=0.164, D_b=0.082, k=0.06093, F=0.062 | (生成器型,场为空) Robert Munafo's U-skater. See http://mrob.com/pub/comp/xmorphia/uskate-world.html |
| Gray-Scott/U-Skate/o-ring_2D.vti | Gray-Scott | 2 | timestep=1.0, D_a=0.164, D_b=0.082, k=0.06093, F=0.062 | (生成器型,场为空) An O-ring with one or a few dots moves slowly forwards. Without dots it is a stable static structure. http://mrob.com/pub/comp/xmorphia/uskate-worl... |
| parameter_modulation_demo.vti | Gray-Scott | 3(导入取前两个) | timestep=1.0, D_a=0.082, D_b=0.041, k=0.064, F=0.035 | (生成器型,场为空) Using an extra chemical (c) to modulate the parameters of a Gray-Scott system. |
| parameter_modulation_demo2.vti | Gray-Scott | 3(导入取前两个) | timestep=1.0, D_a=0.082, D_b=0.041, k=0.055, F=0.035 | (生成器型,场为空) Using an extra chemical (c) to modulate the parameters of a Gray-Scott system. |

## ② 参数参考 —— 公式型/特殊变体(2D)(56 个)

| Pattern | 规则 | 化学量 | 参数 | 文献描述/说明 |
|---|---|---|---|---|
| Brusselator.vti | Brusselator | 2 | timestep=0.01, D_a=0.05, D_b=0.005, k1=1.0, k2=1.0, k3=1.0, k4=1.0, A=1.0, B=3.0 | (生成器型,场为空) The Brusselator is a theoretical model for a type of autocatalytic chemical reaction. http://en.wikipedia.org/wiki/Brusselator Initially the system... |
| Experiments/cglrd_ramps_example_djw.vti | Ginzburg-Landau | 4(导入取前两个) |  | (生成器型,场为空) The complex Ginzburg-Landau equation describes a vast variety of phenomena from nonlinear waves to second-order phase transitions, from superconduc... |
| Experiments/grayscott-historyWave_coralGrow_djw.vti | Gray-Scott | 5(导入取前两个) |  | (生成器型,场为空) Gray-Scott-History-Wave formula, implemented by Dan Wills starting from pre-existing pattern code in Ready. A Gray-Scott reaction-diffusion system ... |
| Experiments/grayscott-historyWave_fuseWorms.vti | Gray-Scott | 5(导入取前两个) |  | (生成器型,场为空) Gray-Scott-History-Wave formula, implemented by Dan Wills based on pre-existing pattern code in Ready. A Gray-Scott reaction-diffusion system is si... |
| Experiments/grayscott-historyWave_moreLifelike.vti | Gray-Scott | 5(导入取前两个) |  | (生成器型,场为空) Gray-Scott-History-Wave formula, implemented by Dan Wills based on pre-existing pattern code in Ready. A Gray-Scott reaction-diffusion system is si... |
| Experiments/grayscott-historyWaveDC_solitonsAndWorms_init.vti | Gray-Scott | 5(导入取前两个) |  | (生成器型,场为空) Gray-Scott-History-Wave formula, implemented by Dan Wills based on pre-existing pattern code in Ready. A Gray-Scott reaction-diffusion system is si... |
| Experiments/mutually-catalytic_spots.vti | coupled Gray-Scott | 5(导入取前两个) | timestep=0.06, diff_ab=2.0, diff_cd=0.041, k1=0.0648, F1=0.03, k2=0.08, F2=0.035, b_fee... | (生成器型,场为空) Mutually-catalytic spot systems. Created by Tim Hutton. Two coupled Gray-Scott systems: a,b and c,d. The large a,b spots can only replicate when fu... |
| Experiments/orbits_explodey_init.djw.vti | Orbit | 4(导入取前两个) |  | (生成器型,场为空) This is an rd formula that uses an iteration step inspired by an orbits-fractal step (eg Mandelbrot/Julia). It treats reagents a and b as a complex... |
| Experiments/orbits_sharpWaves-init_djw.vti | Orbit | 4(导入取前两个) |  | (生成器型,场为空) This is an rd formula that uses an iteration step inspired by an orbits-fractal step (eg Mandelbrot/Julia). It treats reagents a and b as a complex... |
| FitzHugh-Nagumo/Ising_regime.vti | Fitzhugh-Nagumo | 2 | timestep=0.02, a0=-0.1, a1=2.0, epsilon=0.05, delta=4.0, k1=1.0, k2=0.0, k3=1.0 | (生成器型,场为空) A reproduction of Figure 3 from Hagberg and Meron (1994) . They refer to this region of the parameter space as the 'Ising regime'. Small variations... |
| FitzHugh-Nagumo/spiral_turbulence.vti | Fitzhugh-Nagumo | 2 | timestep=0.02, a0=-0.1, a1=2.0, epsilon=0.014, delta=2.8, k1=1.0, k2=0.0, k3=1.0 | (生成器型,场为空) See the paper: From Labyrinthine Patterns to Spiral Turbulence |
| FitzHugh-Nagumo/squid_axon.vti *(1D)* | Fitzhugh-Nagumo | 2 | timestep=0.02, a0=-0.1, a1=2.0, epsilon=0.1, delta=0.0, k1=1.0, k2=0.0, k3=1.0 | (生成器型,场为空) Travelling waves in a mathematical model of excitable media, such as heart tissue and nerve fibre. Based on a model originally developed from the s... |
| FitzHugh-Nagumo/tip-splitting.vti | Fitzhugh-Nagumo | 2 | timestep=0.02, a0=-0.1, a1=2.0, epsilon=0.05, delta=4.0, k1=1.0, k2=0.0, k3=1.0 | (生成器型,场为空) A phenomenon called 'tip-splitting' or 'bifurcating stripes'. Recently observed in the growing palate of mice: Periodic stripe formation by a Turin... |
| Ginzburg-Landau/complex_Ginzburg-Landau.vti | Ginzburg-Landau | 2 | timestep=0.2, alpha=0.0625, beta=1.0, delta=1.0, gamma=0.0625, D_a=0.2, D_b=0.2 | (生成器型,场为空) "The complex Ginzburg-Landau equation describes a vast variety of phenomena from nonlinear waves to second-order phase transitions, from supercondu... |
| Ginzburg-Landau/complex_Ginzburg-Landau_magnitude.vti | Ginzburg-Landau | 3(导入取前两个) | timestep=0.2, alpha=0.0625, beta=1.0, delta=1.0, gamma=0.0625, D_a=0.1, D_b=0.1 | (生成器型,场为空) "The complex Ginzburg-Landau equation describes a vast variety of phenomena from nonlinear waves to second-order phase transitions, from supercondu... |
| Gray-Scott/Lesmes_noisy.vti | Gray-Scott | 3(导入取前两个) | timestep=0.2, D_a=0.4, D_b=0.2, k=0.0655, F=0.05, noise=0.3 | (生成器型,场为空) Lesmes F, et al. (2003) Noise-controlled self-replicating patterns (PDF) . The noise parameter controls the amount of noise added to the system. Wi... |
| Gray-Scott/noisy_solitons_mitosis.vti | Gray-Scott | 3(导入取前两个) | timestep=0.06, D_a=0.2, D_b=0.1, k=0.0648, F=0.03, noise=0.2 | (生成器型,场为空) Inspired by: Lesmes F, et al. (2003) Noise-controlled self-replicating patterns (PDF) . The noise parameter controls the amount of noise added to t... |
| Gray-Scott/parameter-map.vti | Gray-Scott | 2 | timestep=0.2, diff=0.07, k1=0.03, k2=0.07, F1=0.0, F2=0.1 | (生成器型,场为空) A map of the parameters of the Gray-Scott system. Here 'k' increases from left to right and 'F' increases from bottom to top. For more detail, see:... |
| Gray-Scott/Pearson1993.vti | Gray-Scott | 2 | timestep=1.0, delta_x=0.009765625, D_a=2e-05, D_b=1e-05, k=0.06, F=0.04 | (生成器型,场为空) John E. Pearson (1993) " Complex Patterns in a Simple System " Science 261(5118):189-192. Change the parameters k and F to explore the systems that... |
| heat_equation.vti | Heat equation | 1 | timestep=0.1 | The heat equation , also known as the diffusion equation, describes multiple phenomena including the spreading-out of heat in a solid body and the ... |
| heat_equation_interpolation.vti | Heat equation | 2 | timestep=0.2 | (生成器型,场为空) Here the heat equation applies to chemical a but only in those places where chemical b is zero. This has the effect of locking certain areas to the... |
| Kytta2007/Fig5.7a.vti | Yang | 4(导入取前两个) | timestep=0.001, q=0.1, p1=4.5, p2=11.0, Da=1.85, Db=16.66, Dc=25.741, Dd=196.0 | (生成器型,场为空) Klaus Kyttä (2007) "Computational Studies of Pattern Formation in Multiple Layer Turing Systems" PDF Figure 5.7a. Two cubic-coupled Brusselator sys... |
| Kytta2007/Fig5.7c.vti | Yang | 4(导入取前两个) | timestep=0.001, q=0.01, p1=4.5, p2=11.0, Da=7.5, Db=32.5, Dc=27.5, Dd=121.5 | (生成器型,场为空) Klaus Kyttä (2007) "Computational Studies of Pattern Formation in Multiple Layer Turing Systems" PDF Figure 5.7c. Two cubic-coupled Brusselator sys... |
| Kytta2007/Fig5.8c.vti | Yang | 4(导入取前两个) | timestep=0.001, q=0.01, p1=3.0, p2=9.0, Da=1.85, Db=5.66, Dc=50.6, Dd=186.0 | (生成器型,场为空) Klaus Kyttä (2007) "Computational Studies of Pattern Formation in Multiple Layer Turing Systems" PDF Figure 5.8c. Two cubic-coupled Brusselator sys... |
| Kytta2007/Fig5.8d.vti | Yang | 4(导入取前两个) | timestep=0.001, q=0.05, p1=3.0, p2=9.0, Da=1.85, Db=5.66, Dc=50.6, Dd=186.0 | (生成器型,场为空) Klaus Kyttä (2007) "Computational Studies of Pattern Formation in Multiple Layer Turing Systems" PDF Figure 5.8d. Two cubic-coupled Brusselator sys... |
| Kytta2007/Fig5.8e.vti | Yang | 4(导入取前两个) | timestep=0.001, q=0.09, p1=3.0, p2=9.0, Da=1.85, Db=5.66, Dc=50.6, Dd=186.0 | (生成器型,场为空) Klaus Kyttä (2007) "Computational Studies of Pattern Formation in Multiple Layer Turing Systems" PDF Figure 5.8e. Two cubic-coupled Brusselator sys... |
| Kytta2007/Fig5.8f.vti | Yang | 4(导入取前两个) | timestep=0.001, q=0.15, p1=3.0, p2=9.0, Da=1.85, Db=5.66, Dc=50.6, Dd=186.0 | (生成器型,场为空) Klaus Kyttä (2007) "Computational Studies of Pattern Formation in Multiple Layer Turing Systems" PDF Figure 5.8f. Eventually the pattern resolves i... |
| Kytta2007/Fig5.8g.vti | Yang | 4(导入取前两个) | timestep=0.001, q=0.19, p1=3.0, p2=9.0, Da=1.85, Db=5.66, Dc=50.6, Dd=186.0 | (生成器型,场为空) Klaus Kyttä (2007) "Computational Studies of Pattern Formation in Multiple Layer Turing Systems" PDF Figure 5.8g. Two cubic-coupled Brusselator sys... |
| Meinhardt1982/stripes.vti | Meinhardt | 5(导入取前两个) | timestep=0.2, k_ab=0.04, k_c=0.06, k_de=0.04, diff1=0.005, diff2=0.4 | (生成器型,场为空) Hans Meinhardt's five-chemical model for producing stripes. Meinhardt, Hans (1982) "Models of Biological Pattern Formation" book available to downl... |
| oregonator.vti | Oregonator | 2 | timestep=0.0001, D_a=1.0, D_b=0.6, epsilon=0.01, f=1.4, q=0.002, dx=0.2 | (生成器型,场为空) The two-variable Oregonator model of the Belousov–Zhabotinsky reaction . |
| Purwins1999/glider.vti | Schenk | 3(导入取前两个) | D_a=0.00015, D_b=0.00015, D_c=0.0096, k3=8.5, lambda=2.0, k1=-6.92, theta=1.0, tau=48.0... | (生成器型,场为空) C. P. Schenk, A. W. Liehr, M. Bode, and H.-G. Purwins (1999) "Quasi-Particles in a Three-Dimensional Three-Component Reaction-Diffusion System" Hig... |
| Purwins1999/multiGlider.vti | Schenk | 3(导入取前两个) | D_a=9e-05, D_b=0.0007, D_c=0.015, k3=11.0, lambda=2.4, k1=-8.29, theta=4.0, tau=33.0, d... | (生成器型,场为空) C. P. Schenk, A. W. Liehr, M. Bode, and H.-G. Purwins (1999) "Quasi-Particles in a Three-Dimensional Three-Component Reaction-Diffusion System" Hig... |
| Schlogl.vti | Schlogl | 1 | timestep=0.1 | Schlögl’s model is the canonical example of a chemical reaction system that exhibits bistability. Schlögl, F. (1972) Chemical reaction models for n... |
| Schrodinger1926/packet.vti *(1D)* | Schrodinger equation | 3(导入取前两个) | timestep=0.001 | (生成器型,场为空) The Schrödinger equation describes the change in the wave function for some quantum state. For a travelling particle, the magnitude of the wave pac... |
| Schrodinger1926/packet_pass.vti *(1D)* | Schrodinger equation | 4(导入取前两个) | timestep=0.001, potential=0.1 | (生成器型,场为空) The Schrödinger equation describes the change in the wave function for some quantum state. For a travelling particle, the magnitude of the wave pac... |
| Schrodinger1926/packet_reflect.vti *(1D)* | Schrodinger equation | 4(导入取前两个) | timestep=0.001, potential=4.0 | (生成器型,场为空) The Schrödinger equation describes the change in the wave function for some quantum state. For a travelling particle, the magnitude of the wave pac... |
| Schrodinger1926/packet_reflect2D.vti | Schrodinger equation | 4(导入取前两个) | timestep=0.001, potential=4.0 | (生成器型,场为空) The Schrödinger equation describes the change in the wave function for some quantum state. For a travelling particle, the magnitude of the wave pac... |
| Schrodinger1926/quantum_tunnelling.vti *(1D)* | Schrodinger equation | 4(导入取前两个) | timestep=0.001, potential=3.0 | (生成器型,场为空) The Schrödinger equation describes the change in the wave function for some quantum state. For a travelling particle, the magnitude of the wave pac... |
| Turing1952/spots.vti | Turing | 2 | timestep=0.1, D_a=0.25, D_b=0.0625, k=0.0625 | (生成器型,场为空) The system that produces Table 2 from Turing's 1952 paper. |
| Turing1952/spots_noisy.vti | Turing | 3(导入取前两个) | timestep=0.1, D_a=0.5, D_b=0.125, k=0.0625 | (生成器型,场为空) The system that produces Table 2 from Turing's 1952 paper, with added noise. The noise helps the dots pattern become established, and helps the dot... |
| wave_equation.vti | Wave equation | 2 | timestep=0.1, damping=0.2, vis=15.0 | (生成器型,场为空) Wave equation. Here 'a' stores the value, 'b' stores the rate of change. The wave equation says that the second derivative (the rate of change of t... |
| Yang2002/Yang_1.vti | Yang | 4(导入取前两个) | timestep=0.001, p1=3.0, p2=9.0, alpha=1.0, Da=5.0, Db=14.0, Dc=54.9, Dd=159.8 | (生成器型,场为空) "Spatial Resonances and Superposition Patterns in a Reaction-Diffusion Model with Interacting Turing Modes" (2002) Lingfa Yang, Milos Dolnik, Anato... |
| Yang2002/Yang_2b.vti | Yang | 4(导入取前两个) | timestep=0.001, p1=3.0, p2=9.0, alpha=0.1, Da=16.7, Db=36.4, Dc=49.5, Dd=117.6 | (生成器型,场为空) "Spatial Resonances and Superposition Patterns in a Reaction-Diffusion Model with Interacting Turing Modes" (2002) Lingfa Yang, Milos Dolnik, Anato... |
| Yang2002/Yang_2c.vti | Yang | 4(导入取前两个) | timestep=0.001, p1=3.0, p2=9.0, alpha=0.1, Da=12.6, Db=27.5, Dc=49.4, Dd=117.6 | (生成器型,场为空) "Spatial Resonances and Superposition Patterns in a Reaction-Diffusion Model with Interacting Turing Modes" (2002) Lingfa Yang, Milos Dolnik, Anato... |
| Yang2002/Yang_2d.vti | Yang | 4(导入取前两个) | timestep=0.001, p1=3.0, p2=9.0, alpha=0.1, Da=5.6, Db=12.3, Dc=49.3, Dd=117.5 | (生成器型,场为空) "Spatial Resonances and Superposition Patterns in a Reaction-Diffusion Model with Interacting Turing Modes" (2002) Lingfa Yang, Milos Dolnik, Anato... |
| Yang2002/Yang_3a.vti | Yang | 4(导入取前两个) | timestep=0.001, p1=3.0, p2=9.0, alpha=0.1, Da=12.6, Db=27.5, Dc=47.5, Dd=141.5 | (生成器型,场为空) "Spatial Resonances and Superposition Patterns in a Reaction-Diffusion Model with Interacting Turing Modes" (2002) Lingfa Yang, Milos Dolnik, Anato... |
| Yang2002/Yang_3b.vti | Yang | 4(导入取前两个) | timestep=0.001, p1=3.0, p2=9.0, alpha=1.0, Da=1.85, Db=5.66, Dc=50.6, Dd=186.0 | (生成器型,场为空) "Spatial Resonances and Superposition Patterns in a Reaction-Diffusion Model with Interacting Turing Modes" (2002) Lingfa Yang, Milos Dolnik, Anato... |
| Yang2002/Yang_3c.vti | Yang | 4(导入取前两个) | timestep=0.001, p1=3.0, p2=6.0, alpha=1.0, Da=1.31, Db=9.87, Dc=34.0, Dd=344.9 | (生成器型,场为空) "Spatial Resonances and Superposition Patterns in a Reaction-Diffusion Model with Interacting Turing Modes" (2002) Lingfa Yang, Milos Dolnik, Anato... |
| Yang2002/Yang_3d.vti | Yang | 4(导入取前两个) | timestep=0.001, p1=3.0, p2=10.0, alpha=1.0, Da=2.03, Db=4.38, Dc=56.2, Dd=135.3 | (生成器型,场为空) "Spatial Resonances and Superposition Patterns in a Reaction-Diffusion Model with Interacting Turing Modes" (2002) Lingfa Yang, Milos Dolnik, Anato... |
| Yang2002/Yang_4.vti | Yang | 4(导入取前两个) | timestep=0.001, p1=3.0, p2=9.9, alpha=1.0, Da=8.33, Db=8.33, Dc=46.0, Dd=120.0 | (生成器型,场为空) "Spatial Resonances and Superposition Patterns in a Reaction-Diffusion Model with Interacting Turing Modes" (2002) Lingfa Yang, Milos Dolnik, Anato... |
| Yang2003/Fig2.vti | Yang2003 | 5(导入取前两个) |  | (生成器型,场为空) L. Yang and I.R. Epstein. (2003) "Oscillatory Turing Patterns in Reaction-Diffusion Systems with Two Coupled Layers" http://hopf.chem.brandeis.edu/... |
| Yang2003/Fig3a.vti | Yang2003 | 5(导入取前两个) |  | (生成器型,场为空) L. Yang and I.R. Epstein. (2003) "Oscillatory Turing Patterns in Reaction-Diffusion Systems with Two Coupled Layers" http://hopf.chem.brandeis.edu/... |
| Yang2003/Fig3b.vti | Yang2003 | 5(导入取前两个) |  | (生成器型,场为空) L. Yang and I.R. Epstein. (2003) "Oscillatory Turing Patterns in Reaction-Diffusion Systems with Two Coupled Layers" http://hopf.chem.brandeis.edu/... |
| Yang2003/Fig3c.vti | Yang2003 | 5(导入取前两个) |  | (生成器型,场为空) L. Yang and I.R. Epstein. (2003) "Oscillatory Turing Patterns in Reaction-Diffusion Systems with Two Coupled Layers" http://hopf.chem.brandeis.edu/... |
| Yang2006/jumping.vti *(1D)* | Yang2006 | 3(导入取前两个) | D_a=1.0, D_b=1.0, D_c=60.0, k1=-8.5, k3=10.0, k4=2.0, tau=50.0, dx=0.5, timestep=0.001 | (生成器型,场为空) Lingfa Yang, Anatol M. Zhabotinsky and Irving R. Epstein (2006) "Jumping solitary waves in an autonomous reaction–diffusion system with subcritical... |
| Yang2006/jumping_cGL.vti *(1D)* | Ginzburg-Landau | 3(导入取前两个) | timestep=0.01, muRe=-0.1, muIm=0.1, alphaRe=3.0, alphaIm=1.0, betaRe=1.0, betaIm=1.0, n... | (生成器型,场为空) Lingfa Yang, Anatol M. Zhabotinsky and Irving R. Epstein (2006) "Jumping solitary waves in an autonomous reaction–diffusion system with subcritical... |

## ③ 仅文献参考 —— 内核型(2D,本项目无内核引擎)(11 个)

| Pattern | 规则 | 化学量 | 参数 | 文献描述/说明 |
|---|---|---|---|---|
| CellularAutomata/Conway_life.vti | B3/S23 | 2 |  | Conway's Game of Life, just because we can. Not an efficient way to do this, since everything is stored as floats. |
| CellularAutomata/larger-than-life.vti | Larger-than-Life | 2 |  | Larger than Life, by Kellie Michele Evans . The parameter R controls the distance over which the neighbor count is taken. The two ranges [b1,b2] an... |
| CellularAutomata/Salt/salt2D_demo.vti | Salt_2D | 2 |  | Miller and Fredkin's Salt CA, in 2D. From: "Circular Motion of Strings in Cellular Automata, and Other Surprises", Daniel B. Miller and Edward Fred... |
| Experiments/gladman_vermiformSolitons.vti | gladman | 2 |  | (生成器型,场为空) Simon Gladman: "After my recent experiments with cubic coupling different reaction diffusion models, I thought I'd return to my roots and see what ... |
| kernel_test.vti | Kernel test | 2 |  | This is an example rule where we give the whole OpenCL kernel instead of just a formula. See also Conway_life.vti. Note that we can use float (or f... |
| McCabe/McCabe.vti | McCabe | 2 |  | Jonathan McCabe (2010) " Cyclic Symmetric Multi-Scale Turing Patterns " The model from the section 'Multi-Scale Turing Patterns'. The code 'adds va... |
| McCabe/McCabe_additive2a.vti | McCabe | 2 |  | Jonathan McCabe (2010) " Cyclic Symmetric Multi-Scale Turing Patterns " The model from the section 'Compound Turing Patterns', with variation on tw... |
| McCabe/McCabe_additive2b.vti | McCabe | 2 |  | Jonathan McCabe (2010) " Cyclic Symmetric Multi-Scale Turing Patterns " The model from the section 'Compound Turing Patterns', with variation on tw... |
| McCabe/McCabe_simple.vti | McCabe | 2 |  | Jonathan McCabe (2010) " Cyclic Symmetric Multi-Scale Turing Patterns " The model from the section 'Simple Turing Patterns'. The code 'adds variati... |
| SmoothLife/smoothglider.vti | SmoothLife | 2 |  | The smoothglider, a parameter set of SmoothLife, by Stephan Rafler. PDF , software . SmoothLife was designed as a continuous version of Conway's Ga... |
| SmoothLife/smoothlifeL.vti | SmoothLifeL | 2 |  | SmoothLifeL, a parameter set of SmoothLife, by Stephan Rafler. PDF , software . This version uses smooth time stepping - the timestep can be made s... |

## ④ 不支持导入 —— 3D 体素 / .vtu 网格型(19 个)

| Pattern | 规则 | 化学量 | 参数 | 文献描述/说明 |
|---|---|---|---|---|
| bunny.vtu | Gray-Scott | 2 | timestep=1.0, D_a=0.082, D_b=0.041, k=0.06, F=0.035 | Gray-Scott running on the surface of the Stanford Bunny. Mesh courtesy of Greg Turk and Marc Levoy. link |
| CellularAutomata/Bays_3D.vti | 3D-CA rule 4,5/5 | 2 |  | The kernel code implements a 3D cellular automaton for rule 4,5/5 in the notation used by Carter Bays and his colleagues (see applet here ). The in... |
| CellularAutomata/Buss_hex.vtu | HexBuss | 2 |  | Frank Buss' Hex Cellular Automaton, initialized with a glider gun and a rake. http://www.frank-buss.de/automaton/hexautomaton.html |
| CellularAutomata/hex_B2oS2m34_gliders.vtu | B2oS2m34 | 2 |  | Gliders in the hexagonal rule B2o/S2m34, by Paul Callahan http://www.radicaleye.com/lifepage/hexrule.txt Based on a Python transition function by A... |
| CellularAutomata/life_torus.vtu | B3/S23 | 2 |  | Conway's Game of Life, implemented on a torus. |
| CellularAutomata/PenroseTilings/Goucher_glider.vtu | Goucher's Glider | 2 |  | Adam Goucher's Penrose glider rule. See discussion here: http://news.ycombinator.com/item?id=4298515 |
| CellularAutomata/PenroseTilings/Goucher_loops.vtu | Goucher's loops | 2 |  | Adam Goucher's gliders on a darts-and-kites tiling run in loops. His paper is to appear in the Journal of Cellular Automata: "Gliders in cellular a... |
| CellularAutomata/PenroseTilings/Imai_glider_B2SC4.vtu | B2SC4 | 2 |  | Gliders in a Generations-like rule (B2/S/C4) on a Penrose tiling. Discovered by Katsunobu Imai (see http://youtu.be/g0g2q0hecs8 ). |
| CellularAutomata/PenroseTilings/life.vtu | B3/S23 | 2 |  | Life on a Penrose tiling. Various still-lives and oscillators are seen. No gliders have yet been found. Inspired by the work of Nick Owens and Susa... |
| CellularAutomata/PenroseTilings/life_oscillators.vtu | B3/S23 | 2 |  | Some of the oscillators in Conway's Game of Life on a Penrose tiling. From the paper by Nick Owens and Susan Stepney . |
| CellularAutomata/Salt/salt3D_circular330.vti | Salt_3D | 2 |  | Miller and Fredkin's Salt CA, in 2D. From: "Circular Motion of Strings in Cellular Automata, and Other Surprises", Daniel B. Miller and Edward Fred... |
| CellularAutomata/tri_life.vtu | TriLife_B45S34 | 2 |  | A period-7 glider in the B45/S34 rule on a triangular grid. Based on the work of Carter Bays: http://www.cse.sc.edu/~bays/trilife3/home.html |
| CPU-only/grayscott_3D.vti | Gray-Scott | 2 | timestep=1.0, D_a=0.082, D_b=0.041, k=0.064, F=0.035 | (生成器型,场为空) The Gray-Scott rule in three dimensions. This example uses an inbuilt implementation (currently only Gray-Scott is available) and so the formula ca... |
| FitzHugh-Nagumo/pulsate.vti | Fitzhugh-Nagumo | 2 | timestep=0.02, a0=-0.1, a1=2.0, epsilon=0.018, delta=3.0, k1=1.0, k2=0.0, k3=1.0 | (生成器型,场为空)  |
| Gray-Scott/U-Skate/Hutton-and-helix-gliders.vti | Gray-Scott | 2 | timestep=1.0, D_a=0.164, D_b=0.082, k=0.06093, F=0.062 | ★**真实初始场** Two gliders in the 3D version of Robert Munafo's "U-skate world". One was found by Tim Hutton, and travels in a straight line. The other is the sam... |
| lion.vtu | Gray-Scott | 2 | timestep=1.0, D_a=0.082, D_b=0.041, k=0.064, F=0.035 | Gray-Scott running on the surface of a lion mesh. Mesh courtesy of Robert Sumner and Jovan Popovic. link |
| Meinhardt1982/zebra.vtu | Meinhardt | 5(导入取前两个) | timestep=1.0, k_ab=0.04, k_c=0.06, k_de=0.04, diff1=0.009, diff2=0.2 | Hans Meinhardt's five-chemical model for producing stripes. The pattern is initiated at the hoofs, mouth and eyes. Meinhardt, Hans (1982) "Models o... |
| Purwins1999/glider_3D.vti | Schenk | 3(导入取前两个) | D_a=0.00015, D_b=0.00015, D_c=0.0096, k3=8.5, lambda=2.0, k1=-6.92, theta=1.0, tau=48.0... | (生成器型,场为空) C. P. Schenk, A. W. Liehr, M. Bode, and H.-G. Purwins (1999) "Quasi-Particles in a Three-Dimensional Three-Component Reaction-Diffusion System" Hig... |
| SmoothLife/glider_3D.vti | SmoothLifeL | 2 |  | SmoothLife, by Stephan Rafler. PDF , software . This version uses smooth time stepping - the timestep can be made smaller without changing the beha... |