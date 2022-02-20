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
import asyncio
from arclet.letoderea import EventSystem
from arclet.letoderea.entities.event import TemplateEvent

class ExampleEvent(TemplateEvent):
    def get_params(self):
        return self.param_export(
            msg="I'm here!"
        )
 
loop = asyncio.get_event_loop()
es = EventSystem(loop=loop)
@es.register(ExampleEvent)
async def test(msg: str):
    print(msg)

async def main():
    es.event_publish(ExampleEvent())
    await asyncio.sleep(0.1)
loop.run_until_complete(main())
```

## 开源协议
本实现以 MIT 为开源协议。
