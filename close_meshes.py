import glob
import gzip
import os
from copy import deepcopy
from typing import cast

import numpy as np
import open3d as o3d
import trimesh
from easyprocess import EasyProcess
from plumbum import cli
from tqdm.auto import tqdm
from tqdm.contrib.concurrent import thread_map


def remove_ground_plane(
    M: o3d.geometry.TriangleMesh,
    n_scan_steps: int,
    max_scan_height_fraction: float,
    volume_reduction_threshold: float,
):
    """
    Remove ground floor planes. We compute the bounding box of the cluster. We
    then translate the bounding box upwards, clip the mesh, and compute a new
    bounding box. If the new bounding box volume is much smaller than the
    original bounding box, then we win. Otherwise, stop after a certain amount
    of translation distance.
    """
    bb = M.get_axis_aligned_bounding_box()
    max_dy = bb.get_extent()[1] * max_scan_height_fraction
    dy = max_dy / n_scan_steps
    prev_volume = bb.volume()

    for _ in range(n_scan_steps):
        bb_translate = bb.translate(np.array([0.0, dy, 0.0]))
        M_cropped = M.crop(bb_translate)
        if len(M_cropped.vertices) < 4:
            # This cluster doesn't have enough points to define a 3D volume.
            break
        new_volume = M_cropped.get_axis_aligned_bounding_box().volume()
        if (new_volume / prev_volume) < volume_reduction_threshold:
            return M_cropped, True

        prev_volume = new_volume

    return M, False


def select_largest_component(M: o3d.geometry.TriangleMesh):
    # Identify and return the largest connected component by area
    triangle_clusters, cluster_n_triangles, _ = M.cluster_connected_triangles()
    triangle_clusters = np.array(triangle_clusters)
    cluster_volumes = []
    cluster_meshes = []
    for cluster, n_triangles in enumerate(cluster_n_triangles):
        if n_triangles <= 6:
            # This cluster doesn't have enough triangles to define a 3D cube,
            # and so it almost certainly is irrelevant.
            continue
        triangles_to_remove = triangle_clusters != cluster
        M_single_component = deepcopy(M)
        M_single_component.remove_triangles_by_mask(triangles_to_remove)
        M_single_component.remove_unreferenced_vertices()
        if len(M_single_component.vertices) <= 6:
            # After processing, this cluster doesn't have enough triangles to
            # define a 3D cube, and so it almost certainly is irrelevant.
            continue
        cluster_volumes.append(
            M_single_component.get_minimal_oriented_bounding_box(robust=True).volume()
        )
        cluster_meshes.append(M_single_component)

    if len(cluster_meshes) == 0:
        # All clusters were too small to define a 3D volume.
        return M

    biggest_cluster_index = np.argmax(cluster_volumes)
    return cluster_meshes[biggest_cluster_index]


def simplify_mesh(M: o3d.geometry.TriangleMesh, n_simplication_voxels: int):
    voxel_size = max(M.get_max_bound() - M.get_min_bound()) / n_simplication_voxels
    return M.simplify_vertex_clustering(
        voxel_size=voxel_size,
        contraction=o3d.geometry.SimplificationContraction.Average,
    )


class MeshCloser(cli.Application):
    """
    CLI Application that, given a directory of OBJ files, will generate
    watertight versions of those meshes and output them to the specified
    directory. It also performs a set of normalizations on the OBJ.
    """

    n_simplification_voxels = cli.SwitchAttr(["--n_simplification_voxels"], int, 128)
    """
    The dimension of the Voxel Grid to use when simplifying the meshes.
    """

    n_ground_plane_scan_steps = cli.SwitchAttr(["--n_ground_plane_scan_steps"], int, 10)
    """
    The number of slices to iteratively attempt when searching for a ground plane.
    """

    ground_plane_max_scan_height_fraction = cli.SwitchAttr(
        ["--max_scan_height_fraction"], float, 0.15
    )
    """
    The fraction of the total height of the mesh that we can scan to detect the
    ground pane.
    """

    ground_plane_volume_reduction_threshold = cli.SwitchAttr(
        ["--volume_reduction_threshold"], float, 0.8
    )
    """
    The factor by which our clipped volume would have to shrink in order for us
    to consider ourselves to have "won" by removing some large ground plane.
    """

    def normalize_mesh(self, mesh: trimesh.Trimesh):
        M = mesh.as_open3d

        # Simplify the mesh
        M = simplify_mesh(M, self.n_simplification_voxels)

        # Remove spurious components (first pass)
        M = select_largest_component(M)

        # Remove ground plane if it exists
        M, found_ground_plane = remove_ground_plane(
            M,
            self.n_ground_plane_scan_steps,
            self.ground_plane_max_scan_height_fraction,
            self.ground_plane_volume_reduction_threshold,
        )
        if found_ground_plane:
            # Remove any spurious components that might have been detached now
            # that we've removed the ground plane
            M = select_largest_component(M)

        return trimesh.Trimesh(np.array(M.vertices), np.array(M.triangles))

    def close_mesh(self, input_path, output_path):
        with EasyProcess(
            ["./bin/manifold", "--input", input_path, "--output", output_path]
        ) as proc:
            proc.wait()
            if proc.return_code != 0:
                print(
                    f"Failed to close mesh {input_path}. manifold returned {proc.return_code} with the following error:\n{proc.stdout}"
                )

    def process(self, args):
        input_path, output_path = args
        if os.path.exists(output_path):
            return output_path
        print(input_path, output_path)

        close_output_path = output_path.replace(".obj.gz", ".obj")
        self.close_mesh(input_path, close_output_path)

        mesh = cast(trimesh.Trimesh, trimesh.load(close_output_path, force="mesh"))
        mesh = self.normalize_mesh(mesh)

        with gzip.open(output_path, "wb") as f:
            f.write(mesh.export(file_type="obj").encode("utf-8"))

        os.remove(close_output_path)

        return output_path

    def main(
        self,
        input_mesh_dir: cli.ExistingDirectory,
        output_mesh_dir: cli.switches.MakeDirectory,
    ):
        files = glob.glob(os.path.join(input_mesh_dir, "*.obj"))

        def make_output_path(input_path):
            return os.path.join(
                output_mesh_dir,
                os.path.basename(input_path + ".gz"),
            )

        for output_path in thread_map(
            self.process,
            [(f, make_output_path(f)) for f in files],
            max_workers=os.cpu_count() or 4,
        ):
            if output_path is not None:
                tqdm.write(output_path)


if __name__ == "__main__":
    MeshCloser.run()
