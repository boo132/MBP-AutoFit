# Runs in the Jython 2.1 interpreter shipped with MBP 2020.
from java.io import File, FileReader, BufferedReader, FileWriter, RandomAccessFile
from java.lang import Double, Math, String, System
from jarray import array
from javax.swing import JOptionPane
from com.accelicon.core.card import Card, CardTemplateManager
from com.accelicon.core.card.service import CardServiceProvider
from com.accelicon.core import CoreRuntimeException
from com.accelicon.core.common import Boundary
from com.accelicon.modelbuilder import ModelBuilderViewer

REPORT_DIR = "F:/Codex/BSIM4_AutoFit/reports"
SUPPORTED_MODEL_VERSIONS = (4.6, 4.7)

# DATA names come from the MEA Page headers. Edit here if those names differ.
PAGES = (
    ("ids_vgs_vbs", "ids", "vgs", ("vds", "vbs")),
    ("ids_vds_vgs", "ids", "vds", ("vgs", "vbs")),
    ("cgg_vgs_vbs", "cgg", "vgs", ("vds", "vbs")),
    ("cgc_vgs_vbs", "cgc", "vgs", ("vds", "vbs")),
)
CURVES = ("IdVg_lin", "IdVg_sat", "IdVd", "Cgg", "Cgc")
CGC_REGIONS = ("Cgc_left", "Cgc_right")
CGC_TAIL = "Cgc_left_tail"

# Step sizes in model-card units. Use absolute steps for parameters that can start at zero.
STEPS = (("vth0", 0.005, 0), ("u0", 0.05, 1), ("vsat", 0.05, 1),
         ("pclm", 0.10, 1), ("cgso", 0.10, 1), ("cgdo", 0.10, 1),
         ("voff", 0.005, 0), ("nfactor", 0.05, 1), ("ua", 0.10, 1),
         ("rdsw", 0.05, 1), ("eta0", 0.05, 1),
         ("voffcv", 0.015, 0), ("noff", 0.10, 1), ("acde", 0.15, 1),
         ("moin", 0.10, 1), ("dlc", 0.05, 1),
         ("ckappas", 0.05, 0), ("ckappad", 0.05, 0),
         ("cgbo", 1e-10, 0), ("cf", 5e-12, 0),
         ("cgsl", 1e-11, 0), ("cgdl", 1e-11, 0),
         ("ub", 0.15, 1), ("uc", 0.10, 1), ("cit", 1e-4, 0),
         ("minv", 0.10, 0), ("a0", 0.10, 0), ("delta", 0.002, 0),
         ("pdiblc1", 0.005, 0), ("pdiblc2", 0.002, 0), ("k2", 0.002, 0),
         ("phin", 0.01, 0), ("ndep", 0.05, 1), ("k1", 0.02, 0),
         ("dvt0", 0.10, 0), ("dsub", 0.03, 0), ("cdsc", 3e-5, 0),
         ("cdscd", 3e-5, 0), ("prwg", 0.05, 0), ("ags", 0.05, 0),
         ("drout", 0.025, 0), ("pvag", 0.05, 0),
         ("vfb", 0.01, 0), ("dwc", 2e-9, 0),
         ("a1", 0.02, 0), ("a2", 0.03, 0), ("llc", 3e-18, 0),
         ("minvcv", 0.10, 0), ("cvchargemod", 1, 0), ("toxp", 0.025, 1),
         ("ados", 0.10, 0), ("bdos", 0.10, 0))
FIXED_OXIDE_PARAMS = ("toxe", "dtox")
SEARCH_GROUPS = (
    ("iv", ("vth0", "voff", "nfactor", "u0", "ua", "rdsw", "vsat", "pclm", "eta0"),
     (("vth0", "u0"), ("u0", "rdsw"), ("vsat", "pclm"))),
    ("iv_shape", ("ub", "uc", "cit", "minv", "a0", "delta", "pdiblc1", "pdiblc2", "k2"),
     (("ua", "ub"), ("ua", "u0"), ("nfactor", "minv"), ("a0", "delta"),
      ("pdiblc1", "pdiblc2"))),
    ("threshold", ("phin", "ndep", "k1", "dvt0", "dsub", "cdsc", "cdscd"),
     (("phin", "ndep"), ("ndep", "k1"), ("vth0", "k1"),
      ("vth0", "dvt0"), ("eta0", "dsub"))),
    ("output", ("prwg", "ags", "drout", "pvag", "a1", "a2"),
     (("rdsw", "prwg"), ("a0", "ags"), ("pclm", "drout"), ("a1", "a2"))),
    ("cv", ("toxp", "acde", "ados", "bdos", "voffcv", "noff", "dlc", "llc", "moin", "cgso", "cgdo", "vfb", "dwc", "minvcv", "cvchargemod"),
     (("voffcv", "noff"), ("dlc", "cgdo"), ("vfb", "voffcv"), ("dlc", "dwc"),
      ("voffcv", "minvcv"), ("toxp", "acde"), ("toxp", "ados"),
      ("ados", "bdos"), ("vfb", "acde"), ("acde", "ndep"))),
    ("overlap", ("cgbo", "cf", "cgsl", "cgdl", "ckappas", "ckappad"),
     (("cgsl", "ckappas"), ("cgdl", "ckappad"), ("cgbo", "cf"),
      ("cgsl", "cgdl"), ("ckappas", "ckappad"),
      ("cgso", "cgsl"), ("cgdo", "cgdl"), ("cgso", "cgdl"), ("cgso", "cf"),
      ("cgso", "cgbo"))),
)
# Move the low-capacitance floor and overlap slope together. Include both
# Cgg compensation directions because the residual can change sign with bias.
OVERLAP_MOVES = (
    (("cgso", "cgsl", "cgdl"), ((-1, 1, 1), (1, -1, -1))),
    (("cgso", "cgdl", "ckappad"), ((-1, 1, 1), (-1, 1, -1), (1, -1, 1), (1, -1, -1))),
    (("cgso", "cgsl", "ckappas"), ((-1, 1, 1), (-1, 1, -1), (1, -1, 1), (1, -1, -1))),
    (("cgso", "cgsl", "cgdl", "cgbo"), ((-1, 1, 1, 1), (-1, 1, 1, -1))),
)
IV_TARGET = 0.01
DEFAULT_TIMEOUT_SECONDS = 600
MIN_STEP_SCALE = 0.03125
MAX_REGRESSION = 0.10
ERROR_TOLERANCE = 1e-9


class InvalidSimulation(RuntimeError):
    pass


def finite(value):
    return not (Double.isNaN(value) or Double.isInfinite(value))


def close(a, b):
    if not finite(a) or not finite(b):
        return a == b
    return abs(a - b) <= 1e-9 * max(abs(a), abs(b), 1e-30)


def parameter_values(parameters):
    return [float(p.getValue()) for p in parameters]


def require_values(parameters, values):
    for p, value in zip(parameters, values):
        if not close(p.getValue(), value):
            raise RuntimeError("Parameter readback mismatch: " + str(p.getName()))


def restore(parameters, values):
    for p, value in zip(parameters, values):
        if not close(p.getValue(), value):
            p.setValue(value)
    require_values(parameters, values)


def soft_bounds(parameter):
    return parameter.getLower(), parameter.getUpper()


def same_bounds(a, b):
    return ((a[0] == b[0] or close(a[0], b[0])) and
            (a[1] == b[1] or close(a[1], b[1])))


def set_soft_bounds(parameter, limits):
    if soft_bounds(parameter) != limits:
        parameter.setBoundary(limits[0], limits[1])
    return soft_bounds(parameter)


def set_oxide_value(parameter, value):
    if not finite(value) or not parameter.getHardLower() <= value <= parameter.getHardUpper():
        raise InvalidSimulation("Oxide value outside MBP limits: " + str(parameter.getName()))
    if close(parameter.getValue(), value):
        return
    lo, hi = soft_bounds(parameter)
    lo, hi = set_soft_bounds(parameter, (min(lo, value), max(hi, value)))
    if not lo <= value <= hi or not parameter.setValueInBoundary(value):
        raise InvalidSimulation("MBP rejected oxide value: " + str(parameter.getName()))
    require_values([parameter], [value])


def initialize_toxp(raw, value):
    hard = raw.getHardBoundary()
    if not finite(value) or value <= 0 or not hard.contains(value):
        return 0
    soft = raw.getSoftBoundary()
    # Include the inherited thickness and room for the first search step.
    lower = min(soft.getLower(), 0.975 * value)
    upper = max(soft.getUpper(), 1.025 * value)
    try:
        raw.setSoftBoundary(hard.intersect(Boundary(lower, upper)))
        if not raw.getSoftBoundary().contains(value):
            return 0
        raw.setValue(value)
    except CoreRuntimeException:
        return 0
    return close(raw.getDoubleValue(), value)


def add_candidate(model, name, report, added):
    root = model.getCard()
    sections = model.getBinNames()
    if len(sections) != 1:
        log(report, "add_skipped,%s,no_unique_model_section" % name)
        return
    section = str(sections[0])
    card = root.getSimpleCard(section)
    if card is None:
        log(report, "add_skipped,%s,no_model_section" % name)
        return
    template = CardTemplateManager.getInstance().getCardTemplate(card)
    if template is None or template.getParameter(name) is None:
        log(report, "add_skipped,%s,not_in_mbp_template" % name)
        return
    service = CardServiceProvider.getInstance()
    raw = service.newParameter(template, root, section, name)
    if raw is None:
        log(report, "add_skipped,%s,mbp_rejected" % name)
        return
    if name in ("dlc", "dwc", "llc"):
        source = {"dlc": "lint", "dwc": "wint", "llc": "ll"}[name]
        if model.isParamExist(source):
            value = model.getParam(source).getValue()
            if not finite(value) or not raw.getHardBoundary().contains(value):
                log(report, "add_skipped,%s,invalid_inherited_value" % name)
                return
            raw.setValue(value)
    if name == "toxp":
        value = model.getParamValue("toxe")
        if model.isParamExist("dtox"):
            value -= model.getParamValue("dtox")
        if not initialize_toxp(raw, value):
            log(report, "add_skipped,toxp,could_not_initialize,%s" % numbers((value,)))
            return
    owner = root.getCard(section)
    if owner is None:
        log(report, "add_skipped,%s,no_model_section" % name)
        return
    if owner.addParameter(raw) != Card.PARAM_ADD_SUCCESS:
        log(report, "add_skipped,%s,mbp_rejected" % name)
        return
    added[name] = (owner, raw)
    if not model.isParamExist(name):
        raise RuntimeError("Added parameter could not be read back: " + name)
    log(report, "add_trial,%s,%s" % (name, raw.getStringValue()))


def remove_added(model, name, added):
    owner, raw = added[name]
    if not owner.removeParameter(raw) or model.isParamExist(name):
        raise RuntimeError("Could not remove added parameter: " + name)
    del added[name]


def point_columns(points, names, page, kind, indices, allow_missing_output=0):
    # Read raw fields from each point instead of evaluating MBP expressions.
    fields = array(names, String)
    columns = [[] for name in names]
    for index in indices:
        point = points[index]
        row = list(point.getValues(fields))
        if len(row) != len(names):
            raise RuntimeError("Invalid %s field count on %s at point %d" %
                               (kind, page, index + 1))
        for col in range(len(names)):
            missing_output = (allow_missing_output and col == len(names) - 1 and
                              Double.isNaN(row[col]))
            if not finite(row[col]) and not missing_output:
                detail = ", ".join(["%s=%s" % pair for pair in zip(names, row)])
                message = "Invalid %s %s on %s at point %d/%d (%s). MEA: %s" % (
                    kind, names[col], page, index + 1, len(points), detail, point.getFile())
                if kind == "simulation" and col == len(names) - 1:
                    raise InvalidSimulation(message)
                raise RuntimeError(message)
            columns[col].append(row[col])
    return columns


def measured_indices(page, columns, coordinates, values):
    indices = range(len(values))
    if page != "ids_vds_vgs":
        return indices

    # MBP expands nonidentical VDS grids into a union grid for every VGS.
    # A NaN is a grid hole only when another branch has a measurement there.
    vds, vgs = coordinates[:2]
    if "vbs" in columns:
        vbs = coordinates[list(columns).index("vbs")]
    else:
        vbs = [None] * len(values)
    measured_biases = {}
    branch_counts = {}
    valid = []
    for i in indices:
        branch = (vgs[i], vbs[i])
        branch_counts[branch] = branch_counts.get(branch, 0)
        if finite(values[i]):
            valid.append(i)
            branch_counts[branch] += 1
            measured_biases.setdefault((vds[i], vbs[i]), {})[vgs[i]] = 1
    for i in indices:
        if Double.isNaN(values[i]):
            other = measured_biases.get((vds[i], vbs[i]), {})
            if not other or other.has_key(vgs[i]):
                raise RuntimeError("Invalid IdVd measurement at VDS=%s, VGS=%s, VBS=%s" %
                                   (vds[i], vgs[i], vbs[i]))
    for branch, count in branch_counts.items():
        if count < 2:
            raise RuntimeError("IdVd branch %s has fewer than two measured points" % (branch,))
    if len(valid) != len(values):
        System.out.println("IdVd: %d measured points, %d empty grid cells" %
                           (len(valid), len(values) - len(valid)))
    return valid


def load_curves():
    pages = []
    for page, output, axis, biases in PAGES:
        data = mbp.getData(page)
        if page == "cgg_vgs_vbs" and (data is None or not data.size()):
            page = "cgg_vgs_vds"
            data = mbp.getData(page)
        if data is None or not data.size():
            available = list(mbp.getDataCore().getDataNames())
            raise RuntimeError("Missing MEA page %s. Available: %s" % (page, available))
        measured = data.m()
        points = measured.toPointArray()
        if not len(points):
            raise RuntimeError("No measurement points on " + page)
        for point in points:
            data_polarity = str(point.getPolarName()).strip().lower()
            if data_polarity != polarity:
                raise RuntimeError("Active model is %s but MEA %s contains %s data on %s. "
                                   "Load only the MEA for the active model." %
                                   (polarity.upper(), point.getFile(), data_polarity.upper(), page))

        columns = (axis,) + biases
        available_columns = [str(name).lower() for name in measured.getBiasNames()]
        available_columns.extend([str(name).lower() for name in measured.getPropertyNames()])
        required = (axis,)
        if page == "ids_vgs_vbs":
            required += ("vds",)
        if page == "ids_vds_vgs":
            required += ("vgs",)
        for name in required:
            if name not in available_columns:
                raise RuntimeError("Missing MEA field %s on %s (file: %s)" %
                                   (name, page, points[0].getFile()))
        if output not in [str(name).lower() for name in measured.getOutputNames()]:
            raise RuntimeError("Missing MEA output %s on %s" % (output, page))
        columns = tuple([name for name in columns if name in available_columns])
        if len(points) < 2:
            raise RuntimeError("Invalid measurement point count on " + page)
        fields = point_columns(points, columns + (output,), page, "measurement",
                               range(len(points)), page == "ids_vds_vgs")
        coordinates, values = fields[:-1], fields[-1]
        indices = measured_indices(page, columns, coordinates, values)
        pages.append((page, data, output, columns, coordinates, values, indices))

    # The two IdVg groups share one MEA page type and differ by fixed VDS.
    by_vds = {}
    for index in range(len(pages[0][5])):
        vds = float(pages[0][4][1][index])
        if abs(vds) > 1e-9:
            if not by_vds.has_key(vds):
                by_vds[vds] = []
            by_vds[vds].append(index)
    voltages = by_vds.keys()
    voltages.sort(key_by_magnitude)  # Python 2.1 list.sort accepts a comparator.
    if (len(voltages) != 2 or voltages[0] * voltages[1] <= 0 or
        abs(voltages[0]) == abs(voltages[1])):
        raise RuntimeError("IdVg needs exactly two nonzero VDS values, found %s" % voltages)
    System.out.println("IdVg VDS: lin=%s, sat=%s" % tuple(voltages))

    groups = [(0, by_vds[voltages[0]]), (0, by_vds[voltages[1]])]
    for index in range(1, len(pages)):
        groups.append((index, pages[index][6]))
    return pages, groups, voltages


def key_by_magnitude(a, b):
    return cmp(abs(a), abs(b))


def cgc_regions(pages, groups):
    page_index, indices = groups[4]
    vgs = pages[page_index][4][0]
    values = pages[page_index][5]
    # Match the PMOS -VGS plot axis. NMOS uses VGS.
    sign = 1
    if polarity == "pmos":
        sign = -1
    left = [i for i in indices if sign * vgs[i] < -1e-9]
    right = [i for i in indices if sign * vgs[i] >= -1e-9]
    for region in (left, right):
        if len(region) < 2 or max([abs(values[i]) for i in region]) <= 0:
            return []
    return [(page_index, left), (page_index, right)]


def simulate(pages, groups, report=None, label=None):
    simulations = []
    for page, data, output, columns, coordinates, measured, indices in pages:
        if not data.doSimulation(mbp):
            raise InvalidSimulation("Simulation failed on " + page)
        points = data.s().toPointArray()
        if len(points) != len(measured):
            raise RuntimeError("Simulation point count mismatch on " + page)
        fields = point_columns(points, columns + (output,), page, "simulation", indices)
        for name, expected, actual in zip(columns, coordinates, fields[:-1]):
            for i, value in zip(indices, actual):
                if not close(value, expected[i]):
                    raise RuntimeError("Simulation point order mismatch: %s / %s" % (page, name))
        predicted = [None] * len(measured)
        for i, value in zip(indices, fields[-1]):
            predicted[i] = value
        simulations.append(predicted)

    if report is not None:
        for name, group_index in (("cgg", 3), ("cgc", 4)):
            page_index, indices = groups[group_index]
            vgs = pages[page_index][4][0]
            measured = pages[page_index][5]
            for i in indices:
                log(report, "%s_point_%s,%s" %
                    (name, label, numbers((vgs[i], measured[i], simulations[page_index][i]))))
        gg, gg_indices = groups[3]
        gc, gc_indices = groups[4]
        if (pages[gg][3] == pages[gc][3] and
            pages[gg][4] == pages[gc][4] and gg_indices == gc_indices):
            measured_cgb = [pages[gg][5][i] - pages[gc][5][i] for i in gg_indices]
            simulated_cgb = [simulations[gg][i] - simulations[gc][i] for i in gg_indices]
            squares = 0.0
            for measured, simulated in zip(measured_cgb, simulated_cgb):
                squares += (simulated - measured) ** 2
            log(report, "cgb_rmse_f_%s,%s" %
                (label, numbers((Math.sqrt(squares / len(gg_indices)),))))

    metrics = []
    for page_index, indices in groups:
        measured = pages[page_index][5]
        predicted = simulations[page_index]
        peak = max([abs(measured[i]) for i in indices])
        if len(indices) < 2 or peak <= 0:
            raise RuntimeError("Curve must have at least two points and a nonzero peak")
        square_sum = 0.0
        worst = 0.0
        for i in indices:
            residual = abs(predicted[i] - measured[i]) / peak
            if not finite(residual):
                raise InvalidSimulation("Non-finite simulation residual on " +
                                        (CURVES + CGC_REGIONS)[len(metrics)])
            square_sum += residual * residual
            worst = max(worst, residual)
        rms = Math.sqrt(square_sum / len(indices))
        if not finite(rms):
            raise InvalidSimulation("Non-finite RMS on " + (CURVES + CGC_REGIONS)[len(metrics)])
        metrics.append((rms, worst))
    if len(groups) == 7:
        page_index, left = groups[5]
        metrics.append(cgc_tail_error(pages[page_index][4][0], pages[page_index][5],
                                      simulations[page_index], left))
    return metrics


def cgc_tail_error(vgs, measured, predicted, left):
    # Use a straight-line fit to the outer half of the left voltage range.
    sign = 1
    if polarity == "pmos":
        sign = -1
    x = [sign * vgs[i] for i in left]
    lo, hi = min(x), max(x)
    tail = [i for i in left if sign * vgs[i] <= (lo + hi) / 2]
    if len(tail) < 2 or lo == hi:
        return (0.0,)
    total = 0.0
    for i in tail:
        total += sign * vgs[i]
    mean = total / len(tail)
    dx = [(sign * vgs[i] - mean) for i in tail]
    variance, projection = 0.0, 0.0
    for i, delta in zip(tail, dx):
        variance += delta * delta
        projection += delta * (predicted[i] - measured[i])
    peak = max([abs(measured[i]) for i in left])
    span = max([sign * vgs[i] for i in tail]) - lo
    mismatch = abs(projection / variance) * span / peak
    if not finite(mismatch):
        raise InvalidSimulation("Non-finite Cgc left-tail slope error")
    return (mismatch,)


def score(metrics):
    return reduce(lambda total, pair: total + pair[0], metrics[:5], 0.0) / 5


def iv_met(metrics):
    return max([pair[0] for pair in metrics[:3]]) < IV_TARGET


def objective(metrics):
    iv = [pair[0] for pair in metrics[:3]]
    cgg, cgc = metrics[3][0], metrics[4][0]
    cv_score = max(cgg, cgc)
    if iv_met(metrics):
        return 0, cv_score, (cgg + cgc) / 2
    gaps = [max(0.0, rms - IV_TARGET) for rms in iv]
    iv_gap = max(gaps) + Math.sqrt(reduce(lambda total, gap: total + gap * gap, gaps, 0.0))
    return 1, iv_gap, cv_score


def better(candidate, incumbent):
    new_phase, new_primary, new_secondary = objective(candidate)
    phase, primary, secondary = objective(incumbent)
    if new_phase != phase:
        return new_phase < phase
    if abs(new_primary - primary) > ERROR_TOLERANCE:
        return new_primary < primary
    return new_primary <= primary and new_secondary < secondary - ERROR_TOLERANCE


def acceptable(metrics, baseline, exploratory=0):
    cv_refinement = iv_met(baseline)
    if cv_refinement and not iv_met(metrics):
        return 0
    for i in range(3):
        rms, worst = metrics[i]
        initial_rms, initial_worst = baseline[i]
        if worst > initial_worst * (1 + MAX_REGRESSION) + ERROR_TOLERANCE:
            return 0
        ceiling = max(IV_TARGET, initial_rms * (1 + MAX_REGRESSION))
        if rms > ceiling + ERROR_TOLERANCE:
            return 0

    # Use shared C-V ceilings so the better curve can trade some accuracy
    # for an improvement in the worse one.
    cv_rms_limit = max(baseline[3][0], baseline[4][0])
    if exploratory or not cv_refinement:
        cv_rms_limit *= 1 + MAX_REGRESSION
    cv_max_limit = max(baseline[3][1], baseline[4][1]) * (1 + MAX_REGRESSION)
    return (max(metrics[3][0], metrics[4][0]) <= cv_rms_limit + ERROR_TOLERANCE and
            max(metrics[3][1], metrics[4][1]) <= cv_max_limit + ERROR_TOLERANCE)


def numbers(values):
    return ",".join(["%.17g" % value for value in values])


def log(report, row):
    report.write(row + "\n")
    report.flush()


def log_trial(report, label, values, metrics):
    errors = []
    for pair in metrics:
        errors.extend(pair)
    phase, primary, secondary = objective(metrics)
    log(report, "%s,%s,%s,%s," % (label, numbers(values), numbers(errors),
                                 numbers((score(metrics), phase, primary, secondary))))


def any_metric_changed(actual, expected):
    for new, old in zip(actual, expected):
        for a, b in zip(new, old):
            if abs(a - b) > ERROR_TOLERANCE:
                return 1
    return 0


def search(parameters, names, start, baseline, evaluate, report, trial_start, expired):
    specs = {}
    for name, step, relative in STEPS:
        specs[name] = step, relative
    steps, limits = [], []
    for i in range(len(parameters)):
        p = parameters[i]
        step, relative = specs.get(names[i], (0.0, 0))
        if relative:
            step *= abs(start[i])
            if step == 0 and finite(p.getStep()) and p.getStep() > 0:
                step = p.getStep()
        steps.append(step)
        limits.append((max(p.getLower(), p.getHardLower()),
                       min(p.getUpper(), p.getHardUpper())))
    for i in range(len(names)):
        lo, hi = limits[i]
        log(report, "bounds,%s,%s" % (names[i], numbers((lo, hi, steps[i]))))

    best, best_metrics = start[:], trial_start
    eligible, eligible_metrics = best, best_metrics
    exploratory = 0
    blocked = {}
    scale = 1.0
    sweep = 0
    selector = -1
    if "cvchargemod" in names:
        selector = names.index("cvchargemod")
    cv_first = SEARCH_GROUPS[-2:] + SEARCH_GROUPS[:-2]
    while 1:
        if expired():
            return eligible, eligible_metrics, sweep, "timeout"
        sweep += 1
        round_start = best[:]
        target_at_start = iv_met(best_metrics)
        search_groups = SEARCH_GROUPS
        if target_at_start:
            search_groups = cv_first
        for group, singles, pairs in search_groups:
            moves = [((name,), ((-1,), (1,))) for name in singles]
            moves.extend([(pair, ((-1, -1), (-1, 1), (1, -1), (1, 1))) for pair in pairs])
            if group == "overlap":
                moves.extend(OVERLAP_MOVES)
            if group == "cv":
                moves.extend((
                    (("toxp", "acde", "ados"), ((-1, -1, 1), (-1, 1, 1), (1, -1, -1), (1, 1, -1))),
                    (("cvchargemod", "minvcv"), ((1, -3), (1, 3), (1, 10))),
                    (("cvchargemod", "voffcv"), ((1, -3), (1, 3))),
                    (("cvchargemod", "minvcv", "voffcv"),
                     ((1, -3, -3), (1, 3, -3), (1, 10, -6))),
                ))
            for move, directions in moves:
                available = [name for name in move if name in names]
                if len(available) != len(move):
                    continue
                indices = [names.index(name) for name in move]
                base = best[:]
                if "minvcv" in move and "cvchargemod" not in move:
                    if selector < 0 or base[selector] != 1:
                        continue
                label = "r%d_%s_%s" % (sweep, group, "+".join(move))
                for signs in directions:
                    if expired():
                        return eligible, eligible_metrics, sweep, "timeout"
                    trial = base[:]
                    valid = 1
                    for i, sign in zip(indices, signs):
                        lo, hi = limits[i]
                        if i == selector:
                            desired = base[i] + sign
                            if desired not in (0, 1) or not lo <= desired <= hi:
                                valid = 0
                                break
                            trial[i] = desired
                            continue
                        if not lo <= start[i] <= hi:
                            valid = 0
                            break
                        desired = base[i] + sign * steps[i] * scale
                        edge = lo
                        if sign > 0:
                            edge = hi
                        if close(base[i], edge) and not blocked.has_key((i, sign)):
                            p = parameters[i]
                            hard_lo, hard_hi = p.getHardLower(), p.getHardUpper()
                            desired = min(hard_hi, max(hard_lo, desired))
                            if close(desired, edge):
                                blocked[i, sign] = 1
                                log(report, "boundary_limit,%s,%s" % (names[i], edge))
                            else:
                                old = soft_bounds(p)
                                request = min(old[0], desired), max(old[1], desired)
                                actual = set_soft_bounds(p, request)
                                limits[i] = (max(actual[0], hard_lo), min(actual[1], hard_hi))
                                lo, hi = limits[i]
                                if old == actual:
                                    blocked[i, sign] = 1
                                    log(report, "boundary_limit,%s,%s" % (names[i], edge))
                                else:
                                    log(report, "boundary_trial,%s,%s" % (names[i], numbers(actual)))
                        trial[i] = min(hi, max(lo, desired))
                        if close(trial[i], base[i]):
                            valid = 0
                            break
                    if valid:
                        try:
                            metrics = evaluate(trial)
                        except InvalidSimulation, error:
                            detail = '""'.join(str(error).split('"'))
                            log(report, 'rejected_%s,%s,%s,"%s"' %
                                (label, numbers(trial), "," * (reduce(
                                    lambda total, metric: total + len(metric), baseline, 4)),
                                 detail))
                            try:
                                recovered = evaluate(best)
                            except InvalidSimulation, recovery_error:
                                raise RuntimeError("Could not recover the last valid model after %s: %s" %
                                                   (label, recovery_error))
                            if any_metric_changed(recovered, best_metrics):
                                raise RuntimeError("Last valid model was not reproduced after " + label)
                            continue
                        log_trial(report, "trial_" + label, trial, metrics)
                        if acceptable(metrics, baseline) and (
                            not acceptable(eligible_metrics, baseline) or better(metrics, eligible_metrics)):
                            eligible, eligible_metrics = trial, metrics
                            if exploratory:
                                log_trial(report, "eligible_" + label, eligible, eligible_metrics)
                        valid_trial = acceptable(metrics, baseline, exploratory)
                        valid_best = acceptable(best_metrics, baseline, exploratory)
                        improves = better(metrics, best_metrics)
                        if exploratory:
                            delta = ((metrics[3][0] + metrics[4][0]) -
                                     (best_metrics[3][0] + best_metrics[4][0])) / 2
                            if abs(delta) > ERROR_TOLERANCE:
                                improves = delta < 0
                        if valid_trial > valid_best or (valid_trial == valid_best and
                                                       improves):
                            best, best_metrics = trial, metrics
                            prefix = "accepted_"
                            if exploratory:
                                prefix = "exploratory_"
                            log_trial(report, prefix + label, best, best_metrics)
        log_trial(report, "round_%d" % sweep, best, best_metrics)
        if not target_at_start and iv_met(best_metrics):
            scale = 1.0
        elif best == round_start:
            if scale <= MIN_STEP_SCALE:
                if exploratory or not iv_met(baseline):
                    return eligible, eligible_metrics, sweep, "no_improvement_at_minimum_step"
                exploratory = 1
                scale = 1.0
                log(report, "search_phase,temporary_cv_tradeoff")
            else:
                scale /= 2


def run_fit(model, parameters, names, start, missing, expired, search_timeout_seconds, requested_toxe):
    model_version = model.getParamValue("version")
    pages, groups, voltages = load_curves()
    regions = cgc_regions(pages, groups)
    groups.extend(regions)
    curves = CURVES
    slope_column = ""
    if regions:
        curves += CGC_REGIONS
        slope_column = "," + CGC_TAIL + "_slope_error"
    file = File.createTempFile("autofit-" + polarity + "-", ".csv", File(REPORT_DIR))
    report = FileWriter(file)
    System.out.println("Report: " + file.getAbsolutePath())
    keep_result = 0
    original_parameters = parameters[:]
    original_values = start[:]
    original_bounds = [soft_bounds(p) for p in parameters]
    added = {}
    try:
        log(report, "model,%s,%s" % (polarity, model.getSpiceName()))
        log(report, "model_version,%g" % model_version)
        log(report, "search_timeout_seconds,%g" % search_timeout_seconds)
        log(report, "cgc_point_fields,vgs,measured,simulated")
        log(report, "cgg_point_fields,vgs,measured,simulated")
        toxe_index = names.index("toxe")
        configured = start[:]
        if mode == "fit" and requested_toxe is not None:
            configured[toxe_index] = requested_toxe
        if mode == "fit" and "toxp" in names and "dtox" in names:
            configured[names.index("dtox")] = configured[toxe_index] - configured[names.index("toxp")]
        original_metrics = simulate(pages, groups, report, "baseline")
        baseline = original_metrics
        if start != configured:
            for i in range(len(start)):
                if names[i] in FIXED_OXIDE_PARAMS:
                    set_oxide_value(parameters[i], configured[i])
                    start[i] = parameters[i].getValue()
            baseline = simulate(pages, groups, report, "configured_start")
        log(report, "fixed_toxe_m,%s" % numbers((start[toxe_index],)))
        if iv_met(baseline):
            log(report, "cv_guard,shared_rms_and_max_limits")
        trial_start = baseline
        if mode == "fit":
            for name in missing:
                if expired():
                    break
                add_candidate(model, name, report, added)
                if added.has_key(name):
                    parameter = model.getParam(name)
                    if parameter is None or not finite(parameter.getValue()):
                        raise RuntimeError("Invalid added parameter: " + name)
                    try:
                        new_baseline = simulate(pages, groups)
                    except InvalidSimulation, error:
                        log(report, 'add_rejected,%s,"%s"' %
                            (name, '""'.join(str(error).split('"'))))
                        remove_added(model, name, added)
                        if any_metric_changed(simulate(pages, groups), trial_start):
                            raise RuntimeError("Could not recover after testing added parameter: " + name)
                        continue
                    trial_start = new_baseline
                    names.append(name)
                    parameters.append(parameter)
                    start.append(parameter.getValue())
        log(report, "vds_lin,vds_sat," + numbers(voltages))
        log(report, "trial," + ",".join(names) + "," +
            ",".join([curve + "_rms," + curve + "_max" for curve in curves]) +
            slope_column +
            ",score,iv_target_unmet,objective,secondary_objective,error")
        log_trial(report, "baseline", original_values + start[len(original_values):], original_metrics)
        if start[:len(original_values)] != original_values:
            log_trial(report, "configured_start", start, baseline)
        if mode == "preview":
            return ("%s BSIM%g Preview OK. VTH0=%.9g | TOXE: %.4g nm\n"
                    "Five-curve average RMS: %.2f%%\n\nReport: %s" %
                    (polarity.upper(), model_version, start[names.index("vth0")], start[toxe_index] * 1e9,
                     100 * score(baseline), file.getAbsolutePath()))
        if added:
            log_trial(report, "after_add", start, trial_start)

        toxp_index, dtox_index = -1, -1
        if "toxp" in names:
            toxp_index = names.index("toxp")
        if "dtox" in names:
            dtox_index = names.index("dtox")

        def evaluate(trial, parameters=parameters, pages=pages, groups=groups,
                     toxp_index=toxp_index, dtox_index=dtox_index, toxe_index=toxe_index):
            if toxp_index >= 0:
                if trial[toxp_index] <= 0:
                    raise InvalidSimulation("TOXP must be positive")
                if dtox_index >= 0:
                    value = trial[toxe_index] - trial[toxp_index]
                    set_oxide_value(parameters[dtox_index], value)
                    trial[dtox_index] = parameters[dtox_index].getValue()
            for p, value in zip(parameters, trial):
                if not close(p.getValue(), value) and not p.setValueInBoundary(value):
                    raise RuntimeError("MBP rejected " + str(p.getName()))
            require_values(parameters, trial)
            return simulate(pages, groups)

        best, best_metrics, rounds, reason = search(
            parameters, names, start, baseline, evaluate, report, trial_start, expired)
        accepted = acceptable(best_metrics, baseline) and better(best_metrics, baseline)
        if not accepted:
            best = start[:]
            best_metrics = baseline
        restore(parameters, best)
        charge_mode = 0
        if "cvchargemod" in names:
            charge_mode = best[names.index("cvchargemod")]
        kept = []
        for i in range(len(names)):
            name, parameter = names[i], parameters[i]
            unused_toxp = name == "toxp" and close(best[i], start[i])
            if unused_toxp and dtox_index >= 0:
                unused_toxp = close(best[dtox_index], start[dtox_index])
            if added.has_key(name) and (not accepted or
                (name in ("cvchargemod", "minvcv") and charge_mode == 0) or
                unused_toxp):
                remove_added(model, name, added)
            else:
                kept.append(i)
            if i < len(original_bounds):
                lo, hi = original_bounds[i]
                value = best[i]
                limits = min(lo, value), max(hi, value)
                if not same_bounds(set_soft_bounds(parameter, limits), limits):
                    raise RuntimeError("Could not finalize soft boundary: " + name)
        final_metrics = simulate(pages, groups, report, "applied")
        if not acceptable(final_metrics, baseline) or better(best_metrics, final_metrics):
            raise RuntimeError("Best candidate could not be reproduced")
        mbp.getGUI().update()
        for i in kept:
            name = names[i]
            if added.has_key(name):
                log(report, "added,%s" % name)
            elif not same_bounds(soft_bounds(parameters[i]), original_bounds[i]):
                log(report, "boundary_applied,%s,%s" %
                    (name, numbers(original_bounds[i] + soft_bounds(parameters[i]))))
        for name in names[len(original_parameters):]:
            if not added.has_key(name):
                log(report, "add_removed,%s" % name)
        log(report, "stop,%s,%d" % (reason, rounds))
        log_trial(report, "applied", best, final_metrics)
        keep_result = 1
        before = original_values + start[len(original_values):]
        changed = [names[i].upper() for i in kept if not close(before[i], best[i])]
        target = "met"
        if not iv_met(final_metrics):
            target = "not met"
        rms = ["%s %.3f%%" % (name, 100 * pair[0])
               for name, pair in zip(curves, final_metrics)]
        return ("%s BSIM%g done after %d rounds (%s). IV RMS < 1%%: %s\n%s\n%s\n"
                "CVCHARGEMOD: %g | TOXE: %.4g nm\n"
                "Changed: %s\nAdded: %s\n\nReport: %s" %
                (polarity.upper(), model_version, rounds, reason, target,
                 " | ".join(rms[:3]), " | ".join(rms[3:]),
                 charge_mode, best[toxe_index] * 1e9,
                 ", ".join(changed) or "0", ", ".join(added.keys()) or "0",
                 file.getAbsolutePath()))
    finally:
        try:
            if mode == "fit" and not keep_result:
                restore(original_parameters, original_values)
                for p, limits in zip(original_parameters, original_bounds):
                    if not same_bounds(set_soft_bounds(p, limits), limits):
                        raise RuntimeError("Could not restore soft boundary: " + str(p.getName()))
                for name in added.keys():
                    remove_added(model, name, added)
                mbp.getGUI().update()
        finally:
            report.close()


def rollback(model):
    reader = BufferedReader(FileReader(rollback_report))
    records = {}
    added, removed, boundaries = {}, {}, {}
    try:
        line = reader.readLine()
        while line is not None:
            fields = str(line).split(",")
            if fields[0] in ("model", "model_version", "trial", "baseline", "applied"):
                records[fields[0]] = fields[1:]
            elif fields[0] == "added":
                added[fields[1]] = 1
            elif fields[0] == "add_removed":
                removed[fields[1]] = 1
            elif fields[0] == "boundary_applied":
                boundaries[fields[1]] = tuple(map(float, fields[2:]))
            line = reader.readLine()
    finally:
        reader.close()
    if records.get("model") != [polarity, str(model.getSpiceName())]:
        raise RuntimeError("Rollback report belongs to another model")
    # Reports written before version tracking came from the 4.6-only script.
    recorded_version = records.get("model_version", ["4.6"])
    active_version = "%g" % model.getParamValue("version")
    if recorded_version != [active_version]:
        raise RuntimeError("Rollback report version %s does not match active BSIM%s" %
                           (", ".join(recorded_version), active_version))
    for key in ("trial", "baseline", "applied"):
        if not records.has_key(key):
            raise RuntimeError("Incomplete rollback report")
    header = records["trial"]
    if "IdVg_lin_rms" not in header:
        raise RuntimeError("Unrecognized rollback report")
    names = header[:header.index("IdVg_lin_rms")]
    supported = [spec[0] for spec in STEPS] + list(FIXED_OXIDE_PARAMS)
    if not names or len(names) != len(set_names(names)):
        raise RuntimeError("Invalid parameter list in rollback report")
    parameters, active_names, indices = [], [], []
    for i in range(len(names)):
        name = names[i]
        if removed.has_key(name):
            continue
        if name not in supported or not model.isParamExist(name):
            raise RuntimeError("Unknown rollback parameter: " + name)
        parameters.append(model.getParam(name))
        active_names.append(name)
        indices.append(i)
    current = parameter_values(parameters)
    count = len(names)
    if len(records["baseline"]) < count or len(records["applied"]) < count:
        raise RuntimeError("Incomplete rollback report")
    initial = [float(records["baseline"][i]) for i in indices]
    applied = [float(records["applied"][i]) for i in indices]
    for values in (initial, applied):
        if len(filter(finite, values)) != len(indices):
            raise RuntimeError("Incomplete rollback report")
    require_values(parameters, applied)
    current_bounds = [soft_bounds(p) for p in parameters]
    added_params = {}
    if added:
        root = model.getCard()
        sections = model.getBinNames()
        if len(sections) != 1:
            raise RuntimeError("Expected a single model section for rollback")
        owner = root.getCard(sections[0])
        for name in added.keys():
            raw = root.getParameter(sections[0], name)
            if raw is None:
                raise RuntimeError("Missing added parameter: " + name)
            added_params[name] = (owner, raw)
    deleted = []
    try:
        for name, p in zip(active_names, parameters):
            if boundaries.has_key(name) and not same_bounds(soft_bounds(p), boundaries[name][2:]):
                raise RuntimeError("Soft boundary changed since the report: " + name)
        restore(parameters, initial)
        for name, p in zip(active_names, parameters):
            if boundaries.has_key(name):
                limits = boundaries[name][:2]
                if not same_bounds(set_soft_bounds(p, limits), limits):
                    raise RuntimeError("Could not restore soft boundary: " + name)
        for name in added_params.keys():
            owner, raw = added_params[name]
            if not owner.removeParameter(raw):
                raise RuntimeError("Could not remove added parameter: " + name)
            deleted.append((owner, raw))
            if model.isParamExist(name):
                raise RuntimeError("Could not remove added parameter: " + name)
        mbp.getGUI().update()
    except:
        for owner, raw in deleted:
            if owner.addParameter(raw) != Card.PARAM_ADD_SUCCESS:
                raise RuntimeError("Could not undo parameter removal during rollback")
        for p, limits in zip(parameters, current_bounds):
            set_soft_bounds(p, limits)
        restore(parameters, current)
        mbp.getGUI().update()
        raise
    return "Restored parameter values from before the reported round"


def set_names(names):
    unique = {}
    for name in names:
        unique[name] = 1
    return unique


def main():
    global polarity
    if mode not in ("preview", "fit", "rollback"):
        raise RuntimeError("Check mode in the launcher")
    seconds = DEFAULT_TIMEOUT_SECONDS
    if globals().has_key("timeout_seconds"):
        seconds = float(timeout_seconds)
    if not finite(seconds) or seconds <= 0:
        raise RuntimeError("timeout_seconds must be a positive number")
    requested_toxe = None
    if mode == "fit" and globals().has_key("toxe_nm") and str(toxe_nm).strip():
        try:
            requested_toxe = float(toxe_nm) * 1e-9
        except ValueError:
            raise RuntimeError("toxe_nm must be a positive number in nm")
        if not finite(requested_toxe) or requested_toxe <= 0:
            raise RuntimeError("toxe_nm must be a positive number in nm")
    started = System.nanoTime()
    def expired(started=started, seconds=seconds):
        return System.nanoTime() - started >= seconds * 1e9
    if mode != "preview" and ModelBuilderViewer.isViewMode():
        raise RuntimeError("Open MBP in editing mode to change parameters")
    models = mbp.getModels()
    model = models.getMainModel()
    if model is None or len(model.getBinNames()) > 1:
        raise RuntimeError("Open a single BSIM4 model card without bins")
    level = model.getParamValue("level")
    version = model.getParamValue("version")
    if level != 54 or version not in SUPPORTED_MODEL_VERSIONS:
        raise RuntimeError("Select BSIM4.6 or BSIM4.7, level 54 in MBP (found level %s, version %s)" %
                           (level, version))
    # Older launchers may still set polarity explicitly. Use the active model.
    polarity = str(model.getCard().getPolarName()).strip().lower()
    if polarity not in ("nmos", "pmos"):
        raise RuntimeError("Expected an NMOS or PMOS model card, got: " + polarity)
    guard = RandomAccessFile(File(REPORT_DIR, "mbp_autofit.lock"), "rw")
    try:
        lock = guard.getChannel().tryLock()
        if lock is None:
            raise RuntimeError("Another AutoFit run is active")
        try:
            if mode == "rollback":
                message = rollback(model)
            else:
                names, parameters, missing = [], [], []
                for name, step, relative in STEPS:
                    if polarity == "nmos" and name in ("a1", "a2"):
                        continue
                    if model.isParamExist(name):
                        p = model.getParam(name)
                        if p is None or not finite(p.getValue()):
                            raise RuntimeError("Invalid fit parameter: " + name)
                        names.append(name)
                        parameters.append(p)
                    else:
                        missing.append(name)
                for name in FIXED_OXIDE_PARAMS:
                    if model.isParamExist(name):
                        p = model.getParam(name)
                        if p is None or not finite(p.getValue()):
                            raise RuntimeError("Invalid oxide parameter: " + name)
                        names.append(name)
                        parameters.append(p)
                if "toxe" not in names:
                    raise RuntimeError("Missing TOXE on active model")
                if "vth0" not in names:
                    raise RuntimeError("Missing fit parameter: vth0")
                message = run_fit(model, parameters, names, parameter_values(parameters),
                                  missing, expired, seconds, requested_toxe)
        finally:
            lock.release()
    finally:
        guard.close()
    System.out.println(message)
    JOptionPane.showMessageDialog(None, message, "BSIM4 AutoFit", JOptionPane.INFORMATION_MESSAGE)


main()
