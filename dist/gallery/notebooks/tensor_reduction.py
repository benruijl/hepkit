# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "marimo==0.24.0",
# ]
# ///

import marimo

__generated_with = "0.24.0"
app = marimo.App(width="medium", app_title="Covariant tensor reduction")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Tensor reduction

    Perform efficient tensor reduction, even for high-rank tensors.
    """)
    return


@app.cell
def _():
    import marimo as mo
    from symbolica import E, S
    from symbolica import set_namespace as _set_namespace
    import symbolica.community.hepkit as hep
    from symbolica.community import tensor


    _set_namespace("angular_demo")
    return S, hep, mo, tensor


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## 1. Declare the integration variable

    Both vectors inhabit the same Lorentz space. Only `k` is integrated;
    `p` is an external vector and remains in the answer.
    """)
    return


@app.cell
def _(S, hep, tensor):
    D = S("D")
    lorentz = tensor.Representation.mink(D)
    k, p = tensor.TensorName.vector("k"), tensor.TensorName.vector("p")
    reducer = hep.TensorReducer(D, integrated=[k])
    return k, lorentz, p, reducer


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## 2. Reduce a compact scalar product

    Pass the numerator's expression to the reducer. No arithmetic expansion or
    sequence of tensor simplification passes is required.
    """)
    return


@app.cell
def _(k, lorentz, p):
    numerator = (k(1, lorentz) * p(lorentz))**2 * (k(2, lorentz) * p(2, lorentz))**2
    numerator
    return (numerator,)


@app.cell
def _(numerator, reducer, tensor):
    reduced = reducer.reduce(numerator.to_expression())
    tensor.TensorExpression(reduced)
    return


if __name__ == "__main__":
    app.run()
