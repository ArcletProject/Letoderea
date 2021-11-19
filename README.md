# Letoderea

一个高性能，结构简洁，依赖于 Python内置库`asyncio` 的事件系统, 设计灵感来自[`Graia BroadcastControl`](https://github.com/GraiaProject/BroadcastControl)。

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
            str="I'm here!"
        )
 
loop = asyncio.get_event_loop()
es = EventSystem(loop=loop)
@es.register(ExampleEvent)
async def test(this_str: str):
    print(this_str)

async def main():
    es.event_spread(ExampleEvent())
    await asyncio.sleep(0.1)
loop.run_until_complete(main())
```

## 开源协议
本实现以 MIT 为开源协议。
