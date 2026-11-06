"""Compact lighting planes and bounded corrected-image access."""
import numpy as np


class GainPlane:
    def __init__(self, coefficients, shape):
        self.coefficients = np.asarray(coefficients, dtype=np.float64)
        self.height, self.width = shape

    def at(self, x, y):
        result = np.empty(np.broadcast_shapes(x.shape, y.shape)+(3,), np.float32)
        for c, coefficient in enumerate(self.coefficients):
            values = np.exp(coefficient[0]+coefficient[1]*x/self.width+coefficient[2]*y/self.height)
            result[..., c] = np.clip(values, .85, 1.15)
        return result

    def rows(self, start, stop):
        x = np.arange(self.width, dtype=np.float32)[None, :]
        y = np.arange(start, stop, dtype=np.float32)[:, None]
        return self.at(x, y)

    def output_block(self, inverse, factor, x0, y0, width, height, output_size):
        # Match the output map's replicated border, then map into work coordinates.
        u = np.clip((np.arange(x0, x0+width, dtype=np.float64)+.5)*factor-.5, 0, output_size[0]-1)[None, :]
        v = np.clip((np.arange(y0, y0+height, dtype=np.float64)+.5)*factor-.5, 0, output_size[1]-1)[:, None]
        result = np.empty((height, width, 3), np.float32)
        # A plane remains separable after an affine transform: evaluate only
        # two short vectors of exponentials, then their outer product.
        for c, coefficient in enumerate(self.coefficients):
            ax = coefficient[1]/self.width
            ay = coefficient[2]/self.height
            a = ax*inverse[0, 0]+ay*inverse[1, 0]
            b = ax*inverse[0, 1]+ay*inverse[1, 1]
            offset = coefficient[0]+ax*inverse[0, 2]+ay*inverse[1, 2]
            values = np.exp(offset+a*u)*np.exp(b*v)
            result[..., c] = np.clip(values, .85, 1.15)
        corners = np.array([[u[0,0],v[0,0],1],[u[0,-1],v[0,0],1],[u[0,0],v[-1,0],1],[u[0,-1],v[-1,0],1]])@inverse.T
        if (corners[:,0].min()<0 or corners[:,0].max()>self.width-1 or
                corners[:,1].min()<0 or corners[:,1].max()>self.height-1):
            x = inverse[0, 0]*u+inverse[0, 1]*v+inverse[0, 2]
            y = inverse[1, 0]*u+inverse[1, 1]*v+inverse[1, 2]
            coverage = np.clip(x+1, 0, 1)*np.clip(self.width-x, 0, 1)*np.clip(y+1, 0, 1)*np.clip(self.height-y, 0, 1)
            result *= coverage[..., None].astype(np.float32)
        return result


class CorrectedImage:
    def __init__(self, raw):
        self.raw = raw
        self.shape = raw.shape
        self.gain = None

    def __getitem__(self, rows):
        start, stop, step = rows.indices(self.shape[0])
        if step != 1:
            raise ValueError('Corrected images require contiguous row bands')
        result = self.raw[start:stop].astype(np.float32)
        if self.gain is not None:
            result *= self.gain.rows(start, stop)
        return result
