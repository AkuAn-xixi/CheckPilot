"""移植自 aircv/error.py 的异常定义（Apache-2.0，见同目录 NOTICE）。

只保留本项目用到的一支：模板与截图尺寸不合法时抛出的
:class:`TemplateInputError`。上游其余异常（SIFT / 关键点 / 单应矩阵相关）
随对应策略一并丢弃。
"""


class BaseError(Exception):
    """aircv 异常基类。

    上游仅设置 ``message`` 属性而不调用父类构造，此处补上 ``super().__init__``，
    使 ``str(exc)`` 能直接带出上下文信息便于日志定位。
    """

    def __init__(self, message: str = "") -> None:
        super().__init__(message)
        self.message = message


class TemplateInputError(BaseError):
    """模板与截图的尺寸关系不合法（例如模板比截图还大）。"""
