import pypsa
import numpy as np
import pandas as pd
import cartopy.crs as ccrs
import plotly.express as px
import matplotlib.pyplot as plt
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


def capacity_mix(
        network : pypsa.Network,
        period : int,
        mul : float = 1e3,
    ) -> plt.figure:

    '''
    Plot capacity mix at the certain year per technology type
    (not per carrier)

    Parameters
    ----------

    network : pypsa.Network
        The PyPSA network object.
    period : int
        The year to plot (e.g., 2030).
    mul : float
        A scaling factor to convert units.

    Returns:
    ----------

    fig : plt.Figure
        The generated plot figure.

    '''

    # Filter and aggregate capacity data
    capacity = (
        network
        .generators
        .p_nom_opt[network.generators.index.str.contains(str(period))]
        .groupby([network.generators.bus, network.generators.type])
        .sum()
        .reset_index()
    )

    # Drop rows with missing types
    capacity['type'].replace('', np.nan, inplace=True)
    capacity.dropna(subset=['type'], inplace=True)

    # define order for x-axis
    cat_order = capacity.sort_values(by='bus').bus.unique().tolist()

    # function to show only percentages more than 5% in the pie chart
    def autopct_more_than_5(pct):
        return ('%1.f%%' % pct) if pct > 5 else ''

    # Configure figure size based on number of regions
    fig, axs = plt.subplots(
        nrows=1, 
        ncols=len(region_list), 
        figsize=(3 * len(cat_order), 5)  # Dynamically adjust width
    )

    # Ensures axs is always iterable
    axs = np.atleast_1d(axs)  

    # Generate pie chart for each region
    for region, ax in zip(cat_order, axs):
        data_region = capacity[capacity['bus'] == region]
        labels = data_region['type']

        ax.pie(
            data_region['p_nom_opt'] * mul,  # Apply scaling factor
            labels=None,
            autopct=autopct_more_than_5,
            colors=plt.cm.tab20.colors
        )

        ax.set_title(region.upper())

    # Create a single legend for all subplots
    fig.legend(
        labels=capacity['type'].unique(),
        ncols=2,
        bbox_to_anchor=(0.5, 0),
        loc='center'
    )

    fig.suptitle("Capacity mix by technology per region in " + str(period))

    return fig, axs


def total_capacity(
        network : pypsa.Network,
        period : int, 
        mul : float = 1e3,
    ) -> plt.Figure:

    '''
    Plot total installed capacity at the certain year 
    per technology type (not per carrier)

    Parameters
    ----------

    network : pypsa.Network
        The PyPSA network object.
    period : int
        The year to plot (e.g., 2030).
    mul : float
        A scaling factor to convert units.

    Returns:
    ----------

    fig : plt.Figure
        The generated plot figure.

    '''

    capacity = (
        network
        .generators
        .p_nom_opt[network.generators.index.str.contains(str(period))]
        .groupby([network.generators.bus, network.generators.type])
        .sum()
        .reset_index()
    )

    # remove backstop technology indicated by empty technology type
    capacity['type'].replace('', np.nan, inplace=True)
    capacity.dropna(subset=['type'], inplace=True)

    # Apply scaling factor
    capacity.p_nom_opt = capacity.p_nom_opt.div(mul)

    # define order for x-axis
    cat_order = capacity.sort_values(by='bus').bus.unique().tolist()

    fig = px.bar(
        capacity, 
        x = "bus", 
        y = "p_nom_opt", 
        color = "type",
        category_orders = {'bus' : cat_order},
    )

    fig.update_layout(
            yaxis_title= 'Capacity (GW)',
            xaxis_title='',
            title='Installed capacity in ' + str(period),
            width=1200,
            height=500,
            xaxis_tickangle=-45
        )
    
    return fig


def generation_mix(
        network : pypsa.Network,
        period : int, 
        mul : float = 1e6
    ) -> plt.Figure:

    '''
    Plot generation mix at the certain year per technology type
    (not per carrier)

    Parameters
    ----------

    network : pypsa.Network
        The PyPSA network object.
    period : int
        The year to plot (e.g., 2030).
    mul : float
        A scaling factor to convert units.

    Returns:
    ----------

    fig : plt.Figure
        The generated plot figure.

    '''

    generation = (
        network
        .generators_t
        .p
        .loc[period]
        .resample('YE')
        .sum()
        .groupby([network.generators.bus, network.generators.type], axis=1)
        .sum()
        .melt()
        .sort_values(by='bus')
        )
    
    # change empty technology type into 'backstop'
    generation.type.replace('', 'backstop', inplace=True)

    # Apply scaling factor
    generation.value = generation.value.div(mul)

    # define order for x-axis
    cat_order = generation.sort_values(by='bus').bus.unique().tolist()

    # function to show only percentages more than 5% in the pie chart
    def autopct_more_than_5(pct):
        return ('%1.f%%' % pct) if pct > 5 else ''

    # Configure figure size based on number of regions
    fig, axs = plt.subplots(
        nrows=1, 
        ncols=len(region_list), 
        figsize=(3 * len(cat_order), 5)  # Dynamically adjust width
    )

    # Ensures axs is always iterable
    axs = np.atleast_1d(axs)  

    # Generate pie chart for each region
    for region_list, ax in zip(region_list, axs.flat):
        data_region = generation[generation.bus == cat_order]
        labels = data_region.type

        ax.pie(
            data_region.value,
            labels = None, 
            autopct=autopct_more_than_5,
            colors=plt.cm.tab20.colors
            )                       
             
        ax.set_title(cat_order.upper())

    # Create a single legend for all subplots
    fig.legend(
        labels=generation['type'].unique(),
        ncols=2,
        bbox_to_anchor=(0.5, 0),
        loc='center'
    )

    fig.suptitle("Generation mix by technology per region in " + str(period))

    return fig, axs


def total_emission(
        network : pypsa.Network,
        period : int,
        mul : float = 1e6, 
    ) -> plt.Figure:

    '''
    Plot total installed capacity at the certain year per carrier

    Parameters
    ----------

    network : pypsa.Network
        The PyPSA network object.
    period : int
        The year to plot (e.g., 2030).
    mul : float
        A scaling factor to convert units.

    Returns:
    ----------

    fig : plt.Figure
        The generated plot figure.

    '''

    total_gen_per_carrier = (
        network
        .generators_t
        .p
        .loc[period]
        .resample('YE')
        .sum()
        .groupby([network.generators.bus, network.generators.carrier], axis=1)
        .sum()
        .melt()
        .sort_values(by='bus')
    )

    # List carriers from the generators output
    carrier_list = total_gen_per_carrier.carrier

    # List carriers from emission inputs
    emission_per_mwh = network.carriers.co2_emissions.reset_index()

    # Create new column in generators output
    total_gen_per_carrier['emission'] = ''

    # Calculate total emission from the generated power outputs based on 
    # emitted CO2 per MWh defined in the inputs
    for idx, val in enumerate(carrier_list):
        total_gen_per_carrier.emission[idx] = (
            total_gen_per_carrier.value[idx] * 
            (emission_per_mwh.co2_emissions
            .loc[emission_per_mwh.Carrier == val].values[0])
        )

    # convert emission values to MtCO2
    total_gen_per_carrier.emission = total_gen_per_carrier.emission.div(mul)

    # define order for x-axis
    cat_order = total_gen_per_carrier.sort_values(by='bus').bus.unique().tolist()

    fig = px.bar(
        total_gen_per_carrier, 
        x = "bus", 
        y = "emission", 
        color = "carrier",
        category_orders = {'bus' : cat_order},
    )

    fig.update_layout(
            yaxis_title= 'Emission (MtCO2)',
            xaxis_title='',
            title='Emission in ' + str(period),
            width=1200,
            height=500,
            xaxis_tickangle=-45
        )
    
    return fig