# /// script
# requires-python = ">=3.13"
# dependencies = ["marimo==0.24.0", "symbolica==3.0.0"]
# ///

import marimo

__generated_with = "0.24.0"
app = marimo.App(width="medium", app_title="One-loop amplitudes")


@app.cell(hide_code=True)
def _():
    import marimo as mo
    from math import prod
    from time import perf_counter
    from symbolica import E, S, Expression, Replacement, Symbol, get_citations
    from symbolica import set_namespace as _set_namespace
    from symbolica.community import hepkit as hep, tensor
    from symbolica.community.hepkit import oneloop

    _set_namespace("gallery_one_loop")
    _denominator = hep.Symbols.denominator
    denominator_head = _denominator if isinstance(_denominator, Expression) else _denominator()
    return E, Expression, Replacement, S, Symbol, denominator_head, get_citations, hep, mo, oneloop, perf_counter, prod, tensor


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # One-loop amplitudes

    Use **one-loop-reduce** to turn generated Feynman diagrams into scalar
    master integrals. We start with a small numerator reduction, then calculate
    the massless QCD correction to
    $\gamma(p_0)\gamma(p_1)\to d(p_2)\bar d(p_3)$.

    The calculation keeps the Lorentz dimension $D$ symbolic. Setting $D=4$
    before multiplying by divergent integrals would discard finite terms.
    All scalar masters use
    [OneLOop's normalization](https://arxiv.org/abs/1007.4716);
    their last argument is the **squared** scale $\mu^2$.

    Adapted from the
    [symbolica-community example](https://github.com/symbolica-dev/symbolica-community/blob/main/examples/hep/oneloop_reduce.py).
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Start with a loop-momentum numerator

    For $D_0=k^2-m^2$, $D_1=(k+q_1)^2-m^2$ and
    $D_2=(k+q_1+q_2)^2-m^2$, reduce $k\cdot q_1/(D_0D_1D_2)$.
    The identity $2k\cdot q_1=D_1-D_0-q_1^2$ provides a direct check:
    the answer contains two bubbles and one triangle.
    """)
    return


@app.cell
def _(S, hep, oneloop):
    D, mu2 = S("D", "mu2")
    k, q1, q2, mass2, q1sq, q2sq, Qsq = S("k", "q1", "q2", "mass2", "q1sq", "q2sq", "Qsq")
    triangle_kinematics = (
        hep.Kinematics(D, momenta=[k, q1, q2])
        .with_scalar_product(q1, q1, q1sq)
        .with_scalar_product(q2, q2, q2sq)
        .with_scalar_product(q1, q2, (Qsq - q1sq - q2sq) / 2)
    )
    triangle = hep.IntegralFamily(
        [k], [q1, q2],
        [triangle_kinematics.scalar_product(_p, _p) - mass2
         for _p in [k, k + q1, k + q1 + q2]],
        kinematics=triangle_kinematics,
    )
    triangle_reduction = oneloop.reduce(
        triangle, [1, 1, 1], numerator=triangle_kinematics.scalar_product(k, q1)
    ).simplify()
    triangle_reduction.to_expression(mu_squared=mu2)
    return D, Qsq, mass2, mu2, q1sq, q2sq, triangle_reduction


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Generate the QCD correction

    Use the Standard Model's photon–down-quark and gluon–down-quark vertices,
    with a massless down quark, $Q_d=-1/3$ and $N_c=3$. The coupling orders
    select $e^2$ at tree level and $e^2g_s^2$ at one loop. The two photon
    orderings are both generated.

    `maximum_bridges=None` and `self_energy=None` retain the vertex and internal
    self-energy diagrams. External on-shell self energies are omitted: their
    loop integrals are scaleless in dimensional regularization. Closed quark
    triangles vanish by $\operatorname{tr}T^a=0$ and are excluded at generation.
    This leaves **two boxes, four vertex corrections and two self energies**.

    We use $s=(p_0+p_1)^2$, $t=(p_0-p_2)^2$, $u=-s-t$, with all four external
    particles on shell. This is the virtual QCD correction; its infrared poles
    cancel only after including real radiation in an infrared-safe observable.
    """)
    return


@app.cell
def _(D, E, Expression, S, hep):
    s, t = S("s", "t")
    u = -s - t
    # Older community wheels expose these symbols through static methods.
    K, P = [value if isinstance(value, Expression) else value()
            for value in (hep.Kinematics.loop_momentum, hep.Kinematics.external_momentum)]
    kinematics = hep.Kinematics(D, momenta=[K(0), P(0), P(1), P(2)])
    for _p in [P(0), P(1), P(2)]:
        kinematics = kinematics.with_scalar_product(_p, _p, E("0"))
    kinematics = (
        kinematics.with_scalar_product(P(0), P(1), s / 2)
        .with_scalar_product(P(0), P(2), -t / 2)
        .with_scalar_product(P(1), P(2), -u / 2)
    )
    return K, P, kinematics, s, t, u


@app.cell
def _(E, Symbol, hep):
    model = hep.Model.standard_model()
    ee, gs = model.parameter("ee").symbol, model.parameter("G").symbol
    vertices = [
        _v for _v in model.vertex_rules
        if sorted(_v.particles) in [sorted(["d", "d~", "a"]), sorted(["d", "d~", "g"])]
    ]
    process = model.process(["a", "a"], ["d", "d~"], vertex_allow=vertices)

    def generate(loop_order):
        return process.generate_diagrams(
            loops=loop_order,
            coupling_orders={"QED": 2, "QCD": 2 * loop_order},
            maximum_bridges=None,
            self_energy=None,
            fermion_loop_count_range=(0, 0),
            numerator_grouping=None,
            numerator_prefactor=Symbol.I if loop_order else E("1"),
            progress=None,
        ).diagrams

    born_diagrams = generate(0)
    generated_loops = generate(1)
    return born_diagrams, ee, generated_loops, gs, model


@app.cell(hide_code=True)
def _(D, E, K, P, S, denominator_head, hep, kinematics):
    from itertools import permutations

    _edge, _momentum, _mass, _inverse = S("edge_", "momentum_", "mass_", "inverse_")

    def denominator(edge):
        return kinematics.apply(
            edge.denominator_expression(dimension=D, in_lmb=True).to_expression()
            .replace(denominator_head(_edge, _momentum, _mass, _inverse), _inverse)
        ).expand()

    def is_amputated(diagram):
        return all(
            edge.momentum_signature().loops[0] or denominator(edge) != 0
            for edge in diagram.internal_edges
        )

    def loop_family(diagram):
        edges = [edge for edge in diagram.internal_edges if edge.momentum_signature().loops[0]]
        if len(edges) == 4:
            # Cyclic order gives D0(0,0,0,0,x,y,0,0,0,0,mu2).
            shifts = []
            for edge in edges:
                signature = edge.momentum_signature()
                shifts.append(sum((c * P(j) / signature.loops[0]
                                   for j, c in enumerate(signature.external)), E("0")))
            def separation(i, j):
                q = shifts[i] - shifts[j]
                return kinematics.scalar_product(q, q).expand()
            order = next(p for p in permutations(range(4))
                         if all(separation(p[i], p[(i + 1) % 4]) == 0 for i in range(4)))
            edges = [edges[i] for i in order]
        return hep.IntegralFamily(
            [K(0)], [P(0), P(1), P(2)], [denominator(edge) for edge in edges],
            kinematics=kinematics,
        )

    return denominator, is_amputated, loop_family


@app.cell
def _(D, born_diagrams, generated_loops, hep, is_amputated):
    loop_diagrams = [d for d in generated_loops if is_amputated(d)]
    born_amplitude = hep.Amplitude(born_diagrams, dimension=D)
    loop_amplitude = hep.Amplitude(loop_diagrams, dimension=D)
    born_amplitude
    return born_amplitude, loop_amplitude, loop_diagrams


@app.cell(hide_code=True)
def _(loop_diagrams, loop_family, mo):
    topology_names = {2: "Self energy", 3: "Vertex", 4: "Box"}
    diagram_choice = mo.ui.dropdown(
        options={f"{i + 1} · {topology_names[len(loop_family(d).denominators)]}": i
                 for i, d in enumerate(loop_diagrams)},
        value=f"1 · {topology_names[len(loop_family(loop_diagrams[0]).denominators)]}",
        label="Inspect a generated diagram",
    )
    diagram_choice
    return (diagram_choice,)


@app.cell(hide_code=True)
def _(diagram_choice, loop_diagrams, mo):
    # Isolate the diagram's scripts from marimo's DOM when switching diagrams.
    mo.iframe(loop_diagrams[diagram_choice.value].to_html(momenta=True))
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Reduce the entire amplitude

    Keep both photon indices and the outgoing quark spin/color indices open.
    `Amplitude.terms` supplies the graph weights and aligns these external ports
    across diagrams. We cancel the propagators, contract color, and apply
    `TensorReducer` with **all three independent external momenta**. The remaining
    loop scalar products go to `oneloop.reduce`; external tensors stay in its
    coefficients.

    The answer below is the complete amputated one-loop QCD operator in a scalar
    master basis, before choosing spins or photon polarizations. It includes
    terms that would disappear in the tree interference.

    Write $\mathcal M^{(1)}=c_\Gamma\widehat{\mathcal M}^{(1)}/(16\pi^2)$,
    where $c_\Gamma=(4\pi)^\epsilon\Gamma(1+\epsilon)
    \Gamma^2(1-\epsilon)/\Gamma(1-2\epsilon)$ and $D=4-2\epsilon$.
    We compute $\widehat{\mathcal M}^{(1)}$ with the model couplings included.
    The factor $i$ converting the loop measure to OneLOop masters was supplied
    by `numerator_prefactor`; the displayed result excludes $c_\Gamma/(16\pi^2)$.
    """)
    return


@app.cell(hide_code=True)
def _(D, E, K, P, S, denominator_head, hep, kinematics, loop_family, oneloop, prod, tensor):
    _edge, _momentum, _mass, _inverse = S("edge_", "momentum_", "mass_", "inverse_")
    _lorentz = tensor.Representation.mink(D)
    tensor_reducer = hep.TensorReducer(
        D, integrated=[K(0, tensor.PortPattern.exact(_lorentz))],
        external=[P(j, tensor.PortPattern.exact(_lorentz)) for j in range(3)],
    )

    def integrate_operator(diagram, operator):
        denominators = [
            edge.denominator_expression(dimension=D, in_lmb=True).to_expression()
            .replace(denominator_head(_edge, _momentum, _mass, _inverse), _inverse)
            for edge in diagram.internal_edges
        ]
        # Cancel before imposing on-shell kinematics. Restrict contraction to color:
        # premature Dirac-chain collection would hide loop vectors from TensorReducer.
        numerator = (operator.to_expression() * prod(denominators)).expand()
        numerator = tensor.TensorExpression(numerator).simplify_algebra(
            gamma=False, color=True, contract="selected",
            representations=[tensor.Representation.cof(3), tensor.Representation.coad(8)],
            color_substitute_cof_dimension_invariants=True,
        ).to_expression().expand()
        bridges = prod(kinematics.apply(denom) for edge, denom in
                       zip(diagram.internal_edges, denominators)
                       if not edge.momentum_signature().loops[0])
        family = loop_family(diagram)
        tensor_numerator = (kinematics.apply(tensor_reducer.reduce(numerator)) / bridges).expand()
        # Reduce only scalar monomials. External tensor coefficients are spectators;
        # keeping them out of the scalar solver avoids a large rational expansion.
        by_master, reductions = {}, []
        for monomial, tensor_coefficient in tensor_numerator.coefficient_list(*family.scalar_products):
            reduction = oneloop.reduce(
                family, [1] * len(family.denominators), numerator=monomial
            )
            reductions.append(reduction)
            compact = tensor.TensorExpression(tensor_coefficient.collect_factors()).simplify_algebra(
                gamma=False, color=True, contract="minimal", collect_coefficients=False,
                color_substitute_cof_dimension_invariants=True,
            ).to_expression()
            for coefficient, master in reduction.terms:
                if master.kind == "bubble" and all(x == 0 for x in list(master.to_expression())[:3]):
                    continue  # The massless zero-momentum bubble is scaleless.
                key = master.to_expression()
                if key not in by_master:
                    by_master[key] = [E("0"), master]
                by_master[key][0] += compact * coefficient
        terms = [(coefficient.collect_factors(), master) for coefficient, master in by_master.values()]
        return reductions, terms

    return (integrate_operator,)


@app.cell
def _(integrate_operator, loop_amplitude, loop_diagrams, mo, perf_counter):
    _start = perf_counter()
    tensor_reductions, amplitude_terms = [], []
    for _i, (_diagram, _operator) in enumerate(zip(loop_diagrams, loop_amplitude.terms)):
        with mo.status.spinner(title=f"Reducing amplitude · diagram {_i + 1}/{len(loop_diagrams)}"):
            _reduction, _terms = integrate_operator(_diagram, _operator)
        tensor_reductions.append(_reduction)
        amplitude_terms.append(_terms)
    amplitude_seconds = perf_counter() - _start
    return amplitude_seconds, amplitude_terms, tensor_reductions


@app.cell
def _(E, amplitude_terms, mu2, tensor):
    reduced_amplitude = tensor.TensorExpression(sum(
        (coefficient * master.to_expression(mu_squared=mu2)
         for terms in amplitude_terms for coefficient, master in terms), E("0")
    ))
    return (reduced_amplitude,)


@app.cell(hide_code=True)
def _(amplitude_seconds, loop_diagrams, mo, reduced_amplitude):
    mo.vstack([
        mo.md(f"**Reduced all one-loop diagrams.** {len(loop_diagrams)} diagrams · {amplitude_seconds:.1f} s. "
              "The pages below contain the full result, with external indices still open."),
        reduced_amplitude.expand().paged(page_size=25),
    ])
    return


@app.cell(hide_code=True)
def _(amplitude_terms, diagram_choice, mo, mu2, tensor):
    mo.accordion({"Master coefficients for the selected diagram": mo.vstack([
        mo.vstack([master.to_expression(mu_squared=mu2),
                   tensor.TensorExpression(coefficient).expand().paged(page_size=25)])
        for coefficient, master in amplitude_terms[diagram_choice.value]
    ])})
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Evaluate the complete tree interference

    As a scalar cross-check, form the coherent square of the two tree diagrams
    and each loop diagram, then select its $g_s^2$ coefficient. This retains
    **all 16 tree–loop pairings** and both complex-conjugate orientations.
    Sum final spins/colors and average the two incoming photon polarization
    spaces by $(D-2)^{-2}$ (conventional dimensional regularization).

    Define $V$ by
    $$2\,\overline{\operatorname{Re}(\mathcal M^{(0)*}\mathcal M^{(1)})}
      =\frac{c_\Gamma e^4g_s^2}{16\pi^2}\operatorname{Re}V.$$
    The extra calculation below takes about a minute on a native build and
    longer in the browser. Its exact master coefficients are computed from
    the diagrams; only the elementary **massless scalar master formulas** are
    supplied analytically for numerical evaluation.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    evaluate_interference = mo.ui.run_button(label="Compute the tree interference")
    evaluate_interference
    return (evaluate_interference,)


@app.cell(hide_code=True)
def _(D, K, P, S, born_diagrams, ee, gs, hep, kinematics, loop_family, oneloop, prod, tensor):
    _a, _b = S("a_", "b_")

    def interfere(diagram):
        amplitude = hep.Amplitude(born_diagrams + [diagram], dimension=D)
        squared = amplitude.squared().sum_spins(average_initial=True).sum_colors()
        cross = squared.expression().to_expression().expand().coefficient(gs**2)
        # The adjoint renames its dummy loop coordinate; both orientations
        # must use the same integration variable before scalar reduction.
        cross = cross.replace(K(_a, _b), K(0, _b))
        cross = cross.replace(P(3, _a), P(0, _a) + P(1, _a) - P(2, _a))
        scalar = tensor.TensorExpression(cross).simplify_algebra(
            contract="dots", gamma=True, color=True, collect_coefficients=False,
            color_substitute_cof_dimension_invariants=True,
        )
        if not scalar.is_scalar:
            raise ValueError("The spin/color sum left open tensor indices")
        family = loop_family(diagram)
        numerator = (kinematics.apply(scalar).to_expression()
                     * prod(family.denominators) / ee**4).together()
        reduction = oneloop.reduce(
            family, [1] * len(family.denominators), numerator=numerator
        ).simplify()
        return family, numerator, reduction

    return (interfere,)


@app.cell
def _(evaluate_interference, interfere, loop_diagrams, mo):
    mo.stop(not evaluate_interference.value)
    interference_records = []
    for _i, _diagram in enumerate(loop_diagrams):
        with mo.status.spinner(title=f"Tree interference · diagram {_i + 1}/{len(loop_diagrams)}"):
            interference_records.append(interfere(_diagram))
    return (interference_records,)


@app.cell
def _(E, S, interference_records, mu2):
    master_coefficients = {}
    for _, _, _reduction in interference_records:
        for _coefficient, _master in _reduction.terms:
            _call = _master.to_expression(mu_squared=mu2)
            if _master.kind == "triangle":
                _q = next((_x for _x in list(_call)[:3] if _x != 0), E("0"))
                _call = S("oneloopmaster::C0")(0, 0, _q, 0, 0, 0, mu2)
            if _call != S("oneloopmaster::B0")(0, 0, 0, mu2):
                master_coefficients[_call] = master_coefficients.get(_call, E("0")) + _coefficient
    master_coefficients = {m: c.together().factor() for m, c in master_coefficients.items()
                           if c.together() != 0}
    return (master_coefficients,)


@app.cell(hide_code=True)
def _(master_coefficients, mo):
    mo.vstack([
        mo.md("**Complete interference in scalar masters** · Each row is coefficient × master."),
        *[mo.vstack([master, coefficient]) for master, coefficient in master_coefficients.items()],
    ])
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Laurent expansion, including finite terms

    With $L_x=\log[(-x-i0)/\mu^2]$, the required massless masters are
    $$B_0(x)=\frac1\epsilon+2-L_x,\qquad
    C_0(0,0,x)=\frac1x\left(\frac1{\epsilon^2}-\frac{L_x}\epsilon+\frac{L_x^2}2\right),$$
    $$D_0(0,0,0,0,x,y)=\frac1{xy}\left[\frac4{\epsilon^2}
        -\frac{2(L_x+L_y)}\epsilon+2L_xL_y-\pi^2\right]+O(\epsilon).$$
    The first two formulas also omit $O(\epsilon)$. Scaleless bubbles vanish.
    Expanding every rational coefficient through $\epsilon^2$ preserves the
    finite terms multiplying simple and double poles.
    """)
    return


@app.cell(hide_code=True)
def _(D, E, S, Symbol, s, t, u):
    Ls, Lt, Lu = S("L_s", "L_t", "L_u")
    _logs = {s: Ls, t: Lt, u: Lu}

    def massless_master_coefficients(master):
        args = list(master.to_expression())
        zero = E("0")
        if master.kind == "bubble" and all(x == 0 for x in args[1:3]):
            q = args[0].expand()
            return [2 - _logs[q], E("1"), zero] if q != 0 else [zero] * 3
        if master.kind == "triangle" and all(x == 0 for x in args[3:6]):
            nonzero = [x.expand() for x in args[:3] if x.expand() != 0]
            if not nonzero:
                return [zero] * 3
            if len(nonzero) == 1:
                q = nonzero[0]
                return [_logs[q]**2 / (2 * q), -_logs[q] / q, 1 / q]
        if master.kind == "box" and all(x == 0 for x in args[:4] + args[6:10]):
            q, r = [x.expand() for x in args[4:6]]
            return [(2 * _logs[q] * _logs[r] - Symbol.PI**2) / (q * r),
                    -2 * (_logs[q] + _logs[r]) / (q * r), 4 / (q * r)]
        raise ValueError("This numerical section supports only the massless masters of this process")

    def expand_interference(records):
        result = [E("0")] * 3  # finite, simple pole, double pole
        for _, _, reduction in records:
            for coefficient, master in reduction.terms:
                c = coefficient.together()
                finite, pole, double = massless_master_coefficients(master)
                c0 = c.replace(D, 4)
                c1 = -2 * c.derivative(D).replace(D, 4)
                c2 = 2 * c.derivative(D).derivative(D).replace(D, 4)
                result[0] += c0 * finite + c1 * pole + c2 * double
                result[1] += c0 * pole + c1 * double
                result[2] += c0 * double
        return [x.together() for x in result]

    return Ls, Lt, Lu, expand_interference, massless_master_coefficients


@app.cell
def _(expand_interference, interference_records):
    laurent_coefficients = expand_interference(interference_records)
    return (laurent_coefficients,)


@app.cell(hide_code=True)
def _(laurent_coefficients, mo):
    mo.vstack([mo.vstack([mo.md(label), value]) for label, value in
               zip(["**Finite coefficient**", r"**$1/\epsilon$ coefficient**",
                    r"**$1/\epsilon^2$ coefficient**"], laurent_coefficients)])
    return


@app.cell(hide_code=True)
def _(mo):
    phase_space = mo.ui.batch(
        mo.md(r"$s$: {energy} · $\cos\theta$: {angle} · $\mu^2/s$: {scale}"),
        {"energy": mo.ui.number(start=1, stop=10000, value=1, step=1),
         "angle": mo.ui.slider(start=-0.9, stop=0.9, step=0.1, value=0.4),
         "scale": mo.ui.number(start=0.1, stop=10, step=0.1, value=1)},
    )
    phase_space
    return (phase_space,)


@app.cell(hide_code=True)
def _(Ls, Lt, Lu, laurent_coefficients, mo, phase_space, s, t):
    import math

    _inputs = phase_space.value
    _s = float(_inputs["energy"])
    _t = -_s * (1 - _inputs["angle"]) / 2
    _u, _mu2 = -_s - _t, _s * _inputs["scale"]
    _values = {s: _s, t: _t, Ls: complex(math.log(_s / _mu2), -math.pi),
               Lt: math.log(-_t / _mu2), Lu: math.log(-_u / _mu2)}
    numerical_interference = [complex(value.evaluate(_values)) for value in laurent_coefficients]
    mo.vstack([
        mo.md("**Numerical interference** · Real parts of $V$; common coupling/loop factor excluded."),
        mo.ui.table([{"Laurent coefficient": label, "Re V": value.real}
                     for label, value in zip(["finite", "1/ε", "1/ε²"], numerical_interference)],
                    selection=None),
        mo.md("The double and simple poles agree with universal quark infrared factorization. "
              "The complete finite coefficient is symmetric under exchanging the incoming photons, "
              "which sends $t\\leftrightarrow u$. These are checked by the notebook's regression test."),
    ])
    return (numerical_interference,)


@app.cell(hide_code=True)
def _(get_citations, mo, tensor_reductions):
    mo.accordion({"References used in this calculation": mo.vstack(
        [mo.md(citation.to_markdown()) for citation in get_citations()]
    )})
    return


if __name__ == "__main__":
    app.run()
