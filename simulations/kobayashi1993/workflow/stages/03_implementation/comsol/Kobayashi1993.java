import com.comsol.model.*;
import com.comsol.model.util.*;

import java.io.IOException;
import java.util.Properties;

/**
 * COMSOL 6.4 implementation of Kobayashi, Physica D 63 (1993), Eqs. (3) and (5).
 *
 * Two scalar General Form PDE interfaces preserve the paper's conservative
 * fluxes explicitly. Whitelisted key=value product arguments select the run
 * without weakening COMSOL's default file-system security policy.
 */
public class Kobayashi1993 {
  public static Model build() {
    Model model = ModelUtil.create("Model");
    model.label("Kobayashi1993_dendrite.mph");
    model.modelPath(".");

    // One COMSOL metre and second represent one nondimensional L0 and t0.
    model.param().set("L", "9[m]", "paper square domain");
    model.param().set("epsbar", "0.01[m]", "paper mean interface width");
    model.param().set("tau", "0.0003[s]", "paper phase relaxation time");
    model.param().set("alpha", "0.9");
    model.param().set("gamma", "10");
    model.param().set("Teq", "1");
    model.param().set("Klatent", "2");
    model.param().set("delta", "0.02");
    model.param().set("jmode", "4");
    model.param().set("theta0", "0[rad]");
    model.param().set("noiseAmp", "0", "paper value is 0.01; smoke is deterministic");
    model.param().set("noiseSeed", "1993");
    model.param().set("hnoise", "0.03[m]", "paper random field spatial cell");
    model.param().set("dtnoise", "0.0002[s]", "paper random update cadence assumption");
    model.param().set("R0", "0.15[m]", "declared seed-radius assumption");
    model.param().set("D", "1[m^2/s]", "dimensionless thermal diffusivity");
    model.param().set("hmesh", "0.06[m]", "smoke mesh");
    model.param().set("maxStep", "0.0002[s]");
    model.param().set("dtout", "0.0002[s]");
    model.param().set("tfinal", "0.002[s]");

    model.component().create("comp1", true);
    model.component("comp1").geom().create("geom1", 2);
    model.component("comp1").geom("geom1").lengthUnit("m");
    model.component("comp1").geom("geom1").create("r1", "Rectangle");
    model.component("comp1").geom("geom1").feature("r1").set("size", new String[]{"L", "L"});
    model.component("comp1").geom("geom1").run("r1");

    model.component("comp1").variable().create("paper");
    model.component("comp1").variable("paper").label("Kobayashi paper equations 3 and 5");
    model.component("comp1").variable("paper").set("theta", "atan2(-py,-px)");
    model.component("comp1").variable("paper").set("anisArg", "jmode*(theta-theta0)");
    model.component("comp1").variable("paper").set("epsilon", "epsbar*(1+delta*cos(anisArg))");
    model.component("comp1").variable("paper").set("epsilonTheta", "-epsbar*delta*jmode*sin(anisArg)");
    model.component("comp1").variable("paper").set("mT", "alpha/pi*atan(gamma*(Teq-T))");
    model.component("comp1").variable("paper").set(
      "noiseHashArg",
      "12.9898*floor(x/hnoise)+78.233*floor(y/hnoise)+37.719*floor(t/dtnoise)+noiseSeed"
    );
    model.component("comp1").variable("paper").set(
      "chi",
      "mod(abs(sin(noiseHashArg)*43758.5453),1)-0.5"
    );
    // nojac changes the Newton linearization, not the residual flux.
    model.component("comp1").variable("paper").set(
      "GammaPx",
      "nojac(epsilon*epsilonTheta)*py-nojac(epsilon^2)*px"
    );
    model.component("comp1").variable("paper").set(
      "GammaPy",
      "-nojac(epsilon*epsilonTheta)*px-nojac(epsilon^2)*py"
    );
    model.component("comp1").variable("paper").set(
      "phaseSource",
      "p*(1-p)*(p-0.5+mT)+noiseAmp*p*(1-p)*chi"
    );

    // Paper Eq. (3): ea=0, da=tau, Gamma=(GammaPx,GammaPy), f=phaseSource.
    model.component("comp1").physics().create("gp", "GeneralFormPDE", "geom1", new String[]{"p"});
    model.component("comp1").physics("gp").label("Paper Eq. (3): anisotropic phase field");
    model.component("comp1").physics("gp").feature("gfeq1").setIndex(
      "Ga", new String[]{"GammaPx", "GammaPy"}, 0
    );
    model.component("comp1").physics("gp").feature("gfeq1").setIndex("ea", "0", 0);
    model.component("comp1").physics("gp").feature("gfeq1").setIndex("da", "tau", 0);
    model.component("comp1").physics("gp").feature("gfeq1").setIndex("f", "phaseSource", 0);
    model.component("comp1").physics("gp").feature("init1").set(
      "p", "0.5*(1-tanh((sqrt((x-L/2)^2+y^2)-R0)/(sqrt(2)*epsbar)))"
    );
    // The interface's default Zero Flux node is g=0, q=0 on every boundary.

    // Paper Eq. (5): ea=0, da=1, Gamma=-D grad(T), f=K dp/dt.
    model.component("comp1").physics().create("gT", "GeneralFormPDE", "geom1", new String[]{"T"});
    model.component("comp1").physics("gT").label("Paper Eq. (5): heat and latent heat");
    model.component("comp1").physics("gT").feature("gfeq1").setIndex(
      "Ga", new String[]{"-D*Tx", "-D*Ty"}, 0
    );
    model.component("comp1").physics("gT").feature("gfeq1").setIndex("ea", "0", 0);
    model.component("comp1").physics("gT").feature("gfeq1").setIndex("da", "1", 0);
    model.component("comp1").physics("gT").feature("gfeq1").setIndex("f", "Klatent*d(p,t)", 0);
    model.component("comp1").physics("gT").feature("init1").set("T", "0");
    // The interface's default Zero Flux node is the adiabatic condition.

    model.component("comp1").mesh().create("mesh1");
    model.component("comp1").mesh("mesh1").create("size1", "Size");
    model.component("comp1").mesh("mesh1").feature("size1").set("custom", "on");
    model.component("comp1").mesh("mesh1").feature("size1").set("hmax", "hmesh");
    model.component("comp1").mesh("mesh1").feature("size1").set("hmin", "hmesh");
    model.component("comp1").mesh("mesh1").create("map1", "Map");
    model.component("comp1").mesh("mesh1").feature("map1").selection().geom("geom1", 2);
    model.component("comp1").mesh("mesh1").feature("map1").selection().all();
    model.component("comp1").mesh("mesh1").run();

    model.component("comp1").cpl().create("intop1", "Integration");
    model.component("comp1").cpl("intop1").selection().geom("geom1", 2);
    model.component("comp1").cpl("intop1").selection().all();
    model.component("comp1").cpl().create("maxop1", "Maximum");
    model.component("comp1").cpl("maxop1").selection().geom("geom1", 2);
    model.component("comp1").cpl("maxop1").selection().all();
    model.component("comp1").cpl().create("minop1", "Minimum");
    model.component("comp1").cpl("minop1").selection().geom("geom1", 2);
    model.component("comp1").cpl("minop1").selection().all();

    model.component("comp1").variable().create("obs");
    model.component("comp1").variable("obs").set("solidMask", "if(p>=0.5,1,0)");
    model.component("comp1").variable("obs").set("solidArea", "intop1(p)");
    model.component("comp1").variable("obs").set("enthalpyInvariant", "intop1(T-Klatent*p)");
    model.component("comp1").variable("obs").set("tipY", "maxop1(if(p>=0.5,y,0))");
    model.component("comp1").variable("obs").set("halfWidth", "maxop1(if(p>=0.5,abs(x-L/2),0))");
    model.component("comp1").variable("obs").set("pMin", "minop1(p)");
    model.component("comp1").variable("obs").set("pMax", "maxop1(p)");
    model.component("comp1").variable("obs").set("TMin", "minop1(T)");
    model.component("comp1").variable("obs").set("TMax", "maxop1(T)");

    model.study().create("std1");
    model.study("std1").create("time", "Transient");
    model.study("std1").feature("time").set("tlist", "range(0,dtout,tfinal)");
    model.study("std1").feature("time").set("rtol", "1e-3");

    model.sol().create("sol1");
    model.sol("sol1").study("std1");
    model.sol("sol1").attach("std1");
    model.sol("sol1").create("st1", "StudyStep");
    model.sol("sol1").feature("st1").set("study", "std1");
    model.sol("sol1").feature("st1").set("studystep", "time");
    model.sol("sol1").create("v1", "Variables");
    model.sol("sol1").create("t1", "Time");
    model.sol("sol1").feature("t1").set("tlist", "range(0,dtout,tfinal)");
    model.sol("sol1").feature("t1").set("rtol", 1e-3);
    model.sol("sol1").feature("t1").set("timemethod", "bdf");
    model.sol("sol1").feature("t1").set("maxstepconstraintbdf", "const");
    model.sol("sol1").feature("t1").set("maxstepbdf", "maxStep");
    model.sol("sol1").feature("t1").set("maxorder", 2);
    model.sol("sol1").feature("t1").create("fc1", "FullyCoupled");

    model.result().table().create("tblGlobal", "Table");
    model.result().numerical().create("gev1", "EvalGlobal");
    model.result().numerical("gev1").set(
      "expr",
      new String[]{"solidArea", "enthalpyInvariant", "tipY", "halfWidth", "pMin", "pMax", "TMin", "TMax", "delta", "noiseAmp", "R0", "hmesh", "maxStep"}
    );
    model.result().numerical("gev1").set(
      "unit",
      new String[]{"m^2", "m^2", "m", "m", "1", "1", "1", "1", "1", "1", "m", "m", "s"}
    );
    model.result().numerical("gev1").set("table", "tblGlobal");

    model.result().export().create("data1", "Data");
    model.result().export("data1").set("expr", new String[]{"p", "T"});
    model.result().export("data1").set("unit", new String[]{"1", "1"});
    model.result().export("data1").set("descr", new String[]{"phase field", "temperature"});
    model.result().export("data1").set("separator", ",");
    model.result().export("data1").set("header", "on");
    model.result().export("data1").set("location", "regulargrid");
    model.result().export("data1").set("regulargridx2", "301");
    model.result().export("data1").set("regulargridy2", "301");
    return model;
  }

  private static double[] comparisonTimes(double finalTime) {
    if (finalTime >= 1.4 - 1e-12) {
      return new double[]{0.2, 0.8, 1.4};
    }
    if (finalTime >= 0.8 - 1e-12) {
      return new double[]{0.2, 0.8};
    }
    if (finalTime >= 0.2 - 1e-12) {
      return new double[]{0.2};
    }
    return new double[]{finalTime};
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

  private static void apply(Model model, Properties properties, String key) {
    String value = properties.getProperty(key);
    if (value != null && !value.trim().isEmpty()) {
      model.param().set(key, value.trim());
    }
  }

  public static void main(String[] args) throws IOException {
    Properties properties = loadCase(args);
    Model model = build();
    String[] parameterNames = new String[]{
      "delta", "noiseAmp", "noiseSeed", "R0", "hmesh", "maxStep", "dtout", "tfinal"
    };
    for (String parameter : parameterNames) {
      apply(model, properties, parameter);
    }
    String prefix = properties.getProperty("prefix", "smoke").trim();
    if (!prefix.matches("[A-Za-z0-9_.-]+")) {
      throw new IllegalArgumentException("unsafe prefix in case.properties");
    }
    model.save(model.modelPath() + "/" + prefix + "_built.mph");
    model.sol("sol1").runAll();
    model.result().numerical("gev1").setResult();
    model.result().table("tblGlobal").save(model.modelPath() + "/" + prefix + "_global.csv");
    model.result().export("data1").set("innerinput", "interp");
    model.result().export("data1").set("t", comparisonTimes(model.param().evaluate("tfinal")));
    model.result().export("data1").set("filename", model.modelPath() + "/" + prefix + "_fields.csv");
    model.result().export("data1").run();
    model.save(model.modelPath() + "/" + prefix + "_solved.mph");
  }
}
