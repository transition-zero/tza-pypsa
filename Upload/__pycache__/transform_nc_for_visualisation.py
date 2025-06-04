import config
import pandas as pd
import pypsa

market = config.MARKET
pypsa_run_id = config.PYPSA_RUN_ID


def add_hour_of_year_column(df, datetime_col, new_col="hour_of_year"):
    df = df.copy()
    df[datetime_col] = pd.to_datetime(df[datetime_col])
    year_start = df[datetime_col].dt.to_period("Y").dt.start_time
    df[new_col] = ((df[datetime_col] - year_start).dt.total_seconds() // 3600).astype(int)
    return df


def split_and_assign(df, column, new_columns, indices, num_splits=2, delimiter="-"):
    splits = df[column].str.split(delimiter, n=num_splits, expand=True)
    for new_col, idx in zip(new_columns, indices):
        df[new_col] = splits[idx]
    df.drop(columns=[column], inplace=True)
    return df


def interconnector_by_nodes(p0, p1):
    df = pd.concat([p0, p1], ignore_index=True)
    return df.groupby(["snapshot", "Node", "Node_Destination"]).agg({"Value": "sum"}).reset_index()


def transform_visualiser_hourly_output(network: pypsa.Network) -> pd.DataFrame:
    generation = pd.melt(
        network.generators_t.p.reset_index(), id_vars="snapshot", var_name="Generator", value_name="Value"
    )
    loads = pd.melt(network.loads_t.p.reset_index(), id_vars="snapshot", var_name="Node", value_name="Value")
    prices = pd.melt(
        network.buses_t.marginal_price.reset_index(), id_vars="snapshot", var_name="Node", value_name="Value"
    )

    try:
        storage = pd.melt(
            network.storage_units_t.p.reset_index(), id_vars="snapshot", var_name="StorageUnit", value_name="Value"
        )
    except (AttributeError, KeyError) as e:
        print(f"Warning: Failed to extract storage_units_t.p — {e}")
        storage = None

    try:
        inter_p0 = pd.melt(network.links_t.p0.reset_index(), id_vars="snapshot", var_name="Link", value_name="Value")
        inter_p1 = pd.melt(network.links_t.p1.reset_index(), id_vars="snapshot", var_name="Link", value_name="Value")
    except (AttributeError, KeyError) as e:
        print(f"Warning: Failed to extract links_t.p0 or p1 — {e}")
        inter_p0 = inter_p1 = None

    generation = split_and_assign(generation, "Generator", ["Node", "Tech"], [0, 1])
    if storage is not None:
        storage = split_and_assign(storage, "StorageUnit", ["Node", "Tech"], [0, 1])
    if inter_p0 is not None:
        inter_p0 = split_and_assign(inter_p0, "Link", ["Node", "Node_Destination"], [0, 1])
    if inter_p1 is not None:
        inter_p1 = split_and_assign(inter_p1, "Link", ["Node", "Node_Destination"], [1, 0])

    if inter_p0 is not None or inter_p1 is not None:
        interconnector = interconnector_by_nodes(inter_p0, inter_p1)
        interconnector["Value"] *= -1
        interconnector["Type"] = "Interconnector"
        interconnector["Tech"] = "Interconnector"
    else:
        interconnector = None

    generation["Type"] = "Generation"
    if storage is not None:
        storage["Type"] = "Storage"
    loads["Type"] = "Demand"
    loads["Tech"] = "Demand"
    prices["Type"] = "Price"
    prices["Tech"] = "Price"

    dfs = [generation, loads, prices]
    if storage is not None:
        dfs.append(storage)
    if interconnector is not None:
        dfs.append(interconnector)

    merged_df = pd.concat(dfs, ignore_index=True)

    merged_df["HourOfDay"] = merged_df["snapshot"].dt.hour
    merged_df["DayOfMonth"] = merged_df["snapshot"].dt.day
    merged_df["Month"] = merged_df["snapshot"].dt.month
    merged_df["Year"] = merged_df["snapshot"].dt.year

    merged_df["Market"] = market
    merged_df["Pypsa_Run_Id"] = pypsa_run_id
    merged_df["time_resolution"] = "hourly"

    merged_df = add_hour_of_year_column(merged_df, "snapshot", "Hour8760")

    try:
        merged_df = merged_df.merge(network.buses.long_name, how="left", left_on="Node", right_index=True)
    except (AttributeError, KeyError) as e:
        print(f"Warning: Could not merge long_name from buses — {e}")

    return merged_df


def transform_visualiser_yearly_output(network: pypsa.Network) -> pd.DataFrame:
    df = network.statistics(groupby=["bus", "name", "carrier"]).reset_index()
    df.columns = ["Type", "Bus", "Bus_Tech_Vintage", "Tech"] + list(df.columns[4:])
    df = pd.melt(df, id_vars=["Type", "Bus", "Bus_Tech_Vintage", "Tech"], var_name="Metric", value_name="Value")
    df["Market"] = market
    df["Pypsa_Run_Id"] = pypsa_run_id
    df["Year"] = network.snapshots.year[0]
    df["time_resolution"] = "yearly"

    return df
