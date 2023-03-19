import glob
import os
import shutil

from plumbum import cli, local, ProcessExecutionError
from tqdm.contrib.concurrent import thread_map
from tqdm.auto import tqdm
from pyvirtualdisplay import Display
from easyprocess import EasyProcess

binvox = local["./binvox"]


class Voxelizer(cli.Application):
    voxel_resolution = cli.SwitchAttr("resolution", int, default=32)

    def voxelize(self, args):
        input_path, output_path = args
        if os.path.exists(output_path):
            return output_path

        with Display(visible=False, size=(640, 480), color_depth=24) as disp:
            with EasyProcess(["./binvox", "-d", "32", "-t", "binvox", input_path], env=disp.env()) as proc: 
                proc.wait()
                if proc.return_code != 0:
                    print(f"Failed to voxelize file {input_path}. binvox returned {proc.return_code} with the following error:\n{proc.stderr}")
                    return None

        # binvox does not allow us to specify where to put the generated
        # binvox file. It puts it adjacent to the input OBJ, so we need to move it to the destination
        binvox_output_path = input_path.replace(".obj", ".binvox")
        shutil.move(binvox_output_path, output_path)

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
            max_workers=os.cpu_count() or 4
        ):
            if output_path is not None:
                tqdm.write(output_path)


if __name__ == "__main__":
    Voxelizer.run()
