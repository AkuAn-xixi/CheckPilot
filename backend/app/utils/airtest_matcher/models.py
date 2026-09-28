"""本包自有的数据类型（非上游移植，故无 Apache-2.0 归属）。

上游把参数散落在各匹配器的构造参数里，且 ``MultiScaleTemplateMatching`` 自身的
默认值是 ``threshold=0.8, rgb=True``——**与 airtest 产品语义不一致**：用户在
Airtest IDE 里看到的 0.7 与灰度匹配，来自 ``Settings.THRESHOLD`` 与
``Template(rgb=False)`` 在调用时显式传入。因此本包的默认值取 airtest 产品语义
的**灰度匹配**，并由调用方显式传参，不依赖匹配器类的默认值。

有两处默认值刻意偏离 airtest 产品默认，都是本项目拿真实素材实测后的结论，
依据分别记在 ``DEFAULT_STRATEGY`` 与 ``DEFAULT_THRESHOLD`` 处：
strategy 由 ``mstpl`` 改为 ``tpl``（mstpl 会配错位置），
threshold 由 ``0.7`` 改为 ``0.85``（0.7 会放过约 6% 的未命中）。
"""

from dataclasses import dataclass

# 支持的多尺度策略名（与 airtest CVSTRATEGY 的取值一致）
STRATEGY_MULTISCALE = "mstpl"
STRATEGY_TEMPLATE = "tpl"
SUPPORTED_STRATEGIES: tuple[str, ...] = (STRATEGY_MULTISCALE, STRATEGY_TEMPLATE)

# 默认策略取 tpl（单尺度）而非 airtest 产品默认的 mstpl，依据是真实素材实测
# （73 张 1920x1080 设备截图 + 62 张真实参考图）：tpl 单次约 140ms、45/45 定位
# 正确；mstpl 单次约 3026ms（慢 21.6 倍），且 8 组正样本里有 3 组配到错误位置
# （如真值 224x238 处返回 974x1036 的大框，conf 低至 0.0588）。mstpl 的价值在于
# 适配录制/回放分辨率不一致，本项目「参考图对设备截图」绝大多数同分辨率，故默认
# 走 tpl；需要跨分辨率时可在配置里切回 mstpl。
DEFAULT_STRATEGY = STRATEGY_TEMPLATE

# 不取 airtest 的 Settings.THRESHOLD 默认值 0.7，改取 0.85，依据是真实素材实测：
# 45 张参考图 × 25 张不含它的截图 = 1125 对负样本，阈值 0.7 时有 72 对（6.40%）
# 被判为命中（最高误命中 0.8471），0.85 时为 0 对；同时正样本下限在「JPEG 压缩 +
# ±3% 缩放」叠加扰动下仍有 0.9554（45 组无一低于 0.85）。真实间隔为
# 0.8471（负）～0.9554（正），0.85 落在中间且两侧留有余量。
# 与 opencv 引擎的融合分不是同一把尺子，阈值不可互相平移。
DEFAULT_THRESHOLD = 0.85
# 上游 Template 类的默认值，截图长边超过它时先缩放再匹配
DEFAULT_SCALE_MAX = 800
DEFAULT_SCALE_STEP = 0.005


@dataclass(frozen=True)
class MatchOptions:
    """一次模板匹配的参数。

    Attributes:
        threshold: 判定阈值（airtest confidence 语义，默认 0.85）。
        rgb: 是否启用彩色（HSV）置信度；默认 False 即灰度匹配。
        strategy: ``tpl``（单尺度，默认）或 ``mstpl``（多尺度，慢且精度略低，
            仅在参考图与截图分辨率不一致时才需要）。
        scale_max: 截图长边缩放上限。
        scale_step: 多尺度搜索的比例步长。
    """

    threshold: float = DEFAULT_THRESHOLD
    rgb: bool = False
    strategy: str = DEFAULT_STRATEGY
    scale_max: int = DEFAULT_SCALE_MAX
    scale_step: float = DEFAULT_SCALE_STEP


@dataclass(frozen=True)
class MatchOutcome:
    """一次模板匹配的结果。

    Attributes:
        matched: 是否命中（confidence 达到阈值）。
        confidence: 本次匹配的实际置信度；未命中时也是真实分数而非 0。
        strategy: 实际使用的策略名。
        rect: 命中区域的 ``(左上角 x, 左上角 y, 宽, 高)``，原截图坐标系；
            未命中时为 None。
        target: 命中区域中心点 ``(x, y)``；未命中时为 None。
        elapsed_seconds: 本次匹配耗时（秒）。
        message: 未命中或出错时的说明。
    """

    matched: bool
    confidence: float
    strategy: str
    rect: tuple[int, int, int, int] | None = None
    target: tuple[int, int] | None = None
    elapsed_seconds: float = 0.0
    message: str = ""
