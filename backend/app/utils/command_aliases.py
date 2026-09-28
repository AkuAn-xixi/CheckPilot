"""oriStep 工作表指令别名字典的读取与展开。

用例工作簿可额外带一张名为 ``oriStep`` 的工作表，把一段常用按键序列起个别名，
例如 ``OPENSETTING`` -> ``HOME/1/5,SETTING/1/1,DOWN/9/1,OK/1/1``。用例表的
``oriStep`` / ``preScript`` 列便可直接写别名，由本模块展开成真实按键串后交给
执行链路。

逻辑名照 ``KEY/次数/时间`` 的写法补上后缀（``OPENCHILDCODE/1/3``）时后缀是有
含义的：**次数** = 整段按键串重复几遍，**时间** = 整段跑完后、执行下一条命令
前等多少秒。这一列的书写约定本就是那个格式，补后缀是很自然的写法，不该被当成
一个叫 ``OPENCHILDCODE/1/3`` 的按键。不写后缀则完全不动展开结果。

本模块只做「路径 -> 字典」与「命令段 -> 命令段」的转换，不含任何 adb 逻辑，
便于单元测试。别名表是可选增强：所有失败路径都返回空字典或原样返回，绝不抛
异常，避免字典本身有问题时拖垮整份用例的解析。
"""

import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

import pandas as pd

_log = logging.getLogger(__name__)

ORI_STEP_SHEET_NAME = "oriStep"
ALIAS_NAME_COLUMN = "oriStep"
ALIAS_KEY_COLUMN = "Key"
MAX_EXPAND_DEPTH = 5


@dataclass(frozen=True)
class AliasReference:
    """一条逻辑名引用：``NAME``，或照 ``KEY/次数/延迟`` 补了后缀的 ``NAME/次数/延迟``。

    Attributes:
        name: 大写后的逻辑名。
        repeat: 整段按键串重复几遍。
        delay: 整段跑完后额外等待的秒数；后缀里没写时为 ``None``，
            表示沿用展开结果自身的延迟，不做覆盖。
    """

    name: str
    repeat: int = 1
    delay: Optional[float] = None


def split_command_segments(text: str) -> List[str]:
    """按逗号把命令文本切成命令段，逐段去空格并丢弃空段。

    Args:
        text: 形如 ``HOME/1/5,SETTING/1/1`` 的命令文本。

    Returns:
        命令段列表，顺序保持不变。
    """
    if not text:
        return []
    return [segment.strip() for segment in str(text).split(",") if segment.strip()]


def load_command_aliases(excel_path: Optional[Path | str]) -> Dict[str, str]:
    """读取工作簿 oriStep 工作表中的指令别名字典。

    按键串的值保持原样（不做大写转换），以免破坏 ``X:(0:3)`` 这类参数写法。

    Args:
        excel_path: 用例工作簿路径。

    Returns:
        别名（统一大写）到按键串的字典。工作表不存在时静默返回空字典；表存在
        但表头对不上、或文件读取失败时告警后返回空字典。
    """
    try:
        with pd.ExcelFile(excel_path) as workbook:
            sheet_name = _resolve_alias_sheet_name(workbook.sheet_names)
            if sheet_name is None:
                return {}
            frame = workbook.parse(sheet_name)
    except Exception as error:  # 字典是可选增强，读不到就当作没有
        _log.warning(
            "[别名字典] 读取 %s 的 %s 工作表失败，按无别名处理: %s",
            excel_path,
            ORI_STEP_SHEET_NAME,
            error,
        )
        return {}
    return _build_alias_map(frame, excel_path)


def expand_command_aliases_grouped(
    segments: Iterable[str], aliases: Mapping[str, str]
) -> List[Tuple[str, List[str]]]:
    """逐段展开，同时保留每一段的出处，便于把结果映射回用户的原始写法。

    前端要把 ``OPENCHILDCODE/1/3`` 显示成一条 chip、又要在执行时让高亮落在它
    展开出的按键上，就得知道「哪个原始段对应展开后的哪几条」，故留此入口。

    Args:
        segments: 待展开的命令段。
        aliases: :func:`load_command_aliases` 返回的字典。

    Returns:
        ``[(原始段, 该段展开出的命令列表), ...]``，顺序保持不变。空段被丢弃；
        保留下来的段至少展开出一条命令（无法展开时即原样保留），不会是空列表。
    """
    grouped: List[Tuple[str, List[str]]] = []
    for segment in segments:
        text = str(segment).strip()
        if text:
            grouped.append((text, _expand_segment(text, aliases, frozenset())))
    return grouped


def expand_command_aliases(
    segments: Iterable[str], aliases: Mapping[str, str]
) -> List[str]:
    """把命令段逐个展开：命中别名则替换为其按键串，否则原样保留。

    支持别名与普通命令混写（如 ``OPENSETTING,DOWN/1/1``），也支持别名指向
    另一个别名（嵌套），由访问栈防止循环引用。

    Args:
        segments: 待展开的命令段。
        aliases: :func:`load_command_aliases` 返回的字典。

    Returns:
        展开后的命令段列表，顺序保持不变。
    """
    grouped = expand_command_aliases_grouped(segments, aliases)
    return [command for _segment, commands in grouped for command in commands]


def _resolve_alias_sheet_name(sheet_names: Iterable[str]) -> Optional[str]:
    """在表名集合里找别名工作表，大小写与首尾空格不敏感。"""
    for name in sheet_names:
        if str(name).strip().lower() == ORI_STEP_SHEET_NAME.lower():
            return str(name)
    return None


def _resolve_alias_columns(frame: pd.DataFrame) -> Optional[Tuple[str, str]]:
    """按表头文本定位「别名」与「按键串」两列。"""
    lookup = {str(column).strip().lower(): column for column in frame.columns}
    name_column = lookup.get(ALIAS_NAME_COLUMN.lower())
    key_column = lookup.get(ALIAS_KEY_COLUMN.lower())
    if name_column is None or key_column is None:
        return None
    return name_column, key_column


def _build_alias_map(
    frame: pd.DataFrame, excel_path: Optional[Path | str]
) -> Dict[str, str]:
    """把别名工作表转成字典，重复别名保留第一条。"""
    columns = _resolve_alias_columns(frame)
    if columns is None:
        _log.warning(
            "[别名字典] %s 的 %s 工作表缺少 %r/%r 列，实际表头: %s，按无别名处理",
            excel_path,
            ORI_STEP_SHEET_NAME,
            ALIAS_NAME_COLUMN,
            ALIAS_KEY_COLUMN,
            list(frame.columns),
        )
        return {}

    name_column, key_column = columns
    aliases: Dict[str, str] = {}
    for name_value, key_value in zip(frame[name_column], frame[key_column]):
        name = _normalize_cell_text(name_value).upper()
        keys = _normalize_cell_text(key_value)
        if name and keys:
            aliases.setdefault(name, keys)
    return aliases


def _match_alias_reference(
    segment: str, aliases: Mapping[str, str]
) -> Optional[AliasReference]:
    """从命令段里取出逻辑名引用。

    整段命中逻辑名时即 ``NAME`` 本身；否则按 ``KEY/次数/延迟`` 取首段再试一次
    ——``oriStep`` 这一列的书写约定就是那个格式，把逻辑名照同样格式补上后缀
    （``OPENSETTING/1/1``）是很自然的写法，只认整段相等会退化成「未知按键」。

    次数与延迟的取值范围跟 ``KEY/次数/延迟`` 保持一致：次数为正整数，延迟为非负
    数字。超出范围（如随机次数 ``X``）时不认这条引用、保留原文并告警——这里猜
    一个语义（随机重复整段导航？）比让下游按既有规则报错更糟。

    Args:
        segment: 单个命令段，如 ``OPENSETTING`` 或 ``OPENSETTING/1/5``。
        aliases: 别名字典。

    Returns:
        解析出的引用；整段与首段都不是逻辑名、或后缀写法无法识别时返回 ``None``。
    """
    name = segment.strip().upper()
    if name in aliases:
        return AliasReference(name)

    head, separator, suffix = segment.partition("/")
    head = head.strip().upper()
    if not separator or head not in aliases:
        return None

    repeat, delay = _parse_reference_suffix(suffix)
    if repeat is None:
        _log.warning(
            "[别名字典] 逻辑名 %s 的后缀 %s 无法识别，保留原文: %s",
            head,
            suffix,
            segment,
        )
        return None
    return AliasReference(head, repeat, delay)


def _parse_reference_suffix(suffix: str) -> Tuple[Optional[int], Optional[float]]:
    """解析逻辑名后缀里的 ``次数`` 与 ``延迟``，写法非法时次数返回 ``None``。

    延迟可以省略（``NAME/2`` 只重复、不额外等待）；次数不能省略，因为只有省略
    次数时才分不清「整段跑完等 N 秒」还是「每次之间等 N 秒」。

    Args:
        suffix: ``NAME/`` 之后的原文，如 ``1/3``、``2``。

    Returns:
        ``(次数, 延迟)``；写法非法时返回 ``(None, None)``。
    """
    repeat_text, separator, delay_text = suffix.partition("/")
    try:
        repeat = int(repeat_text)
    except ValueError:
        return None, None
    if repeat < 1:
        return None, None

    if not separator or not delay_text:
        return repeat, None
    try:
        delay = float(delay_text)
    except ValueError:
        return None, None
    return (repeat, delay) if delay >= 0 else (None, None)


def _can_expand(name: str, visited: frozenset) -> bool:
    """判断逻辑名此刻能否展开；不能时记下原因并返回 ``False``。

    循环引用与超出嵌套上限都保留原文，让下游照常报错，绝不抛异常或死循环。
    """
    if name in visited:
        _log.warning("[别名字典] 逻辑名存在循环引用，保留原文: %s", name)
        return False
    if len(visited) >= MAX_EXPAND_DEPTH:
        _log.warning("[别名字典] 逻辑名嵌套超过 %d 层，保留原文: %s", MAX_EXPAND_DEPTH, name)
        return False
    return True


def _with_command_delay(command: str, delay: float) -> Optional[str]:
    """把命令的延迟位换成 ``delay``；不足三段的命令承载不了延迟，返回 ``None``。"""
    segments = command.split("/")
    if len(segments) < 3:
        return None
    return "/".join([segments[0], segments[1], f"{delay:g}"])


def _apply_alias_reference(parts: List[str], reference: AliasReference) -> List[str]:
    """把 ``NAME/次数/延迟`` 的后缀落到展开结果上。

    次数 = 整段重复几遍；延迟 = 整段跑完后、执行下一条命令前等多少秒。延迟写在
    末条命令的延迟位上，因为对 ``KEY/次数/延迟`` 而言那一位的含义本就是「发完
    这条之后等多久」，而末条命令发完正是整段结束的时刻。
    """
    if not parts:
        return []

    result = parts * reference.repeat
    if reference.delay is None:
        return result

    delayed = _with_command_delay(result[-1], reference.delay)
    if delayed is None:
        _log.warning(
            "[别名字典] 逻辑名 %s 的末条命令 %s 不带延迟位，%s 秒延迟已忽略",
            reference.name,
            result[-1],
            f"{reference.delay:g}",
        )
        return result
    result[-1] = delayed
    return result


def _expand_segment(
    segment: str, aliases: Mapping[str, str], visited: frozenset
) -> List[str]:
    """展开单个命令段，命中逻辑名时按键串再次切段并递归展开。"""
    reference = _match_alias_reference(segment, aliases)
    if reference is None or not _can_expand(reference.name, visited):
        return [segment]

    expanded: List[str] = []
    for part in split_command_segments(aliases[reference.name]):
        expanded.extend(_expand_segment(part, aliases, visited | {reference.name}))
    if not expanded:  # 逻辑名指向空串，保留原文让下游照常报错，避免命令静默消失
        return [segment]
    return _apply_alias_reference(expanded, reference)


def _normalize_cell_text(value: Any) -> str:
    """把单元格值归一为去空格字符串，空值与 NaN 归一为空串。"""
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value).strip()
