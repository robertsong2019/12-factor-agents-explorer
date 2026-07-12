"""
工具系统 - 支持装饰器式工具注册
"""

import inspect
from typing import Callable, Dict, Any, List
from dataclasses import dataclass, field


@dataclass
class Tool:
    """工具定义"""
    name: str
    description: str
    func: Callable
    parameters: Dict[str, Any] = field(default_factory=dict)

    def validate_args(self, **kwargs) -> List[str]:
        """验证参数，返回错误列表（空=有效）"""
        errors = []
        required = [n for n, p in self.parameters.items() if "default" not in p]
        for name in required:
            if name not in kwargs:
                errors.append(f"缺少必要参数: {name}")
        return errors

    def execute(self, **kwargs) -> Any:
        """执行工具"""
        return self.func(**kwargs)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式（用于 LLM）"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters
        }


# 全局工具注册表
_tools: Dict[str, Tool] = {}


def tool(func: Callable = None, *, name: str = None, description: str = None) -> Callable:
    """
    装饰器：注册函数为工具

    用法:
        @tool
        def search(query: str) -> str:
            '''搜索网络'''
            return f"搜索 {query}"

        @tool(name="my_search", description="我的搜索工具")
        def custom_search(q: str) -> str:
            return f"搜索 {q}"
    """
    def decorator(f: Callable) -> Callable:
        # 确定工具名称
        tool_name = name or f.__name__

        # 确定描述
        tool_desc = description or (f.__doc__ or "").strip()
        if not tool_desc:
            tool_desc = f"工具: {tool_name}"

        # 提取参数信息
        sig = inspect.signature(f)
        params = {}
        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue
            # 类型推断
            type_map = {str: "string", int: "integer", float: "number", bool: "boolean", list: "array", dict: "object"}
            annotation = param.annotation if param.annotation != inspect.Parameter.empty else str
            origin = getattr(annotation, "__origin__", None)
            actual = origin or annotation
            param_info = {"type": type_map.get(actual, "string")}
            if param.default != inspect.Parameter.empty:
                param_info["default"] = param.default
            params[param_name] = param_info

        # 创建工具对象
        tool_obj = Tool(
            name=tool_name,
            description=tool_desc,
            func=f,
            parameters=params
        )

        # 注册工具
        _tools[tool_name] = tool_obj

        # 将工具对象附加到函数上
        f._nano_agent_tool = tool_obj

        return f

    if func is not None:
        return decorator(func)
    return decorator


def get_tool_from_func(func: Callable) -> Tool:
    """从函数获取工具对象"""
    if hasattr(func, '_nano_agent_tool'):
        return func._nano_agent_tool
    return get_tool(func.__name__)


def get_tool(name: str) -> Tool:
    """获取工具"""
    return _tools.get(name)


def list_tools() -> List[Tool]:
    """列出所有工具"""
    return list(_tools.values())


def clear_tools() -> None:
    """清除所有工具"""
    _tools.clear()


def unregister_tool(name: str) -> bool:
    """注销工具，返回是否成功"""
    if name in _tools:
        del _tools[name]
        return True
    return False


def list_tools_by_prefix(prefix: str) -> List[Tool]:
    """按名称前缀筛选工具"""
    return [t for name, t in _tools.items() if name.startswith(prefix)]
