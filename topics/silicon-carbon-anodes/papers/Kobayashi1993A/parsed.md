**PHYSICAI** 

Physica D 63 (1993) 410-423 North-Holland 

# **Modeling and numerical simulations of dendritic crystal growth** 

### Ryo Kobayashi 

_Department of Applied Mathematics and lnformatics, Ryukoku University, Seta, Ohtsu 520-21, Japan_ 

Received 12 August 1991 Revised manuscript received 10 June 1992 Accepted 31 July 1992 Communicated by M. Mimura 

A simple phase field model for one component melt growth is presented, which includes anisotropy in a certain form. The formation of various dendritic patterns can be shown by a series of numerical simulations of this model. Qualitative relations between the shapes of crystals and some physical parameters are discussed. Also it is shown that noises give a crucial influence on the side branch structure of dendrites in some situations. 

### **1. Introduction** 

Crystal growth in one of the most fascinating phenomena of spontaneous pattern formations in nature. For instance, snowflakes have various types of very beautiful and complicated shapes, although they are formed in almost uniform circumstances. Also dendritic structure is commonly seen in solidification of metals [14] or crystalization in supersaturated solutions [11,12]. It's an exciting problem how such complex patterns can be formed by the systems which seem to be too simple to yield them. The aim of the present paper is to give a simplest model which can describe the dendritic pattern formations. There might be some fluid dynamical effects like the convection induced by gravity or Marangoni effect which give influences on the growth rate. Also the expansion or shrinking caused by the phase transition may affect the crystallization process. But these are not considered here, because our approach is not to present a model describing the phenomena minutely but to show the minimal set of factors which can yield variety 

of typical dendritic patterns essentially. For this reason, all the computations and all the discussions in this paper are devoted to the morphology of the crystals. 

There are two types of the crystal forms; such as equilibrium and growth. The equilibrium forms are determined so as to minimize the surface energy and therefore the shape is a sphere if the surface energy is isotropic and is some polyhedron if anisotropy exists. For this meaning, dendrites are not equilibrium forms but growth ones, which is formed under the balance of the surface tension and the thermodynamical driving force, say supercooling or supersaturation. However various dendritic patterns can not be obtained by only these two factors. Anisotropy, as is shown later, affects the shape of the crystal drastically. In our model, we consider the growth process that the only one diffusion field limits the growth rate of crystals, and I concentrate on the melt growth of pure material, in which there are molecules sufficiently dense in the surrounding phase (liquid phase) and they attach to the solid/liquid inter- 

0167-2789/93/$06.00 © 1993 - Elsevier Science Publishers B.V. All rights reserved 

411 

_R. Kobayashi / Simulations of dendritic crystal growth_ 

face collectively. Therefore the process limiting the growth rate of the crystal is a removing process of latent heat from the interface, which keeps the interfacial temperature below the equilibrium temperature. 

From the computational view point, we have two ways to handle such moving boundary problems. The one is to keep the data of the interfacial position explicitly and move it due to the interfacial equation of motion. (See [1-4] for example.) But we don't take this kind of method here because the complicated manipulation is needed when the topology of the interface changes- merging or coming off, and also it must be hard to extend such methods to the three dimensional space. Thus we'll adopt the other way, in which the interface is expressed implicitly using some function defined on the whole region. One of such methods was proposed by Osher and Sethian [5], in which the interface is expressed as a contour line (or surface) of some function and it is driven by Hamilton Jacobi equation. This is a numerical technique to solve the interface equation in which the interface thickness is considered to be zero. 

The model that we introduce here is a kind of phase field model in which the interface has a finite thickness although it is very thin and is expressed as a steep internal layer of a phase indicating function. The typical isotropic version of such model was proposed by Fix [6] and Collins and Levin [7], also it was justified mathematically by Caginalp [8] and Caginalp and Fife [9]. Also Caginalp presented relations between the phase field model and its singular limit equations [10]. A similar model including anisotropy was introduced and proved to be able to describe realistic dendritic patterns numerically by Kobayashi [15] and Mimura, Kobayashi and Okazaki [16]. In the following section, it will be shown that the model equations introduced in [15,16] can exhibit various realistic dendritic patterns by the numerical simulations. And the relations between the growth forms and some physical parameters such as dimensionless latent 

heat or strength of anisotropy are discussed. This article is essentially an explanation of the simulations presented in [17]. 

### **2. Model** 

The model includes two variables; one is a phase field _p(r, t)_ and the other is a temperature field _T(r, t)._ The variable _p(r, t)_ is an ordering parameter at the position r and the time t, p = 0 means being liquid and p = 1 solid. And the solid/liquid interface is expressed by the steep layer of p connecting the values 0 and 1. Fig. 1 shows how the shape of crystal is described by the phase field p. In order to keep the profile of p such form and to move it reasonably, we consider the following Ginzburg-Landau type free energy including m as a parameter: 

@[p; rn] = f IE2[~p[2 -['- _F(p; m) dr,_ 

where e is a small parameter which determines the thickness of the layer. It is a microscopic interaction length and it also controls the mobility of the interface. F is a double-well potential which has local minimums at p = 0 and 1 for each m. Here we take the specific form of F as follows: 

_F(p; rn) = ¼_ p4 _- (~ - ~m)p_ 1 3 _+ ( ~4 - ~m)p ,_ 1 2 Liquid P O(e) O(e) 

Fig. 1. Expression of the solid/liquid interface by the phase indicating function p. 

412 

where I ml< ½. The profile of F and its dependency on m are shown in fig. 2. The difference of the two minimum values is proportional to m, which gives a difference of chemical potentials of both the phases. 

Anisotropy can be introduced by assuming that e depends on the direction of the outer normal vector at the interface. So e is represented as a function of the vector v = (vi) satisfying e(Av)= _e(v)_ for A>0. The outer normal vector is represented by -Vp at the interface. Thus we consider 



From the formula _r 3p/Ot =-8~/8p,_ we have the following evolution equation: 





where r is a small positive constant and 0e/ _Ov=(Oe/3vi) i._ The parameter m gives a thermodynamical driving force. Especially in two dimensional space, we can take e = e(0) where 0 is an angle between v and a certain direction (for example the positive direction of the x-axis). Thus we have 





<!-- Start of picture text -->
F  F  F<br>ra>0  m=0  m<0<br><!-- End of picture text -->

Fig. **2. Double-well potential F controlled by the** parameter m. AF= F(0; m) - F(1; m) = _m/6._ 

where the prime means _d/dO._ Although (2) and (3) have a field equation form, they can be called interface equations, since they have a practical meaning only in the neighborhood of the interface. In fact, every term of them almost equals to zero in bulk. 

In order to understand intuitively how eq. (3) moves the interface, let us derive the singular limit equation in two dimensional case. Put e = g~r(0) where g is a mean value of e and ~r(0) represents anisotropy. Taking r = bg and _m = gf/V~,_ we obtain an interface equation in the limit of g tending to zero, as follows (See appendix): 



where V is the normal velocity and K is the mean curvature of the interface. Note that the limiting equation (4) is defined only on the interface while (3) is defined on the whole region. By taking r and m as stated above, we can regard eq. (3) as a family of equations parametrized by tT. Thus the parameter g is not a physical parameter but a computational parameter corresponding to the thickness of the layer which expresses an interface, or an indicator how well (3) approximates (4). Eq. (4) includes thermodynamical driving force, surface tension effect and anisotropy. Therefore eq. (3) also contains these factors. Anisotropy expressed by (4) will be discussed later. 

Here we assume that m is a function of the temperature T, for example, _m(T)_ = y(T e - T) where T e is an equilibrium temperature, which means that the driving force of interracial motion is proportional to the supercooling there. But in the following simulations, we used the form _m(~)=(a/~r)tan-l[y(Te -_ T)] where a is a positive constant satisfying a < 1, since this assures _Im(T)l_ < ½ for all values of T. Also _re(T)_ is almost linear for T near T~. To take anisotropy into account, let us specify ~r to be 

O'(0) = 1 + 3 COS[j(0 -- 00) ] . 

_R. Kobayashi / Simulations of dendritic crystal growth_ 

413 

The parameter 8 means the strength of anisotropy and j is a mode number of anisotropy. 

The equation for T is derived from the conservation law of enthalpy as 



_cT_ is non-dimensionalized so that the characteristic cooling temperature is 0 and the equilibrium temperature is 1 ,~1. K is a dimensionless latent heat which is proportional to the latent heat and inversely proportional to the strength of the cooling. For simplicity, the diffusion constant is set to be identical in both of solid and liquid regions. (5) is a heat conduction equation having a heat source along the moving interface, since _K Op/Ot_ has non-zero value only when the interface passes through the point. 

Here we refer to the difference between the dynamical term of our model equation (2) or (3) and the one of common phase field model (see [6-10]). In the common models, the dynamical term has a summation form essentially like p(1-p)(p½)+const. × (T e- T). Then the equilibrium value of p depends on the value of T, while they are fixed to be 0 or 1 in our model. Thus if the temperature of a point in bulk changes (in fact, it may change from the cooling temperature to one near T e in supercooling solidification), the value of p at that point varies corresponding to the temporal change of T. Consequently the term _K Op/Ot_ has non-zero value in bulk, which means that latent heat is released there. Therefore we should adopt the form of dynamical term such that the equilibrium values of p are fixed in bulk, if we use _K Op/Ot_ as a latent heat term. Otherwise we should change the latent heat term _K Op/Ot_ to _K Og(p)/Ot,_ where g(p) is a non-decreasing smooth function satisfying _g(p) =- 0_ near p = 0 and _g(p)_ -= 1 near p=l. 

*1The parameter 3" in _re(T)_ is non-dimensionalized corresponding to the non-dimensionalization of T. Hereafter we use the same notation 3' for the dimensionless value. 

### **3. Simulations** 

In this section, two dimensional simulations are presented which reveal various types of formations of dendritic pattern. All the simulations were computed by using the model equations (3) and (5). Dimensionless latent heat K, strength of anisotropy 6 and mode number of anisotropy j are changed, and other parameters are fixed #2. The characteristic cooling temperature was taken as the temperature of the cooling wall in the simulation without supercooling, and the initial temperature of the liquid in the supercooling solidification. Note that small noises were added on the interface all through the computations. This might be somewhat realistic and we can examine the stability of the shape of the interfaces against the noise. Noises were given to the system by using a random number sequence X in the form _ap(1 -P)X,_ where a is an amplitude of the noise and X is uniformly distributed on the interval [-½, ½]. This term was added to the dynamical term of (3) on the whole region, which is equivalent to adding the noises _ax_ to the term _re(T)_ at the interface. Denote that the boundary condition of p is always the zero flux condition. In all the simulations, the parameters are taken as follows: the domain size is 9.0 x 9.0 for the square region and 12.0x3.0 for the rectangular region, and the mesh numbers are 300 x 300 and 400 × 100, respectively. The fixed parameters are evaluated as follows, ~=0.01, ~- = 0.0003, a = 0.9, 3, = 10.0 and a = 0.01. Time mesh size is taken to be 0.0002. In the following simulations, no special technique was used for solving eqs. (3) and (5). A simple explicit scheme is used for (3) and a simple implicit scheme for (5). Note that the last picture of each figure does not mean the last state of the process. 

#2To control the values of K fixing the one of 3' means to consider various materials with different values of latent heat, not to control the strength of supercooling for one material. 

414 

_R. Kobayashi / Simulations of dendritic crystal growth_ 

#### _3. I. No supercooling - isotropic_ 

Initially the vessel is filled with a liquid of equilibrium temperature, and the vessel is cooled from its walls simultaneously. Solidification occurs from the walls and the crystal grows inward. Latent heat is taken away through the solid phase. The result of the simulation is shown in fig. 3. The shape of the interface is rounded as it moves and disappears, in the end. It corresponds to making an ice cube in an ice tray. Next we examine the stability of the advancing flat interface. The vessel is filled with liquid of equilibrium temperature, and along the left wall the solid exists and its interface is deformed as fig. 4 (time = 0.0) although it is rather artificial. The vessel is cooled from the left wall, and no heat flux is allowed at other walls. The crystal grows to the right, and latent heat is taken away through the solid phase to the left. The shape of the interface becomes flat very quickly as shown in fig. 4. In both cases, the interface never becomes complicated, and it acquires a shape with higher symmetry. This is because not only the surface tension but also the temperature field make the shape smooth and simple. In the anisotropic case, the situation is essentially the same, 



<!-- Start of picture text -->
©<br>ti~e = 0800000  t~me = ~ 200000  time = 9 000000<br><!-- End of picture text -->

Fig. 3. Crystal grows inward from the walls. The system is cooled by the surrounding walls. Isotropic. K - 1.0. 



<!-- Start of picture text -->
time " 0.000000  ~e  =  L000000<br><!-- End of picture text -->

Fig. 4. Crystal grows from the left wall to the right. The system is cooled only by the left wall. Isotropic. K = 1.0. 

although the results of simulations are not shown here. These are not interesting from the point of view of pattern formation (not of practical industry). We are interested in the complicated pattern formation like dendrites. In the following simulations, we consider the supercooling solidification. 

In the subsequent simulations, the whole region is initially filled with uniformly supercooled melt (the initial temperature is taken to be zero as stated before). Then the nucleation occurs and the solidification process follows under adiabatic conditions. In such situation, the whole liquid will change to crystal for K < 1. If K > 1, 1/K of the whole region will be solidified, and then lose the supercooling in the end. After that the interface moves only by the surface tension, thus very slowly. 

#### _3.2. Directional solidification - &otropic_ 

Solidification occurs simultaneously from the left wall to the right. Fig. 5 shows the results of the simulations for the various values of K. The flat interface is stable for K = 0.8 and a little bit destabilized for K-0.9. A weak cellular structure is observed for K= 1.0 and 1.1. For the latter parameter the slits between cells sometimes remain behind the front and they become holes by surface tension. For K-> 1.2, tip splitting occurs and the splitting branches tend to spread widely. But there is a limited space in the channel region and therefore they have to compete with each other. Consequently the branches differentiate to the winner and the loser. The loser cannot grow any more because it is screened by the winner. The winners can continue to grow and the tip splitting occurs at the top of them, then the new branches compete with each other again. This process succeeds until the front reaches the right wall. As K becomes larger, the branches come to have a stronger tendency to spread widely. The growth rate is drastically decreasing for K-> 1.6. 

_R. Kobayashi / Simulations of dendritic crystal growth_ 

415 



<!-- Start of picture text -->
(1)  K=0.8<br>D<br>time : 0400000  time  :  O. ?00000<br>(2)  K=0.9<br>time  =  0.000000  time =  0?00000<br>(3) K=  1.0  [<br>time  = 0.400000  time ~  0700000<br>°°  0  ° o'o<br>(4)  K=I.1  I ° oO<br>time  =  O, 400000  time = O. 700000<br>(5)  K = 1.2<br>lime  = O, 400000  time  = O. ?00000<br>time  =  O.  400000  time = 0. ?00000<br>time = 0 500000  time =  1.000000<br>time  = 1.000000  time  = 2.000000<br>ILL  I<br>time  = i, 400000  time  =  2.  000000<br><!-- End of picture text -->

Fig. 5, Crystal grows from the left wall toward supercooled melt under adiabatic condition for various values of K. Isotropic. 

## _3.3. Directional solidification-anisotropic_ 

Next the 4-mode anisotropy is assumed; 6 is fixed to be 0.050 and the horizontal and the vertical directions, are the ones at which e has maximums (i.e. j=4 and 00 =0). The initial state is just the same as in the isotropic case. Fig. 6 shows results. For K = 0.8, the flat interface is 

already destabilized slightly, whereas it was stable in the isotropic situation. For K = 0.9 and 1.0, weak cellular structure is seen, For K = 1.1, 1.2 and 1.4, slits are observed and they remain a long time because the branches have almost no tendency to spread. And their fronts advance faster than the ones of the istropic case. For K >-1.6, we can see that the branches compete 

_R. Kobayashi / Simulations of dendritic crystal growth_ 

416 



<!-- Start of picture text -->
(1)  =o.sj  1 1<br>time = O.  400000  time = 0. 700000<br>(2)<br>time = 0.~00000  time  =  0. 700000<br>(3)  K=10F  l<br>tlze  =  O.  400000  time = 0.  700000<br>• o  . ~<br>(4)  K=I.1  :  ° o*  ° 00~  or<br>I  ..,=====._=_~  time = 0.400000  time = 0.700000<br>%<br>(5) K  = 1.2 ~?'~',,~  ¢<br>time = O. 400000  time = O. 700000<br>(6)  K = 1.4  °<br>)<br>time = O. 400000  time = O.  ?00000<br>tile  = O. 000000  time = 1.000000<br>time = O. 000000  tise = 1.000000<br>tile  • O. 500000  tile  = L 000000<br><!-- End of picture text -->

Fig. 6. **Crystal grows from the left wall toward supercooled** melt under **adiabatic condition for** various values of K. There is 4-mode anisotropy. 6 = 0.050. 

**with each other in a way different from the isotropic one. The branches going faster than the adjacent ones suppress the~growth of the slower ones by becoming thick or having side branches. The growth rates are completely larger than the isotropic growth. The branches sometimes come off at their root by surface tension.** 

## _3.4. Dendrite growth_ 

**In the following simulations, we will show the relations between the strength of anisotropy and the shapes of crystals. Nucleation occurs at the center of the bottom edge, and it triggers the growth process. All the parameters except 6 are** 

417 

_R. Kobayashi / Simulations of dendritic crystal growth_ 



<!-- Start of picture text -->
(1) 6= o.ooo<br>time = O. 200000  time  = O. BOO000  time  =  I.  400000<br>(2)  6= 0.005<br>time  =  O. XO0000  time = 0.800000  time = 1.  400000<br>(3)  (5=  0.010<br>time  = O.  200000  time = 0,000000  time = 1.400000<br>(4) fi=- 0.020<br>time  =  0.  200000  time = 0.000000  time = 1.400000<br>(5) 6= 0.05O<br>time = 0. 200000  time = 0.800000  time = 1.400000<br><!-- End of picture text -->

Fig. 7. After nucleation, crystal grows toward supercooled melt under adiabatic condition for various values of 6. There is 4-mode anisotropy. K = 2.0. 

_R. Kobayashi / Simulations of dendritic crystal growth_ 

418 

fixed and 6 is increased gradually from zero. The horizontal and vertical direction is the one at which E has maximum value (i.e. j = 4 and 0~ = 0). Dimensionless latent heat K is fixed to be 2.0. The results are shown in fig. 7. 

In the first computation, where 3 = 0.000 i.e. perfect isotropic growth is considered, patterns similar to the viscous fingering are obtained. Tip splitting is seen as the crystal grows, and roughly speaking, the shapes of the curve which connects the tops of branches are half circles until the interaction between branches and walls occurs. The shape of the crystal for 6 = 0.005 has both features of the isotropic and of the dendritic structure. We can see the dendritic structure in the vertical branch and the viscous finger-like structure in the other branches. The results for 6 = 0.010 show one typical dendritic structure whose side branches are shifted from the direction of anisotropy. Roughly speaking, their direction is perpendicular to the isothermal lines, 

since it is the easiest direction to grow and the anisotropy is weaker than this effect. Side branches are formed at the top of the principal branch having the constant spacing. For 6 less than 0.010, we sometimes observe the mutual side branching. This non-symmetric side branching occurs more often for smaller values of 6. For = 0.020, we can see other typical dendritic structures whose side branches almost coincide with the direction of anisotropy. They occur from the destabilization of the side surface of the principal branch near the top. For 6 = 0.050, the process of forming side branches is the same as the previous one, but the side branch structure is a little different from it. Competitions and screening clearly occur between the branches which have perpendicular directions. And also when the side branch grows rather longer than other side branches, new side branches grow from it. 

Comparing these simulations, it is obvious that 



<!-- Start of picture text -->
(1) K=0.8<br>©<br>time = O. 040000  time = O. 120000  time = O. 200000<br>(2)  K = 1.0<br>©<br>time = O. 050000  time = O. 150000  0  time = O. 250000<br><!-- End of picture text -->

Fig. 8. After nucleation, crystal grows toward supercooled melt under adiabatic condition for various values of K. There is 6-mode anisotropy. 6 = 0.040. 

419 

_R. Kobayashi / Simulations of dendritic crystal growth_ 



<!-- Start of picture text -->
(3)  K = 1.2<br>(3<br>time  =  0.040000  time  = 0.080000  time  =  0.120000<br>time  =  0. 160000  time = 0. Z00000  time  = O. 2BO000<br>(4)  K = 1.6<br>O<br>time  =  0.040000  time = 0. 160000  time  = 0.360000<br>(5)  K = 2.0<br>time  =  O. OBO000  time = 0.240000  time = 0.480000<br><!-- End of picture text -->

Fig. 8 (cont.). 

the velocity of the principal branch increases as 6 increases. Also it is clear that the branch structure is very sensitively dependent on 6. 

### _3.5. Ice dendrites_ 

At last, snowflake-like patterns are presented in fig. 8. Although patterns observed here are 

similar to snowflakes, the model equations (3) and (5) do not describe the formation of snowflakes, since snowflakes are formed by vapor growth which has a different process from melt growth. In order to simulate such a process, the formation of a facet and its destabilization should be considered [19]. So the following simulations correspond to the supercooling solidifica- 

_R. Kobayashi / Simulations of dendritic crystal growth_ 

420 

tion of water. Nucleation occurs at the center of the vessel and the solidification follows. In these simulations, only the parameter K is changed and the other parameters are fixed as ~ = 0.040, j=6and 0 0=½rr. 

First, the crystal is hexagon which is strictly convex for _K=0.8._ But as K increases, the convexity is broken. In fact, for K = 1.0, we can find the dents at the center of the crystal edges. For K = 1.2, more pictures are shown than for the other parameters, since it presents various patterns during its growth process. At first we can see a hexagonal shape and then the dents at the centers of the edges. After that the dents become slits and next the tuck appears at the top of the slit. At last it shows a thick branching pattern, which is an intermediate pattern between the essentially hexagonal patterns and the branching patterns. For K=1.6, the crystal shows a branching pattern. As K increases, the branches become thinner and we can obtain a typical snowflake-like pattern for K = 2.0. Thus we can observe the change from the hexagonal shape to the branching patterns as K increases. 

### **4. Discussions** 

One may feel curious that the shape of the crystal goes simpler as K decreases, as shown in figs. 5, 6, and 8. It is because these simulations are in the parameter area in which K is close to one. (See [13].) 

Fig. 9 shows a typical dendrite whose side branches' direction almost coincides with the direction of anisotropy (8 = 0.020). As a rough sketch, we can distinguish two regions by connecting the tops of the side branches, region I and region II. In region I, all of the young side branches are growing and restrain each other, thus the growth rate is small. In region II, the competition is already over and the winners grow faster than the branches in region I, because they can have more cooling than the branches in region I. It is just like the situation where the thinned out plants grow faster by obtaining more light or nourishment. While the growth rates of the side branches are different in regions 1 and II, the velocity of the top of the principal branch is almost constant. Thus we have the two lines of different slopes. 

Here let us consider the influence of noises. If the noises are larger, the competition between the young side branches may end earlier because the noises are partial to some branches, then region I becomes smaller. If the noises are smaller, it takes a longer time to select winners and therefore region I will be larger. This is proved by fig. 9, in which the noises are added in the different amplitude a. The parameter a is becoming smaller from left to right. Region I clearly goes larger as a decreases. Comparing the pictures in fig. 9 we have the essential two properties. The one is that the velocity of the top of the main branch is exactly the same in each case. And the other is that the side branch structure is 



<!-- Start of picture text -->
a - 0.010  a -- 0.001  a - 0.000<br>\<br>time =  1.000000  time  =  1.000000  time  =  1.000000<br><!-- End of picture text -->

Fig. 9. The relation between the side branch structure and the amplitude of noise in the non-oscillating growth. K = 2.0 and 6 = 0.020. 

_R. Kobayashi / Simulations of dendritic crystal growth_ 

421 

strongly affected by the existence or amplitude of the noises. 

Fig. 10 shows crystal forms for 6 = 0.010, in which the parameter a is controlled in the same way as in fig. 9. Their side branch structures are less affected by the change of the amplitude of noise than the ones in fig. 9. It is because the growth rate of the top of the principal branch oscillates in fig. 10. while it does not in fig. 9 [18]. As the oscillation is a strong mechanism for making side branches, they are less affected by noises. In fig. 9, the side branches are strongly affected by noises, since they come from the destabilization of the side surface of the principal branch which is a more delicate process than the oscillation. 

Here let us consider the singular limit equation (4), which can be deformed to 

_bY= o'(0) If- do(O ) K] ,_ (6) 

where _do(O )_ = or(0) + o'"(0) + [cr'(0)]2/o'(O). When 6 is small, _(a')2/cr_ is negligible since it is of order 6 2, while a + o-" is 1 + (7(6). For all the values of 8 that I took in the simulations here (8 <--5 × 10-z), _(tr')2/tr_ is completely smaller than tr + o'". Fig. 11 shows graphs of tr(0) and _do(O )_ for the parameters used in the simulations corresponding to fig. 7 (5) and fig. 8. If _do(O )_ is always positive (of course, 8 values for fig. 7(1)(4) are smaller than the one of (5), thus _do(O )_ is always positive for all the simulations in fig. 7)', no corner appears along the interface as shown 

O) (2) 

Fig. 11. The curve with smaller amplitude is a graph of tr(0) = 1 + 6 cos [j(# - 0o) ] and the one with larger amplitude _do(O )._ (1) 6 = 0.050, j = 4 and 00 = 0, corresponding to fig. 7(5). (2) 6 = 0.040, j = 6 and 60 = ~r/2, corresponding to fig. 8. 

in fig. 7. If _do(O )_ is negative for some interval of 0, we can observe the formation of corners as shown in fig. 8. The parameter 8 gives crucial influence on the growth form of crystal even if it is rather small, because _do(O )_ includes a term or" which magnifies anisotropy by rn 2 times in our setting of anisotropy. 

As shown in the previous part, the model equations (3) and (5) can exhibit various solutions which represent the crystal growth realistically, although they are obtained for only a small part of the total range of the parameter values. Thus we would like to conclude that eqs. (3) and (5) are a very good model for simulating dendritic crystal growth. 

But it still has some problems. The phase field p cannot describe a structure which is finer than or the same size as the layer thickness. So we must take e sufficiently small if we want to simulate the fine structure. The computation does not go well if the physical parameters re- 



<!-- Start of picture text -->
a = 0.010  a = 0.001<br><!-- End of picture text -->



<!-- Start of picture text -->
a = 0.000<br><!-- End of picture text -->

tile ~ 1. 300000 



<!-- Start of picture text -->
time = 1. 300000  time  : 1.300000<br><!-- End of picture text -->

Fig. 10. The relation between the side branch structure and the amplitude of noise in the oscillating growth. K = 2.0 and 6 = 0.010. 

_R. Kobayashi / Simulations of dendritic crvstal growth_ 

422 

quire a finer structure than the size which the phase field can express with given e. For example, as seen in fig. 6(4), the narrow slits are buried easier than the real physical system, since the interfacial thickness is not so small compared with the width of slits. One more problem is a computational one, which comes from the fact that (3) includes small parameters. The values of _e/Sx_ and _r/St_ (Sx is a space mesh size and 8t is a time mesh size) should be taken large in order to obtain good approximations quantitatively. But in the limited CPU power, we cannot take space mesh size and time mesh size so small. In fact, in the simulations presented here, we selected the space mesh size small such that anisotropy induced by the computational lattice does not appear, but not so small such that the interracial velocity of (3) is precisely approximated. This is because we intended to see the qualitative properties of the whole crystal structure here. If we want quantitatively precise results, we should restrict the size of the computational region and take the space mesh size and the time mesh size small enough. 

Thus (3) is deformed to 



Stretching the coordinate r near the interface by the factor go- and assuming the traveling front solution in the stretched interval, we have 



where ~7 is a traveling coordinate in the stretched interval. Solving this non-linear eigenvalue problem (see [20]), we have (4) as a singular limit equation. For the general case, we can obtain the same result by taking the polar coordinate system for each point on the interface such that the origin coincides with the center of curvature. 

### **References** 

- [11 D.A. Kessler, J. Koplik and H. Levine, Phys. Rev. A 31 (1985) 1712. 

### **Appendix** 

Eq. (3) is rewritten as 



where the prime means _d/dO._ Here let us assume the axi-symmetric solution p, and deform the terms in the bracket { } using polar coordinates as follows: 

- [2] E. Ben-Jacob, N. Goldenfeld, J.S. Langer and G. Schon, Phys. Rev. A 29 (1984) 330. 

- [3] Y. Saito, G. Goldbeck-wood and H. Muller-Krumbhaar, Phys. Rev. A 38 (1988) 2148. 

- [4] L.N. Brush and R.F. Sekerka, J. Crystal Growth 96 (1989) 419. 

- [5] S. Osher and J.A. Sethian, J. Comput. Phys. 79 (1988) 12. 

- [6] G. Fix, in: Free Boundary Problems, ed. A. Fasano and M. Primicero, Research Notes in Mathematics, Vol. 2 (Pitman, New York, 1983) p. 580. 

- [7] J.B. Collins and H. Levine, Phys. Rev. B 31 (1985) 6119. 

- [8] G. Caginalp, Arch. Rat. Mech. Anal. 92 (1986) 205. [9] G. Caginalp and P.C. Fife, SIAM J. Appl. Math. 48 (1988) 506. 

- [lO] G. Caginalp, Phys. Rev. A 39 (1989) 5887. 



- [11] H. Honjo and Y. Sawada, J. Crystal Growth 58 (1982) 297. 

- [121 S.-C. Huang and M.E. Glicksman, Acta Metal. 29 (1981) 717. 

- [13] G.E. Glicksman and R,J. Schaefer, J. Crystal Growth 1 (1967) 297. 

_R. Kobayashi / Simulations of dendritic crystal growth_ 

423 

- [14] B. Chalmers, Principles of Solidification (Wiley, New York, 1964). 

- [15] R. Kobayashi, RIMS kokyuroku 614 (1987) 39 [in Japanese]. 

- [16] M. Mimura, R. Kobayashi and H. Okazaki, Dynamics of Interfaces in Systems of Reaction Diffusion, videotape (1986). 

- [17] R. Kobayashi, Simulations on Dendrite Growth, videotape (1990), 

- [18] Y. Sawada and A. Tanaka, private communication. [19] E. Yokoyama and T. Kuroda, Phys. Rev. A 41 (1990) 2038. 

- [20] P.C. Fife and J.B. Mcleod, Arch. Rat. Mech. Anal. 65 (1977) 335. 

- [21] J.S. Langer, Rev. Mod. Phys. 52 (1980). 

- [22] Dynamics of Curved Fronts, ed. Pierre Pelc~ (Academic Press, New York, 1988). 

