from typing import Union, Type, overload, List, Dict, Any

ParamRet = Dict[type, Dict[str, Any]]
Inserts = List[Union["TemplateEvent", Type["TemplateEvent"]]]


class TemplateEvent:
    """
    事件基类, 用于承载事件信息
    """
    inserts: List[Union["TemplateEvent", Type["TemplateEvent"]]] = []

    @classmethod
    def param_export(
            cls,
            **kwargs
    ):
        """该函数用于包装参数"""
        result: ParamRet = {}
        for k, v in kwargs.items():
            if not result.get(type(v)):
                result[type(v)] = {}
            result[v.__class__][k] = v
        return result

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
         - 参数类型名 = 实际参数, 当事件只返回一个该类参数时, 请用该参数的类型名
         - 参数默认名 = 实际参数, 当事件返回多个该类参数时, 请用默认名区分各参数
        """
        return self.param_export()

    def get(self, attr_name: str):
        return getattr(self, attr_name, None)


class StructuredEvent(TemplateEvent):
    """
    可结构化的事件类
    """

    def __init__(self, **kwargs):
        __anno: Dict[str, type] = {}
        for a in [m.__annotations__ for m in self.__class__.__mro__[-2::-1]]:
            __anno.update(a)
        for k, v in kwargs.items():
            if k in __anno and type(v) != __anno[k]:
                raise TypeError(f"{k} must be {__anno[k]}")
            setattr(self, k, v)


if __name__ == "__main__":

    class TestInsert(TemplateEvent):
        msg: str = "world"

        def get_params(self) -> ParamRet:
            return self.param_export(
                str=self.msg,
            )


    class TestEvent(TemplateEvent):
        inserts = [TestInsert]
        msg: str = "hello"

        def get_params(self) -> ParamRet:
            return self.param_export(
                msg="hello",
                str=self.msg,
                int=1
            )


    print(TestEvent().get_params())
