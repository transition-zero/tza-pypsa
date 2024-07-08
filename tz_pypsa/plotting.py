import pypsa

import pandas as pd
import cartopy.crs as ccrs
import matplotlib.pyplot as plt

def dispatch(
        network : pypsa.Network,
        time : pd.Timestamp = None,
        multiplier : float = 1,
):
    '''Plots dispatch curve for defined timestep
    '''
    p_by_carrier = network.generators_t.p.groupby(network.generators.carrier, axis=1).sum().mul(multiplier)

    if not network.storage_units.empty:
        sto = network.storage_units_t.p.T.groupby(network.storage_units.carrier).sum().T.mul(multiplier)
        p_by_carrier = pd.concat([p_by_carrier, sto], axis=1)

    fig, ax = plt.subplots(figsize=(6, 3))

    color = p_by_carrier.columns.map(network.carriers.color)

    if not time:
        time = network.snapshots[0:24]

    p_by_carrier.where(p_by_carrier > 0).loc[time].plot.area(
        ax=ax,
        linewidth=0,
        color=color,
    )

    charge = p_by_carrier.where(p_by_carrier < 0).dropna(how="all", axis=1).loc[time].mul(multiplier)

    if not charge.empty:
        charge.plot.area(
            ax=ax,
            linewidth=0,
            color=charge.columns.map(network.carriers.color),
        )

    network.loads_t.p_set.sum(axis=1).loc[time].mul(multiplier).plot(ax=ax, c="k")

    plt.legend(loc=(1.05, 0.1), ncol=1)
    ax.set_ylabel("Dispatch")
    return fig, ax


def network_map(
        network : pypsa.Network,
        bus_sizer : float = 4e8,
        link_sizer : float = 2e4,
):
    '''A version of PyPSA's built-in n.plot() function that formats everything somewhat nicely
    '''
    s = network.generators_t.p.sum(axis=0).groupby([network.generators.bus, network.generators.carrier]).sum()
    flow = pd.Series(network.links_t.p0.sum(axis=0).div(link_sizer).replace(0, 0).values, index=network.branches().index)

    fig,ax=plt.subplots(1,1,figsize=(10, 8),subplot_kw={"projection":ccrs.EqualEarth()})

    # Pandas series with MultiIndex
    collection = network.plot(
        bus_sizes=s / bus_sizer,
        #bus_colors={"gas": "indianred", "wind": "midnightblue"},
        margin=0.1,
        flow=flow,
        line_widths=0,
        link_widths=2.7, #network.links_t.p0.sum(axis=0).div(link_sizer).replace(0, 1)
        link_colors=network.links_t.p0.mean().abs(),
        link_alpha=1,
        projection=ccrs.EqualEarth(),
        color_geomap=True,
        ax=ax,
    )

    plt.colorbar(collection[2], fraction=0.04, pad=0.004, label="Mean Flow [MW]")
    plt.show()