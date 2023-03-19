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
from arclet.letoderea import EventSystem, BaseEvent, Provider, Collection

es = EventSystem()


class TestEvent(BaseEvent):

    async def gather(self, collection: Collection):
        collection["name"] = "Letoderea"


@es.register(TestEvent)
async def test_subscriber(name: str):
    print(name)


es.loop.run_until_complete(es.publish(TestEvent()))
```

## 开源协议
本实现以 MIT 为开源协议。
