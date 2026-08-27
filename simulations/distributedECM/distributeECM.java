/*
 * distributeECM.java
 */

import com.comsol.model.*;
import com.comsol.model.util.*;

import java.io.IOException;
import java.util.Properties;

/** Model exported on Aug 27 2026, 17:05 by COMSOL 6.4.0.293. */
public class distributeECM {

  public static Model run() {
    Model model = ModelUtil.create("Model");

    model.modelPath(".");

    model.label("Distributed ECM_debug.mph");

    model.param().set("sigma", "1[S/m]");
    model.param().set("t_top", "0.1[m]");
    model.param().set("tau", "1365[s]");
    model.param().set("SOC0", "0");
    model.param().set("cs_max", "3E5[mol/m^3]");
    model.param().set("n_shape", "3", "shape order of particle");
    model.param().set("Q_cell", "60[Ah]");
    model.param().set("i_1C", "Q_cell/3600[s]");
    model.param().set("i_tot", "Q_cell*C_rate/3600[s]");
    model.param().set("C_rate", "1");
    model.param().set("T0", "298[K]");
    model.param().set("J0_init", "1.266");
    model.param().set("eta_IR_1C", "0.508[V]");
    model.param().set("I_cell", "i_1C*C_rate");
    model.param().set("hetero_amp", "0.8", "linear impedance heterogeneity amplitude; 0 is uniform");
    model.param().set("dt_out", "20[s]");
    model.param().set("t_final", "1200[s]");
    model.param().set("max_step", "5[s]");
    model.param().set("ramp_time", "1[s]", "smooth startup interval for DAE-consistent initialization");
    model.param().group().create("par2");
    model.param("par2").set("t_tab", "4[mm]");
    model.param("par2").set("L_JR", "4[cm]");
    model.param("par2").set("W_JR", "5[cm]");
    model.param("par2").set("t_CC", "15[um]");
    model.param("par2").set("t_pos", "60[um]");
    model.param("par2").set("t_sep", "15[um]");
    model.param("par2").set("t_neg", "50[um]");
    model.param("par2").set("r_particle", "1[m]", "Radius of postive electrode particle");
    model.param("par2").set("A_JR", "L_JR*W_JR");
    model.param("par2").set("t_JR", "t_pos+t_sep+t_neg");
    model.param("par2").label("Cell dimension");

    model.component().create("comp1", true);

    model.component("comp1").geom().create("geom1", 3);

    model.component().create("xdim1", "ExtraDim");

    model.component("comp1").geom().create("geom2", 1);

    model.result().table().create("evl3", "Table");

    model.component("comp1").func().create("int1", "Interpolation");
    model.component("comp1").func().create("int2", "Interpolation");
    model.component("comp1").func().create("int3", "Interpolation");
    model.component("comp1").func("int1")
         .set("table", new String[][]{{"0", "2.5166"},
         {"0.01", "2.7379"},
         {"0.02", "2.9137"},
         {"0.03", "3.0102"},
         {"0.04", "3.0755"},
         {"0.05", "3.1226"},
         {"0.06", "3.155"},
         {"0.07", "3.1701"},
         {"0.08", "3.1775"},
         {"0.09", "3.182"},
         {"0.1", "3.1856"},
         {"0.11", "3.1894"},
         {"0.12", "3.1935"},
         {"0.13", "3.1985"},
         {"0.14", "3.2042"},
         {"0.15", "3.2103"},
         {"0.16", "3.2167"},
         {"0.17", "3.2229"},
         {"0.18", "3.2285"},
         {"0.19", "3.2333"},
         {"0.2", "3.2376"},
         {"0.21", "3.242"},
         {"0.22", "3.2465"},
         {"0.23", "3.2506"},
         {"0.24", "3.254"},
         {"0.25", "3.2566"},
         {"0.26", "3.2591"},
         {"0.27", "3.2614"},
         {"0.28", "3.2634"},
         {"0.29", "3.265"},
         {"0.3", "3.2663"},
         {"0.31", "3.2674"},
         {"0.32", "3.2684"},
         {"0.33", "3.2694"},
         {"0.34", "3.2703"},
         {"0.35", "3.2713"},
         {"0.36", "3.272"},
         {"0.37", "3.273"},
         {"0.38", "3.2737"},
         {"0.39", "3.2746"},
         {"0.4", "3.2753"},
         {"0.41", "3.2761"},
         {"0.42", "3.2768"},
         {"0.43", "3.2776"},
         {"0.44", "3.2783"},
         {"0.45", "3.279"},
         {"0.46", "3.2798"},
         {"0.47", "3.2805"},
         {"0.48", "3.2813"},
         {"0.49", "3.2822"},
         {"0.5", "3.2831"},
         {"0.51", "3.2839"},
         {"0.52", "3.285"},
         {"0.53", "3.2862"},
         {"0.54", "3.2875"},
         {"0.55", "3.289"},
         {"0.56", "3.2909"},
         {"0.57", "3.2933"},
         {"0.58", "3.2962"},
         {"0.59", "3.2993"},
         {"0.6", "3.302"},
         {"0.61", "3.3039"},
         {"0.62", "3.3052"},
         {"0.63", "3.3062"},
         {"0.64", "3.3071"},
         {"0.65", "3.3083"},
         {"0.66", "3.3093"},
         {"0.67", "3.3102"},
         {"0.68", "3.3113"},
         {"0.69", "3.3124"},
         {"0.7", "3.3135"},
         {"0.71", "3.3145"},
         {"0.72", "3.3154"},
         {"0.73", "3.3161"},
         {"0.74", "3.3168"},
         {"0.75", "3.3175"},
         {"0.76", "3.318"},
         {"0.77", "3.3185"},
         {"0.78", "3.3189"},
         {"0.79", "3.3194"},
         {"0.8", "3.3198"},
         {"0.81", "3.3203"},
         {"0.82", "3.3208"},
         {"0.83", "3.3213"},
         {"0.84", "3.3218"},
         {"0.85", "3.3222"},
         {"0.86", "3.3228"},
         {"0.87", "3.3234"},
         {"0.88", "3.3239"},
         {"0.89", "3.3243"},
         {"0.9", "3.3249"},
         {"0.91", "3.3255"},
         {"0.92", "3.3262"},
         {"0.93", "3.3271"},
         {"0.94", "3.3279"},
         {"0.95", "3.3292"},
         {"0.96", "3.3307"},
         {"0.97", "3.3331"},
         {"0.98", "3.3374"},
         {"0.99", "3.353"},
         {"1", "3.557"}});
    model.component("comp1").func("int1").set("fununit", new String[]{"V"});
    model.component("comp1").func("int1").set("argunit", new String[]{"1"});
    model.component("comp1").func("int2").label("Normalized cell-layer impedance profile");
    model.component("comp1").func("int2").set("table", new String[][]{{"0", "-1"}, {"0.04", "1"}});
    model.component("comp1").func("int2").set("fununit", new String[]{"1"});
    model.component("comp1").func("int2").set("argunit", new String[]{"m"});
    model.component("comp1").func("int3").label("dEeqdT");
    model.component("comp1").func("int3")
         .set("table", new String[][]{{"0", "3.0e-4"},
         {"0.17", "0"},
         {"0.24", "-6e-5"},
         {"0.28", "-1.6e-4"},
         {"0.5", "-1.6e-4"},
         {"0.54", "-9e-5"},
         {"0.71", "-9e-5"},
         {"0.85", "-1.0e-4"},
         {"1.0", "-1.2e-4"}});
    model.component("comp1").func("int3").set("fununit", new String[]{"V/degC"});
    model.component("comp1").func("int3").set("argunit", new String[]{"1"});

    model.component("comp1").mesh().create("mesh1");

    model.component("comp1").geom("geom2").model("xdim1");

    model.mesh().create("mesh2", "geom2");

    model.component("comp1").geom("geom1").geomRep("cadps");
    model.component("comp1").geom("geom1").designBooleans(false);
    model.component("comp1").geom("geom1").create("blk1", "Block");
    model.component("comp1").geom("geom1").feature("blk1").set("size", new String[]{"W_JR", "L_JR", "t_CC/2"});
    model.component("comp1").geom("geom1").create("blk2", "Block");
    model.component("comp1").geom("geom1").feature("blk2").set("size", new String[]{"t_tab", "t_tab", "t_CC/2"});
    model.component("comp1").geom("geom1").feature("blk2").set("pos", new String[]{"W_JR", "L_JR/8", "0"});
    model.component("comp1").geom("geom1").create("blk3", "Block");
    model.component("comp1").geom("geom1").feature("blk3")
         .set("size", new String[]{"W_JR", "L_JR", "t_neg+t_sep+t_pos"});
    model.component("comp1").geom("geom1").feature("blk3").set("pos", new String[]{"0", "0", "t_CC/2"});
    model.component("comp1").geom("geom1").create("blk4", "Block");
    model.component("comp1").geom("geom1").feature("blk4").set("size", new String[]{"W_JR", "L_JR", "t_CC/2"});
    model.component("comp1").geom("geom1").feature("blk4")
         .set("pos", new String[]{"0", "0", "t_CC/2+t_neg+t_sep+t_pos"});
    model.component("comp1").geom("geom1").create("blk5", "Block");
    model.component("comp1").geom("geom1").feature("blk5").set("size", new String[]{"t_tab", "t_tab", "t_CC/2"});
    model.component("comp1").geom("geom1").feature("blk5")
         .set("pos", new String[]{"W_JR", "L_JR*6/8", "t_CC/2+t_neg+t_sep+t_pos"});
    model.component("comp1").geom("geom1").create("sel1", "ExplicitSelection");
    model.component("comp1").geom("geom1").feature("sel1").label("Aluminum");
    model.component("comp1").geom("geom1").feature("sel1").selection("selection").set("blk4(1)", 1);
    model.component("comp1").geom("geom1").feature("sel1").selection("selection").set("blk5(1)", 1);
    model.component("comp1").geom("geom1").create("sel2", "ExplicitSelection");
    model.component("comp1").geom("geom1").feature("sel2").label("Copper");
    model.component("comp1").geom("geom1").feature("sel2").selection("selection").set("blk2(1)", 1);
    model.component("comp1").geom("geom1").feature("sel2").selection("selection").set("blk1(1)", 1);
    model.component("comp1").geom("geom1").feature("sel2").set("color", "13");
    model.component("comp1").geom("geom1").run();
    model.geom("geom2").create("i1", "Interval");
    model.geom("geom2").run();

    model.extraDim().create("pa1", "PointsToAttach");
    model.extraDim().create("ad1", "AttachDimensions");
    model.extraDim().create("xdintop1", "Integration");
    model.extraDim().create("xdintop2", "Integration");
    model.extraDim().create("xdaveop1", "Average");
    model.component("comp1").extraDim("ad1").selection().geom("geom1", 2);
    model.component("comp1").extraDim("ad1").selection().set(9);
    model.extraDim("xdintop1").selection().set(1);
    model.extraDim("xdintop2").selection().geom("geom2", 0);
    model.extraDim("xdintop2").selection().set(2);
    model.extraDim("xdaveop1").selection().set(1);

    model.component("comp1").variable().create("var2");
    model.component("comp1").variable("var2").label("Global load ramp");
    model.component("comp1").variable("var2").set("load_factor", "min(1,t/ramp_time)");
    model.component("comp1").variable("var2")
         .set("current_cv", "sqrt(aveop1((C_rate_loc-aveop1(C_rate_loc))^2))/max(aveop1(C_rate_loc),1e-12)");
    model.component("comp1").variable().create("var1");
    model.component("comp1").variable("var1").set("i_loc", "ec.nJ");
    model.component("comp1").variable("var1").set("C_rate_loc", "sqrt((i_loc/(i_1C/A_JR))^2+1e-12)");
    model.component("comp1").variable("var1").set("V_act_1C", "2*(R_const*T0/F_const)*asinh(1/(2*J0))");
    model.component("comp1").variable("var1").set("V_act", "V_act_1C*C_rate_loc");
    model.component("comp1").variable("var1").set("V_conc", "0[V]");
    model.component("comp1").variable("var1").set("R_factor", "1+hetero_amp*int2(y)");
    model.component("comp1").variable("var1").set("V_ohm", "eta_IR_1C*R_factor*C_rate_loc");
    model.component("comp1").variable("var1").set("R_area", "(V_act_1C+eta_IR_1C*R_factor)/(i_1C/A_JR)");
    model.component("comp1").variable("var1").set("OCV", "int1(SOCb)");
    model.component("comp1").variable("var1").set("J0", "J0_init");
    model.component("comp1").variable("var1").set("Particle_AveSOC", "SOCb");
    model.component("comp1").variable("var1").set("V_cell", "V1-linext2(V1)");
    model.component("comp1").variable("var1").selection().geom("geom1", 2);
    model.component("comp1").variable("var1").selection().set(9);

    model.component("comp1").view("view1").hideEntities().create("hide1");
    model.component("comp1").view("view1").hideEntities("hide1").geom("geom1", 2);
    model.component("comp1").view("view1").hideEntities("hide1").set(10);
    model.view().create("view3", 2);

    model.component("comp1").material().create("mat1", "Common");
    model.component("comp1").material().create("mat4", "Common");
    model.component("comp1").material("mat1").selection().set();
    model.component("comp1").material("mat1").propertyGroup()
         .create("Enu", "Enu", "Young's modulus and Poisson's ratio");
    model.component("comp1").material("mat1").propertyGroup().create("Murnaghan", "Murnaghan", "Murnaghan");
    model.component("comp1").material("mat1").selection().set(3, 5);
    model.component("comp1").material("mat4").selection().set(1, 4);
    model.component("comp1").material("mat4").propertyGroup()
         .create("Enu", "Enu", "Young's modulus and Poisson's ratio");
    model.component("comp1").material("mat4").propertyGroup().create("linzRes", "linzRes", "Linearized resistivity");

    model.component("comp1").cpl().create("linext1", "LinearExtrusion");
    model.component("comp1").cpl().create("linext2", "LinearExtrusion");
    model.component("comp1").cpl().create("intop1", "Integration");
    model.component("comp1").cpl().create("aveop1", "Average");
    model.component("comp1").cpl().create("aveop2", "Average");
    model.component("comp1").cpl().create("maxop1", "Maximum");
    model.component("comp1").cpl().create("minop1", "Minimum");
    model.component("comp1").cpl().create("genext1", "GeneralExtrusion");
    model.component("comp1").cpl("linext1").selection().geom("geom1", 2);
    model.component("comp1").cpl("linext1").selection().set(9);
    model.component("comp1").cpl("linext2").selection().geom("geom1", 2);
    model.component("comp1").cpl("linext2").selection().set(6);
    model.component("comp1").cpl("intop1").selection().geom("geom1", 2);
    model.component("comp1").cpl("intop1").selection().set(9);
    model.component("comp1").cpl("aveop1").selection().geom("geom1", 2);
    model.component("comp1").cpl("aveop1").selection().set(9);
    model.component("comp1").cpl("aveop2").selection().geom("geom1", 2);
    model.component("comp1").cpl("aveop2").selection().set(26);
    model.component("comp1").cpl("maxop1").selection().geom("geom1", 2);
    model.component("comp1").cpl("maxop1").selection().set(9);
    model.component("comp1").cpl("minop1").selection().geom("geom1", 2);
    model.component("comp1").cpl("minop1").selection().set(9);
    model.component("comp1").cpl("genext1").selection().geom("geom1", 2);
    model.component("comp1").cpl("genext1").selection().set(9);

    model.component("comp1").physics().create("ec", "ConductiveMedia", "geom1");
    model.component("comp1").physics("ec").field("electricpotential").field("V1");
    model.component("comp1").physics("ec").selection().set();
    model.component("comp1").physics("ec").create("cucn1", "CurrentConservationFluid", 3);
    model.component("comp1").physics("ec").feature("cucn1").selection().set(3, 5);
    model.component("comp1").physics("ec").feature("cucn1").featureInfo().create("information");
    model.component("comp1").physics("ec").create("ncd1", "NormalCurrentDensity", 2);
    model.component("comp1").physics("ec").feature("ncd1").selection().set(26);
    model.component("comp1").physics("ec").create("ncd2", "NormalCurrentDensity", 2);
    model.component("comp1").physics("ec").feature("ncd2").selection().set(6);
    model.component("comp1").physics("ec").create("ncd3", "NormalCurrentDensity", 2);
    model.component("comp1").physics("ec").feature("ncd3").selection().set(9);
    model.component("comp1").physics("ec").create("gnd1", "Ground", 2);
    model.component("comp1").physics("ec").feature("gnd1").selection().set(3);
    model.component("comp1").physics("ec").create("init2", "init", 3);
    model.component("comp1").physics("ec").feature("init2").selection().set(3, 5);
    model.component("comp1").physics("ec").feature("init2").set("V1", "int1(SOC0)");
    model.component("comp1").physics("ec").create("cucn2", "CurrentConservationFluid", 3);
    model.component("comp1").physics("ec").feature("cucn2").selection().set(1, 4);
    model.component("comp1").physics().create("bode", "BoundaryODE", "geom1");
    model.component("comp1").physics("bode").field("dimensionless").field("SOCb");
    model.component("comp1").physics("bode").field("dimensionless").component(new String[]{"SOCb"});
    model.component("comp1").physics("bode").prop("Units").set("DependentVariableQuantity", "none");
    model.component("comp1").physics("bode").prop("Units").set("CustomDependentVariableUnit", "1");
    model.component("comp1").physics("bode").selection().set(9);

    model.component("comp1").mesh("mesh1").create("edg1", "Edge");
    model.component("comp1").mesh("mesh1").create("map1", "Map");
    model.component("comp1").mesh("mesh1").create("swe1", "Sweep");
    model.component("comp1").mesh("mesh1").create("map2", "Map");
    model.component("comp1").mesh("mesh1").create("swe2", "Sweep");
    model.component("comp1").mesh("mesh1").create("fq1", "FreeQuad");
    model.component("comp1").mesh("mesh1").create("swe3", "Sweep");
    model.component("comp1").mesh("mesh1").feature("edg1").selection().set(27, 39);
    model.component("comp1").mesh("mesh1").feature("edg1").create("size1", "Size");
    model.component("comp1").mesh("mesh1").feature("map1").selection().set(6);
    model.component("comp1").mesh("mesh1").feature("map1").create("size1", "Size");
    model.component("comp1").mesh("mesh1").feature("swe1").selection().geom("geom1", 3);
    model.component("comp1").mesh("mesh1").feature("swe1").selection().set(2);
    model.component("comp1").mesh("mesh1").feature("swe1").create("dis1", "Distribution");
    model.component("comp1").mesh("mesh1").feature("map2").selection().set(3, 10);
    model.component("comp1").mesh("mesh1").feature("map2").create("size1", "Size");
    model.component("comp1").mesh("mesh1").feature("swe2").selection().geom("geom1", 3);
    model.component("comp1").mesh("mesh1").feature("swe2").selection().set(1, 3);
    model.component("comp1").mesh("mesh1").feature("fq1").selection().set(19, 26);
    model.component("comp1").mesh("mesh1").feature("fq1").create("size1", "Size");
    model.component("comp1").mesh("mesh1").feature("swe3").selection().geom("geom1", 3);
    model.component("comp1").mesh("mesh1").feature("swe3").selection().set(4, 5);
    model.mesh("mesh2").create("edg2", "Edge");

    model.result().table("evl3").label("Evaluation 3D");
    model.result().table("evl3").comments("Interactive 3D values");

    model.view("view2").axis().set("xmin", -0.04999998211860657);
    model.view("view2").axis().set("xmax", 1.0499999523162842);

    model.component("comp1").material("mat1").label("Aluminum");
    model.component("comp1").material("mat1").set("family", "aluminum");
    model.component("comp1").material("mat1").propertyGroup("def")
         .set("relpermeability", new String[]{"1", "0", "0", "0", "1", "0", "0", "0", "1"});
    model.component("comp1").material("mat1").propertyGroup("def").set("heatcapacity", "900[J/(kg*K)]");
    model.component("comp1").material("mat1").propertyGroup("def")
         .set("thermalconductivity", new String[]{"238[W/(m*K)]", "0", "0", "0", "238[W/(m*K)]", "0", "0", "0", "238[W/(m*K)]"});
    model.component("comp1").material("mat1").propertyGroup("def")
         .set("electricconductivity", new String[]{"3.77E7[S/m]", "0", "0", "0", "3.77E7[S/m]", "0", "0", "0", "3.77E7[S/m]"});
    model.component("comp1").material("mat1").propertyGroup("def")
         .set("relpermittivity", new String[]{"1", "0", "0", "0", "1", "0", "0", "0", "1"});
    model.component("comp1").material("mat1").propertyGroup("def")
         .set("thermalexpansioncoefficient", new String[]{"23e-6[1/K]", "0", "0", "0", "23e-6[1/K]", "0", "0", "0", "23e-6[1/K]"});
    model.component("comp1").material("mat1").propertyGroup("def").set("density", "2700[kg/m^3]");
    model.component("comp1").material("mat1").propertyGroup("Enu").set("E", "70[GPa]");
    model.component("comp1").material("mat1").propertyGroup("Enu").set("nu", "0.33");
    model.component("comp1").material("mat1").propertyGroup("Murnaghan").set("l", "-250[GPa]");
    model.component("comp1").material("mat1").propertyGroup("Murnaghan").set("m", "-330[GPa]");
    model.component("comp1").material("mat1").propertyGroup("Murnaghan").set("n", "-350[GPa]");
    model.component("comp1").material("mat4").label("Copper");
    model.component("comp1").material("mat4").set("family", "copper");
    model.component("comp1").material("mat4").propertyGroup("def")
         .set("relpermeability", new String[]{"1", "0", "0", "0", "1", "0", "0", "0", "1"});
    model.component("comp1").material("mat4").propertyGroup("def")
         .set("electricconductivity", new String[]{"5.998e7[S/m]", "0", "0", "0", "5.998e7[S/m]", "0", "0", "0", "5.998e7[S/m]"});
    model.component("comp1").material("mat4").propertyGroup("def").set("heatcapacity", "385[J/(kg*K)]");
    model.component("comp1").material("mat4").propertyGroup("def")
         .set("relpermittivity", new String[]{"1", "0", "0", "0", "1", "0", "0", "0", "1"});
    model.component("comp1").material("mat4").propertyGroup("def").set("emissivity", "0.5");
    model.component("comp1").material("mat4").propertyGroup("def").set("density", "8940[kg/m^3]");
    model.component("comp1").material("mat4").propertyGroup("def")
         .set("thermalconductivity", new String[]{"400[W/(m*K)]", "0", "0", "0", "400[W/(m*K)]", "0", "0", "0", "400[W/(m*K)]"});
    model.component("comp1").material("mat4").propertyGroup("Enu").set("E", "126e9[Pa]");
    model.component("comp1").material("mat4").propertyGroup("Enu").set("nu", "0.34");
    model.component("comp1").material("mat4").propertyGroup("linzRes").set("rho0", "1.667e-8[ohm*m]");
    model.component("comp1").material("mat4").propertyGroup("linzRes").set("alpha", "3.862e-3[1/K]");
    model.component("comp1").material("mat4").propertyGroup("linzRes").set("Tref", "293.15[K]");
    model.component("comp1").material("mat4").propertyGroup("linzRes").addInput("temperature");

    model.component("comp1").cpl("linext1").selection("srcvertex1").set(7);
    model.component("comp1").cpl("linext1").selection("srcvertex2").set(3);
    model.component("comp1").cpl("linext1").selection("srcvertex3").set(11);
    model.component("comp1").cpl("linext1").selection("srcvertex4").set(23);
    model.component("comp1").cpl("linext1").selection("dstvertex1").set(6);
    model.component("comp1").cpl("linext1").selection("dstvertex2").set(2);
    model.component("comp1").cpl("linext1").selection("dstvertex3").set(10);
    model.component("comp1").cpl("linext1").selection("dstvertex4").set(22);
    model.component("comp1").cpl("linext2").selection("srcvertex1").set(6);
    model.component("comp1").cpl("linext2").selection("srcvertex2").set(2);
    model.component("comp1").cpl("linext2").selection("srcvertex3").set(10);
    model.component("comp1").cpl("linext2").selection("srcvertex4").set(22);
    model.component("comp1").cpl("linext2").selection("dstvertex1").set(7);
    model.component("comp1").cpl("linext2").selection("dstvertex2").set(3);
    model.component("comp1").cpl("linext2").selection("dstvertex3").set(11);
    model.component("comp1").cpl("linext2").selection("dstvertex4").set(23);
    model.component("comp1").cpl("genext1").set("dstmap", new String[]{"x", "y", ""});
    model.component("comp1").cpl("genext1").set("usesrcmap", true);
    model.component("comp1").cpl("genext1").set("srcmap", new String[]{"x", "y", ""});

    model.component("comp1").physics("ec").selection().set(1, 3, 4, 5);
    model.component("comp1").physics("ec").feature("cucn1")
         .set("sigma", new String[][]{{"3.77E7"}, {"0"}, {"0"}, {"0"}, {"3.77E7"}, {"0"}, {"0"}, {"0"}, {"3.77E7"}});
    model.component("comp1").physics("ec").feature("cucn1").label("Aluminum");
    model.component("comp1").physics("ec").feature("cucn1").featureInfo("information").label("Migrated Feature");
    model.component("comp1").physics("ec").feature("dcont1").label("Continuity 1");
    model.component("comp1").physics("ec").feature("ncd1").set("nJ", "load_factor*I_cell/t_tab^2");
    model.component("comp1").physics("ec").feature("ncd2").set("nJ", "linext1(ec.nJ)");
    model.component("comp1").physics("ec").feature("ncd2")
         .set("J0", new String[][]{{"linext1(ec.Jx)"}, {"linext1(ec.Jy)"}, {"linext1(ec.Jz)"}});
    model.component("comp1").physics("ec").feature("ncd3").set("nJ", "(V1-linext2(V1)-OCV)/R_area");
    model.component("comp1").physics("ec").feature("cucn2")
         .set("sigma", new String[][]{{"5.998E7"}, {"0"}, {"0"}, {"0"}, {"5.998E7"}, {"0"}, {"0"}, {"0"}, {"5.998E7"}});
    model.component("comp1").physics("ec").feature("cucn2").label("Copper");
    model.component("comp1").physics("bode").prop("EquationForm").set("form", "Automatic");
    model.component("comp1").physics("bode").prop("Units").set("CustomSourceTermUnit", "1/s");
    model.component("comp1").physics("bode").selection().set(9);
    model.component("comp1").physics("bode").feature("dode1").set("f", "C_rate_loc/3600[s]");
    model.component("comp1").physics("bode").feature("dode1").set("ea", "0");
    model.component("comp1").physics("bode").feature("dode1").set("da", "1");
    model.component("comp1").physics("bode").feature("init1").set("SOCb", "SOC0");

    model.component("comp1").mesh("mesh1").feature("size").set("hauto", 2);
    model.component("comp1").mesh("mesh1").feature("edg1").feature("size1").set("hauto", 1);
    model.component("comp1").mesh("mesh1").feature("edg1").feature("size1").set("custom", "on");
    model.component("comp1").mesh("mesh1").feature("edg1").feature("size1").set("hmax", "1E-3");
    model.component("comp1").mesh("mesh1").feature("edg1").feature("size1").set("hmaxactive", true);
    model.component("comp1").mesh("mesh1").feature("map1").feature("size1").set("hauto", 2);
    model.component("comp1").mesh("mesh1").feature("map1").feature("size1").set("custom", "on");
    model.component("comp1").mesh("mesh1").feature("map1").feature("size1").set("hmax", "1E-3");
    model.component("comp1").mesh("mesh1").feature("map1").feature("size1").set("hmaxactive", true);
    model.component("comp1").mesh("mesh1").feature("map1").feature("size1").set("hmin", "1E-5");
    model.component("comp1").mesh("mesh1").feature("map1").feature("size1").set("hminactive", false);
    model.component("comp1").mesh("mesh1").feature("map2").feature("size1").set("hauto", 2);
    model.component("comp1").mesh("mesh1").feature("map2").feature("size1").set("custom", "on");
    model.component("comp1").mesh("mesh1").feature("map2").feature("size1").set("hmax", "1E-3");
    model.component("comp1").mesh("mesh1").feature("map2").feature("size1").set("hmaxactive", true);
    model.component("comp1").mesh("mesh1").feature("map2").feature("size1").set("hmin", "1E-3");
    model.component("comp1").mesh("mesh1").feature("map2").feature("size1").set("hminactive", false);
    model.component("comp1").mesh("mesh1").feature("fq1").feature("size1").set("hauto", 2);
    model.component("comp1").mesh("mesh1").feature("fq1").feature("size1").set("custom", "on");
    model.component("comp1").mesh("mesh1").feature("fq1").feature("size1").set("hmax", "1e-3");
    model.component("comp1").mesh("mesh1").feature("fq1").feature("size1").set("hmaxactive", true);
    model.component("comp1").mesh("mesh1").run();
    model.mesh("mesh2").feature("size").set("hauto", 6);
    model.mesh("mesh2").run();

    model.study().create("std1");
    model.study("std1").create("time", "Transient");
    model.study("std1").feature("time").set("tlist", "range(0,dt_out,t_final)");
    model.study("std1").feature("time").set("rtol", "1e-3");

    model.sol().create("sol1");
    model.sol("sol1").study("std1");
    model.sol("sol1").attach("std1");
    model.sol("sol1").create("st1", "StudyStep");
    model.sol("sol1").feature("st1").set("study", "std1");
    model.sol("sol1").feature("st1").set("studystep", "time");
    model.sol("sol1").create("v1", "Variables");
    model.sol("sol1").create("t1", "Time");
    model.sol("sol1").feature("t1").set("tlist", "range(0,dt_out,t_final)");
    model.sol("sol1").feature("t1").set("rtol", 1e-3);
    model.sol("sol1").feature("t1").set("timemethod", "bdf");
    model.sol("sol1").feature("t1").set("maxstepconstraintbdf", "const");
    model.sol("sol1").feature("t1").set("maxstepbdf", "max_step");
    model.sol("sol1").feature("t1").set("maxorder", 2);
    model.sol("sol1").feature("t1").create("fc1", "FullyCoupled");
    model.sol("sol1").feature("t1").feature("fc1").set("dtech", "auto");
    model.sol("sol1").feature("t1").feature("fc1").set("maxiter", 50);

    model.result().table().create("tblGlobal", "Table");
    model.result().numerical().create("gev1", "EvalGlobal");
    model.result().numerical("gev1").set("expr", new String[]{
      "C_rate", "hetero_amp", "load_factor", "I_cell", "abs(intop1(ec.nJ))", "aveop1(C_rate_loc)",
      "minop1(C_rate_loc)", "maxop1(C_rate_loc)", "current_cv", "minop1(R_factor)",
      "maxop1(R_factor)", "aveop2(V1)", "aveop1(V_cell)", "aveop1(Particle_AveSOC)",
      "minop1(SOCb)", "maxop1(SOCb)"
    });
    model.result().numerical("gev1").set("unit", new String[]{
      "1", "1", "1", "A", "A", "1", "1", "1", "1", "1", "1", "V", "V", "1", "1", "1"
    });
    model.result().numerical("gev1").set("table", "tblGlobal");

    model.result().dataset().create("surfLayer", "Surface");
    model.result().dataset("surfLayer").set("data", "dset1");
    model.result().dataset("surfLayer").selection().geom("geom1", 2);
    model.result().dataset("surfLayer").selection().set(9);
    model.result().export().create("dataCurrent", "Data");
    model.result().export("dataCurrent").set("data", "surfLayer");
    model.result().export("dataCurrent").set(
      "expr", new String[]{
        "R_factor", "C_rate_loc", "ec.nJ", "V_cell", "Particle_AveSOC",
        "SOCb", "V_conc", "V_ohm"
      }
    );
    model.result().export("dataCurrent").set(
      "unit", new String[]{"1", "1", "A/m^2", "V", "1", "1", "V", "V"}
    );
    model.result().export("dataCurrent").set("separator", ",");
    model.result().export("dataCurrent").set("header", "on");

    return model;
  }

  public static Model run2(Model model) {
    model.sol("sol1").runAll();
    return model;
  }

  private static Properties loadCase(String[] args) {
    Properties properties = new Properties();
    for (String argument : args) {
      int separator = argument.indexOf('=');
      if (separator > 0 && separator + 1 < argument.length()) {
        properties.setProperty(argument.substring(0, separator), argument.substring(separator + 1));
      }
    }
    return properties;
  }

  private static void apply(Model model, Properties properties, String parameter) {
    String value = properties.getProperty(parameter);
    if (value != null && !value.trim().isEmpty()) {
      model.param().set(parameter, value.trim());
    }
  }

  private static double[] outputTimes(double finalTime) {
    return new double[]{0.0, 0.5 * finalTime, finalTime};
  }

  public static void main(String[] args) throws IOException {
    Properties properties = loadCase(args);
    Model model = run();
    String[] parameterNames = new String[]{
      "C_rate", "hetero_amp", "dt_out", "t_final", "max_step", "ramp_time", "SOC0"
    };
    for (String parameter : parameterNames) {
      apply(model, properties, parameter);
    }
    String prefix = properties.getProperty("prefix", "distributed_ecm").trim();
    if (!prefix.matches("[A-Za-z0-9_.-]+")) {
      throw new IllegalArgumentException("unsafe output prefix");
    }
    model.save(model.modelPath() + "/" + prefix + "_built.mph");
    run2(model);
    model.result().numerical("gev1").setResult();
    model.result().table("tblGlobal").save(model.modelPath() + "/" + prefix + "_global.csv");
    model.result().export("dataCurrent").set("innerinput", "interp");
    model.result().export("dataCurrent").set("t", outputTimes(model.param().evaluate("t_final")));
    model.result().export("dataCurrent").set("filename", model.modelPath() + "/" + prefix + "_fields.csv");
    model.result().export("dataCurrent").run();
    model.save(model.modelPath() + "/" + prefix + "_solved.mph");
  }

}
