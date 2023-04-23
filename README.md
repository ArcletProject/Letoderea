# Letoderea
[![Licence](https://img.shields.io/github/license/ArcletProject/Letoderea)](https://github.com/ArcletProject/Letoderea/blob/master/LICENSE)
[![PyPI](https://img.shields.io/pypi/v/arclet-letoderea)](https://pypi.org/project/arclet-letoderea)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/arclet-letoderea)](https://www.python.org/)

一个高性能，结构简洁，依赖于 Python内置库`asyncio` 的事件系统, 设计灵感来自[`Graia BroadcastControl`](https://github.com/GraiaProject/BroadcastControl)。

项目仍处于开发阶段，部分内容可能会有较大改变

## 安装
### 从 PyPI 安装
``` bash
pip install arclet-letoderea
```

## 样例

```python
from arclet.letoderea import EventSystem, Contexts

es = EventSystem()


class TestEvent:

    async def gather(self, context: Contexts):
        context["name"] = "Letoderea"


@es.on(TestEvent)
async def test_subscriber(name: str):
    print(name)


es.loop.run_until_complete(es.publish(TestEvent()))
```

## 特性

- 任何实现了 `gather` 方法的类都可以作为事件
- 通过 `Provider` 实现依赖注入的静态绑定，提高性能
- 通过 `Contexts` 增强事件传递的灵活性
- 通过 `Publisher` 实现事件响应的隔离
- 通过 `Auxiliary` 提供了一系列辅助方法，方便事件的处理

## 开源协议
本实现以 MIT 为开源协议。
