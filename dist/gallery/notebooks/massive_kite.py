import marimo

__generated_with = "0.24.2"
app = marimo.App(
    width="medium",
    app_title="Two-loop kite: exact integration and transports",
)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # A two-loop kite: exact integration and transports

    Give two propagators on one outer arm of the kite **equal or different masses**,
    keeping the central line and the other arm massless. The integral depends
    on **three scales** in massive mode: $Q^2=-p^2>0$, $m_1^2>0$ and $m_2^2>0$.
    We compare $f=M^2I_E$ at $\rho=Q^2/M^2$, using a fixed reference scale
    $M^2=1$. In massive mode, $m_1^2=M^2$ and $r=m_2^2/M^2$; the same
    reference scale remains meaningful when both masses vanish.

    We generate the graph and its integral family with HEPkit, calculate $f$
    exactly using **HyperInt's hyperlogarithmic method**, then compare it with
    an independent **AMFlow starting value and DiffExp transport**. Try equal
    or unequal masses, or **set both masses to zero** with the toggle below.
    Change the momentum slider to evaluate the integral at different
    spacelike virtualities.
    """)
    return


@app.cell(hide_code=True)
def _():
    import marimo as mo
    from symbolica.community.hepkit import integration
    from symbolica.community.hep import integration as numerical_flow

    return integration, mo, numerical_flow


@app.cell(hide_code=True)
def _(mo, numerical_flow):
    from collections import Counter
    from fractions import Fraction
    from functools import lru_cache
    from math import factorial, log, log1p
    from pathlib import Path

    from scipy.integrate import quad
    from symbolica import E, S, get_citations
    from symbolica.community import hepkit as hep

    def is_kite(candidate):
        pairs = [tuple(sorted((e.source, e.target))) for e in candidate.internal_edges]
        return candidate.loop_count == 2 and len(pairs) == len(set(pairs)) == 5

    def hyperlogarithmic_value(expression, tolerance):
        @lru_cache(maxsize=4096)
        def g(word, endpoint):
            if not word:
                return 1.0
            if all(letter == 0 for letter in word):
                return log(endpoint) ** len(word) / factorial(len(word))
            if all(letter == word[0] for letter in word):
                return log1p(-endpoint / word[0]) ** len(word) / factorial(len(word))
            if all(letter == 0 for letter in word[:-1]):
                return -float(
                    E(str(endpoint / word[-1])).polylog(len(word)).evaluate({}).real
                )
            return quad(
                lambda t: g(word[1:], t) / (t - word[0]),
                0,
                endpoint,
                epsabs=tolerance,
                epsrel=tolerance,
                limit=200,
            )[0]

        constants = {}
        for atom in expression.get_all_indeterminates(False):
            name = atom.get_name().rsplit("::", 1)[-1]
            if name == "Hlog":
                endpoint, *word = [float(arg.evaluate({}).real) for arg in atom]
                if any(0 < letter < endpoint for letter in word):
                    raise ValueError(
                        "This helper requires a pole-free real integration path."
                    )
                constants[atom] = g(tuple(word), endpoint)
            elif name == "MZV":
                indices = list(atom)
                if len(indices) != 1:
                    raise ValueError(
                        "This example only requires depth-one zeta values."
                    )
                constants[atom] = indices[0].zeta().evaluate({}).real
            elif name == "Log2":
                constants[atom] = E("2").log().evaluate({}).real
            else:
                raise ValueError(f"Cannot evaluate the remaining constant {atom}.")
        return float(expression.evaluate(constants).real)

    def exact_value(expression):
        coarse = hyperlogarithmic_value(expression, 2e-9)
        fine = hyperlogarithmic_value(expression, 2e-12)
        # Refinement is an error estimate, rather than a rigorous enclosure.
        uncertainty = max(abs(fine - coarse), 2e-11 * max(1.0, abs(fine)))
        return fine, uncertainty

    cache_root = Path.home() / ".cache/symbolica/massive-kite/two-mass-arm-midpoint-v5"
    return (
        Counter,
        E,
        Fraction,
        S,
        cache_root,
        exact_value,
        get_citations,
        hep,
        is_kite,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Define the physical integral

    We use normalized Euclidean loop measures and strip coupling constants and
    the diagram symmetry factor:

    $$
    I_E(Q^2,m_1^2,m_2^2)=\int\frac{d^4k_E}{\pi^2}\frac{d^4\ell_E}{\pi^2}
    \frac{1}{[k_E^2+m_1^2](k_E-p_E)^2[\ell_E^2+m_2^2]
    (\ell_E-p_E)^2(k_E-\ell_E)^2},\qquad p_E^2=Q^2.
    $$

    All five powers are one. This integral is UV and IR convergent for
    $Q^2,m_1^2,m_2^2>0$, so the parameter integral can be evaluated at $D=4$.
    Choose a fixed reference scale **$M^2=1$** and write $\rho=Q^2/M^2$.
    In the massive mode, $m_1^2=M^2$ and $m_2^2=rM^2$. In the massless mode,
    both masses vanish while $M$ stays fixed. The displayed dimensionless
    quantity is always $f=M^2I_E$.

    ### Generate and display the graph

    The built-in $\phi^3$ model generates the kite topology. The two highlighted
    edges carry $m_1$ and $m_2$ in the integral below; the other three lines
    carry zero mass. Their momenta and mass assignment are listed explicitly
    when we construct the family.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    massless = mo.ui.checkbox(value=False, label="Set both masses to zero")
    mo.vstack(
        [
            mo.md("### Choose to set the masses to zero"),
            massless,
        ]
    )
    return (massless,)

@app.cell
def _(Counter, hep, is_kite):
    model = hep.Model.phi3()
    generated = model.process(["phi"], ["phi"]).generate_diagrams(
        loops=2,
        threads=1,
        max_vertices=4,
        allow_self_loops=False,
        maximum_bridges=0,
        progress=None,
    )
    (diagram,) = [candidate for candidate in generated if is_kite(candidate)]
    edges = sorted(diagram.internal_edges, key=lambda edge: edge.id)
    degrees = Counter(vertex for edge in edges for vertex in (edge.source, edge.target))
    (central_slot,) = [
        i
        for i, edge in enumerate(edges)
        if degrees[edge.source] == degrees[edge.target] == 3
    ]
    _massive_vertex = min(edges[central_slot].source, edges[central_slot].target)
    massive_slots = [
        i
        for i, edge in enumerate(edges)
        if i != central_slot and _massive_vertex in (edge.source, edge.target)
    ]
    return central_slot, diagram, edges, massive_slots, model


@app.cell(hide_code=True)
def _(diagram, edges, hep, massive_slots, massless, mo):
    from symbolica.community.graph import RenderSettings

    # The interactive viewer moves SVG nodes and styles its document. Keep
    # it in a separate frame so reactive mass changes cannot disrupt marimo.
    mo.output.append(
        mo.iframe(
            diagram.to_html(
                momenta=True,
                highlight=(
                    None
                    if massless.value
                    else diagram.subgraph(edges=[edges[i].id for i in massive_slots])
                ),
                style=hep.DiagramStyle(show_particle=False),
                config=RenderSettings(
                    title="Massless kite"
                    if massless.value
                    else "Two massive propagators on one arm",
                ),
            )
        )
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Derive the family and Symanzik polynomials

    HEPkit supplies the loop routing and physical propagator order. We keep
    that routing, assign squared masses $1$ and $r$ to the highlighted arm
    (or zero to every line in massless mode),
    and set the other masses to zero. The propagators span all scalar products, so no
    extra irreducible numerator slots are needed.

    With $p^2=-\rho$ and $D=4$, the normalized parameter formula is

    $$f(\rho,r)=\int_{x_i\ge0}d^5x\,\delta(1-\sum_i x_i)\frac{1}{U F}.$$

    In massive mode $F=\rho\,\widehat F_0+(x_a+r x_b)U$, where $x_a,x_b$ label
    the massive lines. Setting both masses to zero gives $F=\rho\widehat F_0$.
    The gamma prefactor is $\Gamma(1)=1$ in either mode.
    """)
    return


@app.cell
def _(E, S, diagram, edges, hep, massive_slots, massless, mo, model):
    rho, r = S("massive_kite::rho", "massive_kite::r")
    p = hep.Kinematics.external_momentum()(0)
    kinematics = hep.Kinematics(E("4"), momenta=[p]).with_scalar_product(p, p, -rho)
    graph_family = diagram.integral_family(kinematics=kinematics)
    model_mass = model.particle("phi").mass
    denominators = [
        denominator.replace(model_mass, E("0"))
        - (
            E("0")
            if massless.value
            else E("1")
            if i == massive_slots[0]
            else r
            if i == massive_slots[1]
            else E("0")
        )
        for i, denominator in enumerate(graph_family.denominators)
    ]
    family = hep.IntegralFamily(
        graph_family.loop_momenta,
        graph_family.external_momenta,
        denominators,
        kinematics=kinematics,
    )
    x = S(*[f"massive_kite::x{i}" for i in range(1, 6)])
    U, F = family.symanzik(x)
    mo.output.append(family)
    _routing = diagram.loop_momentum_basis.edge_signatures
    _rows = ["| Parameter | Edge | Momentum | Mass² / M² |", "|---|---:|---|---:|"]
    _rows += [
        f"| ${parameter}$ | {edge.id} | ${_routing[edge.id].format_momentum()}$ | {'0' if massless.value else '1' if i == massive_slots[0] else 'r' if i == massive_slots[1] else '0'} |"
        for i, (parameter, edge) in enumerate(zip(x, edges))
    ]
    mo.output.append(mo.md("\n".join(_rows)))
    mo.output.append(mo.vstack([mo.md("**First Symanzik polynomial $U$:**"), U]))
    mo.output.append(mo.vstack([mo.md("**Second Symanzik polynomial $F$:**"), F]))
    return F, U, p, r, rho, x


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Exact integration with HyperInt's method

    Fix the first massive-line parameter to one by the Cheng–Wu theorem. The other
    parameters range over $[0,\infty)$ in the supplied integration order.
    HEPkit's `integration.integrate` uses Hyperbolica's implementation of
    hyperlogarithmic integration; it does not call the Maple HyperInt package.
    `Expression.integrate(x)` instead computes an antiderivative.

    This mass assignment is linearly reducible in the chosen parameters.
    The exact answer consists of weight-three hyperlogarithms and zeta values,
    **without algebraic letters**. The expression below retains its full
    dependence on $\rho$ and $r$. We also integrate the equal-mass case directly,
    so no limiting procedure is needed when $r=1$.
    With the massless toggle, both mass terms are removed before integration.
    """)
    return


@app.cell
def _(E, F, U, central_slot, integration, massive_slots, massless, mo, r, x):
    parameter_integrand = (1 / (U * F)).replace(x[massive_slots[0]], E("1"))
    _massless_outer = [i for i in range(5) if i not in [central_slot, *massive_slots]]
    variables = [
        x[central_slot],
        *[x[i] for i in _massless_outer[::-1]],
        x[massive_slots[1]],
    ]
    _options = integration.IntegrationOptions(check_divergences=True)
    exact_expression = (
        integration.integrate(parameter_integrand, variables, _options)
        .expand()
        .cancel()
    )
    equal_mass_expression = (
        exact_expression
        if massless.value
        else (
            integration.integrate(
                parameter_integrand.replace(r, E("1")),
                variables,
                _options,
            )
            .expand()
            .cancel()
        )
    )
    mo.output.append(
        mo.accordion(
            {"Massless expression for f₀(ρ)": exact_expression}
            if massless.value
            else {
                "Exact expression for f(ρ, r)": exact_expression,
                "Equal-mass expression for f(ρ, 1)": equal_mass_expression,
            }
        )
    )
    return equal_mass_expression, exact_expression


@app.cell(hide_code=True)
def _(massless, mo):
    destination = mo.ui.slider(
        start=2,
        stop=3,
        step=0.25,
        value=2.5,
        label="Spacelike virtuality ρ = −p²/M²",
        show_value=True,
    )
    mass_ratio = mo.ui.dropdown(
        options={
            "Equal masses: r = 1": "1",
            "Unequal masses: r = 2": "2",
            "Unequal masses: r = 1/2": "1/2",
        },
        value="Equal masses: r = 1",
        label="Mass ratio r = m₂²/m₁² (massive mode)",
        disabled=massless.value,
    )
    mo.vstack(
        [
            mo.md("### Choose the masses, then vary the momentum"),
            mo.hstack([mass_ratio, destination]),
        ]
    )
    return destination, mass_ratio


@app.cell
def _(
    E,
    Fraction,
    destination,
    equal_mass_expression,
    exact_expression,
    exact_value,
    mass_ratio,
    massless,
    mo,
    r,
    rho,
):
    comparison_points = sorted(
        {
            Fraction("2"),
            Fraction("5/2"),
            Fraction("3"),
            Fraction(str(destination.value)),
        }
    )
    selected_expression = (
        equal_mass_expression
        if mass_ratio.value == "1"
        else exact_expression.replace(r, E(mass_ratio.value))
    )
    exact_results = {
        point: exact_value(selected_expression.replace(rho, E(str(point))))
        for point in comparison_points
    }
    _value, _uncertainty = exact_results[Fraction(str(destination.value))]
    _mass_description = (
        "both masses zero" if massless.value else rf"$r={mass_ratio.value}$"
    )
    mo.md(rf"""
    At $\rho={destination.value}$ with {_mass_description}, **$f={_value:.10f}$**.

    The expression is exact; this decimal evaluates its remaining finite
    hyperlogarithms using their iterated-integral definition,
    $G(a,\mathbf b;z)=\int_0^z dt\,G(\mathbf b;t)/(t-a)$.
    Symbolica evaluates the classical polylogarithms and zeta values.
    Tightening the quadrature tolerance gives an estimated absolute uncertainty
    of {_uncertainty:.1e}; this is not a rigorous error bound.
    """)
    return comparison_points, exact_results


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## AMFlow: compute an independent starting value

    We now use the **same selected family** in $D=4-2\epsilon$. AMFlow introduces
    an auxiliary mass, computes a simpler boundary, and flows back to the
    selected physical masses, including zero in massless mode. No exact hyperlogarithmic values
    are supplied as boundary data. The seed is at $p^2/M^2=-2.5$, in the
    middle of the comparison interval.

    IBP coefficients can contain poles in $\epsilon$ even though this target
    is finite. `required_master_range` determines how far to expand the
    masters before extracting the target's $\epsilon^0$ coefficient.

    The numerical loop measure is $d^Dk/(i\pi^{D/2})$ per loop, with propagators
    $q^2-m^2+i0$. Wick rotation contributes $(-1)^5$: we negate the numerical
    target to compare with the positive Euclidean integral defined above.

    **Compute the seed once**, then change the slider. The equal-mass case is
    the starting example, and its seed is computed with one worker.
    Opening the notebook does not start the calculation.
    Changing the masses requires a new seed; changing only the momentum
    reuses the seed for the chosen masses.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    run_amflow = mo.ui.run_button(label="Compute AMFlow seed at p²/M² = −2.5")
    mo.output.append(run_amflow)
    return (run_amflow,)


@app.cell
def _(
    E,
    S,
    cache_root,
    diagram,
    hep,
    mass_ratio,
    massive_slots,
    massless,
    mo,
    model,
    numerical_flow,
    p,
    rho,
    run_amflow,
):
    mo.stop(
        not run_amflow.value,
        mo.md("Press **Compute AMFlow seed** to start the independent comparison."),
    )
    D, epsilon = S("massive_kite_flow::D", "massive_kite_flow::epsilon")
    flow_kinematics = hep.Kinematics(D, momenta=[p]).with_scalar_product(p, p, -rho)
    _flow_graph_family = diagram.integral_family(kinematics=flow_kinematics)
    _model_mass = model.particle("phi").mass
    _flow_denominators = [
        denominator.replace(_model_mass, E("0"))
        - (
            E("0")
            if massless.value
            else E("1")
            if i == massive_slots[0]
            else E(mass_ratio.value)
            if i == massive_slots[1]
            else E("0")
        )
        for i, denominator in enumerate(_flow_graph_family.denominators)
    ]
    flow_family = hep.IntegralFamily(
        _flow_graph_family.loop_momenta,
        _flow_graph_family.external_momenta,
        _flow_denominators,
        kinematics=flow_kinematics,
    )
    _mass_cache = cache_root / (
        "massless" if massless.value else "r-" + mass_ratio.value.replace("/", "_")
    )
    evaluator = numerical_flow.IntegralEvaluator(
        options=numerical_flow.EvaluationOptions(
            digits=8,
            guard_digits=24,
            series_order=70,
            workers=1,
            mass_mode="branch" if massless.value else "mass",
            sampled_reduction=not massless.value,
            cache_directory=str(_mass_cache / "reductions"),
            sample_cache_directory=str(_mass_cache / "samples"),
        )
    )
    with mo.status.spinner(title="Preparing the selected family and AMFlow boundary"):
        prepared_flow = evaluator.prepare(
            flow_family,
            [[1] * 5],
            [rho],
            epsilon,
            branch_domain=f"Euclidean rho > 1; p squared = -rho; squared masses = {'0, 0' if massless.value else '1, ' + mass_ratio.value}",
        )
        seed_point = {rho: E("5/2")}
        _seed_leading, _seed_last = prepared_flow.required_master_range(
            seed_point, 0, 0
        )
        seed_directory = _mass_cache / "seed"
        flow_cache = (
            numerical_flow.BoundaryCache.load(seed_directory)
            if (seed_directory / "physical-boundaries.bin").exists()
            else numerical_flow.BoundaryCache()
        )
        if len(flow_cache):
            seed = prepared_flow.transport(
                flow_cache,
                seed_point,
                _seed_leading,
                _seed_last,
                admit_straight_path=True,
            )
        else:
            seed = prepared_flow.generate_boundary(
                flow_cache,
                seed_point,
                last=_seed_last,
                extra_digits=5 if massless.value else 6,
            )
            flow_cache.save(seed_directory)
        (seed_target,) = prepared_flow.project_targets(seed, 0, 0, digits=8)
    destination_caches = {}
    seed_value = -seed_target.coefficients[0]
    _seed_label = "f_0(2.5)" if massless.value else f"f(2.5,{mass_ratio.value})"
    mo.md(rf"""
    **AMFlow seed: ${_seed_label}={float(seed_value.real):.10f}$**

    Estimated absolute uncertainty: {float(seed_target.absolute_errors[0]):.2e}.
    The family has {len(prepared_flow.basis)} masters, retained through
    $\epsilon^{_seed_last}$ for this finite target.
    """)
    return destination_caches, flow_cache, prepared_flow


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## DiffExp: transport at fixed mass, then compare

    HEPkit derives the coupled differential equations in $\rho$ from the selected
    family. DiffExp solves them by local series expansions, starting from the
    AMFlow seed. The selected masses remain fixed; all paths stay spacelike.

    The table compares the independently computed finite terms. The exact
    result is used only on the comparison side, never to seed or guide transport.
    Every destination starts from the original seed so changing the slider does
    not accumulate uncertainty along previously visited destinations.

    The default comparison uses $2\le\rho\le3$ and eight-digit target values.
    To transport farther, increase the AMFlow seed precision before extending
    the slider; the exact formula itself is not restricted to this interval.
    """)
    return


@app.cell
def _(
    E,
    comparison_points,
    destination_caches,
    exact_results,
    flow_cache,
    mo,
    numerical_flow,
    prepared_flow,
    rho,
):
    flow_results = []
    with mo.status.spinner(title="DiffExp transport at the selected masses"):
        for point in comparison_points:
            coordinates = {rho: E(str(point))}
            _leading, _last = prepared_flow.required_master_range(coordinates, 0, 0)
            if point not in destination_caches:
                point_cache = numerical_flow.BoundaryCache()
                point_cache.extend(flow_cache)
                destination_caches[point] = point_cache
            transported = prepared_flow.transport(
                destination_caches[point],
                coordinates,
                _leading,
                _last,
                admit_straight_path=True,
            )
            (target,) = prepared_flow.project_targets(transported, 0, 0, digits=8)
            value = -target.coefficients[0]
            uncertainty = float(target.absolute_errors[0])
            flow_results.append(
                (point, float(value.real), float(value.imag), uncertainty)
            )
    _rows = [
        "| ρ | Hyperlogarithms | AMFlow / DiffExp | Absolute difference | Estimated uncertainties: exact / flow |",
        "|---:|---:|---:|---:|---:|",
    ]
    agreement = True
    for point, value, imaginary, uncertainty in flow_results:
        exact, exact_uncertainty = exact_results[point]
        difference = abs(value - exact)
        agreement &= max(difference, abs(imaginary)) <= 5 * (
            uncertainty + exact_uncertainty
        )
        _rows.append(
            f"| {point} | {exact:.10f} | {value:.10f} | {difference:.2e} | {exact_uncertainty:.1e} / {uncertainty:.1e} |"
        )
    mo.output.append(mo.md("\n".join(_rows)))
    mo.output.append(
        mo.callout(
            "The independent determinations agree within five times their combined estimated uncertainties, and the imaginary parts are consistent with zero."
            if agreement
            else "At least one point needs more precision: inspect the differences and estimated uncertainties above.",
            kind="success" if agreement else "warn",
        )
    )
    return (flow_results,)


@app.cell
def _(exact_results, flow_results, massless, mo):
    import matplotlib.pyplot as _plt

    _points = [float(row[0]) for row in flow_results]
    _flow = [row[1] for row in flow_results]
    _exact = [exact_results[row[0]][0] for row in flow_results]
    _uncertainties = [row[3] for row in flow_results]
    _figure, _axes = _plt.subplots(figsize=(6, 3.8), constrained_layout=True)
    _axes.plot(
        _points, _exact, "-", label="Analytic hyperlogarithmic result", color="#0e7490"
    )
    _axes.errorbar(
        _points,
        _flow,
        yerr=_uncertainties,
        fmt="o",
        capsize=3,
        label="AMFlow / DiffExp",
        color="#b45309",
    )
    _axes.set(
        xlabel=r"ρ = Q² / M²",
        ylabel=r"f = M² I_E",
        title="Massless kite" if massless.value else "Momentum dependence with two masses",
    )
    _axes.legend(fontsize=8)
    mo.output.append(_figure)
    _plt.close(_figure)
    return


@app.cell(hide_code=True)
def _(get_citations, mo):
    mo.vstack(get_citations())
    return


if __name__ == "__main__":
    app.run()
