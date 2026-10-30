# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "marimo==0.24.0",
#     "symbolica==3.0.0",
# ]
# ///

import marimo

__generated_with = "0.24.0"
app = marimo.App(
    width="medium",
    app_title="Four-loop gluon propagator numerators",
)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Four-loop gluon propagator numerators

    Generate all **four-loop 1PI gluon propagator graphs** in QCD with
    **one massless quark flavor**, and apply the Feynman rules of the numerator.

    Performed naively, the application of the Feynman rules may take a long time and generate large intermediate expressions. HEPkit tries to keep the expression factored as much as possible, optimizes its partial expansions and performs the contractions in an informed order.
    """)
    return


@app.cell
def _():
    from collections import Counter

    import marimo as mo
    from symbolica import S
    from symbolica.community.hepkit import Model
    from symbolica.community.tensor import TensorExpression

    return Counter, Model, S, TensorExpression, mo


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Generate the graphs

    Choose the model, create the process and generate the 4-loop diagrams.
    """)
    return


@app.cell
def _(Model):
    model = Model.qcd()
    # This example uses a massless down quark explicitly, independent of
    # the Standard Model's default masses. ZERO also fixes symbolic masses.
    import json as _json
    import re as _re

    _model_data = _json.loads(model.to_json())
    for _particle in _model_data["particles"]:
        if abs(_particle["pdg_code"]) == 1:
            _particle["mass"] = "ZERO"
    # Parameter cards change numerical values; these symbolic propagator
    # formulas must also be specialized for the massless calculation.
    for _propagator in _model_data["propagators"]:
        if _propagator["particle"] in {"d", "d~"}:
            for _field in ("numerator", "denominator"):
                _propagator[_field] = _re.sub(r"\bMD\b", "0", _propagator[_field])
    model = Model.from_json(_json.dumps(_model_data))

    process = model.process(["g"], ["g"], particle_veto=["u", "c", "s", "t", "b"])

    generation_result = process.generate_diagrams(loops=4)
    return generation_result, model, process


@app.cell
def _(process):
    process
    return


@app.cell(hide_code=True)
def _(Counter, generation_result, mo):
    mo.stop(
        not generation_result.report.completed,
        mo.md("Generation was interrupted. Rerun the generation cell to continue."),
    )
    _diagrams = generation_result.diagrams
    mo.stop(
        not _diagrams, mo.md("No four-loop gluon propagator graphs were generated.")
    )
    _options = {}
    for _index, _diagram in enumerate(_diagrams):
        _counts = Counter(edge.particle_name for edge in _diagram.internal_edges)
        _content = ", ".join(
            f"{count} {particle}" for particle, count in sorted(_counts.items())
        )
        _options[f"{_index + 1}: {_diagram.name} — {_content}"] = _index
    topology_choice = mo.ui.dropdown(
        options=_options,
        value=next(iter(_options)),
        allow_select_none=False,
        searchable=True,
        full_width=True,
        label="Topology",
    )
    mo.vstack(
        [
            mo.md(
                f"Generated **{len(_diagrams):,} graphs**. "
                "Search by graph name or internal particle content."
            ),
            topology_choice,
        ]
    )
    return (topology_choice,)


@app.cell
def _(generation_result, topology_choice):
    diagram = generation_result[topology_choice.value]
    diagram
    return (diagram,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Build the numerator and projector

    Build a $D$-dimensional numerator and display its structure. Then, construct a projector to turn the tensor a scalar.
    """)
    return


@app.cell
def _(S, diagram, model):
    numerator = diagram.numerator_expression(
        in_lmb=True
    ) * diagram.overall_factor_expression(evaluate=True)
    numerator = model.expand_couplings(numerator)
    numerator = numerator.with_lorentz_dimension(S("D")).collect_factors()
    numerator.structure
    return (numerator,)


@app.cell
def _(TensorExpression, numerator):
    slots = numerator.structure.slots()
    projector = (
        TensorExpression.g(slots[0], slots[1])
        * TensorExpression.g(slots[2], slots[3])
        / 8
    )
    projector
    return (projector,)


@app.cell
def _(numerator, projector):
    projected_numerator = projector * numerator
    projected_numerator
    return (projected_numerator,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Perform simple contractions that do not generate new terms

    Apply a subset of contractions to the tensor that do not generate new terms. Also fully simplify the graph's color tensor down to scalars.
    """)
    return


@app.cell
def _(projected_numerator):
    projected_numerator.simplify_algebra(
        contract="minimal", color=True, gamma=False
    ).to_dots()
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Contract to dot products

    Reduce the projected tensor in one call, including color and Dirac identities
    and Lorentz contractions. The order of contractions is optimized by studying the tensor network.
    """)
    return


@app.cell
def _(projected_numerator):
    reduced = projected_numerator.simplify_algebra(contract="dots")
    reduced
    return (reduced,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    Number of terms after a full expansion:
    """)
    return


@app.cell
def _(reduced):
    len(reduced.expand().to_expression())
    return


if __name__ == "__main__":
    app.run()
