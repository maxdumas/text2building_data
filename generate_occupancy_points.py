import glob
from typing import cast
import os

from plumbum import cli
from tqdm.contrib.concurrent import process_map
from tqdm.auto import tqdm
import trimesh
import numpy as np


class OccupancyPointSampler(cli.Application):
    """
    CLI Application that, given a directory of watertight OBJ files, generates
    numpy archives of sampled occupancy points for those OBJ files.
    """
    padding: float = cli.SwitchAttr("padding", float, default=0.1)
    n_points: int = cli.SwitchAttr("n_points", int, default=1e5)


    def sample_occupancy_points(self, args):
        input_path, output_path = args
        if os.path.exists(output_path):
            return output_path
        
        mesh = cast(trimesh.Trimesh, trimesh.load(input_path, force="mesh"))

        boxsize = np.max(mesh.extents)
        points = np.random.rand(self.n_points, 3).astype(np.float16)
        points = boxsize * (points - 0.5)

        occupancies = mesh.contains(points)
        occupancies = np.packbits(occupancies)

        np.savez_compressed(output_path, points=points, occupancies=occupancies)
        
        return output_path

    def main(
        self,
        input_mesh_dir: cli.ExistingDirectory,
        output_points_dir: cli.switches.MakeDirectory,
    ):
        files = glob.glob(os.path.join(input_mesh_dir, "*.obj"))

        def make_output_path(input_path):
            return os.path.join(
                output_points_dir,
                os.path.basename(input_path.replace(".obj", ".npz")),
            )

        for output_path in process_map(
            self.sample_occupancy_points,
            [(f, make_output_path(f)) for f in files],
            max_workers=os.cpu_count() or 4,
            chunksize=10,
        ):
            if output_path is not None:
                tqdm.write(output_path)


if __name__ == "__main__":
    OccupancyPointSampler.run()
