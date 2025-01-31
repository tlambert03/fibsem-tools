from typing import Tuple
import pytest
import dask.array as da
from xarray import DataArray
from fibsem_tools.io.core import access, read
from fibsem_tools.io.dask import store_blocks
from numcodecs import GZip
from fibsem_tools.io.multiscale import (
    multiscale_group,
    multiscale_metadata,
)


@pytest.mark.parametrize(
    "metadata_types",
    [("ome-ngff@0.4",), ("neuroglancer",), ("ome-ngff",), ("ome-ngff", "neuroglancer")],
)
def test_multiscale_storage(temp_zarr, metadata_types: Tuple[str, ...]):
    data = da.random.randint(0, 8, (16, 16, 16), chunks=(8, 8, 8), dtype="uint8")
    coords = [
        DataArray(
            da.arange(data.shape[0]) + 10,
            attrs={"units": "nm", "type": "space"},
            dims=("z",),
        ),
        DataArray(
            da.arange(data.shape[1]) + 20,
            attrs={"units": "nm", "type": "space"},
            dims=("y"),
        ),
        DataArray(
            da.arange(data.shape[2]) - 30,
            attrs={"units": "nm", "type": "space"},
            dims=("x",),
        ),
    ]
    multi = [DataArray(data, coords=coords)]
    multi.append(multi[0].coarsen({"x": 2, "y": 2, "z": 2}).mean().astype("uint8"))
    array_paths = ["s0", "s1"]
    g_meta, a_meta = multiscale_metadata(
        multi, metadata_types=metadata_types, array_paths=array_paths
    )

    chunks = ((8, 8, 8), (8, 8, 8))
    multi = [m.chunk(c) for m, c in zip(multi, chunks)]
    group = multiscale_group(
        temp_zarr,
        multi,
        array_paths=array_paths,
        metadata_types=metadata_types,
        chunks=chunks,
        compressor=GZip(-1),
    )

    array_urls = [f"{temp_zarr}/{ap}" for ap in array_paths]
    da.compute(store_blocks(multi, [access(a_url, mode="a") for a_url in array_urls]))

    assert dict(group.attrs) == g_meta
    assert tuple(read(a).chunks for a in array_urls) == chunks
