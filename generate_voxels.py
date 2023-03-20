import glob
import os
import shutil

from plumbum import cli, local
from tqdm.contrib.concurrent import thread_map
from tqdm.auto import tqdm
from easyprocess import EasyProcess


class Voxelizer(cli.Application):
    voxel_resolution = cli.SwitchAttr("resolution", int, default=32)

    def voxelize(self, args):
        input_path, output_path = args
        if os.path.exists(output_path):
            return output_path

        with EasyProcess(
            [
                "docker",
                "run",
                "--gpus",
                "all",
                "-v",
                f"{os.getcwd()}/citydata:/citydata",
                "cuda_voxelizer",
                "-f",
                f"/{os.path.relpath(input_path)}",
                "-s",
                str(self.voxel_resolution),
                "-o",
                "binvox",
                "-thrust",
            ]
        ) as proc:
            proc.wait()
            if proc.return_code != 0:
                print(
                    f"Failed to voxelize file {input_path}. cuda_voxelizer returned {proc.return_code} with the following error:\n{proc.stdout}"
                )
                return None

        # cuda_voxelizer does not allow us to specify where to put the generated
        # cuda_voxelizer file. It puts it adjacent to the input OBJ, so we need
        # to move it to the destination
        voxelizer_output_path = input_path + "_32.binvox"
        shutil.move(voxelizer_output_path, output_path)

        return output_path

    def main(
        self,
        input_mesh_dir: cli.ExistingDirectory,
        output_voxels_dir: cli.ExistingDirectory,
    ):
        files = glob.glob(os.path.join(input_mesh_dir, "*.obj"))

        def make_output_path(input_path):
            return os.path.join(
                output_voxels_dir,
                os.path.basename(input_path.replace(".obj", ".binvox")),
            )

        for output_path in thread_map(
            self.voxelize,
            [(f, make_output_path(f)) for f in files],
            max_workers=os.cpu_count() or 4,
        ):
            if output_path is not None:
                tqdm.write(output_path)


if __name__ == "__main__":
    Voxelizer.run()
