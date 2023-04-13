from typing import Optional, Tuple

import geopandas as gpd
import numpy as np
from rasterio import features, profiles, transform

from eis_toolkit import exceptions


def rasterize_vector(
    geodataframe: gpd.GeoDataFrame,
    resolution: float,
    value_column: Optional[str] = None,
    default_value: float = 1.0,
    fill_value: float = 0.0,
    base_raster_profile: Optional[profiles.Profile] = None,
    buffer_value: Optional[float] = None,
) -> Tuple[np.ndarray, dict]:
    """Transform vector data into raster data.

    Args:
        geodataframe (geopandas.GeoDataFrame): The vector dataframe to be rasterized.
        resolution (float): The resolution i.e. cell size of the output raster
        value_column (Optional[str]): The column name with values for each geometry.
            If None, then default_value is used for all geometries.
        default_value (int): Default value burned into raster cells based on geometries.
        fill_value (int): VAlue used outside the burned geometry cells.
        buffer_value (float): Add buffer around passed geometries before rasterization.

    Returns:
        out_raster (tuple(numpy.ndarray, dict)): Raster data and metadata.
    """

    if geodataframe.shape[0] == 0:
        # Empty GeoDataFrame
        raise exceptions.EmptyDataFrameException("Expected geodataframe to contain geometries.")

    if not resolution > 0:
        raise ValueError(f"Expected a positive value resolution ({dict(resolution=resolution)})")
    if value_column is not None and value_column not in geodataframe.columns:
        raise ValueError(f"Expected value_column ({value_column}) to be contained in geodataframe columns.")
    if buffer_value is not None and buffer_value < 0:
        raise ValueError(f"Expected a positive buffer_value ({dict(buffer_value=buffer_value)})")

    if buffer_value is not None:
        geodataframe["geometry"] = geodataframe["geometry"].apply(lambda geom: geom.buffer(buffer_value))

    return _rasterize_vector(
        geodataframe=geodataframe,
        value_column=value_column,
        default_value=default_value,
        fill_value=fill_value,
        base_raster_profile=base_raster_profile,
        resolution=resolution,
    )


def _transform_from_geometries(
    geodataframe: gpd.GeoDataFrame, resolution: float
) -> Tuple[float, float, transform.Affine]:
    """Determine transform from the input geometries.

    Returns:
        width (float): Width of the raster
        height (float): Height of the raster
        out_transform (rasterio.transform.Affine): Affine transform of the output
    """
    min_x, min_y, max_x, max_y = geodataframe.total_bounds
    width = (max_x - min_x) / resolution
    height = (max_y - min_y) / resolution

    out_transform = transform.from_bounds(min_x, min_y, max_x, max_y, width=width, height=height)
    return width, height, out_transform


def _rasterize_vector(
    geodataframe: gpd.GeoDataFrame,
    value_column: Optional[str],
    default_value: float,
    fill_value: float,
    base_raster_profile: Optional[profiles.Profile],
    resolution: float,
) -> Tuple[np.ndarray, dict]:
    # rasterio.features.rasterize expects a shapes parameter which is
    # an iterable of tuples where the first value is a geometry and
    # the other a value for the geometry
    # Alternatively, if there are not values for each geometry,
    # an iterable of geometries can be passed
    geometries = geodataframe["geometry"].values
    values = geodataframe[value_column].values if value_column is not None else None
    geometry_value_pairs = list(geometries) if values is None else list(zip(geometries, values))

    if base_raster_profile is None:
        width, height, out_transform = _transform_from_geometries(geodataframe=geodataframe, resolution=resolution)
    else:
        width, height, out_transform = (
            base_raster_profile["width"],
            base_raster_profile["height"],
            base_raster_profile["transform"],
        )

    out_raster_array = features.rasterize(
        shapes=geometry_value_pairs,
        # fill and default_value can be floats even though typing claims otherwise
        fill=fill_value,
        default_value=default_value,
        transform=out_transform,
        out_shape=(round(height), round(width)),
    )
    return out_raster_array, dict(transform=out_transform, height=height, width=width)
