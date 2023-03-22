from functools import partial
import glob
from typing import cast
from enum import Enum
import os

from plumbum import cli
from tqdm.contrib.concurrent import process_map
from tqdm.auto import tqdm
import trimesh
import numpy as np


class SamplingMethod(str, Enum):
    MESH_CONTAINS = "mesh_contains"
    VOXELGRID_LOOKUP = "voxelgrid_lookup"


def sample_occupancy_points(method: SamplingMethod, n_points: int, args):
    input_path, output_path = args
    if os.path.exists(output_path):
        return output_path

    mesh = cast(
        trimesh.Trimesh | trimesh.voxel.VoxelGrid,
        trimesh.load(input_path, force="mesh"),
    )

    boxsize = np.max(mesh.extents)
    points = np.random.rand(n_points, 3).astype(np.float16)
    points = boxsize * (points - 0.5)

    # This operation seems very slow.
    if method == SamplingMethod.MESH_CONTAINS:
        mesh = cast(trimesh.Trimesh, mesh)
        occupancies = mesh.contains(points)
    else:
        # A much faster approach might be to load the voxel grid instead and map
        # the sampled points onto the voxel grid to detect occupancy. This is a
        # nothing more than a very quick matrix lookup. It will be much lower
        # resolution than checking against the mesh itself, of course, but it
        # may be good enough.
        voxel_grid = cast(trimesh.voxel.VoxelGrid, mesh)
        N = voxel_grid.shape[0]
        point_indices = voxel_grid.points_to_indices(points)
        # Clip the indices to the shape of the voxel grid N. Points that are
        # outside the grid will be given an index of N, which blows up indexing.
        clipped_point_indices = np.clip(point_indices, 0, N - 1)
        occupancies = voxel_grid.matrix[
            clipped_point_indices[:, 0],
            clipped_point_indices[:, 1],
            clipped_point_indices[:, 2],
        ]
        # For any points that fell outside of the bounding box of the
        occupancies[
            (point_indices[:, 0] >= N)
            | (point_indices[:, 1] >= N)
            | (point_indices[:, 2] >= N)
        ] = False

    occupancies = np.packbits(occupancies)
    np.savez_compressed(output_path, points=points, occupancies=occupancies)

    return output_path


class OccupancyPointSampler(cli.Application):
    """
    CLI Application that, given a directory of watertight OBJ files, generates
    numpy archives of sampled occupancy points for those OBJ files.
    """

    padding: float = cli.SwitchAttr("padding", float, default=0.1)
    n_points: int = cli.SwitchAttr("n_points", int, default=100_000)
    sampling_method: SamplingMethod = cli.SwitchAttr("sampling_method", SamplingMethod)

    def main(
        self,
        input_voxel_or_mesh_dir: cli.ExistingDirectory,
        output_points_dir: cli.switches.MakeDirectory,
    ):
        files = glob.glob(os.path.join(input_voxel_or_mesh_dir, "*.binvox"))

        def make_output_path(input_path):
            return os.path.join(
                output_points_dir,
                os.path.basename(input_path.replace(".binvox", ".npz")),
            )

        for output_path in process_map(
            partial(sample_occupancy_points, self.sampling_method, self.n_points),
            [(f, make_output_path(f)) for f in files],
            max_workers=os.cpu_count() or 4,
            chunksize=100,
        ):
            if output_path is not None:
                tqdm.write(output_path)


if __name__ == "__main__":
    OccupancyPointSampler.run()
