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

### 基本使用
```python
import asyncio
from arclet.letoderea import es, make_even

@make_event
class TestEvent:
    name = "Letoderea"

@es.on(TestEvent)
async def test_subscriber(name: str):
    print(name)

async def main():
    await es.publish(TestEvent())

asyncio.run(main())
```

### 依赖注入
```python
import asyncio
from arclet.letoderea import es, make_event, Depends

@make_event
class TestEvent:
    name = "Letoderea"

async def get_msg(event):
    return f"Hello, {event.name}"
    
@es.on(TestEvent)
async def test_subscriber(msg: str = Depends(get_msg)):
    print(msg)
    
async def main():
    await es.publish(TestEvent())
     
asyncio.run(main())
```

### 通信
```python
import asyncio
import random
from dataclasses import dataclass
from arclet.letoderea import es, make_event

@make_event
@dataclass
class Event:
    name: str

@dataclass
class RandomData:
    seed: int

@es.define("rand", RandomData).register()
def random_subscriber(seed: int):
    return random.Random(seed).random()

@es.on(Event)
async def event_subscriber(event: Event):
    print(f"Event: {event.name}")
    result = await es.post(RandomData(42))
    if result:
        print(f"Random: {result.value}")

async def main():
    await es.publish(Event("Letoderea"))
    
asyncio.run(main())
```

## 说明

### 事件

- 事件可以是任何对象，只要实现了 `gather` 异步方法, 或使用 `EventSystem.define` 并传入 `supplier` 参数
- `gather` 方法的参数为 `Contexts` 类型，用于传递上下文信息
- 事件可以通过 `gather` 方法将自身想要传递的信息整合进 `Contexts` 中
- 事件可以携带 `Provider` 与 `Auxiliary`，它们会在事件被订阅时注入到订阅者中
- 订阅子类事件时，父类事件的 `Provider` 与 `Auxiliary` 会被继承
- 订阅父类事件时，其子类事件也会被分发给订阅者

### 订阅

- 通过 `Publisher.register`, `EventSystem.on`, `EventSystem.use` 或 `subscribe` 装饰器可以将一个函数注册为事件的订阅者
- 上述方法会返回 `Subscriber` 类型对象，可以通过其 `.dispose` 方法取消订阅
- 订阅者的参数可以是任何类型，事件系统会尝试从 `Contexts` 中查找对应的值并注入
- 默认情况下 `event` 为名字的参数会被注入为事件的实例
- 订阅者可以设置优先级，值越小优先级越高

### 上下文

- `Contexts` 类型是一个 `dict` 的子类，用于传递上下文信息，除此之外与 `dict` 没有区别
- `Contexts` 默认包含 `$event` 键，其值为事件的实例
- `Contexts` 默认包含 `$subscriber` 键，其值为订阅者的实例
- 在订阅者的函数执行后，其结果会被存储在 `Contexts` 中，键为 `$result`
- 若在解析参数时抛出异常，异常值会被存储在 `Contexts` 中，键为 `$error`


### 依赖注入

- `Provider[T]` 负责管理参数的注入, 其会尝试从 `Contexts` 中选择需求的参数返回
- 对于订阅者的每个参数，在订阅者注册后，事件系统会遍历该订阅者拥有的所有 `Provider`，
    并依次调用 `Provider.validate` 方法，如果返回 `True`，则将该 `Provider` 绑定到该参数上。
    当进行依赖解析时，事件系统会遍历该参数绑定的所有 `Provider`，并依次调用 `Provider.__call__` 方法，
    如果返回值不为 `None`，则将该返回值注入到该参数中。
- `Provider.validate` 方法用于验证订阅函数的参数是否为该 `Provider` 可绑定的参数。默认实现为检查目标参数的类型声明是否为 `T`。
    也可以通过重写该方法来实现自定义的验证逻辑。
- `Provider.__call__` 方法用于从 `Contexts` 中获取参数
- 原则上 `Provider` 只负责注入单一类型的参数。若想处理多个类型的参数，可以声明自己为 `Provider[Union[A, B, ...]]` 类型，
    并在 `Provider.validate` 方法中进行自定义的逻辑判断。但更推荐的做法是构造多个 `Provider`，并将其绑定到同一个参数上。
- 对于特殊的辅助器 `Depend`，事件系统会将其作为特殊的 `Provider` 处理，绑定了 `Depend` 的参数在解析时将直接调用设置在
    `Depend` 上的方法。
- `Provider` 可以设置优先级，值越小优先级越高
- 另有 `ProviderFactory`，用于集成多个 `Provider` 的分配，以方便 `event.providers` 的设置

### 事件发布

- 一般情况下通过 `EventSystem.publish` 或 `EventSystem.post` 方法可以发布一个事件让事件系统进行处理
- `publish` 会处理所有合适的订阅者，而 `post` 会在某一个订阅者返回了有效值后停止处理，并返回该值
- `Publisher` 类负责管理订阅者与事件的交互
- `Publisher.validate` 方法用于验证该事件是否为该发布者的订阅者所关注的事件
- `Publisher.emit` 和 `Publisher.bail` 方法用于将事件直接分发给属于自身的订阅者，`emit` 与 `bail` 的区别类似于 `publish` 与 `post`
- `Publisher.supply` 方法用于让事件系统主动获取事件并分发给所有订阅者
- `EventSystem.use`, `EventSystem.publish` 和 `EventSystem.post` 可以指定 `Publisher`
- 通过 `EventSystem.define` 可以便捷的定义发布者，并在 `.use` 等处通过定义的名字引用

### 辅助

- `Auxiliary` 提供了一系列辅助方法，方便事件的处理
- `Auxiliary` 分为 `Judge`, `Supply` 两类:
    - `Judge`: 用于判断此时是否应该处理事件
    - `Supply`: 用于为 `Contexts` 提供额外的信息
- `Auxiliary.scopes` 声明了 `Auxiliary` 的作用域:
    - `prepare`: 表示该 `Auxiliary` 会在依赖注入之前执行
    - `complete`: 表示该 `Auxiliary` 会在依赖注入完成后执行
    - `onerror`: 表示该 `Auxiliary` 会在上述两个作用域中发生异常时执行
    - `cleanup`: 表示该 `Auxiliary` 会在事件处理完成后执行
- `Auxiliary` 可以设置优先级，值越小优先级越高
- `Auxiliary` 的 `__call__` 方法多增加了一个 `Interface` 参数，可用于操作 `Contexts` 或 `Provider`, 获取已执行的 `Auxiliary` 等

## 开源协议
本实现以 MIT 为开源协议。
