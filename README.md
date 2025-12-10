# Wang tiles blue noise

A python port of part of the code from
[*Recursive Wang Tiles for Real-Time Blue Noise*](johanneskopf.de/publications/blue_noise/). Citation:

“Kopf, J., Cohen-Or D., Deussen O, and Lischinski D”. 2006. Recursive Wang Tiles for Real-Time Blue Noise.
*ACM Transactions on Graphics 25*, 3 (Proceedings of SIGGRAPH 2006), 509–518

The original c++ code was made publicly available. It did not contain a license but it had the following note:

> If you use this software for research purposes, please cite
> the aforementioned paper in any resulting publication.

The port includes the code to load the data sets with points, and to draw samples from just datasets.

Simple example:

```py
import wangtilesbluenoise
tileset = wangtilesbluenoise.load_tiles()

# the returned points fill the unit square, so the maximum rank approximately
# defines the number of points per unit area.
max_rank = 1000

# box should be a subset of the unit square
box = [0, 0, 1, 1]

# The points and ranks are yielded in blocks as numpy arrays, as yielding
# individual points would be too slow.
# It is not guaranteed the points are yielded in increasing rank order.
for tile_points in tileset.point_iter(box, max_rank):
    for p, rank in zip(tile_points.points, tile_points.ranks):
        # you can do some extra calculations
        p *= 100
        # use points
        print(f"{rank:4d} ({p[0]:4.1f}, {p[1]:4.1f})")
```
