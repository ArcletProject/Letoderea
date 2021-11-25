from typing import Union, Type, overload, Tuple, Dict, Any


ParamRet = Tuple[Tuple[Union["Insertable", Type["Insertable"]]], Dict[str, Any]]


class TemplateEvent:
    """
    事件基类, 用于承载事件信息
    """

    @staticmethod
    def param_export(
            *args: Union["Insertable", Type["Insertable"]],
            **kwargs
    ):
        """该静态函数用于包装参数"""
        return args, kwargs

    @staticmethod
    @overload
    def get_params() -> ParamRet:
        ...

    @classmethod
    @overload
    def get_params(cls) -> ParamRet:
        ...

    def get_params(self) -> ParamRet:
        """外部方法,用于返回该事件实例的内部参数;该方法可以是 `classmethod`

        需要返回的内容应当是以下形式的:
         - *插入器, 一类特殊的事件, 可以为其他事件提供额外参数
         - 参数类型名 = 实际参数, 当事件只返回一个该类参数时, 请用该参数的类型名
         - 参数默认名 = 实际参数, 当事件返回多个该类参数时, 请用默认名区分各参数
        """
        return self.param_export(
        )

    def get(self, attr_name: str):
        return getattr(self, attr_name, None)


class StructuredEvent(TemplateEvent):
    """
    可结构化的事件类
    """
    def __init__(self, **kwargs):
        for k, v in kwargs:
            setattr(self, k, v)


class Insertable(TemplateEvent):
    """用于标记插入器的事件类, 非继承该类的插入器会无法使用"""
    pass
