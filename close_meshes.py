import glob
import os

from plumbum import cli
from tqdm.contrib.concurrent import thread_map
from tqdm.auto import tqdm
from easyprocess import EasyProcess


class MeshCloser(cli.Application):
    """
    CLI Application that, given a directory of OBJ files, will generate
    watertight versions of those meshes and output them to the specified
    directory.
    """

    def close_mesh(self, args):
        input_path, output_path = args
        if os.path.exists(output_path):
            return output_path

        with EasyProcess(
            ["./bin/manifold", "--input", input_path, "--output", output_path]
        ) as proc:
            proc.wait()
            if proc.return_code != 0:
                print(
                    f"Failed to close mesh {input_path}. manifold returned {proc.return_code} with the following error:\n{proc.stdout}"
                )
                return None

        return output_path

    def main(
        self,
        input_mesh_dir: cli.ExistingDirectory,
        output_mesh_dir: cli.ExistingDirectory,
    ):
        files = glob.glob(os.path.join(input_mesh_dir, "*.obj"))

        def make_output_path(input_path):
            return os.path.join(
                output_mesh_dir,
                os.path.basename(input_path),
            )

        for output_path in thread_map(
            self.close_mesh,
            [(f, make_output_path(f)) for f in files],
            max_workers=os.cpu_count() or 4,
        ):
            if output_path is not None:
                tqdm.write(output_path)


if __name__ == "__main__":
    MeshCloser.run()
