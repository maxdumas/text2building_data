from os.path import join

from plumbum import cli
import pyvista
from cjio import cityjson
from tqdm.contrib.concurrent import process_map

class OBJExtractor(cli.Application):
    def main(self, input_cityjson: cli.ExistingFile, output_mesh_dir: cli.ExistingDirectory):
        cm = cityjson.load(input_cityjson)

        for building_id, building in process_map(cm.get_cityobjects(type="building").items()):
            for obj in building.geometry:
                tqdm.write(building_id)
                faces, vertmap, n_vertices = obj.build_index()

                if len(faces) == 1:
                    # Sometimes the faces are nested in a singleton array
                    faces = faces[0]
                faces_pyv = [[len(f[0]), *f[0]] for f in faces]
                faces_pyv = [g for f in faces_pyv for g in f]
                verts = list(vertmap.keys())

                mesh = pyvista.PolyData(verts, faces_pyv)

                # TODO: Figure out how to extract the textures simultaneously.
                mesh.save(join(output_mesh_dir, f"{building_id}.ply"))
