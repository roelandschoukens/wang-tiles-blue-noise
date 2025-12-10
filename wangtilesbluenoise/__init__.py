"""
Load data sets and draw points with a given density.
"""

import dataclasses as _dataclasses
import importlib.resources as _res
import math as _m
import typing as _typing

import numpy as _np

from . import bbox as _bbox

def _freadi(file):
    b = file.read(4)
    if len(b) < 4:
        raise EOFError(f"End of file reached while reading tiles")
    return int.from_bytes(b, "little")


def _freadarray(file, type, shape):
    s = _np.prod(shape) * type().itemsize
    buffer = file.read(s)
    if len(buffer) < s:
        raise EOFError(f"End of file reached while reading tiles")
    return _np.frombuffer(buffer, dtype=type).reshape(shape)


@_dataclasses.dataclass
class Tile:
    n: int
    e: int
    s: int
    w: int
    subDivs: _np.ndarray = None
    points: _np.ndarray = None
    sub_points: _np.ndarray = None


@_dataclasses.dataclass
class RecursiveTilePoints:
    points : _np.ndarray
    ranks : _np.ndarray
    bbox : _np.ndarray
    level : int


class TileSet:
    tiles : list[Tile]
    numSubtiles : int

    def __init__(self, tiles, numSubtiles):
        self.tiles = tiles
        self.numSubtiles = numSubtiles


    def point_iter(self, clipbox : _np.ndarray, max_rank : float) -> _typing.Iterable[RecursiveTilePoints]:
        """ Iterate all points below a certain rank
        
        Yields RecursiveTilePoints """
        clipbox = _np.array(clipbox, dtype=_np.float32)
        max_rank = int(_m.ceil(max_rank))
        tile_points = self.tiles[0].points[:max_rank]
        ranks = _np.arange(len(tile_points))
        mask = _bbox.contains(clipbox, tile_points)
        yield RecursiveTilePoints(tile_points[mask], ranks[mask], _bbox.UNIT, 0)
        
        if max_rank > len(tile_points):
            yield from _recurse_point_iter(self, self.tiles[0], clipbox, _bbox.UNIT, max_rank, 1)


def load_tiles(num_basepoints=2048) -> TileSet:
    """ Loads the built-in 2048 base points data set """
    available_num_basepoints = (512, 2048)
    if num_basepoints in available_num_basepoints:
        with _res.open_binary("wangtilesbluenoise.data", f"tileset_{num_basepoints}.dat") as h:
            return load_tiles_fh(h)
    raise ValueError(f"No data set with {num_basepoints} base points available"
                     ", pick one of " + ", ".join(map(str, available_num_basepoints)))


def load_tiles_file(file) -> TileSet:
    """ Loads a tiles data set from a data file """
    with open(file, "rb") as h:
        return load_tiles_fh(h)


def load_tiles_fh(file : _typing.BinaryIO | str) -> TileSet:
    """ Loads a tiles data set from a file object """
    numTiles = _freadi(file)
    numSubtiles = _freadi(file)
    numSubdivs = _freadi(file)
    tiles : list[Tile] = []

    for _ in range(numTiles):
        n, e, s, w = _freadarray(file, _np.uint32, [4])
        tiles.append(Tile(n, e, s, w))
        t = tiles[-1]

        t.subDivs = _freadarray(file, _np.uint32, [numSubdivs, numSubtiles, numSubtiles])

        numPoints = _freadi(file)
        pdata = _freadarray(file, _np.float32, [numPoints, 6])
        t.points = pdata[:, 0:2]

        numSubPoints = _freadi(file)
        pdata = _freadarray(file, _np.float32, [numSubPoints, 6])
        t.sub_points = pdata[:, 0:2]

    return TileSet(tiles, numSubtiles)


def _recurse_point_iter(tileset : TileSet, tile : Tile, clipbox : _np.ndarray, tilebox : _np.ndarray,
                        max_rank : float, level : int):
    if not _bbox.overlaps(clipbox, tilebox):
        return

    # we iterate over a scaled down version of the tile, the points
    # must be transformed to our tile box and their rank boosted
    # appropriately
    density_scale = 1 / _bbox.area(tilebox)
    subPoints = tile.sub_points
    count = max(0, min(len(subPoints), int(_m.ceil(max_rank / density_scale - len(tile.points)))))

    subrank_l = (_np.arange(count) + len(tile.points)) * density_scale
    pp_l = tilebox[0:2] + (tilebox[2:4] - tilebox[0:2]) * tile.sub_points[:count]
    mask = _bbox.contains(clipbox, pp_l)
    yield RecursiveTilePoints(pp_l[mask], subrank_l[mask], tilebox, level)

	# check if we need sub tiles
    if (len(subPoints) + len(tile.points)) * density_scale > max_rank:
        return
    
	# sub tiles
    subTileSize = (tilebox[2:4] - tilebox[0:2]) / tileset.numSubtiles
    for ix in range(tileset.numSubtiles):
        for iy in range(tileset.numSubtiles):
            p1 = tilebox[0:2] + [ix, iy] * subTileSize
            subtilebox = _np.concatenate([p1, p1 + subTileSize])
            if _bbox.overlaps(subtilebox, clipbox):
                st = tileset.tiles[tile.subDivs[0][iy][ix]]
                yield from _recurse_point_iter(
                    tileset, st, clipbox, subtilebox, max_rank, level + 1)
