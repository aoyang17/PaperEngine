import com.comsol.model.*;
import com.comsol.model.util.*;
import java.util.Properties;

/**
 * COMSOL 6.4 builder for Laghmach et al., JCP 142, 244905 (2015).
 *
 * The model uses Weak Form PDE interfaces so that the paper's Eulerian
 * equations (18), (20), and (27) remain visible and auditable in the MPH file.
 * Invoke with COMSOL compile/run from the intended output directory.
 */
public class Laghmach2015 {
  public static Model run() {
    Model model = ModelUtil.create("Model");
    model.label("Laghmach2015_phase_field.mph");
    model.modelPath(".");

    model.param().set("L", "200[nm]", "square box side");
    model.param().set("w", "1[nm]", "diffuse interface width");
    model.param().set("Rn", "9[nm]", "initial nucleus radius");
    model.param().set("T", "303[K]");
    model.param().set("Tm0", "303[K]");
    model.param().set("lamStretch", "4");
    model.param().set("nseg", "95");
    model.param().set("rho", "1.47e4[mol/m^3]");
    model.param().set("Rgas", "8.31446261815324[J/(mol*K)]");
    model.param().set("hm", "4.986[kJ/mol]", "paper: approximately 600 R");
    model.param().set("fscale", "37.03[MJ/m^3]", "rho R Tm0 using tabulated values");
    model.param().set("Gamma", "169.7[MJ/m^3]");
    model.param().set("lamTopo", "0.611[MPa]");
    model.param().set("muTopo", "0.15275[MPa]");
    model.param().set("alphaCut", "1e-4");
    model.param().set("tau1", "1[s]", "dimensionless time carrier");
    model.param().set("tau2", "0.1*tau1");
    model.param().set("topoOn", "1", "set zero for growth control");
    model.param().set("relaxOn", "1", "set zero for stable prescribed-strain COMSOL control");
    model.param().set("anisOn", "0", "set one for Eq. 13 anisotropy");
    model.param().set("anisMode", "2");
    model.param().set("anisDelta", "0.33");
    model.param().set("phi0", "0[rad]");
    model.param().set("hmesh", "2[nm]", "smoke-test mesh; production runs override this in the saved MPH");
    model.param().set("dtout", "0.01*tau1");
    model.param().set("tfinal", "0.1*tau1", "pipeline smoke-test end time; production runs override this in the saved MPH");
    model.param().set("maxStep", "0.005*tau1", "pipeline smoke-test maximum step; production runs override this in the saved MPH");
    model.param().set("barrierCoeff", "-0.5", "variationally consistent; printed Eq. 27 shows +0.25");
    model.param().set("pressureGauge", "1e-8", "removes the pressure null mode; audited by detF error");

    model.component().create("comp1", true);
    model.component("comp1").geom().create("geom1", 2);
    model.component("comp1").geom("geom1").lengthUnit("nm");
    model.component("comp1").geom("geom1").create("r1", "Rectangle");
    model.component("comp1").geom("geom1").feature("r1").set("size", new String[]{"L", "L"});
    model.component("comp1").geom("geom1").feature("r1").set("pos", new String[]{"-L/2", "-L/2"});
    model.component("comp1").geom("geom1").run();
    System.out.println("LAGHMACH_STAGE geometry");

    model.component("comp1").variable().create("paper");
    model.component("comp1").variable("paper").label("Paper equations 18, 20, 27");
    model.component("comp1").variable("paper").set("g", "1-theta^2*(3-2*theta)");
    model.component("comp1").variable("paper").set("gp", "6*theta*(theta-1)");
    model.component("comp1").variable("paper").set("Aphase", "Gamma/fscale");
    model.component("comp1").variable("paper").set("F11", "1-w*uyy");
    model.component("comp1").variable("paper").set("F12", "w*uyx");
    model.component("comp1").variable("paper").set("F21", "w*uxy");
    model.component("comp1").variable("paper").set("F22", "1-w*uxx");
    model.component("comp1").variable("paper").set("detF", "F11*F22-F12*F21");
    model.component("comp1").variable("paper").set("dudX11", "w*(uxx*F11+uxy*F21)");
    model.component("comp1").variable("paper").set("dudX12", "w*(uxx*F12+uxy*F22)");
    model.component("comp1").variable("paper").set("dudX21", "w*(uyx*F11+uyy*F21)");
    model.component("comp1").variable("paper").set("dudX22", "w*(uyx*F12+uyy*F22)");
    model.component("comp1").variable("paper").set("E11", "0.5*(F11^2+F21^2-1)");
    model.component("comp1").variable("paper").set("E22", "0.5*(F12^2+F22^2-1)");
    model.component("comp1").variable("paper").set("trE", "E11+E22");
    model.component("comp1").variable("paper").set("et11", "w*utxx");
    model.component("comp1").variable("paper").set("et22", "w*utyy");
    model.component("comp1").variable("paper").set("et12", "0.5*w*(utxy+utyx)");
    model.component("comp1").variable("paper").set("trEt", "et11+et22");
    model.component("comp1").variable("paper").set("trEt2", "et11^2+et22^2+2*et12^2");
    model.component("comp1").variable("paper").set("Wtopo", "topoOn*(lamTopo/2*trEt^2+muTopo*trEt2)");
    model.component("comp1").variable("paper").set("driveNoTopo", "hm/(Rgas*Tm0)*(Tm0-T)/Tm0+T/(nseg*Tm0)*trE");
    model.component("comp1").variable("paper").set("drive", "driveNoTopo-Wtopo/fscale");
    model.component("comp1").variable("paper").set("fbulk", "Gamma/4*theta^2*(1-theta)^2+g*fscale*driveNoTopo-g*Wtopo");
    model.component("comp1").variable("paper").set("fgrad", "Gamma*w^2/2*(thetax^2+thetay^2)");
    model.component("comp1").variable("paper").set("phi", "atan2(thetay,thetax)");
    model.component("comp1").variable("paper").set("aq", "anisMode*(phi-phi0)");
    model.component("comp1").variable("paper").set("fw", "1+anisOn*(anisDelta*cos(aq)+0.5*anisDelta*sin(aq)^2)");
    model.component("comp1").variable("paper").set("fwp", "anisOn*anisMode*anisDelta*sin(aq)*(cos(aq)-1)");
    // Treat the orientation coefficients explicitly in the Newton Jacobian.
    // This avoids the undefined symbolic derivative of atan2 at grad(theta)=0;
    // the residual still updates fw and fwp from the current phase field.
    model.component("comp1").variable("paper").set("qphix", "nojac(fw^2)*thetax-nojac(fw*fwp)*thetay");
    model.component("comp1").variable("paper").set("qphiy", "nojac(fw^2)*thetay+nojac(fw*fwp)*thetax");
    model.component("comp1").variable("paper").set("vix", "-d(theta,t)*(w*thetax)/(w^2*(thetax^2+thetay^2)+alphaCut)");
    model.component("comp1").variable("paper").set("viy", "-d(theta,t)*(w*thetay)/(w^2*(thetax^2+thetay^2)+alphaCut)");
    model.component("comp1").variable("paper").set("Knet", "rho*Rgas*T/nseg");
    model.component("comp1").variable("paper").set("q11", "-P*fscale+g*Knet*dudX11");
    model.component("comp1").variable("paper").set("q12", "g*Knet*dudX12");
    model.component("comp1").variable("paper").set("q21", "g*Knet*dudX21");
    model.component("comp1").variable("paper").set("q22", "-P*fscale+g*Knet*dudX22");
    model.component("comp1").variable("paper").set("mechX", "F11*d(q11,x)+F21*d(q11,y)+F12*d(q12,x)+F22*d(q12,y)");
    model.component("comp1").variable("paper").set("mechY", "F11*d(q21,x)+F21*d(q21,y)+F12*d(q22,x)+F22*d(q22,y)");
    model.component("comp1").variable("paper").set("sigxx", "g*Knet*w*(uxx-uyy)", "paper Eq. 30");
    System.out.println("LAGHMACH_STAGE variables");

    // Equation (27): isotropic form. Coordinates in COMSOL remain dimensional.
    model.component("comp1").physics().create("pf", "WeakFormPDE", "geom1");
    model.component("comp1").physics("pf").field("dimensionless").field("theta");
    model.component("comp1").physics("pf").field("dimensionless").component(new String[]{"theta"});
    model.component("comp1").physics("pf").feature("wfeq1").set(
      "weak",
      "test(theta)*d(theta,t)+Aphase*w^2/tau1*(test(thetax)*qphix+test(thetay)*qphiy)-test(theta)*Aphase*barrierCoeff/tau1*theta*(1-theta)*(1-2*theta)+test(theta)*gp*drive/tau1"
    );
    model.component("comp1").physics("pf").feature("init1").set(
      "theta", "0.5*(1-tanh((sqrt(x^2+y^2)-Rn)/(2*sqrt(2)*w)))"
    );
    model.component("comp1").physics("pf").create("dir1", "DirichletBoundary", 1);
    model.component("comp1").physics("pf").feature("dir1").selection().all();
    model.component("comp1").physics("pf").feature("dir1").set("r", "0");
    System.out.println("LAGHMACH_STAGE phase");

    // Equation (20): interface-velocity transport for both topology components.
    model.component("comp1").physics().create("topo", "WeakFormPDE", "geom1");
    model.component("comp1").physics("topo").field("dimensionless").field("utopo");
    model.component("comp1").physics("topo").field("dimensionless").component(new String[]{"utx", "uty"});
    model.component("comp1").physics("topo").feature("wfeq1").set(
      "weak",
      new String[]{
        "test(utx)*(d(utx,t)+vix*w*utxx+viy*w*utxy-vix)",
        "test(uty)*(d(uty,t)+vix*w*utyx+viy*w*utyy-viy)"
      }
    );
    model.component("comp1").physics("topo").feature("init1").set("utx", "0");
    model.component("comp1").physics("topo").feature("init1").set("uty", "0");
    System.out.println("LAGHMACH_STAGE topology");

    // Equations (18)-(19): Eulerian large-deformation relaxation plus pressure DAE.
    model.component("comp1").physics().create("mechx", "WeakFormPDE", "geom1");
    model.component("comp1").physics("mechx").field("dimensionless").field("elasticx");
    model.component("comp1").physics("mechx").field("dimensionless").component(new String[]{"ux"});
    model.component("comp1").physics("mechx").feature("wfeq1").set(
      "weak", "test(ux)*(d(ux,t)-relaxOn*w/(tau2*fscale)*mechX)"
    );
    model.component("comp1").physics("mechx").feature("init1").set("ux", "(lamStretch-1)/lamStretch*x/w");
    model.component("comp1").physics("mechx").create("dir1", "DirichletBoundary", 1);
    model.component("comp1").physics("mechx").feature("dir1").selection().set(new int[]{2, 4});
    model.component("comp1").physics("mechx").feature("dir1").set("r", "(lamStretch-1)/lamStretch*x/w");

    model.component("comp1").physics().create("mechy", "WeakFormPDE", "geom1");
    model.component("comp1").physics("mechy").field("dimensionless").field("elasticy");
    model.component("comp1").physics("mechy").field("dimensionless").component(new String[]{"uy"});
    model.component("comp1").physics("mechy").feature("wfeq1").set(
      "weak", "test(uy)*(d(uy,t)-relaxOn*w/(tau2*fscale)*mechY)"
    );
    model.component("comp1").physics("mechy").feature("init1").set("uy", "(1-lamStretch)*y/w");
    model.component("comp1").physics("mechy").create("dir1", "DirichletBoundary", 1);
    model.component("comp1").physics("mechy").feature("dir1").selection().set(new int[]{1, 3});
    model.component("comp1").physics("mechy").feature("dir1").set("r", "(1-lamStretch)*y/w");
    System.out.println("LAGHMACH_STAGE mechanics");

    // Pressure is a separate scalar field, avoiding an unphysical pressure
    // Dirichlet condition while supplying the incompressibility constraint.
    model.component("comp1").physics().create("inc", "WeakFormPDE", "geom1");
    model.component("comp1").physics("inc").field("dimensionless").field("pressure");
    model.component("comp1").physics("inc").field("dimensionless").component(new String[]{"P"});
    model.component("comp1").physics("inc").feature("wfeq1").set("weak", "test(P)*(detF-1+pressureGauge*P)/tau1");
    model.component("comp1").physics("inc").feature("init1").set("P", "0");
    System.out.println("LAGHMACH_STAGE pressure");

    model.component("comp1").mesh().create("mesh1");
    model.component("comp1").mesh("mesh1").create("size1", "Size");
    model.component("comp1").mesh("mesh1").feature("size1").set("custom", "on");
    model.component("comp1").mesh("mesh1").feature("size1").set("hmax", "hmesh");
    model.component("comp1").mesh("mesh1").feature("size1").set("hmin", "hmesh");
    model.component("comp1").mesh("mesh1").create("map1", "Map");
    System.out.println("LAGHMACH_STAGE mesh_selection_start");
    model.component("comp1").mesh("mesh1").feature("map1").selection().geom("geom1", 2);
    model.component("comp1").mesh("mesh1").feature("map1").selection().all();
    model.component("comp1").mesh("mesh1").run();
    System.out.println("LAGHMACH_STAGE mesh");

    model.component("comp1").cpl().create("intop1", "Integration");
    model.component("comp1").cpl("intop1").selection().geom("geom1", 2);
    model.component("comp1").cpl("intop1").selection().all();
    model.component("comp1").cpl().create("maxop1", "Maximum");
    model.component("comp1").cpl("maxop1").selection().geom("geom1", 2);
    model.component("comp1").cpl("maxop1").selection().all();
    model.component("comp1").cpl().create("minop1", "Minimum");
    model.component("comp1").cpl("minop1").selection().geom("geom1", 2);
    model.component("comp1").cpl("minop1").selection().all();
    System.out.println("LAGHMACH_STAGE couplings");
    model.component("comp1").variable().create("obs");
    model.component("comp1").variable("obs").set("crystalArea", "intop1(theta)");
    model.component("comp1").variable("obs").set("effectiveRadius", "sqrt(crystalArea/pi)");
    model.component("comp1").variable("obs").set("incompL2", "sqrt(intop1((detF-1)^2)/intop1(1))");
    model.component("comp1").variable("obs").set("incompMax", "maxop1(abs(detF-1))");
    model.component("comp1").variable("obs").set("amorphWeight", "1-flc2hs(theta-0.05,0.01)");
    model.component("comp1").variable("obs").set("sigmaAmorph", "intop1(amorphWeight*sigxx)/intop1(amorphWeight)");
    model.component("comp1").variable("obs").set("interfaceWeight", "flc2hs(theta-0.05,0.01)-flc2hs(theta-0.95,0.01)");
    model.component("comp1").variable("obs").set("beltInterfaceOverlap", "intop1(interfaceWeight*g*Wtopo)/(intop1(g*Wtopo)+1e-30[J/m])");
    model.component("comp1").variable("obs").set("elasticGamma", "intop1(g*Wtopo)/(2*pi*effectiveRadius)");
    model.component("comp1").variable("obs").set("topologicalEnergy2D", "intop1(g*Wtopo)");
    model.component("comp1").variable("obs").set("totalEnergy2D", "intop1(fbulk+fgrad)");

    model.study().create("std1");
    model.study("std1").create("time", "Transient");
    model.study("std1").feature("time").set("tlist", "range(0,dtout,tfinal)");
    model.study("std1").feature("time").set("rtol", "1e-4");
    model.sol().create("sol1");
    model.sol("sol1").study("std1");
    model.sol("sol1").attach("std1");
    model.sol("sol1").create("st1", "StudyStep");
    model.sol("sol1").feature("st1").set("study", "std1");
    model.sol("sol1").feature("st1").set("studystep", "time");
    model.sol("sol1").create("v1", "Variables");
    model.sol("sol1").create("t1", "Time");
    model.sol("sol1").feature("t1").set("tlist", "range(0,dtout,tfinal)");
    model.sol("sol1").feature("t1").set("rtol", 1e-4);
    model.sol("sol1").feature("t1").set("timemethod", "bdf");
    model.sol("sol1").feature("t1").set("maxstepconstraintbdf", "const");
    model.sol("sol1").feature("t1").set("maxstepbdf", "maxStep");
    model.sol("sol1").feature("t1").set("maxorder", 2);
    model.sol("sol1").feature("t1").set("estrat", "exclude");
    // Split the stiff DAE into phase/topology and mechanics/pressure blocks.
    // The damped segregated iterations are materially more robust than a
    // monolithic Newton solve for the large imposed stretch.
    model.sol("sol1").feature("t1").create("se1", "Segregated");
    model.sol("sol1").feature("t1").feature("se1").create("seg1", "SegregatedStep");
    model.sol("sol1").feature("t1").feature("se1").feature("seg1").set("subdtech", "auto");
    model.sol("sol1").feature("t1").feature("se1").feature("seg1").set("subinitstep", 0.5);
    model.sol("sol1").feature("t1").feature("se1").feature("seg1").set("subminstep", 1e-4);
    model.sol("sol1").feature("t1").feature("se1").feature("seg1").set("maxsubiter", 12);
    model.sol("sol1").feature("t1").feature("se1").create("seg2", "SegregatedStep");
    model.sol("sol1").feature("t1").feature("se1").feature("seg2").set("subdtech", "auto");
    model.sol("sol1").feature("t1").feature("se1").feature("seg2").set("subinitstep", 0.25);
    model.sol("sol1").feature("t1").feature("se1").feature("seg2").set("subminstep", 1e-5);
    model.sol("sol1").feature("t1").feature("se1").feature("seg2").set("maxsubiter", 20);

    model.result().table().create("tblRadius", "Table");
    model.result().numerical().create("gev1", "EvalGlobal");
    model.result().numerical("gev1").set("expr", new String[]{"effectiveRadius", "incompL2", "incompMax", "maxop1(theta)", "minop1(theta)", "sigmaAmorph", "beltInterfaceOverlap", "elasticGamma", "topologicalEnergy2D", "totalEnergy2D", "T", "lamStretch", "topoOn", "hmesh", "maxStep", "barrierCoeff", "pressureGauge"});
    model.result().numerical("gev1").set("unit", new String[]{"nm", "1", "1", "1", "1", "MPa", "1", "J/m^2", "J/m", "J/m", "K", "1", "1", "nm", "s", "1", "1"});
    model.result().numerical("gev1").set("table", "tblRadius");

    return model;
  }

  private static void apply(Model model, Properties properties, String parameter) {
    String value = properties.getProperty(parameter);
    if (value != null && !value.trim().isEmpty()) {
      model.param().set(parameter, value.trim());
    }
  }

  public static void main(String[] args) throws java.io.IOException {
    Properties properties = new Properties();
    for (String argument : args) {
      int separator = argument.indexOf('=');
      if (separator > 0 && separator + 1 < argument.length()) {
        properties.setProperty(argument.substring(0, separator), argument.substring(separator + 1));
      }
    }
    Model model = run();
    String[] parameterNames = new String[]{
      "T", "lamStretch", "topoOn", "relaxOn", "anisOn", "anisMode", "anisDelta",
      "Rn", "hmesh", "maxStep", "tfinal", "dtout"
    };
    for (String parameter : parameterNames) apply(model, properties, parameter);
    String prefix = properties.getProperty("prefix", "smoke").trim();
    if (!prefix.matches("[A-Za-z0-9_.-]+")) {
      throw new IllegalArgumentException("unsafe prefix in case arguments");
    }
    model.save(model.modelPath() + "/" + prefix + "_built.mph");
    model.sol("sol1").runAll();
    model.result().numerical("gev1").setResult();
    model.result().table("tblRadius").save(model.modelPath() + "/" + prefix + "_radius_and_quality.csv");
    // Persist the solved state before optional visualization exports.
    model.save(model.modelPath() + "/" + prefix + "_solved.mph");
    // Export spatial fields from the final time slice for audit-ready figures.
    model.result().create("pgTheta", "PlotGroup2D");
    model.result("pgTheta").create("surfTheta", "Surface");
    model.result("pgTheta").feature("surfTheta").set("expr", "theta");
    model.result("pgTheta").label("Phase field theta");
    model.result().export().create("imgTheta", "Image");
    model.result().export("imgTheta").set("plotgroup", "pgTheta");
    model.result().export("imgTheta").set("imagetype", "png");
    model.result().export("imgTheta").set("filename", model.modelPath() + "/" + prefix + "_theta.png");
    model.result().export("imgTheta").set("pngfilename", model.modelPath() + "/" + prefix + "_theta.png");
    model.result().export().create("imgTopo", "Image");
    model.result().create("pgTopo", "PlotGroup2D");
    model.result("pgTopo").create("surfTopo", "Surface");
    model.result("pgTopo").feature("surfTopo").set("expr", "sqrt(utx^2+uty^2)");
    model.result("pgTopo").label("Topology displacement magnitude");
    model.result().export("imgTopo").set("plotgroup", "pgTopo");
    model.result().export("imgTopo").set("imagetype", "png");
    model.result().export("imgTopo").set("filename", model.modelPath() + "/" + prefix + "_topology.png");
    model.result().export("imgTopo").set("pngfilename", model.modelPath() + "/" + prefix + "_topology.png");
    model.result().export("imgTheta").run();
    model.result().export("imgTopo").run();
  }
}
