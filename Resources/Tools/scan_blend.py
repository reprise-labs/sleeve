"""Bounded low-frequency filtering; original-resolution detail stays in the stitcher."""
import math
import cv2


def detail_blur(image, sigma):
    """Evaluate broad Gaussian fields on a Gaussian pyramid.

    pyrDown and pyrUp each add variance in source-pixel units. Subtract that
    variance from the remaining Gaussian, so its effective width is preserved.
    This only filters the lighting/blending field, never the original detail.
    The caller already supplies a convolution halo and discards its edge.
    """
    levels = 2 if sigma >= 16 else 1 if sigma >= 8 else 0
    if not levels or min(image.shape[:2]) < 32:
        return cv2.GaussianBlur(image, (0, 0), sigma)
    sizes = []
    result = image
    for _ in range(levels):
        sizes.append((result.shape[1], result.shape[0]))
        result = cv2.pyrDown(result)
    variance = 2 * sum(4 ** level for level in range(levels))
    remaining = math.sqrt(sigma * sigma - variance) / (2 ** levels)
    result = cv2.GaussianBlur(result, (0, 0), remaining)
    for size in reversed(sizes):
        result = cv2.pyrUp(result, dstsize=size)
    return result
