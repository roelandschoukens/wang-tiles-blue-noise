""" A few utility functions for bounding boxes

Bounding boxes are given as [x_min, y_min, x_max, y_max]

All functions accept numpy arrays of arbitrary shapes, as long
as the last dimension has the expected length (2 for points and
4 for bounding boxes). The return values will have the same
shape except for the last dimension.
"""

import numpy as np

UNIT = np.array([0.0, 0.0, 1.0, 1.0])

def area(box, /):
    return (box[..., 2] - box[..., 0]) * (box[..., 3] - box[..., 1])


def contains(box, p, /):
    c =  box[..., 0] < p[..., 0]
    c &= p[..., 0] < box[..., 2]
    c &= box[..., 1] < p[..., 1]
    c &= p[..., 1] < box[..., 3]
    return c


def overlaps(a, b, /):
    c =  a[..., 0] < b[..., 2]
    c &= b[..., 0] < a[..., 2]
    c &= a[..., 1] < b[..., 3]
    c &= b[..., 1] < a[..., 3]
    return c


def toXYWH(box):
    xywh = np.array(box)
    xywh[..., 2:4] -= xywh[..., 0:2]
    return xywh
