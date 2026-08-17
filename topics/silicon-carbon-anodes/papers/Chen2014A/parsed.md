Journal of The Electrochemical Society 



<!-- Start of picture text -->
EESBe ectroceriel Society<br><!-- End of picture text -->

#### **OPEN ACCESS** 

# A Phase-Field Model Coupled with Large ElastoPlastic Deformation: Application to Lithiated Silicon Electrodes 

To cite this article: L. Chen et al 2014 J. Electrochem. Soc. 161 F3164 

### You may also like 

- <u>A Comparative Study on Continuum-Scale Modeling of Elasto-Plastic Deformation in Rechargeable Ion Batteries</u> Ajaykrishna Ramasubramanian, Vitaliy Yurkiv, Ali Najafi et al. 

- <u>Local strain and its influence on</u> 

- <u>mechanical–electromagnetic properties of twisted and untwisted ITER Nb</u> ~~3~~ <u>Sn strands</u> K Osamura, S Machiya, Y Tsuchiya et al. 

- <u>Thermal strain exerted on superconductive filaments in practical Nb</u> ~~3~~ <u>Sn and Nb</u> ~~3~~ <u>Al strands</u> 

- K Osamura, S Machiya, Y Tsuchiya et al. 

View the <u>article online</u> for updates and enhancements. 



<!-- Start of picture text -->
The New PAT-Cell-Solid!s EL-CELL®<br>Cycle Solid-State Batteries Under Controlled Pressure of up to 300 MPa (6mm Diameter)!<br>en Ha ce ct ch nts<br>= V Adjust and measure a force of up to 9000 Non the cell stack! —__ sogmmnennnenennaman 9<br>Ra > hex Force adjustment possible throughout the entire experiment z) Cane |<br>27] cf MH<br>| 1 VY Built-in force, and temperature sensors! cae| Botm CEmd | I x5<br>a: With optional gas pressure sensor and gas in- and outlet i ier ae —1<br>ris a er<br>| PAT-Solid-Core for easy assembly and reproducible results! ,<br>r, v lid-Core f bly and reproducible resul 2 \AAAATTT a<br>a L iat Press and cycle solid-state batteries with 6 or 10mm electrode diameter Batg_VVVVVVVVVVVV\ 7<br>= V Cableless and highly sealed battery test cell! 3 =<br>= For precise long-term measurements of solid-state cell chemistries Be JAM<br>oea ae ee a oe<br>Learn more on our product website: Download the data sheet (PDF): Or contact us directly:<br>parvaSept esoarsaa bp[a] CE Pans]Ea= & +49 40 79012-734<br>sens @ = sales@el-cell.com<br>mina ras ® nell<br>Scan me! Scan me! bd percell.com<br><!-- End of picture text -->

This content was downloaded from IP address 23.165.184.98 on 17/08/2026 at 02:09 

_Journal of The Electrochemical Society_ , **161** (11) F3164-F3172 (2014) 

F3164 



<!-- Start of picture text -->
|<br><!-- End of picture text -->

~~JES FOCUS ISSUE ON MECHANO-ELECTRO-CHEMICAL COUPLING IN ENERGY RELATED MATERIALS AND DEVICES~~ 

## **A Phase-Field Model Coupled with Large Elasto-Plastic Deformation: Application to Lithiated Silicon Electrodes** 

**L. Chen,**<sup>**a,∗,z**</sup> **F. Fan,**<sup>**b**</sup> **L. Hong,**<sup>**a**</sup> **J. Chen,**<sup>**c**</sup> **Y. Z. Ji,**<sup>**a,∗∗**</sup> **S. L. Zhang,**<sup>**d**</sup> **T. Zhu,**<sup>**b,∗**</sup> **and L. Q. Chen**<sup>**a**</sup> 

_aDepartment of Materials Science and Engineering, Pennsylvania State University, University Park, Pennsylvania 16802, USA_ 

_bWoodruff School of Mechanical Engineering, Georgia Institute of Technology, Atlanta, Georgia 30332, USA cDepartment of Engineering, Pennsylvania State University, The Altoona College, Altoona, Pennsylvania 16601, USA_ 

_dDepartment of Engineering Science and Mechanics, Pennsylvania State University, University Park, Pennsylvania 16802, USA_ 

A phase-field model, accounting for large elasto-plastic deformation, is developed to study the evolution of phase, morphology and stress in crystalline silicon (Si) electrodes upon lithium (Li) insertion. The Li concentration profiles and deformation geometries are co-evolved by solving a set of coupled phase-field and mechanics equations using the finite element method. The present phase-field model is validated in comparison with a non-linear concentration-dependent diffusion model of lithiation in Si electrodes. It is shown that as the lithiation proceeds, the hoop stress changes from the initial compression to tension in the surface layer of the Si electrode, which may explain the surface cracking observed in experiments. The present phase-field model is generally applicable to high-capacity electrode systems undergoing both phase change and large elasto-plastic deformation. © The Author(s) 2014. Published by ECS. This is an open access article distributed under the terms of the Creative Commons Attribution Non-Commercial No Derivatives 4.0 License (CC BY-NC-ND, http://creativecommons.org/licenses/by-nc-nd/4.0/), which permits non-commercial reuse, distribution, and reproduction in any medium, provided the original work is not changed in any way and is properly cited. For permission for commercial reuse, please email: oa@electrochem.org. [DOI: 10.1149/2.0171411jes] All rights reserved. 

Manuscript submitted June 23, 2014; revised manuscript received September 11, 2014. Published October 4, 2014. This was Paper 325 presented at the Orlando, Florida, Meeting of the Society, May 11–15, 2014. _This paper is part of the JES Focus Issue on Mechano-Electro-Chemical Coupling in Energy Related Materials and Devices._ 

As a promising anode material for lithium (Li)-ion batteries,<sup>1–3</sup> the theoretical Li capacity of Silicon (Si) is 4200 mAh/g (corresponding to the lithiated phase of Li4.4Si), which is one order of magnitude larger than the commercialized graphite anode.<sup>1,2</sup> Recent experiments revealed that the lithiation of crystalline Si ( _c_ -Si) occurs through a two-phase mechanism, i.e., growth of lithiated amorphous LixSi ( _a-_ LixSi, _x_ ∼ 3.75) phase separated from the unlithiated _c_ -Si phase by a sharp phase boundary of about 1 nm thick.<sup>4–8</sup> An abrupt change of Li concentration across the amorphous-crystalline interface (ACI) gives rise to drastic volume strain inhomogeneity. The resulting high stresses induce plastic flow, fracture, and pulverization of Si electrodes, thereby leading to the loss of electrical contact and limiting the cycle life of Li-ion batteries.<sup>9–11</sup> 

Electrochemically driven mechanical degradation in high-capacity electrodes has stimulated enormous efforts on the development of chemo-mechanical models to understand how the stress arises and evolves in lithiated Si electrodes.<sup>12–15</sup> These chemo-mechanical models often treated the lithiation-induced stress as the diffusion-induced stress by considering Li diffusion in a solid-state electrode that results in the change of composition from its stoichiometric state. Deviation from stoichiometry usually results in a volume change that generates stress if the Li distribution is non-uniform. Early chemo-mechanical models only involved a unidirectional coupling. Namely, the diffusioninduced mechanical stress was considered, whereas the effect of mechanical stress on diffusion was ignored. Both experimental and computational studies, however, have shown that the mechanical stresses play an important role in the lithiation kinetics of Si electrodes.<sup>4,6,16,17</sup> Recently, fully coupled chemo-mechanical models were developed to incorporate the mechanical stress into the chemical potential.<sup>18–22</sup> In these models, the local stress modulates lithiation kinetics (reaction rate and diffusivity),<sup>4,6,23</sup> and in turn, lithiation kinetics regulates the stress generation in lithiated Si electrodes.<sup>6</sup> However, most efforts of coupling the diffusion with stress were made in the elastic regime of Si electrodes. 

> ∗Electrochemical Society Active Member. 

Motivated by recent experimental observations of drastic morphological changes in lithiated Si electrodes, more sophisticated models have recently been developed to account for the large elasto-plastic deformation coupled with Li diffusion.<sup>12,15,18,19,21,24</sup> Based on nonequilibrium thermodynamics, Zhao et al.<sup>15,21</sup> considered the coupled large plastic deformation and lithiation in a spherical Si electrode. Bower et al.<sup>12,18</sup> developed a theoretical framework to incorporate finite deformation, diffusion, plastic flow, and electrochemical reaction in lithiation of Si electrodes. Such models treated Li diffusion in a single phase with a gradual variation of Li concentration, which is inconsistent with the two-phase lithiation mechanism uncovered by the recent in situ transmission electron microscopy (TEM) experiments. Huang et al.<sup>25,26</sup> and Yang et al.<sup>27,28</sup> developed a non-linear concentration-dependent diffusion model in which Li diffusivity was treated as a non-linear function of Li concentration so as to effectively generate a sharp phase boundary. However, such non-linear diffusion model, implemented in a general finite element framework, failed to provide a characteristic length scale as the interface thickness varied with the lithiation time. Cui et al.<sup>24</sup> and Liu et al.<sup>4</sup> studied the lithiation of Si by considering the interfacial chemical reactions and bulk diffusion as two sequential processes. But they did not directly simulate the concurrent processes of Li diffusion and reaction. 

Phase-field method (PFM) has been applied to a vast range of phenomena in materials processes, e.g., solidification,<sup>29</sup> solid-state phase transformation,<sup>30</sup> recrystallization,<sup>31</sup> and grain growth.<sup>32,33</sup> PFM is formulated based on the theory of irreversible thermodynamics, and is advantageous in addressing the time-dependent evolving morphologies and describing the complex microstructure evolution process. In particular, the diffuse interface between adjacent phases can be conveniently captured by a gradient term without the need of cumbersome tracking of a sharp interface in every step of numerical simulations. The early attempt along this line was to couple PFM with a linear elasticity model by Van de Ven et al.,<sup>34</sup> who investigated the effect of coherency strains on phase stability in LiFePO4. Later, Bazant et al.<sup>35,36</sup> developed a thermodynamically consistent PFM, coupled with the linear elasticity, to simulate the non-linear Butler-Volmer reaction kinetics. More recently, Anand et al.<sup>37</sup> proposed a general formalism to couple phase-field with large elasto-plastic deformation. 

∗∗Electrochemical Society Student Member. zE-mail: luc28@psu.edu 

_Journal of The Electrochemical Society_ , **161** (11) F3164-F3172 (2014) 

F3165 

Di Leo et al.<sup>38</sup> subsequently implemented this formalism with a numerical approach to simulate the LiFePO4 electrode material. However, these phase-field models either assume linear elastic deformation that is not applicable to the Si electrodes undergoing large plastic deformation during lithiation, or are still at the early stage of development without numerical implementations for the high-capacity electrode materials. 

In this paper, we aim to develop a phase-field model coupled with large elasto-plastic deformation. We employ this model to simulate lithiation of Si electrodes, which involve both the large geometrical change and phase change. The Li-poor/Li-rich phase boundary is naturally captured without any special treatment (e.g., usage of an interfacial domain). We solve the elasto-plastic equilibrium equations in every step of temporal phase-field evolution by the finite element method (FEM). Our phase-field model is numerically implemented in the physical space such that it is well suited to study the effects of complex geometries and boundary conditions. Moreover, this model is thermodynamically consistent and enables the full chemo-mechanical coupling. 



<!-- Start of picture text -->
(a) Current configuration (b)<br>2< a<br>eal VAY<br>configuration Intermediate . 7<br>" configuration a “s<br><!-- End of picture text -->

**Figure 2.** Schematic diagram showing (a) decomposition of deformation gradient and definition of intermediate configuration; (b) double well chemical free energy function. 

#### **A Constitutive Model of Lithiation-Induced Elasto-Plastic Deformation** 

In this section, a constitutive model is developed to characterize the large elasto-plastic deformation in a lithiated Si electrode. 

#### **Problem Description** 

We study a simple model problem: lithiation of a nanowire electrode with a cross section of radius _A_ , as shown in Figure 1a. Upon lithiation, the Li distribution becomes non-uniform in the radial direction, but retains circular symmetry. The insertion of Li atoms causes the nanowire electrode to swell to a radius _a_ , as shown in Figure 1b. The non-uniform distribution of Li generates the stress inside the nanowire. A key feature of lithiation in the _c_ -Si electrode is the formation of a phase boundary of 1 nm in thickness,<sup>4–8,11</sup> which separates the Li-rich and Li-poor phases (see Figure 1c). The electron diffraction pattern indicates that the Li-rich phase is _a_ -Li3.75Si. This composition is further confirmed by the apparent volume expansion close to that of _c_ -Li3.75Si as well as the dynamic formation of Li3.75Si nanocrystals within the amorphous phase.<sup>4,6,9</sup> In the _c_ -Si core the lattice expansion remains negligibly small, indicating the low Li concentration and accordingly the Li-poor phase therein. Across the sharp phase boundary, Li concentration changes abruptly. In other words, the Li-poor phase does not continuously transform to the Li-rich one with a gradual change of Li content, and lithiation is mediated by the phase boundary migration. The sharp phase boundary plays a critical role in stress generation and fracture in _c_ -Si during lithiation.<sup>4,6</sup> Hence, it is important to develop a fully coupled chemo-mechanical model to simulate the co-evolution of phase, morphology and stress during the lithiation process. 

_Kinematics of deformation.—_ The kinematics for any material point in a continuum can be described by a continuous displacement field **u** given by 



where **x** is the position of the material point at time _t_ and **X** is the initial position at _t_ = 0. The deformation gradient is defined as **F** ( **X** _, t_ ) = ∇ **Xx** , where ∇ **X** is the gradient operator with respect to **X** . 

In continuum mechanics, a multiplicative decomposition of the deformation gradient is typically assumed 



where **F**<sup>_c_</sup> represents the chemically-induced deformation gradient due to the compositional inhomogeneity, **F**<sup>_p_</sup> is the plastic deformation gradient, and **F**<sup>_e_</sup> is the elastic deformation gradient. Eq. 2 indicates that the total deformation can be considered as an accumulation of an inelastic deformation followed by an elastic deformation . The state of the material point after inelastic deformation is named as the intermediate state, as shown in Figure 2a. In particular, such state is stress free and is not necessarily compatible in kinematical sense.<sup>39</sup> 

Following Eq. 2, the total Lagrange strain can be given as 





<!-- Start of picture text -->
Initial state Current state Experiment observation<br>@ ) ©<br>ee a—Li,Si+ LiO<br>g boundaryPhase 4iesOO, 3 a—Li,Si<br>a ie AC!<br>phase a<br>. Li-tich is<br>phase es<br>Initial aS<br>profile Be<br><!-- End of picture text -->

**Figure 1.** Schematic diagram showing a typical lithiation process from (a) the initial state with a lithiation-free and stress-free silicon nanowire electrode to (b) the current state in which the electrode is partially lithiated with the sharp phase boundary and a stress field is developed. The model is consistent with (c) In situ TEM observed core-shell structure in a partially lithiated Si electrode, where the crystalline core ( _c-_ Si) is surrounded by the amorphous shell (a-LixSi). The amorphous-crystalline interface (ACI), i.e., the phase boundary separating the amorphous lithiated shell and the unlithiated crystalline core, is atomically sharp (∼1 nm).<sup>4–8</sup> 

_Journal of The Electrochemical Society_ , **161** (11) F3164-F3172 (2014) 

F3166 

In the _J_ 2-flow theory, the plastic stretch rate is given by 

where 



where _Deq_<sup>_p_=</sup> �2 **D**<sup>_p_</sup> : **D**<sup>_p_</sup> _/_ 3 is the equivalent plastic stretch rate. The lithiated Si electrode is modeled as an isotropic elasto-plastic material with a simple linear hardening rule 

are, respectively, the elastic, chemical, and plastic strain tensors. 



_Stress equilibrium.—_ As the long-range Li diffusion is typically much slower than the local stress relaxation, a mechanical equilibrium holds at any time, i.e. 

where σ _y_ 0 denotes the initial yield strength, _H_ is the hardening modulus of the material, and ε¯<sup>_p_</sup> is the total accumulated equivalent plastic stretch, given by 





where **σ**<sup>0</sup> ( **X** ) is the first Piola-Kirchhoff (P-K) stress tensor, 



In the above expressions, all the field variables such as the GreenLagrange elastic strain tensor **E**<sup>_e_</sup> , the first P-K stress **σ**<sup>0</sup> , and the plastic stretch rate **D**<sup>_p_</sup> are functions of the deformation gradient tensor **F** . Once **F** is known, **E**<sup>_e_</sup> can be calculated from Eq. 4, **σ**<sup>0</sup> from Eqs. 6 and 7, and **L**<sup>_p_</sup> from Eq. 13. 

We denote _c_ and _c_ max as the current and maximum true Li concentration in the lithiated Si, respectively. The normalized Li concentration is defined as _c_ ˆ = _c/c_ max. Note that _c_ ˆ represents the fraction of lithiation at a material point relative to its fully lithiated state, which is independent of the deformation gradient **F** of the associated material point. For brevity, ˆ _c_ will still be called the Li concentration in the rest of this paper. 

#### **Phase-Field Model** 

A phase-field model usually relies on the continuous order parameter such as local concentration. In a lithiated Si electrode, Li atoms are assumed to reside in the lattice sites of a crystalline phase of LixSi - the actual phase could be amorphous, but with the same composition. The concentration field, as a conserved property, evolves by long-range diffusion. Hence, in principle, a description of diffusion and phase boundary migration within the electrode material requires two fields: the Li concentration field describing the local degree of lithiation, and a phase-field that distinguishes the crystalline state and the amorphous state. For simplicity, in this paper both the local degree of lithiation and the structural difference between the crystalline and amorphous states together are described by a single Li concentration field. The temporal and spatial evolution of the Li concentration field is obtained by solving the Cahn-Hilliard equation. It should be emphasized that since every material point in lithiated Si can locally undergo very large volume expansion up to about 300%, care must be taken in choosing the appropriate field variable that accounts for lithiation-induced large strains. In this work, we choose the normalized Li concentration _c_ ˆ as the field variable, so as to facilitate the coupling between the phase-field and constitutive models. 

_Elasto-plastic deformation.—_ We take the total deformation gradient **F** and the concentration ˆ _c_ as the independent variables, thus, the elastic energy density in the Lagrangian description (initial configuration) _Wel_ ( **F** _,_ ˆ _c_ ) can be written as 



where _E_ and _v_ are, respectively, Young’s modulus and Poisson’s ratio for the LixSi phase, both of which depend on ˆ _c_ , and _J_<sup>_c_</sup> is the chemical deformation Jacobian. The elastic energy density corresponding to the intermediate state _wel_ ( **F** _,_ ˆ _c_ ) is 



where _J_<sup>∗</sup> is the Jacobian that transforms an infinitesimal element of volume in the initial configuration to the corresponding fraction of volume in the intermediate configuration, i.e. 



In a phase-field model, the free energy functional _G_ is the total free energy of an inhomogeneous system, 

Assuming the plastic deformation is volume preserving, i.e., the plastic deformation Jacobian _J_<sup>_p_</sup> = det( **F**<sup>_p_</sup> ) = 1, one can write 





We assume the chemical deformation is isotropic that is given by 

where _fch_ (ˆ _c_ ), _fel_ ( **F** _, c_ ˆ) and _f pl_ ( **F** ) represent the local energy density from the chemical, elastic and plastic contribution, respectively. The Li concentration gradient term κ _/_ 2(∇ _c_ ˆ)<sup>2</sup> contributes to the phase boundary energy. More specifically, _fch_ (ˆ _c_ ) is the chemical free energy density of the stress-free state and is given by a double-well function 



where β is the coefficient of chemical expansion associated with Li insertion, and **I** is the second-order identity tensor. 

Next, we turn to the constitutive law (i.e., the flow rule) of plastic deformation. The rate of plastic stretch is expressed as 





While Eq. 18 is a regular solution model, the lithiated Si is amorphous and cannot be simply characterized as a regular solution. Hence we only take Eq. 18 as a mathematic function with double energy wells, which represent the Li-poor and Li-rich phases, respectively. The dimensionless parameter _�_ controls the profile of the double-well energy function. In addition, _fel_ ( **F** _, c_ ˆ) and _f pl_ ( **F** ) are, respectively, the elastic and plastic energy densities arising from the inhomogeneous lithiation 

where **L**<sup>_p_</sup> corresponds to the plastic part of the spatial gradient of velocity, given as 



The plastic stretch rate, **D**<sup>_p_</sup> , obeys the associated _J_ 2-flow rule. Namely, <u>plastic</u> yielding occurs when the equivalent stress, τ _e_ = <u>3</u> � 2<sup>**τ**′:</sup><sup>**τ**′, reaches the yield strength,</sup><sup>**σ**</sup><sup>_y_. Here</sup><sup>**τ**′is the deviatoric</sup> part of the Kirchhoff stress tensor **τ** , i.e., **τ**<sup>′</sup> = **τ** − _tr_ ( **τ** ) **I** _/_ 3. Note that the Kirchhoff stress tensor is related to the first P-K stress tensor as **τ** = **Fσ**<sup>0</sup> ( **X** ). Also, the Cauchy stress is expressed as **σ** = _J_<sup>−1</sup> **Fσ**<sup>0</sup> ( **X** ), where _J_ corresponds to the total deformation Jacobian. 



and 



_Journal of The Electrochemical Society_ , **161** (11) F3164-F3172 (2014) 

F3167 

where _�W pl_ corresponds to the increment of the plastic energy density, given by 





where the chemical driving force, including the gradient term, is given by 







where _�kk_ is the conventional Eshelby’s stress tensor,<sup>40,41</sup> as 



Regarding Eq. 24, the terms of the order **σ**<sup>0</sup> **E** or higher can be neglected if both the elastic and chemical strains are small, such that _J_<sup>_c_</sup> = 1 and different stress measures are equivalent. Under these conditions, one can show that Eq. 24 can be reduced to the classic equation by Larche and Cahn<sup>42</sup> 



We assume that the plastic energy density is independent of _c_ ˆ, so that 



The Li diffusion equation is derived by 



with the concentration flux _J f lux_ related to the Li potential μaccording to 



where _M_ Li is the Li mobility tensor that is in general a function of Li concentration _c_ ˆ, as 



_Decomposition of the Cahn-Hilliard formulation.—_ The CahnHilliard formulation involves a fourth-order, non-linear parabolic equation. Unfortunately, the present FEM-based numerical platform is not directly applicable to the fourth-order equations. Hence, we deal with the Cahn-Hilliard equation by decomposing it into a set of two second-order equations: one is the parabolic equation expressed as 



and the other is 



The occurrence of two phases results from a non-convex, doublewell chemical free energy of Eq. 18 shown in Figure 2b. Experiments show that the Li-rich phase likely consists of amorphous Li3.75Si at room temperature, whereas the theoretical lithiation product is Li4.4Si. Hence, the normalized Li concentration for the actual Li-rich phase is 3.75/4.4 = 0.872. Thus, the coefficient _�_ in Eq. 18 is chosen as _�_ = 2 _._ 6 in order to enforce the Li-rich phase to take such a concentration value, as shown in Figure 2b. 

_Boundary conditions.—_ In the present numerical platform, two types of boundary conditions are imposed, one corresponds to the Cahn-Hilliard (phase-field) equation, and the other to the mechanical stress equilibrium. For the former, since the governing equation is of the fourth-order, two boundary conditions are required to solve the resulting two second-order partial differential equations after decomposition. 



where **n** is the outward normal at the outer surface _�_<sup>_d_</sup> of the Si electrode. 

- 1) In experiments, Li was observed to quickly cover the outer surface of the Si nanowire electrode due to its much lower migration barriers on the Si surface than in the bulk.<sup>9,10,43</sup> We thus prescribe a Dirichlet boundary condition that assumes a saturated Li concentration of _c_ ˆβ , corresponding to Li-rich phase (see Figure 2b), on the Si outer surface throughout the lithiation process; 

- 2) The flux of potential is set to be zero on the Si electrode outer surface _�_<sup>_d_</sup> . 

Further, regarding the mechanics boundary conditions, we assume the outer surface _�_<sup>_d_</sup> of the Si electrode is traction free 

where _D_ is the inter-diffusion coefficient. 

Combining Eqs. 22–30 yields the Cahn-Hilliard type of phase-field equation 



#### **Numerical Implementation** 

The phase-field equations coupled with the constitutive equations of elasto-plastic deformation are solved by using a FEM-based numerical method through a commercial software package, COMSOL. Compared to the commonly used spectral method for the phase-field simulations, the FEM-based approach facilitates the integration of the combined phase-field and mechanics equations, such that it is well suited to solve problems with large elasto-plastic deformation and finite-sized geometry of an arbitrary shape under various initial and boundary conditions. 



Due to circular symmetry, only a quarter of each Si nanowire electrode is simulated and the symmetrical boundary conditions are imposed in order to reduce the computational cost. 

_Transformation to the weak form.—_ Plane 3-node triangular elements with four degrees of freedom ( _c,_ μ _, ui_ ) per node are used in the 2D discretization. Time integration is accomplished using an implicit first-order scheme. The weak (variational) form of the problem reads: 

find **d** = [ˆ _c,_ μ _, ui_ ]<sup>_T_</sup> ∈ _V_ × _V_ where 



such that: 



_Journal of The Electrochemical Society_ , **161** (11) F3164-F3172 (2014) 

F3168 

**Table I. Phase-field simulation parameters and their normalized values.** 

||Real value|Normalized value|
|---|---|---|
|Parameter<br>Symbol|Value|Symbol<br>Value|
|Mobility<br>_M_|2_._186×1<br>|0<sup>−26</sup>m<sup>5</sup>_/_J×s<br>_M_<sup>∗</sup>= _M/M _<sup>_N_</sup><br>10.0<br><br>|
|Gradient energy coefficient<br>κ|2_._0×10<sup>−</sup>|J_/_m<br>κ<sup>∗</sup>=κ_/_(_RT c_max×_l_<sup>2</sup>)<br>0.0005|
|Expansion coefficient<br>β|0.5874|0.5874|
|Elastic modulus<br>_E_|160∼40|GPa<br>σ<sup>∗</sup><br>_y_ <sup>= σ</sup>_y_<sup>_/RT c_max</sup><br>175|
|Poisson’s ratio<br>ν|0_._24∼0_._2|2<br>0.24|
|Yield strength<br>σ_y_|1_._5 GPa|σ<sup>∗</sup><br>_y_ <sup>= σ</sup>_y_<sup>_/RT c_max</sup><br>1.64|
|Strain hardness<br>_H_|1_._0 GPa|_H_<sup>∗</sup>= _H/RT c_max<br>1.092|
|Radius<br>_A_|70 nm|_A_<sup>∗</sup>= _A/l_<br>1<br><br>|
|Time step<br>_�t_<br>A|2.45 s|_�t_<sup>∗</sup>=_�t/_(_l_<sup>2</sup>_/M _<sup>_N _</sup>_RT c_max)<br>10<sup>−3</sup><br>A<br>A|
|�<br>0_�_<br>μ· _p d_<sup>0</sup>_�_+<br>�<br>0_�_<br>κ∇ˆ_c_· ∇_p d_<sup>0</sup>_�_<br>J,<br>2°,<br>8<br>2<br>2|∀_p_ ∈_V_ =|_Validation of the phase-field model.—_ In this work, we focus on<br>validating the phase-field model so as to provide a solid basis for its<br>|
|−<br>�<br>0_�_<br>�<br>_c_max_RT_<br>�<br>_�_(1−2ˆ_c_)+In<br>ˆ_c_<br>1−ˆ_c_<br>�<br>+μ_el_<br>�<br>fl<br>(<br>~~—)~~<br><br>|· _p d_<sup>0</sup>_�_=0<br>[38]<br>Js<br>|applications to the complex boundary-value problems in the future.<br>Figure 3 shows the radial distribution of normalized Li concentra-<br>tion, ˆ_c_, at different lithiation times of _t_ = 500_,_ 5000_,_ 9000_�t_. A<br>sharp interface is simulated between the Li-poor and Li-rich phases at<br>each snapshot, thus yielding a core/shell structure as experimentally<br>observed during lithiation of Si nanowires.<sup>3,5 </sup>Further, the lithiation<br>~~2~~A|
|�<br>0_�_<br>˙σ<sup>0</sup><br>_i j_ <sup>· ∇</sup><br>�_∂v j_<br>_∂Xi_<br>�<br>_d_<sup>0</sup>_�_=0<br> <br>f,<br>~~(-)~~<br>8<br>2|∀_vi_ ∈_V_ =<br>[39]<br>|front distance at the time interval of_t_ =5000−9000_�t_ is markedly<br>smaller than that from_t_ =500−5000_�t_, indicating the slowing down<br>of lithiation as lithiation proceeds, which agrees with the experimen-<br>tally observed self-limiting lithiation phenomenon.<sup>4,6 </sup>The lithiation-<br>A<br>°|
|where the superscript 0 indicates that the integration e<br>eference (initial) configuration. Rates are indicated by<br>ot. The prefix ∇on _q, p, vi_ identifies the test (a|xtents are in the<br>i     the superposed<br>rbitrary virtual)|induced compressive stress at the reaction front is expected to play<br>a role in lowering the lithiation rate.<sup>4,6 </sup>A systematic investigation of<br>such retardation effect will be reported in a forthcoming publication.|



where the superscript 0 indicates that the integration extents are in the reference (initial) configuration. Rates are indicated by the superposed dot. The prefix ∇ on _q, p, vi_ identifies the test (arbitrary virtual) function. 

We next compare the radial stress distributions predicted from the present phase-field with the previously developed non-linear diffusion model.<sup>25</sup> As shown in Figure 4, three stress components are included, i.e., the radial stress, σ _r_ , the hoop stress σθ, and the von Mises effective stress, σ _e_ = |σ _r_ − σθ|. Specifically, Figure 4a and 4b show the results of the present phase-field model at _t_ = 500 _�_ A _t_ and _t_ = 9000 _�_ A _t_ , respectively, giving the phase boundary position at _R/A_ = 0 _._ 85 and _R/A_ = 0 _._ 5. Figure 4c and 4d show the corresponding numerical results from the non-linear diffusion model.<sup>25</sup> 

#### **Numerical Results** 

_Model parameters.—_ We adopt an isotropic elasto-plastic model along with a linear hardening law to describe the lithiation-induced deformation in Si electrodes, as described before. For material properties in the elastic range, Young’s modulus and Poisson’s ratio are both assumed to vary linearly with Li concentration from 160 to 40 GPa and from 0.24 to 0.22,<sup>20,43</sup> respectively. However, the material properties in the plastic range are not available. Hence, we use typical values for the yield strength σ _y_ = 1 _._ 5 GPa, and the hardening modulus _H_ = 1.0 GPa, which provide a reasonable fit to recent experiments.<sup>1,17,44</sup> 

Figure 4a and 4c are representative of the early stage of lithiation, while Figure 4b and 4d the late stage of lithiation. The present phase-field model exhibits the overall consistency with the previous non-linear diffusion model. The small difference arises possibly from the fact that a rate-dependent plasticity model without strain hardening was employed in the previous non-linear diffusion model, whereas a rate-independent plasticity model with linear (but weak) strain hard- 

The coefficient of compositional expansion is taken as β = 0 _._ 5874 which yields a volume increase of 300% in the fully lithiated phase. The gradient energy coefficient κ is assumed to be 2 _._ 0 × 10<sup>−9</sup> Jm<sup>−1</sup> . The mobility _M_<sup>0</sup> = _D/c_ max _RT_ for the Cahn-Hilliard equation (see Eq. 30) is chosen to be 2 _._ 186 × 10<sup>−26</sup> m<sup>5</sup> _/_ J · s, which corresponds to the inter-diffusion coefficient _D_ of 2 × 10<sup>−17</sup> m<sup>2</sup> _/_ s. The initial radius of Si electrode is _A_ = 70 nm. The time step _�t_ for integration is taken as 2 _._ 45 s. A In both phase-field and non-linear diffusion models, the equations 



<!-- Start of picture text -->
1.0<br>g 08<br>g A<br>2<br>S04g8 06 1=9000A1 @:t J<br>3 1 = 50041<br>g }<br>iF i<br>E5 02 1= 500A,<br>Zz<br>0.0<br>0.0 0.2 0.4 06 08 1.0<br><!-- End of picture text -->

In both phase-field and non-linear diffusion models, the equations are solved in their dimensionless forms. Both moduli and stresses are normalized by _c_ max _RT_ that is estimated as follows. The volume of one mole Si atoms in solid is given by _V_ = _m_ si _/_ ρsi = 1 _._ 2 × 10<sup>−5</sup> m<sup>3</sup> _/_ mole, where _m_ si and ρsi are molar mass and density of Si, respectively. It is known that the compound with maximum Li concentration among all the possible Li/Si compounds during the electrochemical reactions is Li4.4Si. Thus, the maximum nominal Li concentration _c_ max is determined by _c_ max = 4 _._ 4 _/V_ = 0 _._ 3667 × 10<sup>6</sup> mole _/_ m<sup>3</sup> , thus _c_ max _RT_ = 0 _._ 915 GPa. 

The length parameters are normalized by _l_ = 70 nm, yielding a normalized Si electrode radius of _A_<sup>∗</sup> = _A/l_ = 1. The mobility _M_<sup>0</sup> is normalized by a factor _M_<sup>_N_</sup> = 2 _._ 186 × 10<sup>−27</sup> m<sup>5</sup> _/_ J · s as _M_<sup>∗</sup> = _M_<sup>0</sup> _/M_<sup>_N_</sup> = 10 _._ 0. To further normalize time, the factor _td_ = _l_<sup>2</sup> _/M_<sup>_N_</sup> _c_ max _RT_ is employed as _�_ AA _t_<sup>∗</sup> = _�t/td_ = 10<sup>−3</sup> . The physical parameters and their normalized value are summarized in Table I. 

**Figure 3.** Radial distribution of Li concentration, _c_ ˆ = _c/c_ max, at different lithiation times. 

_Journal of The Electrochemical Society_ , **161** (11) F3164-F3172 (2014) 

F3169 



<!-- Start of picture text -->
(a) (b)<br>0.10 0.10:<br>i 0.05 0.08;<br>i oN a<br>i 0.00 :B ooo<br>2S -0.05 % 2S 0.05. ue<br>‘ich<br>0.10 0.10:<br>00 02 04 06 08 10 0.0 02 04 06 08 1.0<br>(c) RIA (a) RIA<br>0.10 fe, 0.10 o,<br>i 0.05 g 005<br>5 0.00 el] 5 0.00 a<br>5 005 o,' S 005 o,<br>0.10 ich 9.10<br>0.0 02 04 06 08 1.0 00 02 04 06 08 10<br>RIA RIA<br><!-- End of picture text -->

**Figure 4.** Comparison of radial distributions of the von Mises effective stress, σ _e_ , radial stress, σ _r_ and hoop stress σθ obtained by: (a) the phase-field model at time of _t_ = 500 _�_ A _t_ with phase boundary located approximately at _R/A_ = 0 _._ 85, (b) the phase-field model at time of _t_ = 9000 _�_ A _t_ with phase boundary around at _R/A_ = 0 _._ 5, (c) the non-linear diffusion model<sup>25</sup> with phase boundary at _R/A_ = 0 _._ 85 and (d) the non-linear diffusion model<sup>25</sup> with phase boundary at _R/A_ = 0 _._ 5. All the stress components are normalized by Young’s modulus of Si, _E_ si. 

ening is used in the present phase-field model, that is necessary for numerical stability. Furthermore, the mesh density and geometry could contribute to numerical differences between the two models, e.g., the phase-field results exhibit small fluctuations in stress distribution and a further improvement on numerical stability is necessary in the future. 

For completeness, the main findings from Figure 4 are summarized as follows: 

- 1) As lithiation proceeds to the late stage, Figure 4b and 4d show that the hoop stress σθ is tensile in the surface layer of a Si electrode, opposite to the compressive hoop stress at the early stage, as shown in Figure 4a and 4c. This reversal of hoop compression to tension explains the surface cracking of Si electrodes as observed in in situ lithiation experiments. 

- 2) The traction-free boundary condition dictates that the radial stress, σ _r_ , at the surface of a Si electrode vanishes all the time. Also, the radial stress, σ _r_ is always equal to the hoop stress σθ in the Li-poor phase, due to the symmetry of the system. 

- 3) Both the radial stress σ _r_ and hoop stress σθ in the Li-poor phase change from tension to compression, as the lithiation proceeds. 

Further, to visualize the evolution of the hoop stress in the time domain, Figure 5 plots the hoop stress at the center and at the surface of the Si electrode with respect to the lithiation time. It is seen that the hoop stress at the center is positive, increases to a (positive) maximum at the initial stage, and then changes its sign, i.e., decreases quickly to a negative value. In contrast, the hoop stress at the surface is initially 

negative, reaches a (negative) maximum, then starts to reverse and becomes positive rapidly. At the initial stage of lithiation, compressive plastic yielding occurs near the surface layer that undergoes large compressive stress. As the lithiation proceeds, the newly lithiated region at the moving phase boundary starts to expand. However, the surface layer has already been fully lithiated and thus acts as a thin shell to constraint the expansion occurring at the moving phase boundary inside the Si electrode. As a result, a tensile hoop stress is generated near the surface layer, resembling the inflation of a balloon causing the wall stretch. 

_Phase boundary width.—_ The phase-field model can yield a phase boundary between the Li-poor and Li-rich phases with a well-defined boundary width λ, while such an essential material length scale is missing in the previous non-linear diffusion model. The phase boundary width can be theoretically estimated according to<sup>30</sup> 



where ˆ _c_ α and ˆ _c_ β are the normalized Li concentration of the Li-poor and Li-rich phases, respectively, as indicated in Figure 2b; κ is the gradient energy coefficient defined earlier; and _�_ A _g_ is the barrier height in the chemical free energy shown in Figure 2b. The theoretical value of λ 

_Journal of The Electrochemical Society_ , **161** (11) F3164-F3172 (2014) 

F3170 



<!-- Start of picture text -->
(a) surface (b) center<br>= 040 0.10<br>3) =<br>0.05. x<br>3 ©<br>6 0.0or5 553 0.05.<br>a<br>A<br>8 0.10 g qd<br>3 0.15. 8 0.00. im<br>g -020 8 Tomi<br>S 025 E<br>= 2 0.05<br>0 2000 4000 6000 8000 0 2000 4000 6000 8000<br>Time step Time step<br><!-- End of picture text -->

**Figure 5.** The evolution of the hoop stress, σθ, at the (a) surface and (b) center of Si electrode. All the stress components are normalized by Young’s modulus of Si, _E_ si. 



<!-- Start of picture text -->
Ee 1.44|--7- Analytical solution<br>e —— Phasefiled model<br><<br>sg 12<br>3 wooo<br>= - oe og+++ a 4<br>= 10<br>i<br>3<br>5<br>g 08. Aamaiyica = (Ey ~ 6x) VK/2Ag =1.12nm<br>8<br>= 06<br>Eo<br>0 2000 4000 6000 8000<br>Time (unit: ar)<br><!-- End of picture text -->

**Figure 6.** Comparison of evolution of phase boundary width, λ, from the analytical estimate and phase-field model. 

agrees well with the experimental measurement, and it also provides a basis for the validation of the present phase-field model. 

Figure 6 shows the evolution of phase boundary width λ from the present phase-field model, which is compared with the theoretical estimation. The simulation result is consistent with the theoretical value during the entire lithiation process. More importantly, in the non-linear diffusion model, the phase boundary width can increase to several times the initial value with lithiation. In contrast, the variation of phase boundary width in the present phase-field model is almost negligible. Hence, the material length scale related to this phase boundary thickness is well captured by the present phase-field model. 

_Effect of plasticity on stress evolution.—_ In order to illustrate the effect of plasticity, we compare the results of pure elasticity and elastoplaticity. Figure 7 shows the radial distribution of three stress comrepresent,ponents at respectively, _t_ = 500 _�_ 4 _t_ andthe _t_ stresses= 9000distribution _�_ 4 _t_ . The solidfromandthedashedpure lineselasticity and elasto-plasticity models. In addition, Figure 5 shows the hoop stress evolution at both the center and surface of the Si electrode 



<!-- Start of picture text -->
@) (b)<br>02 3, 02<br>g o,. g2 ol 1<br>i 0.0 i 0.0 eel<br>Ss 0 o Ss 01<br>0.2 ich o<br>0.0 02 04 06 08 1.0 0.0 02 04 06 08 1.0<br>RIA RIA<br><!-- End of picture text -->

**Figure 7.** The effect of plasticity on radial distributions of the von Mises effective stress, σ _e_ , radial stress, σ _r_ and hoop stress σθ at different lithiation times of (a) _t_ = 500 _�_ A _t_ , (b) _t_ = 9000 _�_ A _t_ . The solid and dash lines represent, respectively, the stresses distributions by the models with only elasticity and with elasto-plasticity. All the stress components are normalized by Young’s modulus of Si, _E_ si. 

_Journal of The Electrochemical Society_ , **161** (11) F3164-F3172 (2014) 

F3171 



<!-- Start of picture text -->
0.4<br>—a— t=500at<br>—*—t= 5000at<br>4 034 —2e— t=9000at<br>3<br>2 | z<br>3s i}4<br>‘a 02 i<br>€<br>oy<br>&5 |<br>gz 04 } |<br>en<br>0.0.0.0 02 04 06 08 1.0<br>RIA<br><!-- End of picture text -->

**Figure 8.** Radial distribution of equivalent plastic strain at different lithiation moments. 

Our model allows the phase-field method to simultaneously account for the stress induced by lithiation as well as the Li transport mediated by stress. A systematic investigation of the coupling between stress and Li diffusion/reaction kinetics is beyond the scope of this study, and will be reported in a forthcoming publication. Our phase-field model is generally applicable to the high-capacity electrode systems undergoing large elasto-plastic deformation.<sup>23,45,46</sup> 

#### **Acknowledgment** 

The authors are grateful for the financial support by NSF under CMMI-1235092, 1100205, 1201058, DMR-1410936, and DOE Basic Sciences under the CMCSN Program. The computer simulations were carried out on the LION clusters at the Pennsylvania State University. 

#### **References** 

1. V. A. Sethuraman, L. J. Hardwick, V. Srinivasan, and R. Kostecki, _Journal of Power Sources_ , **195** , 3655 (2010). 

2. J.-M. Tarascon and M. Armand, _Nature_ , **414** , 359 (2001). 

during the entire lithiation process. As expected, plastic yielding significantly reduces the stress levels at all lithiation stages. Plasticity also alters the distribution of stress. In comparison, in the absence of plasticity, the hoop stress σθ is always compressive at the surface layer of the Si electrode and tensile in the Li-poor phase. This result implies that fracture would initiate at the center of the Li-poor phase, which contradicts with both the experimental observations and the prediction with plasticity included (as discussed in detail previously), that is, the reversal of hoop compression to tension in the surface layer. 

Another interesting observation is that the central region of the Si electrode, corresponding to the Li-poor phase, remains elastic. More specifically, from the radial distribution of equivalent plastic strain at different lithiation moments, shown in Figure 8, it is clear that the boundary between the elastic and plastic regions moves toward the center in the Si electrode, in consistent with the movement of the phase boundary (i.e., the abrupt change of the Li concentration profile) in Figure 3. Interestingly, the center region still remains elastic even at the late stage. This is because the stress field near the center region is almost hydrostatic (σ _e_ = |σ _r_ − σθ| = 0), which does not facilitate plastic deformation in terms of the deviatoric stress-dependent yielding criterion. 

3. C. K. Chan, H. Peng, G. Liu, K. McIlwrath, X. F. Zhang, R. A. Huggins, and Y. Cui, _Nature nanotechnology_ , **3** , 31 (2008). 

4. X. H. Liu, F. Fan, H. Yang, S. Zhang, J. Y. Huang, and T. Zhu, _Acs Nano_ , **7** , 1495 (2013). 

5. X. H. Liu, J. W. Wang, S. Huang, F. Fan, X. Huang, Y. Liu, S. Krylyuk, J. Yoo, S. A. Dayeh, and A. V. Davydov, _Nature nanotechnology_ , **7** , 749 (2012). 

6. M. T. McDowell, I. Ryu, S. W. Lee, C. Wang, W. D. Nix, and Y. Cui, _Advanced Materials_ , **24** , 6034 (2012). 

7. J. W. Wang, Y. He, F. Fan, X. H. Liu, S. Xia, Y. Liu, C. T. Harris, H. Li, J. Y. Huang, and S. X. Mao, _Nano Letters_ , **13** , 709 (2013). 

8. L.-F. Cui, R. Ruffo, C. K. Chan, H. Peng, and Y. Cui, _Nano Letters_ , **9** , 491 (2008). 

9. X. H. Liu, H. Zheng, L. Zhong, S. Huang, K. Karki, L. Q. Zhang, Y. Liu, A. Kushima, W. T. Liang, J. W. Wang, J.-H. Cho, E. Epstein, S. A. Dayeh, S. T. Picraux, T. Zhu, J. Li, J. P. Sullivan, J. Cumings, C. Wang, S. X. Mao, Z. Z. Ye, S. Zhang, and J. Y. Huang, _Nano Letters_ , **11** , 3312 (2011). 

10. X. H. Liu, L. Zhong, S. Huang, S. X. Mao, T. Zhu, and J. Y. Huang, _Acs Nano_ , **6** , 1522 (2012). 

11. M. J. Chon, V. A. Sethuraman, A. McCormick, V. Srinivasan, and P. R. Guduru, _Physical Review Letters_ , **107** , 045503 (2011). 

12. A. F. Bower, P. R. Guduru, and V. A. Sethuraman, _Journal of the Mechanics and Physics of Solids_ , **59** , 804 (2011). 

13. H. Haftbaradaran, J. Song, W. Curtin, and H. Gao, _Journal of Power Sources_ , **196** , 361 (2011). 

14. Y. Yao, M. T. McDowell, I. Ryu, H. Wu, N. Liu, L. Hu, W. D. Nix, and Y. Cui, _Nano Letters_ , **11** , 2949 (2011). 

15. K. Zhao, M. Pharr, J. J. Vlassak, and Z. Suo, _Journal of Applied Physics_ , **109** , 016110 (2011). 

16. J. L. Goldman, B. R. Long, A. A. Gewirth, and R. G. Nuzzo, _Advanced Functional Materials_ , **21** , 2412 (2011). 

17. V. A. Sethuraman, V. Srinivasan, A. F. Bower, and P. R. Guduru, _Journal of the Electrochemical Society_ , **157** , A1253 (2010). 

#### **Conclusions** 

We have developed a phase-field model coupled with large elastoplastic deformation in an open system. The model accounts for the concurrent processes of material insertion, phase change, and large elasto-plastic swelling. The concentration profiles and deformation geometries were co-evolved by a set of integrated phase-field and mechanics equations. In order to facilitate the study of complex geometries and boundary conditions, these equations are numerically solved by the finite element method. 

As an example, the phase-field model was applied to studying the stress evolution in a _c_ -Si electrode upon lithiation. It is shown that as the lithiation proceeds, the hoop stress can change from the initial compression to tension in the surface layer of a Si electrode, which explains the experimentally observed surface cracking. 

The sharp phase boundary between the Li-poor and Li-rich phases is naturally captured in the present phase-field model, in contrast to the previous non-linear diffusion model where an elaborate interfacial domain is needed to model the phase boundary. The phase boundary width in the present model is shown to be nearly unchanged during lithiation, in contrast to the non-linear diffusion model where the phase boundary width changes with the lithiation extent. 

Finally, we note that the present phase-field model is thermodynamically consistent, thus enabling a full chemo-mechanical coupling. 

18. A. Bower and P. Guduru, _Modelling and Simulation in Materials Science and Engineering_ , **20** , 045004 (2012). 

19. Z. Cui, F. Gao, and J. Qu, _Journal of the Mechanics and Physics of Solids_ , **60** , 1280 (2012). 

20. V. Shenoy, P. Johari, and Y. Qi, _Journal of Power Sources_ , **195** , 6825 (2010). 

21. K. Zhao, M. Pharr, S. Cai, J. J. Vlassak, and Z. Suo, _Journal of the American Ceramic Society_ , **94** , s226 (2011). 

22. Y. An and H. Jiang, _Modelling and Simulation in Materials Science and Engineering_ , **21** , 074007 (2013). 

23. M. Gu, H. Yang, D. E. Perea, J.-G. Zhang, S. Zhang, and C. Wang, _Nano Letters_ (2014). 

24. Z. Cui, F. Gao, and J. Qu, _Journal of the Mechanics and Physics of Solids_ , **61** , 293 (2013). 

25. S. Huang, F. Fan, J. Li, S. Zhang, and T. Zhu, _Acta materialia_ , **61** , 4354 (2013). 

26. S. Huang and T. Zhu, _Journal of Power Sources_ , **196** , 3664 (2011). 

27. H. Yang, S. Huang, X. Huang, F. Fan, W. Liang, X. H. Liu, L.-Q. Chen, J. Y. Huang, J. Li, and T. Zhu, _Nano Letters_ , **12** , 1953 (2012). 

28. H. Yang, X. Huang, T. Zhu, and S. Zhang, _Journal of the Mechanics and Physics of Solids_ (2014). 

29. I. Steinbach and M. Apel, _Physica D: Nonlinear Phenomena_ , **217** , 153 (2006). 

30. L.-Q. Chen, _Annual review of materials research_ , **32** , 113 (2002). 

31. Y. Suwa, Y. Saito, and H. Onodera, _Computational materials science_ , **44** , 286 (2008). 

32. S. Hu and L. Chen, _Acta materialia_ , **49** , 1879 (2001). 

33. C. Krill Iii and L.-Q. Chen, _Acta materialia_ , **50** , 3059 (2002). 

34. A. Van der Ven, K. Garikipati, S. Kim, and M. Wagemaker, _Journal of the Electrochemical Society_ , **156** , A949 (2009). 

35. M. Z. Bazant, _Accounts of chemical research_ , **46** , 1144 (2013). 

36. D. A. Cogswell and M. Z. Bazant, _Acs Nano_ , **6** , 2215 (2012). 

37. L. Anand, _Journal of the Mechanics and Physics of Solids_ , **60** , 1983 (2012). 

_Journal of The Electrochemical Society_ , **161** (11) F3164-F3172 (2014) 

F3172 

38. C. V. Di Leo, E. Rejovitzky, and L. Anand, _Journal of the Mechanics and Physics of Solids_ (2014). 

39. T. Belytschko, W. K. Liu, B. Moran, and K. Elkhodary, _Nonlinear finite elements for continua and structures_ , John Wiley & Sons (2013). 

40. J. Eshelby, _Journal of Elasticity_ , **5** , 321 (1975). 

41. J. D. Eshelby, _Philosophical Transactions of the Royal Society of London. Series A, Mathematical and Physical Sciences_ , **244** , 87 (1951). 

42. F. Larch´e and J. Cahn, _Acta Metallurgica_ , **21** , 1051 (1973). 

43. Q. Zhang, W. Zhang, W. Wan, Y. Cui, and E. Wang, _Nano Letters_ , **10** , 3243 (2010). 

44. V. A. Sethuraman, M. J. Chon, M. Shimshak, V. Srinivasan, and P. R. Guduru, _Journal of Power Sources_ , **195** , 5062 (2010). 

45. W. Liang, L. Hong, H. Yang, F. Fan, Y. Liu, H. Li, J. Li, J. Y. Huang, L.-Q. Chen, and T. Zhu, _Nano Letters_ , **13** , 5212 (2013). 

46. W. Liang, H. Yang, F. Fan, Y. Liu, X. H. Liu, J. Y. Huang, T. Zhu, and S. Zhang, _Acs Nano_ , **7** , 3427 (2013). 

