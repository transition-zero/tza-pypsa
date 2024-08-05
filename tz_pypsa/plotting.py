import pypsa

import pandas as pd
import cartopy.crs as ccrs
import matplotlib.pyplot as plt

import plotly.express as px
import plotly.graph_objects as go


def energy_balance(
        network : pypsa.Network, 
        period : int,
        mul : float = 1e6,
        unit : str = 'TWh',
        show_imports : bool = True,
    ) -> go.Figure:

    '''
    Plot dispatch at daily resolution.

    Parameters
    ----------

    network : pypsa.Network
        The PyPSA network object.
    period : int
        The year to plot (e.g., 2030).
    mul : float
        The multiplier to convert units.
    unit : str
        The unit of the plot.
    show_imports : bool
        If True, show imports.
        
    Returns:
    ----------

    fig : go.Figure
        The generated plot figure.

    '''


    loads = (
        network
        .loads_t
        .p_set
        .loc[period]
        .resample('YE')
        .sum()
        .div(mul)
        .melt()
        .sort_values(by='Load')
        .reset_index(drop=True)
    )

    total_generation = (
        network
        .generators_t
        .p
        .loc[period]
        .resample('YE')
        .sum()
        .groupby([network.generators.bus, network.generators.carrier], axis=1)
        .sum()
        .div(mul)
        .melt()
        .sort_values(by='bus')
    )

    # append imports to df
    if show_imports:
        imports = (
            network
            .links_t
            .p0
            .loc[period]
            .resample('YE')
            .sum()
            .melt()
        )

        imports['bus'] = imports['Link'].apply(lambda x: x.split('-')[1])
        imports = imports.groupby(by='bus').sum(numeric_only=True).div(mul).reset_index().assign(carrier='imports')
        total_generation = pd.concat([total_generation, imports], ignore_index=True)

    # define order for x-axis
    cat_order = total_generation.sort_values(by='bus').bus.unique().tolist()

    # define colours for carriers
    colour_map = network.carriers.color.to_dict()
    colour_map['imports'] = 'peru'

    fig = px.bar(
        total_generation, 
        x="bus", 
        y="value", 
        color="carrier",
        color_discrete_map=colour_map,
        category_orders={'bus' : cat_order},
        #barmode="group",
    )

    fig.add_scatter(
        x=loads.Load,
        y=loads.value,
        mode='markers',
        name='Load',
        marker=dict(
            size=7,
            color='red',
            symbol='circle',
        ),
    )

    fig.update_layout(
        yaxis_title=f'Load [{unit}]',
        xaxis_title='',
        title='Bus-level energy balance',
        width=1200,
        height=500,
        xaxis_tickangle=-45
    )
    
    return fig


def dispatch(
        network : pypsa.Network, 
        period : int,
        iso_code : str, 
        resample : str = 'D',
        mul : float = 1e3,
        unit : str = 'GW',
        show_imports : bool = True,
        show_exports : bool = False,
    ) -> go.Figure:

    '''
    Plot dispatch at daily resolution.

    Parameters
    ----------

    network : pypsa.Network
        The PyPSA network object.
    period : int
        The year to plot (e.g., 2030).
    iso_code : str
        The ISO code of the country to plot (e.g., 'PHL').
    resample : str
        The resampling frequency.
    mul : float
        The multiplier to convert units.
    unit : str
        The unit of the plot.
    show_imports : bool
        If True, show imports.
    show_exports : bool
        If True, show exports.

    Returns:
    ----------

    fig : go.Figure
        The generated plot figure.

    '''

    # get exports
    cols = [i for i in network.links_t.p0.columns if iso_code in i.split('-')[0] and iso_code not in i.split('-')[1]]
    exports = (
        network
        .links_t
        .p0
        .loc[period]
        [cols]
        .sum(axis=1)
        .mul(-1)
        .resample(resample)
        .sum()
        .reset_index()
    )

    # get imports
    cols = [i for i in network.links_t.p0.columns if iso_code in i.split('-')[1] and iso_code not in i.split('-')[0]]
    imports = (
        network
        .links_t
        .p0
        .loc[period]
        [cols]
        .sum(axis=1)
        .resample(resample)
        .sum()
        .reset_index()
    )

    # get generation
    generation = (
        network
        .generators_t
        .p
        .loc[period]
        .filter(regex=iso_code)
        .groupby(network.generators.carrier, axis=1)
        .sum()
        .resample(resample)
        .sum()
        .reset_index()
        .copy()
    )

    # get storage dispatch
    storage_dispatch = (
        network
        .storage_units_t
        .p_dispatch
        .loc[period]
        .filter(regex=iso_code)
        .resample(resample)
        .sum()
        .sum(axis=1)
        .to_numpy()
    )

    # append storage dispatch to generation
    generation['battery'] = storage_dispatch

    # get load
    load = (
        network
        .loads_t
        .p
        .loc[period]
        .filter(regex=iso_code)
        .sum(axis=1)
        .resample(resample)
        .sum()
        .reset_index()
    )

    # Create figure
    fig = go.Figure()

    # add traces
    for generator in generation.columns:

        if generator != 'timestep':
            fig.add_trace(
                go.Scatter(
                    x=list(generation.timestep),
                    y=list(generation[generator].div(mul)),
                    mode='lines',
                    stackgroup='one',
                    name=generator,
                    line=dict(color=network.carriers.color.to_dict()[generator]),
                )
            )

    # add exports
    if show_exports:
        fig.add_trace(
                go.Scatter(
                x=list(exports.timestep),
                y=list(exports[0].div(mul)),
                mode='lines',
                #stackgroup='one',
                name='Exports',
                line=dict(color='magenta'),
                #fill='tozeroy',
            )
        )
    
    # add imports
    if show_imports:
        fig.add_trace(
                go.Scatter(
                x=list(imports.timestep),
                y=list(imports[0].div(mul)),
                mode='lines',
                stackgroup='one',
                name='Imports',
                line=dict(color='cyan'),
            )
        )
    
    # add load
    fig.add_trace(
            go.Scatter(
            x=list(load.timestep),
            y=list(load[0].div(mul)),
            mode='lines',
            #stackgroup='one',
            name='Load',
            line=dict(color='black', width=3),
        )
    )

    # Add range slider
    fig.update_layout(
        xaxis=dict(
            rangeselector=dict(
                buttons=list([
                    dict(count=5,
                         label="5D",
                         step="day",
                         stepmode="backward"),
                    dict(count=1,
                         label="1M",
                         step="month",
                         stepmode="backward"),
                    dict(count=3,
                         label="3M",
                         step="month",
                         stepmode="backward"),
                    dict(count=1,
                         label="1Y",
                         step="year",
                         stepmode="backward"),
                    # dict(step="all")
                ])
            ),
            rangeslider=dict(
                visible=True
            ),
            type="date",
        ),
        # yaxis_range=(0, (df.drop('timestep',axis=1).sum(axis=1).max() / 1e3)*1.05 ),
        yaxis_title=f'Generation [{unit}]',
        xaxis_title='Time (Day)',
        title='Daily Generation',
        width=1200,
        height=500,
    )

    # Show the plot
    return fig


def dispatch_simple(
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