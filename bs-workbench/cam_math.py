"""Numerical routines ported from the workbench's native cam_math.cpp."""

from math import copysign, inf, isfinite, isnan, nan, pow, sqrt
from time import monotonic


SAMPLE_COUNT = 100
MAX_ITERATIONS = 10_000
ROOT_TOLERANCE = 1e-7
CURVE_TOLERANCE = 1e-6
TIME_LIMIT_SECONDS = 30.0


class CamMathError(ValueError):
    """The curves do not give a usable numerical solution."""


def _check_deadline(deadline):
    if monotonic() >= deadline:
        raise TimeoutError('CAM calculation exceeded its time limit')


def _smooth_values(x, y, weights, deadline):
    """Return the knot values from the original weighted smoothing iteration."""
    n = len(x)
    last = n - 1
    t = [0.0] * n
    t1 = [0.0] * n
    r = [0.0] * n
    r1 = [0.0] * n
    r2 = [0.0] * (n + 1)
    u = [0.0] * (n + 1)
    v = [0.0] * n
    a = [0.0] * n
    b = [0.0] * n
    c = [0.0] * n
    d = [0.0] * n
    p = 0.0
    target = float(n)

    width = x[1] - x[0]
    slope = (y[1] - y[0]) / width
    for i in range(1, last):
        prev_width, prev_slope = width, slope
        width = x[i + 1] - x[i]
        slope = (y[i + 1] - y[i]) / width
        a[i] = slope - prev_slope
        t[i] = (prev_width + width) * 2.0 / 3.0
        t1[i] = width / 3.0
        r2[i] = weights[i - 1] / prev_width
        r[i] = weights[i + 1] / width
        r1[i] = -weights[i] / prev_width - weights[i] / width
    for i in range(1, last):
        b[i] = r[i] * r[i] + r1[i] * r1[i] + r2[i] * r2[i]
        c[i] = r[i] * r1[i + 1] + r1[i] * r2[i + 1]
        d[i] = r[i] * r2[i + 2]

    for _ in range(MAX_ITERATIONS):
        _check_deadline(deadline)
        r[1] = 1.0 / (b[1] + p * t[1])
        u[1] = a[1]
        for i in range(2, last):
            outer = d[i - 2]
            inner = c[i - 1] + p * t1[i - 1] - outer * r1[i - 2]
            r1[i - 1] = inner * r[i - 1]
            r2[i - 2] = outer * r[i - 2]
            r[i] = 1.0 / (b[i] + p * t[i] - inner * r1[i - 1] - outer * r2[i - 2])
            u[i] = a[i] - r1[i - 1] * u[i - 1] - r2[i - 2] * u[i - 2]
        for i in range(last - 1, 0, -1):
            u[i] = r[i] * u[i] - r1[i] * u[i + 1] - r2[i] * u[i + 2]

        error = 0.0
        slope = 0.0
        for i in range(last):
            prev_slope = slope
            slope = (u[i + 1] - u[i]) / (x[i + 1] - x[i])
            v[i] = (slope - prev_slope) * weights[i]
            error += v[i] * v[i]
        v[last] = u[last - 1] / (x[last] - x[last - 1]) * weights[last]
        error += v[last] * v[last]
        if not isfinite(error):
            raise CamMathError('Non-finite smoothing error')
        if error - target <= 1e-4:
            return [y[i] - weights[i] * v[i] for i in range(n)]

        residual = 0.0
        correction = 0.0
        prev_w = prev_prev_w = 0.0
        for i in range(1, last):
            g = u[i - 1] * t1[i - 1] + u[i + 1] * t1[i] + u[i] * t[i]
            residual += g * u[i]
            w = g - r1[i - 1] * prev_w - r2[i - 2] * prev_prev_w if i > 1 else g
            prev_prev_w, prev_w = prev_w, w
            correction += w * w * r[i]
        p += (error - sqrt(target * error)) / (residual - p * correction)
        if p < 0.0:
            target *= 0.8
            p = 0.0
    raise CamMathError('Smoothing did not converge')


def _quadratic_derivatives(x, y):
    n = len(x)
    width = x[1] - x[0]
    change = y[1] - y[0]
    if n == 2:
        return [change / width] * n

    deriv = [0.0] * n
    b = [0.0] * (n - 1)
    deriv[0] = -0.333333333
    b[0] = 1.33333333 * change / width
    for j in range(1, n - 1):
        prev_width, prev_change = width, change
        width = x[j + 1] - x[j]
        change = y[j + 1] - y[j]
        ratio = prev_width / (prev_width + width)
        weighted_slope = 4.0 * ((1.0 - ratio) * prev_change / prev_width + ratio * change / width)
        pivot = 3.0 + (1.0 - ratio) * deriv[j - 1]
        deriv[j] = -ratio / pivot
        b[j] = (weighted_slope - (1.0 - ratio) * b[j - 1]) / pivot
    deriv[-1] = (4.0 * change / width - b[-1]) / (3.0 + deriv[-2])
    for j in range(n - 2, -1, -1):
        deriv[j] = deriv[j] * deriv[j + 1] + b[j]
    return deriv


def _arc_lengths(flow, efficiency):
    lengths = [0.0]
    for i in range(1, len(flow)):
        dx = flow[i] - flow[i - 1]
        dy = efficiency[i] - efficiency[i - 1]
        lengths.append(lengths[-1] + sqrt(pow(dx, 2.0) + pow(dy, 2.0)))
    return lengths


def _segment_index(x, position):
    for i in range(len(x) - 1):
        if x[i] <= position <= x[i + 1]:
            return i
    raise CamMathError('Interpolation position outside the curve')


def _interpolate(x, y, deriv, position):
    if position < x[0] and position > 1.1 * x[0] - 0.1 * x[1]:
        return y[0] + (position - x[0]) * deriv[0]
    if position > x[-1] and position < 1.1 * x[-1] - 0.1 * x[-2]:
        return y[-1] + (position - x[-1]) * deriv[-1]

    i = _segment_index(x, position)
    width = x[i + 1] - x[i]
    offset = position - x[i]
    slope_term = 4.0 * (y[i + 1] - y[i]) / pow(width, 2.0)
    if offset <= 0.5 * width:
        curvature = slope_term - (deriv[i + 1] + 3.0 * deriv[i]) / width
        return y[i] + offset * (deriv[i] + 0.5 * offset * curvature)
    offset = width - offset
    curvature = (3.0 * deriv[i + 1] + deriv[i]) / width - slope_term
    return y[i + 1] + offset * (-deriv[i + 1] + 0.5 * offset * curvature)


def _segment_derivative(x, y, deriv, position, i):
    width = x[i + 1] - x[i]
    t = (position - x[i]) / width
    slope = 4.0 * (y[i + 1] - y[i]) / width
    if t <= 0.5:
        return deriv[i] + t * (slope - deriv[i + 1] - 3.0 * deriv[i])
    return -deriv[i] - 2.0 * deriv[i + 1] + slope + t * (-slope + 3.0 * deriv[i + 1] + deriv[i])


def _slope_ratio(numerator, denominator):
    # The native solver uses IEEE double division at vertical tangents.
    if denominator != 0.0:
        return numerator / denominator
    if numerator == 0.0 or isnan(numerator):
        return nan
    return copysign(inf, numerator) * copysign(1.0, denominator)


def _point_at_slope(lengths, flow, efficiency, dflow, deff, slope, deadline):
    knot_slopes = [_slope_ratio(de, dq) for dq, de in zip(dflow, deff)]
    for i, knot_slope in enumerate(knot_slopes):
        if knot_slope == slope:
            # The original exact-knot branch scales efficiency by d(flow)/d(length).
            return _interpolate(lengths, flow, dflow, lengths[i]), efficiency[i] / dflow[i]

    for i in range(len(knot_slopes) - 1):
        if (slope - knot_slopes[i]) * (knot_slopes[i + 1] - slope) > 0.0:
            left, right = lengths[i], lengths[i + 1]
            left_error = knot_slopes[i] - slope
            break
    else:
        raise CamMathError('No derivative root bracket')

    for _ in range(MAX_ITERATIONS):
        _check_deadline(deadline)
        width = abs(right - left)
        midpoint = (left + right) / 2.0
        segment = _segment_index(lengths, midpoint)
        flow_slope = _segment_derivative(lengths, flow, dflow, midpoint, segment)
        efficiency_slope = _segment_derivative(lengths, efficiency, deff, midpoint, segment)
        mid_error = _slope_ratio(efficiency_slope, flow_slope) - slope
        if width <= ROOT_TOLERANCE:
            return (
                _interpolate(lengths, flow, dflow, midpoint),
                _interpolate(lengths, efficiency, deff, midpoint),
            )
        if left_error * mid_error < 0.0:
            right = midpoint
        else:
            left, left_error = midpoint, mid_error
    raise CamMathError('Derivative root did not converge')


def _cam_envelope(curves, deadline):
    knots = [_point_at_slope(*curve, 0.0, deadline) for curve in curves]
    for _ in range(MAX_ITERATIONS):
        _check_deadline(deadline)
        flow, efficiency = map(list, zip(*knots))
        derivatives = _quadratic_derivatives(flow, efficiency)
        knots = [
            _point_at_slope(*curve, slope, deadline)
            for curve, slope in zip(curves, derivatives)
        ]
        if max(abs(previous - point[0]) for previous, point in zip(flow, knots)) <= CURVE_TOLERANCE:
            # The original samples the new knots with the derivatives from this iteration.
            flow, efficiency = map(list, zip(*knots))
            return flow, efficiency, derivatives
    raise CamMathError('CAM envelope did not converge')


def _sample_positions(x):
    for i in range(SAMPLE_COUNT):
        yield x[0] + (x[-1] - x[0]) * i / (SAMPLE_COUNT - 1)


def calculate(input_curves):
    """Return sampled fixed-blade curves followed by the sampled CAM envelope."""
    deadline = monotonic() + TIME_LIMIT_SECONDS
    curves = []
    for i, points in enumerate(input_curves):
        flow, efficiency = map(list, zip(*points))
        n = len(flow)
        lengths = _arc_lengths(flow, efficiency)
        eff_weight = 0.001 if i == len(input_curves) - 1 else 0.002
        efficiency = _smooth_values(lengths, efficiency, [eff_weight] * n, deadline)
        flow_weight = (flow[-1] - flow[0]) / 100.0
        flow = _smooth_values(lengths, flow, [flow_weight] * n, deadline)
        lengths = _arc_lengths(flow, efficiency)
        dflow = _quadratic_derivatives(lengths, flow)
        deff = _quadratic_derivatives(lengths, efficiency)
        curves.append((lengths, flow, efficiency, dflow, deff))

    cam_flow, cam_efficiency, cam_derivatives = _cam_envelope(curves, deadline)
    sampled = []
    for lengths, flow, efficiency, dflow, deff in curves:
        _check_deadline(deadline)
        sampled.append([
            [_interpolate(lengths, flow, dflow, t), _interpolate(lengths, efficiency, deff, t)]
            for t in _sample_positions(lengths)
        ])
    sampled.append([
        [t, _interpolate(cam_flow, cam_efficiency, cam_derivatives, t)]
        for t in _sample_positions(cam_flow)
    ])
    return sampled
