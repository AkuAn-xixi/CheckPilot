"""airtest 图像匹配内核的本项目移植版。

上游为 AirtestProject/Airtest 仓库的 ``airtest/aircv`` 子模块（Apache-2.0，
归属与修改说明见同目录 NOTICE）。此处只保留「模板匹配」所需算法，并按本项目
约定做了三处改造：

1. 去掉 ``airtest.core.*`` 与全局 ``Settings`` 单例依赖，参数改为逐次传入
   （并发安全：本应用允许两个浏览器标签同时执行）。
2. 去掉 PIL 与文件 IO，输入统一为 OpenCV 的 BGR ``np.ndarray``。
3. 策略只保留 ``mstpl`` / ``tpl``。本环境 opencv-python-headless 5.0 已不提供
   BRISK / KAZE / AKAZE 检测器（实测缺失），相关分支连同依赖录制元数据的
   ``MultiScaleTemplateMatchingPre`` 一并丢弃。

对外只暴露 :func:`match_template`、:class:`MatchOptions`、:class:`MatchOutcome`。
"""

from .matcher import match_template
from .models import MatchOptions, MatchOutcome

__all__ = ["match_template", "MatchOptions", "MatchOutcome"]
