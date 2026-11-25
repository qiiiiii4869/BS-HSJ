"""Read legacy ICA files and format CAM results for the workbench API."""

from math import isfinite

from cam_math import CamMathError, calculate
from sel_reader import SelError


def _parse_ica(text):
    if not isinstance(text, str) or len(text) > 1024 * 1024:
        raise SelError('请加载有效 ICA 文件')
    tokens = iter(text.split())
    try:
        count = int(next(tokens))
        if not 2 <= count <= 20:
            raise ValueError
        curves = []
        for _ in range(count):
            size = int(next(tokens))
            if not 3 <= size <= 30:
                raise ValueError
            curve = []
            for _ in range(size):
                flow, efficiency = float(next(tokens)), float(next(tokens))
                if not isfinite(flow + efficiency):
                    raise ValueError
                curve.append((flow, efficiency))
            curves.append(curve)
        if next(tokens, None) is not None:
            raise ValueError
    except (StopIteration, ValueError) as error:
        raise SelError('ICA 格式须为曲线数、各曲线点数及流量/效率数对，2–20条曲线，每条3–30点') from error
    return curves


def compute(body):
    input_curves = _parse_ica(body.get('text'))
    try:
        points = calculate(input_curves)
    except TimeoutError as error:
        raise SelError('协联迭代未在30秒内收敛，请核对数据') from error
    except (CamMathError, ArithmeticError) as error:
        raise SelError('协联算法无法处理此数据：检查曲线顺序、导数根与收敛条件') from error
    if any(not isfinite(value) or abs(value) > 1e90 for curve in points for pair in curve for value in pair):
        raise SelError('协联数值结果无效或插值超出范围')

    fixed_blade_count = len(input_curves)
    rows = points[-1]
    return dict(
        title='协联工况',
        axes=['流量', '效率'],
        curves=[
            dict(
                name=f'定桨曲线{i + 1}' if i < fixed_blade_count else '协联曲线',
                points=curve,
                color='#888888' if i < fixed_blade_count else '#0000ff',
                visible=True,
            )
            for i, curve in enumerate(points)
        ],
        rows=rows,
        columns=['流量', '效率'],
        legacy_text=''.join(f'{x:.6f}\t{y:.6f}\r\n' for x, y in rows),
        legacy_extension='oca',
    )
