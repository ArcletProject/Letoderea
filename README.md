# Letoderea
[![Licence](https://img.shields.io/github/license/ArcletProject/Letoderea)](https://github.com/ArcletProject/Letoderea/blob/master/LICENSE)
[![PyPI](https://img.shields.io/pypi/v/arclet-letoderea)](https://pypi.org/project/arclet-letoderea)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/arclet-letoderea)](https://www.python.org/)
[![codecov](https://codecov.io/gh/ArcletProject/Letoderea/branch/main/graph/badge.svg?token=DOMUPLN5XO)](https://codecov.io/gh/ArcletProject/Letoderea)

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
import arclet.letoderea as le


@le.make_event
class TestEvent:
    name: str


@le.on_global
async def test_subscriber(name: str):
    print(name)


async def main():
    await le.publish(TestEvent("Letoderea"))


asyncio.run(main())
```

### 依赖注入
```python
import asyncio
import arclet.letoderea as le

@le.make_event
class TestEvent:
    name: str

@le.depends()
async def get_msg(event):
    return f"Hello, {event.name}"

@le.on(TestEvent)
async def test_subscriber(msg: str = get_msg):
    print(msg)

async def main():
    await le.publish(TestEvent("Letoderea"))

asyncio.run(main())
```

### 通信
```python
import asyncio
import random
import arclet.letoderea as le

@le.make_event
class Event:
    name: str

@le.make_event(name="rand")
class RandomData:
    seed: int
    
    __result_type__ = float

@le.on(RandomData)
def random_subscriber(seed: int):
    return random.Random(seed).random()

@le.on(Event)
async def event_subscriber(event: Event):
    print(f"Event: {event.name}")
    result = await le.post(RandomData(42))
    if result:
        print(f"Random: {result.value}")

async def main():
    await le.publish(Event("Letoderea"))
    
asyncio.run(main())
```

### 过滤
```python
import asyncio
import arclet.letoderea as le


@le.make_event
class Event:
    name: str
    flag: bool = False


@le.on_global
@le.enter_if(le.deref(Event).name == "Letoderea")
async def sub_if_letoderea():
    ...

@le.on_global
@le.enter_if & le.deref(Event).flag & (le.deref(Event).name != "Letoderea")
async def sub_if_not_letoderea():
    ...


async def main():
    await le.publish(Event("Letoderea"))
    await le.publish(Event("OtherEvent", True))

asyncio.run(main())
```


## 说明

### 事件

- 事件可以是任何对象，只要实现了 `gather` 异步方法, 或使用 `define` 并传入 `supplier` 参数，或使用 `@gather` 装饰器注册了 supplier 方法
- `gather` 方法的参数为 `Contexts` 类型，用于传递上下文信息
- 事件可以通过 `gather` 方法将自身想要传递的信息整合进 `Contexts` 中
- 事件可以携带 `Provider`，它们会在事件被订阅时注入到订阅者中
- 订阅子类事件时，父类事件的 `Provider` 会被继承
- 订阅父类事件时，其子类事件也会被分发给订阅者

### 订阅

- 通过 `Scope.register`, `on`, `use` 或 `on_global` 装饰器可以将一个函数注册为事件的订阅者
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

- 一般情况下通过 `publish` 或 `post` 方法可以发布一个事件让事件系统进行处理
- `publish` 会处理所有合适的订阅者，而 `post` 会在某一个订阅者返回了有效值后停止处理，并返回该值
- `Publisher.validate` 方法用于验证该事件是否为该发布者的订阅者所关注的事件
- `Publisher.supply` 方法用于让事件系统主动获取事件并分发给所有订阅者
- `use`, `Scope.register` 可以指定 `Publisher`
- 通过 `define` 可以便捷的定义发布者，并在 `.use` 等处通过定义的名字引用

### 层次

- `Scope` 类负责管理订阅者与事件的交互
- 所有的订阅者都会存储在 `Scope` 中
- `publish` 与 `post` 可以指定 `Scope`

### 传播

- `Subscriber` 类型对象被创建后，其能通过 `propagate` 方法来设置订阅的同级传播。
- 传播中的订阅者会在当前订阅者执行后或执行前执行，取决于 `propagate` 的参数 `prepend`。 向后传播的订阅者能拿到上一个订阅者的返回值。
- 传播中的订阅者会继承当前订阅者的 `Provider`。
- 传播中的订阅者可以通过返回特殊值 `STOP` 来中止同级传播。
- 对于传播中的订阅者，若其依赖注入的参数未满足，则会尝试延迟执行。若所有的传播订阅者都无法满足其依赖注入的参数，则会抛出异常。
- `propagate` 方法可以为传播订阅者设置优先级，值越小优先级越高。
- `propagate` 方法可以接受特殊类型 `Propagator`, 其有一个 `compose` 方法，用来提供一系列的传播订阅者。


## 开源协议
本实现以 MIT 为开源协议。
