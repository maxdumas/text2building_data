import glob
import os
from typing import cast

import numpy as np
from plumbum import cli
import pyrender
import trimesh
from PIL import Image
from tqdm.auto import tqdm

os.environ["PYOPENGL_PLATFORM"] = "egl"


def rotate_y(angle):
    c = np.cos(angle)
    s = np.sin(angle)
    rotation_matrix = np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    return rotation_matrix


def fit_view_to_bbox(xfov, obj_bbox):
    padding = 0.4
    max_dim = np.max(obj_bbox[1] - obj_bbox[0]) + padding
    dist = max_dim / (2 * np.tan(xfov)) + max_dim / 2
    return np.array([0, 0, dist])


def look_at(camera_pos, target_pos):
    camera_z = (camera_pos - target_pos) / np.linalg.norm(camera_pos - target_pos)
    camera_x = np.cross(np.array([0, 1, 0]), camera_z)
    camera_x = camera_x / np.linalg.norm(camera_x)
    camera_y = np.cross(camera_z, camera_x)
    camera_pose = np.eye(4)
    camera_pose[:3, 0] = camera_x
    camera_pose[:3, 1] = camera_y
    camera_pose[:3, 2] = camera_z
    camera_pose[:3, 3] = camera_pos
    return camera_pose


class ImageRenderer(cli.Application):
    output_width = cli.SwitchAttr("output_width", int, default=512)
    output_height = cli.SwitchAttr("output_height", int, default=512)
    camera_yfov = cli.SwitchAttr("yfov", float, default=np.pi / 3)

    def render_scene(self, file: str):
        scene = cast(trimesh.Scene, trimesh.load(file, force="scene"))

        # Ensure model is directly in center of camera
        scene.apply_translation(-scene.centroid)
        pyr_scene = pyrender.Scene.from_trimesh_scene(scene)
        camera_aspect_ratio = self.output_width / self.output_height
        camera_xfov = self.camera_yfov / camera_aspect_ratio

        for i, angle in enumerate(np.linspace(0, 2 * np.pi, 12, endpoint=False)):
            # Prepare lighting and camera
            camera_pos = (
                fit_view_to_bbox(camera_xfov, scene.bounds) * rotate_y(angle)
            )[:, 2]
            camera_pose = look_at(camera_pos, np.array([0, 0, 0]))
            pyr_scene.main_camera_node = pyr_scene.add(
                pyrender.PerspectiveCamera(
                    yfov=self.camera_yfov, aspectRatio=camera_aspect_ratio
                ),
                pose=camera_pose,
            )
            light = pyr_scene.add(
                pyrender.DirectionalLight(color=[1.0, 1.0, 1.0], intensity=2.0),
                pose=camera_pose,
            )

            color, _ = self.r.render(
                pyr_scene, flags=pyrender.RenderFlags.SHADOWS_DIRECTIONAL
            )

            # Clean up scene for next rendering pass
            pyr_scene.remove_node(pyr_scene.main_camera_node)
            pyr_scene.remove_node(light)

            yield Image.fromarray(color), i

    def main(
        self,
        input_mesh_dir: cli.ExistingDirectory,
        output_image_dir: cli.switches.MakeDirectory,
    ):
        files = glob.glob(os.path.join(input_mesh_dir, "*.obj"))

        self.r = pyrender.OffscreenRenderer(
            viewport_width=self.output_width,
            viewport_height=self.output_width,
            point_size=1.0,
        )

        for f in tqdm(files):
            if os.path.exists(
                os.path.join(output_image_dir, f"{os.path.basename(f)}_0.png")
            ):
                continue
            for im, i in self.render_scene(f):
                im.save(
                    os.path.join(output_image_dir, f"{os.path.basename(f)}_{i}.png")
                )

    def cleanup(self, retcode):
        self.r.delete()
        return super().cleanup(retcode)


if __name__ == "__main__":
    ImageRenderer.run()
